from __future__ import annotations

import asyncio
import time

from onlinecoc_p2p.common import Fault, atomic_json, digest, require, token
from onlinecoc_p2p.host import Host, HostPeer
from .resources import Resources
from .bridge import service_config, service_call
from .creation import make_room_setup


class WebPeer(HostPeer):
    def __init__(self, *args):
        super().__init__(*args)
        self.groups_ready = set()

    async def handle(self, method, params, channel):
        lease = await self.host.authorization(self.intent["intentId"])
        # Game authority comes only from the authenticated upstream account, never platform ownership.
        if self.account and self.host.service_url:
            view = await self.upstream.request('view')
            require(view.get('role') in {'player', 'kp'} and view.get('accountId') == self.account, 'GAME_IDENTITY_INVALID', 403)
        if method == 'service.request':
            require(self.host.service_url and self.proved and self.account and self.ready, 'CONTENT_NOT_READY', 409)
            require(channel == 'control', 'CHANNEL_INVALID')
            path, verb, query, body = service_call(self.host.resources.descriptor, params)
            return await self.upstream.service_request(self.host.service_url, path, verb, query, body)
        if method in {"package.manifest", "package.chunk"}:
            raise Fault("RESOURCE_PROTOCOL_REQUIRED", 409)
        if method.startswith("resource.") or method == "ready":
            require(self.proved and self.account, "AUTH_REQUIRED", 401)
            current = await self.upstream.request("me")
            require(current["accountId"] == self.account and self.account not in self.host.config.get("bannedAccounts", []), "MEMBERSHIP_REVOKED", 403)
            resources = self.host.resources
            require(params.get("resourceVersion") == resources.version, "VERSION_CHANGED", 409)
            gid = params.get("group", "startup")
            package = resources.allowed(gid, lease["groups"])
            signed = resources.manifest(gid, lease["groups"], self.host.identity)
            if method == "resource.manifest":
                return signed
            require(params.get("manifestDigest") == signed["digest"], "MANIFEST_CHANGED", 409)
            if method == "resource.chunk":
                require(channel == "package", "CHANNEL_INVALID")
                async with self.host.transfer_lock:
                    result = package.chunk(package.digest, params["fileDigest"], params["index"])
                    await asyncio.sleep(len(result["data"]) * .75 / self.host.config.get("fileBytesPerSecond", 131072))
                    # Recheck after queued/rate-limited transfers.
                    await self.host.authorization(self.intent["intentId"])
                    return result
            if method == "resource.ready" or method == "ready":
                self.groups_ready.add(gid)
                if gid == "startup":
                    await self.host.control.request("POST", "/v1/members/" + self.intent["intentId"] + "/ready",
                        self.host.lease_token, {"roomId": self.host.room_id})
                    self.ready = True
                return {"ready": True, "group": gid, "resourceVersion": resources.version}
            raise Fault("METHOD_NOT_EXPOSED", 404)
        if method == "request":
            path, options = params.get("path"), params.get("options", {})
            if path in {"login", "logout"}:
                self.groups_ready.clear()
            if path not in {"login", "logout", "me", "capabilities", "contracts"}:
                routes = self.host.resources.descriptor["routes"]
                match = next((r for r in routes if r["path"] == path and r["method"] == options.get("method", "GET")), None)
                require(match, "ROUTE_NOT_EXPOSED", 404)
                require(set(match.get("requires", [])) <= self.groups_ready, "RESOURCE_NOT_READY", 409)
        result = await super().handle(method, params, channel)
        if method == 'request' and params.get('path') == 'login' and self.host.service_url:
            view = await self.upstream.request('view')
            if view.get('role') not in {'player', 'kp'} or view.get('accountId') != self.account:
                await self.upstream.request('logout', {'method':'POST', 'body':{}})
                self.account, self.ready = None, False
                raise Fault('GAME_IDENTITY_INVALID', 403)
        if method == "admit":
            return {**result, "resourceProtocol": 2, "resourceVersion": self.host.resources.version}
        return result


class WebHost(Host):
    peer_type = WebPeer

    def __init__(self, config):
        self.resources = Resources(config["webPackagePath"])
        self.service_url = service_config(config, self.resources.descriptor)
        config = {**config, "packagePath": None, "settings": {**config.get("settings", {}),
            "visibility": "code", "approvalRequired": False, "passwordVerifier": "", "invites": {}}}
        super().__init__(config)
        self.settings["packageSummary"] = {"id": self.resources.descriptor["package"]["id"],
            "version": self.resources.descriptor["package"]["version"], "digest": self.resources.version,
            "bytes": self.resources.metadata("")["totalBytes"]}
        self.claim = token()
        self.authorized = {}
        self.guard_checked = set()
        self.authorized_until = 0
        self.guard_lock = asyncio.Lock()
        self.guard_task = None

    async def configure(self):
        result = await self.control.request("POST", "/v1/web/host/" + self.room_id, self.lease_token,
            {"metadata": self.resources.metadata(self.settings["title"]), "policy": self.config.get("webPolicy", {}),
             "claimHash": digest(self.claim.encode())})
        entry = {"url": self.config["directory"], "roomCode": self.room["roomCode"], "roomId": self.room_id,
                 **({"claim": self.claim, "claimExpiresIn": 600, "claimExpiresAt": time.time() + 600,
                     "creationString": make_room_setup(self.config["directory"], self.room["roomCode"], self.claim)}
                    if not result["claimed"] else {})}
        atomic_json(self.state_path / "web-entry.json", entry)
        return entry

    async def prepare_creation(self):
        """Refresh the one-use handoff for a pack's local host management page."""
        self.claim = token()
        entry = await self.configure()
        require("creationString" in entry, "ROOM_ALREADY_CLAIMED", 409)
        return entry["creationString"]

    async def start(self):
        if self.service_url:
            capabilities = await self.control.request('GET', '/v1/web/capabilities')
            require(capabilities.get('packageBridge') == 1 and capabilities.get('storageBridge') == 1, 'WEB_BRIDGE_UNAVAILABLE')
        await super().start()
        entry = await self.configure()
        self.guard_task = asyncio.create_task(self.guard_loop())
        return entry

    async def republish(self):
        await super().republish()
        await self.configure()

    async def refresh_authorization(self):
        async with self.guard_lock:
            requested = list(self.accepted)
            result = await self.control.request("POST", "/v1/web/host/" + self.room_id + "/guard", self.lease_token,
                {"intentIds": requested})
            self.authorized = result["active"]
            self.guard_checked = set(requested)
            self.authorized_until = time.monotonic() + min(result["leaseSeconds"], 10)

    async def authorization(self, iid):
        if iid not in self.authorized or self.authorized_until < time.monotonic():
            try:
                await asyncio.wait_for(self.refresh_authorization(), 3)
            except Exception:
                raise Fault("AUTHORIZATION_UNAVAILABLE", 503) from None
        require(self.authorized_until > time.monotonic() and iid in self.authorized, "MEMBERSHIP_REVOKED", 403)
        return self.authorized[iid]

    async def guard_loop(self):
        while not self.stopping:
            try:
                await asyncio.wait_for(self.refresh_authorization(), 3)
            except Exception:
                pass
            for iid, peer in list(self.peers.items()):
                if (self.authorized_until <= time.monotonic() and time.monotonic() - peer.started > 10) or (iid in self.guard_checked and iid not in self.authorized):
                    await peer.close()
            await asyncio.sleep(2)

    async def _close(self):
        if self.guard_task:
            self.guard_task.cancel()
            await asyncio.gather(self.guard_task, return_exceptions=True)
        await super()._close()
