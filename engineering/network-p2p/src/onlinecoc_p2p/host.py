from __future__ import annotations

import asyncio
import contextlib
import time
from pathlib import Path

from aiohttp import WSMsgType
from aiortc import RTCSessionDescription

from .common import Fault, MAX_REQUEST, atomic_json, canonical, load_identity, public_key, read_json, require, sdp_fingerprint, sign, token, verify
from .control import Control
from .packages import Package
from .ownership import SessionLock
from .rooms import settings
from .rtc import connection, selected_path
from .upstream import Upstream
from .wire import Frames, Sender


class HostPeer:
    def __init__(self, host, intent, servers):
        self.host, self.intent = host, intent
        self.pc = connection(servers, host.config.get("relayOnly", False))
        self.upstream = Upstream(host.config["upstream"])
        self.channels, self.senders, self.frames, self.tasks = {}, {}, {}, set()
        self.proved = self.ready = self.closed = False
        self.close_task = None
        self.challenge = token()
        self.account = None
        self.stream_task = None
        self.started = time.monotonic()

        @self.pc.on("datachannel")
        def channel_open(channel):
            if channel.label not in {"control", "state", "package"} or channel.label in self.channels:
                self.spawn(self.close())
                return
            self.channels[channel.label] = channel
            self.senders[channel.label], self.frames[channel.label] = Sender(channel), Frames(MAX_REQUEST)
            @channel.on("message")
            def receive(raw):
                try:
                    require(channel.label in {"control", "package"}, "CHANNEL_INVALID")
                    value = self.frames[channel.label].feed(raw)
                    if value:
                        require(len(self.tasks) < 12, "PEER_BUSY")
                        self.spawn(self.dispatch(value, channel.label))
                except (Fault, ValueError, UnicodeError):
                    self.spawn(self.close())
            if channel.label == "control":
                if channel.readyState == "open":
                    self.spawn(self.senders["control"].send({"event": "challenge", "challenge": self.challenge}))
                else:
                    @channel.on("open")
                    def opened():
                        self.spawn(self.senders["control"].send({"event": "challenge", "challenge": self.challenge}))

        @self.pc.on("connectionstatechange")
        async def state_change():
            if self.pc.connectionState in {"failed", "closed"} and not self.closed:
                await self.close()

        self.timeout_task = asyncio.create_task(self.timeout())

    def spawn(self, awaitable):
        task = asyncio.create_task(awaitable)
        self.tasks.add(task)
        def completed(done):
            self.tasks.discard(done)
            if not done.cancelled():
                done.exception()
        task.add_done_callback(completed)
        return task

    async def timeout(self):
        await asyncio.sleep(60)
        if not self.proved:
            await self.close()
            return
        await asyncio.sleep(540)
        if not self.ready:
            await self.close()

    async def dispatch(self, value, channel):
        rid = value.get("id")
        try:
            require(isinstance(rid, str) and len(rid) <= 64 and set(value) == {"id", "method", "params"}, "REQUEST_INVALID")
            require(isinstance(value["params"], dict), "REQUEST_INVALID")
            result = await self.handle(value["method"], value["params"], channel)
            response = {"id": rid, "ok": True, "result": result}
        except Fault as exc:
            response = {"id": rid, "ok": False, "error": {"code": exc.code, "status": exc.status}}
        except (KeyError, TypeError, ValueError):
            response = {"id": rid, "ok": False, "error": {"code": "INPUT_INVALID", "status": 400}}
        except Exception:
            response = {"id": rid, "ok": False, "error": {"code": "PEER_ERROR", "status": 500}}
        if channel in self.senders and not self.closed:
            with contextlib.suppress(Fault):
                await self.senders[channel].send(response)

    async def handle(self, method, params, channel):
        if method == "admit":
            require(channel == "control" and not self.proved, "TICKET_INVALID", 403)
            require(params.get("ticket") == self.intent["ticket"], "TICKET_INVALID", 403)
            verify(self.intent["clientKey"], self.challenge, params.get("signature", ""))
            await self.host.control.request("POST", "/v1/join-tickets/redeem", self.host.lease_token,
                {"roomId": self.host.room_id, "ticket": params["ticket"], "clientId": self.intent["clientId"]})
            self.proved = True
            return {"protocolVersion": 1, "roomId": self.host.room_id, "manifestDigest": self.host.package.digest}
        require(self.proved, "ADMISSION_REQUIRED", 401)
        if method == "request":
            require(channel == "control" and set(params) <= {"path", "options"}, "REQUEST_INVALID")
            path, options = params["path"], params.get("options", {})
            require(self.ready or path in {"login", "logout", "me", "capabilities", "contracts"}, "CONTENT_NOT_READY", 409)
            if path == "login":
                self.account = None
                self.ready = False
                await self.stop_stream()
            result = await self.upstream.request(path, options)
            if path == "login":
                me = await self.upstream.request("me")
                if me["accountId"] in self.host.config.get("bannedAccounts", []):
                    self.upstream.cookie, self.upstream.csrf, self.upstream.account_id = "", "", None
                    raise Fault("MEMBER_BANNED", 403)
                self.account = me["accountId"]
            if path == "logout":
                self.ready, self.account = False, None
                await self.stop_stream()
            return result
        require(self.account is not None, "AUTH_REQUIRED", 401)
        # Refresh upstream authorization for every file/READY/subscription operation.
        me = await self.upstream.request("me")
        require(me["accountId"] not in self.host.config.get("bannedAccounts", []), "MEMBER_BANNED", 403)
        if method == "package.manifest":
            return self.host.package.signed_manifest(self.host.identity)
        if method == "package.chunk":
            require(channel == "package", "CHANNEL_INVALID")
            async with self.host.transfer_lock:
                result = self.host.package.chunk(params["manifestDigest"], params["fileDigest"], params["index"])
                await asyncio.sleep(len(result["data"]) * .75 / max(1024, self.host.config.get("packageBytesPerSecond", 131072)))
            return result
        if method == "ready":
            require(params.get("manifestDigest") == self.host.package.digest, "CONTENT_CHANGED", 409)
            await self.host.control.request("POST", "/v1/members/" + self.intent["intentId"] + "/ready",
                self.host.lease_token, {"roomId": self.host.room_id})
            self.ready = True
            return {"ready": True}
        if method == "subscribe":
            require(self.ready and "state" in self.senders, "CONTENT_NOT_READY", 409)
            await self.stop_stream()
            self.stream_task = asyncio.create_task(self.stream())
            return {"subscribed": True}
        if method == "unsubscribe":
            await self.stop_stream()
            return {"subscribed": False}
        if method == "network.stats":
            return selected_path(self.pc)
        raise Fault("METHOD_NOT_EXPOSED", 404)

    async def stream(self):
        try:
            async for message in self.upstream.stream():
                await self.senders["state"].send({"event": "state", "message": message})
        except (Fault, KeyError):
            pass
        finally:
            if not self.closed and "state" in self.senders:
                with contextlib.suppress(Fault):
                    await self.senders["state"].send({"event": "state", "message": {"type": "reset"}})

    async def stop_stream(self):
        if self.stream_task:
            self.stream_task.cancel()
            await asyncio.gather(self.stream_task, return_exceptions=True)
            self.stream_task = None

    async def close(self):
        if self.close_task is None:
            self.close_task = asyncio.create_task(self._close())
        await asyncio.shield(self.close_task)

    async def _close(self):
        self.closed = True
        self.timeout_task.cancel()
        await self.stop_stream()
        for task in tuple(self.tasks):
            if task is not asyncio.current_task():
                task.cancel()
        await self.pc.close()
        await self.upstream.close()
        iid = self.intent["intentId"]
        self.host.peers.pop(iid, None)
        self.host.accepted.pop(iid, None)
        with contextlib.suppress(Fault):
            await self.host.control.request("POST", "/v1/members/" + iid + "/release",
                self.host.lease_token, {"roomId": self.host.room_id})


