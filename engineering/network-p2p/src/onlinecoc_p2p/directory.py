from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time
from pathlib import Path

from aiohttp import WSMsgType, web
from argon2.exceptions import VerificationError

from .common import Fault, MAX_REQUEST, RateLimit, digest, require, sdp_fingerprint
from .rooms import PASSWORDS, Rooms


def bearer(request):
    value = request.headers.get("Authorization", "")
    require(value.startswith("Bearer ") and len(value) < 256, "AUTH_REQUIRED", 401)
    return value[7:]


class Directory:
    def __init__(self, config: dict, state_path: Path | None = None):
        self.config = config
        self.store = Rooms(state_path, lease_seconds=config.get("leaseSeconds", 60),
                           retention_seconds=config.get("roomRetentionSeconds", 86400))
        self.hosts, self.clients, self.sockets = {}, {}, set()
        self.rate = RateLimit(maximum=120)
        self.join_rate, self.password_slots = RateLimit(maximum=12), asyncio.Semaphore(2)
        self.ws_rate = RateLimit(maximum=120, window=60)
        self.tasks = set()

    def publisher(self, credential):
        for name, hashed in self.config.get("publishers", {}).items():
            if hmac.compare_digest(hashed, digest(credential.encode())):
                return name
        raise Fault("PUBLISHER_AUTH_REQUIRED", 401)

    async def send(self, socket, data):
        if socket is not None and not socket.closed:
            try:
                await asyncio.wait_for(socket.send_json(data), 5)
            except (ConnectionError, TimeoutError, RuntimeError):
                await socket.close()

    async def client_event(self, item, event):
        await self.send(self.clients.get(item["clientId"]), event)

    async def cancel(self, items, reason):
        for item in items:
            event = {"type": "cancelled", "intentId": item["intentId"], "code": reason}
            await self.client_event(item, event)
            await self.send(self.hosts.get(item["roomId"]), event)

    async def json(self, request):
        try:
            value = await request.json()
        except (json.JSONDecodeError, UnicodeError):
            raise Fault("INPUT_INVALID") from None
        require(isinstance(value, dict))
        return value

    @web.middleware
    async def boundary(self, request, handler):
        try:
            self.rate.check(request.remote or "unknown")
            origin = request.headers.get("Origin")
            require(not origin or origin in self.config.get("allowedOrigins", []), "ORIGIN_REJECTED", 403)
            if request.content_length:
                require(request.content_length <= MAX_REQUEST, "LIMIT_EXCEEDED", 413)
            response = await handler(request)
            if not response.prepared:
                response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                                         "Referrer-Policy": "no-referrer"})
            return response
        except Fault as exc:
            return web.json_response({"code": exc.code}, status=exc.status)
        except (TypeError, ValueError, KeyError):
            return web.json_response({"code": "INPUT_INVALID"}, status=400)

    def app(self):
        app = web.Application(client_max_size=MAX_REQUEST, middlewares=[self.boundary])
        async def health(_):
            return web.json_response({"status": "ok", "protocolVersion": 1})
        app.router.add_get("/health", health)
        app.router.add_post("/v1/client-sessions", self.new_client)
        app.router.add_get("/v1/rooms", self.list_rooms)
        app.router.add_post("/v1/rooms", self.publish)
        app.router.add_patch("/v1/rooms/{rid}", self.patch)
        app.router.add_post("/v1/rooms/{rid}/heartbeat", self.heartbeat)
        app.router.add_delete("/v1/rooms/{rid}/lease", self.close)
        app.router.add_post("/v1/join-intents", self.join)
        app.router.add_get("/v1/join-intents/{iid}", self.intent_status)
        app.router.add_post("/v1/join-intents/{iid}/decision", self.decision)
        app.router.add_post("/v1/join-tickets/redeem", self.redeem)
        app.router.add_post("/v1/members/{iid}/{action}", self.member)
        app.router.add_post("/v1/turn-credentials", self.turn_credentials)
        app.router.add_get("/v1/signaling", self.websocket)
        app.cleanup_ctx.append(self.lifecycle)
        return app

    async def sweep_hosts(self):
        self.store.purge()
        # A request can already have purged a lease before this sweep runs.
        for rid in list(self.hosts):
            if rid not in self.store.leases:
                socket = self.hosts.pop(rid)
                await socket.close(code=1008, message=b"lease expired")

    async def lifecycle(self, app):
        async def sweep():
            while True:
                await asyncio.sleep(2)
                await self.sweep_hosts()
        task = asyncio.create_task(sweep())
        yield
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.gather(*(s.close(code=1001) for s in tuple(self.sockets)), return_exceptions=True)

    async def new_client(self, request):
        self.join_rate.check("session:" + (request.remote or "unknown"))
        data = await self.json(request)
        require(set(data) == {"publicKey"})
        return web.json_response(self.store.new_client(data["publicKey"]))

    async def list_rooms(self, request):
        return web.json_response(self.store.listing(request.query.get("cursor", "")))

    async def publish(self, request):
        owner, data = self.publisher(bearer(request)), await self.json(request)
        require(set(data) <= {"hostKey", "settings", "roomId"})
        result = self.store.acquire(owner, data["hostKey"], data["settings"], data.get("roomId"))
        return web.json_response(result)

    async def heartbeat(self, request):
        rid = request.match_info["rid"]
        return web.json_response(self.store.heartbeat(rid, bearer(request)))

    async def patch(self, request):
        rid, data = request.match_info["rid"], await self.json(request)
        self.store.lease(rid, bearer(request))
        result, cancelled = self.store.patch(rid, data["settings"], data["expectedRevision"])
        await self.cancel(cancelled, "POLICY_CHANGED")
        return web.json_response(result)

    async def close(self, request):
        rid = request.match_info["rid"]
        self.store.lease(rid, bearer(request))
        await self.cancel(self.store.close(rid), "ROOM_CLOSED")
        return web.json_response({"ok": True})

    async def join(self, request):
        client, data = self.store.client(bearer(request)), await self.json(request)
        require(set(data) <= {"roomId", "roomCode", "password", "invitation"})
        require(("roomId" in data) != ("roomCode" in data), "INPUT_INVALID")
        self.join_rate.check("ip:" + (request.remote or "unknown"))
        self.join_rate.check("device:" + client["keyId"])
        rid = self.store.resolve_code(data["roomCode"]) if "roomCode" in data else data["roomId"]
        require(isinstance(rid, str) and 0 < len(rid) <= 128)
        self.join_rate.check("room:" + rid)
        room, invitation_hash = self.store.precheck(rid, client, data.get("invitation"))
        verifier, policy = room["settings"]["passwordVerifier"], room["policyRevision"]
        password = data.get("password", "")
        require(isinstance(password, str) and len(password) <= 128, "ROOM_UNAVAILABLE", 404)
        if verifier:
            try:
                async with self.password_slots:
                    await asyncio.to_thread(PASSWORDS.verify, verifier, password)
            except VerificationError:
                raise Fault("ROOM_UNAVAILABLE", 404) from None
        # Hash verification yields; re-check lease, invite and policy before reserving.
        self.store.precheck(rid, client, data.get("invitation"))
        item = self.store.new_intent(rid, client, invitation_hash, policy)
        await self.send(self.hosts.get(rid), {"type": "join", "intent": item})
        return web.json_response(self.store.for_client(item))

    async def intent_status(self, request):
        client = self.store.client(bearer(request))
        item = self.store.intents.get(request.match_info["iid"])
        require(item and item["clientId"] == client["id"], "INTENT_EXPIRED", 404)
        return web.json_response(self.store.for_client(item))

    async def decision(self, request):
        data = await self.json(request)
        rid = data["roomId"]
        self.store.lease(rid, bearer(request))
        require(type(data["approve"]) is bool)
        item = self.store.decide(rid, request.match_info["iid"], data["approve"], data["policyRevision"])
        await self.client_event(item, {"type": "decision", "intent": self.store.for_client(item)})
        return web.json_response(item)

    async def redeem(self, request):
        data = await self.json(request)
        self.store.lease(data["roomId"], bearer(request))
        return web.json_response(self.store.redeem(data["roomId"], data["ticket"], data["clientId"]))

    async def member(self, request):
        data = await self.json(request)
        rid, action, iid = data["roomId"], request.match_info["action"], request.match_info["iid"]
        self.store.lease(rid, bearer(request))
        require(action in {"ready", "release"})
        item = self.store.intents.get(iid)
        require(item and item["roomId"] == rid, "INTENT_EXPIRED", 404)
        if action == "ready":
            self.store.ready(rid, iid)
        else:
            await self.cancel([self.store.drop_intent(iid)], "MEMBER_REMOVED")
        return web.json_response({"ok": True})

    async def turn_credentials(self, request):
        data = await self.json(request)
        credential = bearer(request)
        self.store.purge()
        item = self.store.intents.get(data.get("intentId"))
        require(item and item["status"] in {"approved", "syncing", "ready"}, "TURN_NOT_AUTHORIZED", 403)
        if data.get("role") == "host":
            self.store.lease(item["roomId"], credential)
            subject = "h-" + item["intentId"][:16]
        else:
            client = self.store.client(credential)
            require(client["id"] == item["clientId"], "TURN_NOT_AUTHORIZED", 403)
            subject = "p-" + item["intentId"][:16]
        turn = self.config.get("turn", {})
        if not turn.get("urls"):
            return web.json_response({"iceServers": [], "expires": int(time.time()) + 600})
        expiry = int(time.time()) + 600
        username = f"{expiry}:{subject}"
        password = base64.b64encode(hmac.new(turn["secret"].encode(), username.encode(), hashlib.sha1).digest()).decode()
        return web.json_response({"iceServers": [{"urls": turn["urls"], "username": username, "credential": password}],
                                  "expires": expiry})

    async def websocket(self, request):
        require(len(self.sockets) < 512, "CAPACITY", 503)
        socket = web.WebSocketResponse(max_msg_size=MAX_REQUEST, heartbeat=20, compress=0)
        await socket.prepare(request)
        self.sockets.add(socket)
        role, identity, lease_token = None, None, None
        try:
            hello = await asyncio.wait_for(socket.receive_json(), 8)
            require(isinstance(hello, dict) and hello.get("type") == "auth")
            role = hello.get("role")
            if role == "host":
                identity, lease_token = hello["roomId"], hello["token"]
                lease = self.store.lease(identity, lease_token)
                old = self.hosts.get(identity)
                self.hosts[identity] = socket
                self.store.connected(identity, True)
            else:
                require(role == "client")
                client = self.store.client(hello["token"])
                identity = client["id"]
                old = self.clients.get(identity)
                self.clients[identity] = socket
            if old is not None and old is not socket:
                await old.close(code=1000)
            await self.send(socket, {"type": "authenticated", "role": role})
            async for message in socket:
                if message.type != WSMsgType.TEXT:
                    break
                self.ws_rate.check(role + ":" + identity)
                if role == "host":
                    self.store.lease(identity, lease_token)
                else:
                    self.store.client(hello["token"])
                data = json.loads(message.data)
                require(isinstance(data, dict))
                if data.get("type") == "heartbeat":
                    if role == "host":
                        self.store.heartbeat(identity, lease_token)
                    await self.send(socket, {"type": "heartbeat"})
                    continue
                require(data.get("type") == "signal" and set(data) <= {"type", "intentId", "description", "signature"},
                        "SIGNAL_INVALID")
                self.store.purge()
                item = self.store.intents.get(data.get("intentId"))
                require(item and item["status"] in {"approved", "syncing", "ready"}, "INTENT_EXPIRED", 403)
                description = data["description"]
                require(isinstance(description, dict) and set(description) == {"type", "sdp"}, "SIGNAL_INVALID")
                fingerprint = sdp_fingerprint(description["sdp"])
                if role == "host":
                    require(item["roomId"] == identity and description["type"] == "answer", "SIGNAL_FORBIDDEN", 403)
                    require(isinstance(data.get("signature"), str) and len(data["signature"]) <= 128, "SIGNAL_INVALID")
                    require("offerFingerprint" in item and "answerFingerprint" not in item, "SIGNAL_REPLAY", 409)
                    item["answerFingerprint"] = fingerprint
                    target = self.clients.get(item["clientId"])
                else:
                    require(item["clientId"] == identity and description["type"] == "offer", "SIGNAL_FORBIDDEN", 403)
                    require("offerFingerprint" not in item, "SIGNAL_REPLAY", 409)
                    item["offerFingerprint"] = fingerprint
                    target = self.hosts.get(item["roomId"])
                await self.send(target, data)
        except (Fault, KeyError, TypeError, ValueError, TimeoutError) as exc:
            await self.send(socket, {"type": "error", "code": exc.code if isinstance(exc, Fault) else "SIGNAL_INVALID"})
            await socket.close(code=1008)
        finally:
            self.sockets.discard(socket)
            mapping = self.hosts if role == "host" else self.clients
            if identity and mapping.get(identity) is socket:
                mapping.pop(identity, None)
                if role == "host" and identity in self.store.leases:
                    self.store.connected(identity, False)
        return socket