class Host:
    peer_type = HostPeer
    """Attach to an explicitly configured local host; never starts/stops borrowed game processes."""
    def __init__(self, config: dict):
        self.config = config
        self.state_path = Path(config["statePath"])
        self.identity = None
        self.ownership = SessionLock(self.state_path / "session.lock")
        bans = self.state_path / "banned-accounts.json"
        if bans.exists():
            self.config["bannedAccounts"] = read_json(bans)
        self.package = Package(Path(config["packagePath"]) if config.get("packagePath") else None)
        self.settings = settings(config["settings"])
        self.settings["packageSummary"] = {"id": self.package.manifest["packageId"],
            "version": self.package.manifest["version"], "bytes": sum(f["size"] for f in self.package.manifest["files"]),
            "digest": self.package.digest}
        self.control = Control(config["directory"], config.get("caFile"))
        self.pending, self.accepted, self.peers, self.tasks = {}, {}, {}, set()
        self.socket = self.listener = self.beater = None
        self.room = None
        self.stopping = False
        self.close_task = None
        self.transfer_lock, self.decision_lock = asyncio.Lock(), asyncio.Lock()
        self.error = ""

    @property
    def room_id(self):
        return self.room["roomId"]

    @property
    def lease_token(self):
        return self.room["leaseToken"]

    async def start(self):
        self.ownership.acquire()
        self.identity = load_identity(self.state_path / "host-key.pem")
        check = Upstream(self.config["upstream"])
        try:
            capability = await check.request("capabilities")
            require(capability.get("protocolVersion") == 1, "HOST_PROTOCOL_UNSUPPORTED")
        finally:
            await check.close()
        state_file = self.state_path / "room.json"
        previous = read_json(state_file).get("roomId") if state_file.exists() else None
        self.room = await self.control.request("POST", "/v1/rooms", self.config["publisherToken"],
            {"hostKey": public_key(self.identity), "settings": self.settings, **({"roomId": previous} if previous else {})})
        atomic_json(state_file, {"roomId": self.room_id})
        self.socket = await self.control.socket(self.lease_token, "host", self.room_id)
        self.listener, self.beater = asyncio.create_task(self.listen()), asyncio.create_task(self.heartbeat())
        return self.status()

    def status(self):
        return {"room": {k: v for k, v in (self.room or {}).items() if k not in {"leaseToken", "settings"}},
                "running": bool(self.socket and not self.socket.closed), "error": self.error,
                "pending": [{"intentId": i["intentId"], "clientKeyId": i["clientKeyId"]} for i in self.pending.values()],
                "players": [{"intentId": iid, "accountId": p.account, "ready": p.ready, "network": selected_path(p.pc)}
                            for iid, p in self.peers.items()], "ownership": "borrowed"}

    def spawn(self, coroutine):
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        def finished(done):
            self.tasks.discard(done)
            if not done.cancelled():
                error = done.exception()
                if error:
                    self.error = error.code if isinstance(error, Fault) else type(error).__name__
        task.add_done_callback(finished)

    async def listen(self):
        while not self.stopping:
            try:
                async for message in self.socket:
                    if message.type != WSMsgType.TEXT:
                        break
                    data = message.json()
                    if data["type"] == "join":
                        intent = data["intent"]
                        self.pending[intent["intentId"]] = intent
                        if not self.settings["approvalRequired"]:
                            self.spawn(self.decide(intent["intentId"], True))
                    elif data["type"] == "signal":
                        self.spawn(self.offer(data))
                    elif data["type"] == "cancelled":
                        iid = data["intentId"]
                        self.pending.pop(iid, None)
                        self.accepted.pop(iid, None)
                        if iid in self.peers:
                            await self.peers[iid].close()
                if not self.stopping:
                    await asyncio.sleep(1)
                    self.socket = await self.control.socket(self.lease_token, "host", self.room_id)
                    self.error = ""
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.error = exc.code if isinstance(exc, Fault) else "SIGNAL_DISCONNECTED"
                await asyncio.sleep(2)

    async def heartbeat(self):
        while not self.stopping:
            await asyncio.sleep(15)
            try:
                await self.control.request("POST", "/v1/rooms/" + self.room_id + "/heartbeat", self.lease_token)
            except Fault as exc:
                self.error = exc.code
                if exc.code == "LEASE_INVALID":
                    try:
                        await self.republish()
                    except Fault as recovery:
                        self.error = recovery.code
            for iid, item in list(self.accepted.items()):
                if item["expires"] < time.time() and iid not in self.peers:
                    self.accepted.pop(iid, None)

    async def republish(self):
        # A new epoch invalidates old membership. Clients explicitly rejoin.
        async with self.decision_lock:
            await asyncio.gather(*(p.close() for p in tuple(self.peers.values())), return_exceptions=True)
            self.pending.clear()
            self.accepted.clear()
            room = await self.control.request("POST", "/v1/rooms", self.config["publisherToken"],
                {"hostKey": public_key(self.identity), "settings": self.settings, "roomId": self.room_id})
            self.room = room
            if self.socket is not None:
                await self.socket.close()
            self.error = ""

    async def decide(self, iid, approve):
        async with self.decision_lock:
            intent = self.pending.get(iid)
            require(intent and intent["policyRevision"] == self.room["policyRevision"], "POLICY_CHANGED", 409)
            approve = bool(approve and len(self.accepted) < self.settings["maxPlayers"]
                           and intent["clientKeyId"] not in self.settings["bannedKeys"] and self.settings["joinable"])
            result = await self.control.request("POST", "/v1/join-intents/" + iid + "/decision", self.lease_token,
                {"roomId": self.room_id, "approve": approve, "policyRevision": self.room["policyRevision"]})
            self.pending.pop(iid, None)
            if approve:
                self.accepted[iid] = result
            return {"approved": approve}

    async def offer(self, data):
        iid = data["intentId"]
        async with self.decision_lock:
            require(iid in self.accepted and iid not in self.peers, "INTENT_INVALID", 403)
            intent = self.accepted[iid]
        require(intent["connectionEpoch"] == self.room["connectionEpoch"]
                and intent["policyRevision"] == self.room["policyRevision"], "POLICY_CHANGED", 409)
        description = data["description"]
        require(description["type"] == "offer")
        offer_fp = sdp_fingerprint(description["sdp"])
        ice = await self.control.request("POST", "/v1/turn-credentials", self.lease_token, {"role": "host", "intentId": iid})
        peer = self.peer_type(self, intent, ice["iceServers"])
        self.peers[iid] = peer
        try:
            await peer.pc.setRemoteDescription(RTCSessionDescription(**description))
            await peer.pc.setLocalDescription(await peer.pc.createAnswer())
            answer = {"type": "answer", "sdp": peer.pc.localDescription.sdp}
            answer_fp = sdp_fingerprint(answer["sdp"])
            signature = sign(self.identity, f"{iid}|{offer_fp}|{answer_fp}|{intent['connectionEpoch']}")
            await self.socket.send_json({"type": "signal", "intentId": iid, "description": answer, "signature": signature})
        except Exception:
            await peer.close()
            raise

    async def patch(self, value, expected_revision):
        self.room = await self.control.request("PATCH", "/v1/rooms/" + self.room_id, self.lease_token,
            {"settings": value, "expectedRevision": expected_revision})
        self.settings = self.room["settings"]
        return self.status()

    async def kick(self, iid, ban=False):
        peer = self.peers.get(iid)
        require(peer is not None, "MEMBER_NOT_FOUND", 404)
        if ban:
            if peer.account:
                self.config.setdefault("bannedAccounts", []).append(peer.account)
                atomic_json(self.state_path / "banned-accounts.json", self.config["bannedAccounts"])
            value = dict(self.settings)
            value["bannedKeys"] = list(set(value["bannedKeys"] + [peer.intent["clientKeyId"]]))
            await self.patch(value, self.room["revision"])
        targets = [p for p in self.peers.values() if p is peer or (ban and peer.account and p.account == peer.account)]
        await asyncio.gather(*(p.close() for p in targets))
        return {"ok": True}

    async def close(self):
        if self.close_task is None:
            self.close_task = asyncio.create_task(self._close())
        await asyncio.shield(self.close_task)

    async def _close(self):
        self.stopping = True
        if self.room:
            with contextlib.suppress(Fault):
                await self.control.request("DELETE", "/v1/rooms/" + self.room_id + "/lease", self.lease_token)
        running = [task for task in (self.listener, self.beater, *self.tasks) if task is not None]
        for task in running:
            task.cancel()
        await asyncio.gather(*running, return_exceptions=True)
        await asyncio.gather(*(p.close() for p in tuple(self.peers.values())), return_exceptions=True)
        if self.socket is not None:
            await self.socket.close()
        await self.control.close()
        self.ownership.close()
