from __future__ import annotations

import asyncio
import re
import secrets
import time
from pathlib import Path

from aiohttp import web
from argon2.exceptions import VerificationError

from onlinecoc_p2p.common import Fault, MAX_REQUEST, RateLimit, canonical, digest, require, token
from onlinecoc_p2p.directory import Directory, bearer
from onlinecoc_p2p.rooms import PASSWORDS
from .store import PortalStore
from .creation import parse_room_setup

ASSETS = Path(__file__).parent / "web"
COOKIE = "onlinecoc_web"


class WebDirectory(Directory):
    """Optional account portal layered on the existing directory and signaling protocol."""
    def __init__(self, config, state_path=None):
        super().__init__(config, state_path)
        self.portal = PortalStore(config["webStateFile"])
        self.presence = {}
        self.auth_rate = RateLimit(12, 300)
        self.web_rate = RateLimit(600)
        self.web_task = None

    @web.middleware
    async def boundary(self, request, handler):
        try:
            self.web_rate.check(request.remote or "unknown")
            origin = request.headers.get("Origin")
            expected = self.config.get("publicOrigin") or str(request.url.origin())
            require(not origin or origin == expected or origin in self.config.get("allowedOrigins", []), "ORIGIN_DENIED", 403)
            require(request.content_length is None or request.content_length <= MAX_REQUEST, "LIMIT_EXCEEDED", 413)
            response = await handler(request)
            response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data: blob:; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"})
            if request.path == "/sandbox.html":
                response.headers.pop("X-Frame-Options", None)
                response.headers["Content-Security-Policy"] = "default-src 'none'; script-src 'self' 'unsafe-inline' blob:; style-src 'unsafe-inline' blob:; img-src data: blob:; media-src blob:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'; sandbox allow-scripts"
            return response
        except Fault as exc:
            return web.json_response({"code": exc.code}, status=exc.status, headers={"Cache-Control": "no-store"})
        except (KeyError, TypeError, ValueError):
            return web.json_response({"code": "INPUT_INVALID"}, status=400)

    def auth(self, request, write=False):
        key = digest(request.cookies.get(COOKIE, "").encode())
        session = self.portal.session(key)
        if write:
            require(secrets.compare_digest(request.headers.get("X-CSRF-Token", ""), session["csrf"]), "CSRF_INVALID", 403)
        return session["accountId"], key, session

    def app(self):
        app = super().app()
        routes = [
            ("POST", "auth/{action}", self.account), ("GET", "me", self.me),
            ("GET", "rooms", self.mine), ("POST", "join", self.join_room),
            ("GET", "public-rooms", self.public_rooms),
            ("POST", "rooms/preview", self.preview_creation), ("POST", "rooms/create", self.create_room),
            ("POST", "claim", self.claim), ("POST", "rooms/{rid}/presence", self.room_info),
            ("POST", "rooms/{rid}/manage", self.manage),
            ("POST", "host/{rid}", self.configure_host), ("POST", "host/{rid}/guard", self.guard),
            ("POST", "game/session", self.game_session), ("POST", "game/join", self.game_join),
            ("POST", "game/ping", self.game_ping), ("POST", "game/leave", self.game_leave),
        ]
        for method, path, handler in routes:
            app.router.add_route(method, "/v1/web/" + path, handler)
        for path in ("/", "/create", "/join", "/manage", "/manage/{rid}", "/room/{rid}", "/game/{rid}"):
            app.router.add_get(path, self.page)
        app.router.add_get("/assets/{name}", self.asset)
        app.router.add_get("/sandbox.html", self.sandbox)
        app.router.add_get('/v1/web/capabilities', self.capabilities)
        app.on_startup.append(self.web_start)
        app.on_cleanup.append(self.web_close)
        return app

    async def page(self, request):
        return web.Response(text=(ASSETS / "index.html").read_text(encoding="utf-8"), content_type="text/html")

    async def capabilities(self, request):
        return web.json_response({'webVersion':2, 'packageBridge':1, 'storageBridge':1, 'roomCreation':1, 'publicRooms':1})

    async def sandbox(self, request):
        return web.Response(text='<!doctype html><html><head><meta charset="utf-8"></head><body><script src="/assets/sandbox-boot.js"></script></body></html>', content_type="text/html")

    async def asset(self, request):
        name = request.match_info["name"]
        if name == "transport.js":
            from onlinecoc_p2p import __file__ as p2p_file
            file = Path(p2p_file).parent / "web/transport.js"
        else:
            require(name in {"app.js", "game.js", "remember.js", "resources.js", "sandbox.js", "sandbox-boot.js", "storage.js", "style.css"}, "NOT_FOUND", 404)
            file = ASSETS / name
        return web.Response(body=file.read_bytes(), content_type="text/css" if name.endswith(".css") else "text/javascript")

    async def web_start(self, app):
        self.web_task = asyncio.create_task(self.web_sweep())

    async def web_close(self, app):
        if self.web_task:
            self.web_task.cancel()
            await asyncio.gather(self.web_task, return_exceptions=True)
        self.portal.close()

    async def web_sweep(self):
        while True:
            await asyncio.sleep(2)
            for iid, item in list(self.store.intents.items()):
                if "webAccountId" in item:
                    try:
                        self.valid_game(item)
                    except Fault:
                        self.store.drop_intent(iid)
                        await self.cancel([item], "MEMBERSHIP_REVOKED")
            now = time.time()
            self.presence = {k: v for k, v in self.presence.items() if v > now - 35}

    async def account(self, request):
        action = request.match_info["action"]
        if action == "logout":
            aid, key, _ = self.auth(request, True)
            self.portal.data["sessions"].pop(key, None)
            self.portal.save()
            await self.revoke(aid, session_key=key)
            result = web.json_response({"ok": True})
            result.del_cookie(COOKIE, path="/")
            return result
        require(action in {"register", "login", "recover"})
        self.auth_rate.check(request.remote or "unknown")
        data = await self.json(request)
        name, password = data.get("name", ""), data.get("password", "")
        require(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_-]{3,32}", name), "NAME_INVALID")
        require(isinstance(password, str) and len(password) >= 6, "PASSWORD_LENGTH")
        self.auth_rate.check("name:" + name.lower())
        accounts = self.portal.data["accounts"]
        aid = next((k for k, v in accounts.items() if v["name"].lower() == name.lower()), None)
        recovery = None
        async with self.password_slots:
            if action == "register":
                require(self.config.get("registration", True) and len(accounts) < self.config.get("maxAccounts", 2000), "REGISTRATION_CLOSED", 403)
                require(aid is None, "ACCOUNT_EXISTS", 409)
                hashed = await asyncio.to_thread(PASSWORDS.hash, password)
                # Recheck after yielding to another registration.
                require(not any(v["name"].lower() == name.lower() for v in accounts.values()), "ACCOUNT_EXISTS", 409)
                aid, recovery = token(), token()
                accounts[aid] = {"name": name, "password": hashed, "recovery": digest(recovery.encode())}
            elif action == "recover":
                code = data.get("recovery", "")
                require(isinstance(code, str) and len(code) <= 128 and aid and secrets.compare_digest(accounts[aid]["recovery"], digest(code.encode())), "AUTH_INVALID", 401)
                hashed = await asyncio.to_thread(PASSWORDS.hash, password)
                require(secrets.compare_digest(accounts[aid]["recovery"], digest(code.encode())), "AUTH_INVALID", 401)
                accounts[aid]["password"] = hashed
                recovery = token()
                accounts[aid]["recovery"] = digest(recovery.encode())
                self.portal.data["sessions"] = {k: v for k, v in self.portal.data["sessions"].items() if v["accountId"] != aid}
                await self.revoke(aid)
            else:
                # Hash an unknown login too, avoiding a cheap account existence oracle.
                if not aid:
                    await asyncio.to_thread(PASSWORDS.hash, password)
                    raise Fault("AUTH_INVALID", 401)
                try:
                    previous_hash = accounts[aid]["password"]
                    await asyncio.to_thread(PASSWORDS.verify, previous_hash, password)
                    require(accounts[aid]["password"] == previous_hash, "AUTH_INVALID", 401)
                except VerificationError:
                    raise Fault("AUTH_INVALID", 401) from None
        credential, csrf = token(), token()
        now = time.time()
        self.portal.data["sessions"] = {k: v for k, v in self.portal.data["sessions"].items() if v["expires"] > now}
        active = [(k, v) for k, v in self.portal.data["sessions"].items() if v["accountId"] == aid]
        for k, _ in sorted(active, key=lambda item: item[1]["expires"])[:-7]:
            self.portal.data["sessions"].pop(k)
        self.portal.data["sessions"][digest(credential.encode())] = {"accountId": aid, "csrf": csrf, "expires": now + 604800}
        self.portal.save()
        result = web.json_response({**self.portal.public_account(aid), "csrf": csrf, **({"recovery": recovery} if recovery else {})})
        result.set_cookie(COOKIE, credential, secure=request.secure, httponly=True, samesite="Strict", max_age=604800, path="/")
        return result

    async def me(self, request):
        aid, _, session = self.auth(request)
        return web.json_response({**self.portal.public_account(aid), "csrf": session["csrf"]})

    def online(self, rid):
        lease = self.store.leases.get(rid)
        return bool(lease and lease["connected"] and lease["expires"] > time.time())

    async def mine(self, request):
        aid, _, _ = self.auth(request)
        items = []
        for rid, room in self.portal.data["rooms"].items():
            if aid in room["members"] and aid not in room["banned"]:
                items.append({"roomId": rid, "title": room["metadata"]["title"], "closed": room["closed"], "online": self.online(rid), "updated": room["updated"], "owner": room["owner"] == aid})
        return web.json_response({"items": items})

    async def public_rooms(self, request):
        # The legacy directory remains code-only so its admission cannot bypass web policy.
        offset = int(request.query.get("offset", "0"))
        require(0 <= offset <= 100000, "INPUT_INVALID")
        items = []
        for rid, room in self.portal.data["rooms"].items():
            base = self.store.rooms.get(rid)
            if not (room.get("public", False) and room["owner"] and not room["closed"]
                    and self.online(rid) and base and base["settings"]["joinable"]):
                continue
            meta = room["metadata"]
            items.append({"roomCode": base["roomCode"], "title": meta["title"],
                "package": {k: meta["package"][k] for k in ("id", "name", "version")},
                "passwordRequired": bool(room["policy"].get("passwordVerifier")),
                "approvalRequired": bool(room["policy"].get("approvalRequired")),
                "invitationRequired": bool(room["policy"].get("invitationHash")),
                "seats": self.store.count(rid), "maxPlayers": base["settings"]["maxPlayers"]})
        items.sort(key=lambda r: r["roomCode"])
        return web.json_response({"items": items[offset:offset + 50],
            "nextOffset": offset + 50 if len(items) > offset + 50 else None})

    def setup_room(self, request, data):
        setup = parse_room_setup(data.get("setupString"), self.config.get("publicOrigin") or str(request.url.origin()))
        rid = self.store.resolve_code(setup["roomCode"])
        room = self.portal.room(rid)
        self.check_claim(rid, room, setup["claim"])
        return rid, room, setup

    def check_claim(self, rid, room, claim):
        require(not room["owner"] and self.online(rid) and room.get("claimExpires", 0) > time.time(), "CLAIM_INVALID", 403)
        require(isinstance(claim, str) and secrets.compare_digest(room["claimHash"], digest(claim.encode())), "CLAIM_INVALID", 403)

    def assign_owner(self, room, aid):
        room["owner"] = aid
        room["members"][aid] = {"role": "host", "joined": time.time(), "groups": [], "revision": 1}
        room.pop("claimHash", None)
        room.pop("claimExpires", None)

    async def preview_creation(self, request):
        aid, _, _ = self.auth(request, True)
        self.join_rate.check("claim:" + aid)
        rid, room, _ = self.setup_room(request, await self.json(request))
        return web.json_response({"roomCode": self.store.rooms[rid]["roomCode"], "metadata": room["metadata"],
            "approvalRequired": bool(room["policy"].get("approvalRequired")),
            "invitationRequired": bool(room["policy"].get("invitationHash"))})

    async def room_password(self, password):
        require(isinstance(password, str) and len(password) <= 128, "ROOM_PASSWORD_INVALID")
        if not password:
            return ""
        async with self.password_slots:
            return await asyncio.to_thread(PASSWORDS.hash, password)

    async def create_room(self, request):
        aid, _, _ = self.auth(request, True)
        self.join_rate.check("claim:" + aid)
        data = await self.json(request)
        require(type(data.get("public")) is bool, "INPUT_INVALID")
        rid, room, setup = self.setup_room(request, data)
        hashed = await self.room_password(data.get("password", ""))
        self.auth(request, True)
        room = self.portal.room(rid)
        self.check_claim(rid, room, setup["claim"])
        self.assign_owner(room, aid)
        room.update(public=data["public"], policyManaged=True, updated=time.time())
        room["policy"] = {**room["policy"], "passwordVerifier": hashed}
        self.portal.save()
        return web.json_response({"roomId": rid})

    async def configure_host(self, request):
        rid = request.match_info["rid"]
        self.store.lease(rid, bearer(request))
        require(self.store.rooms[rid]["settings"]["visibility"] == "code", "WEB_ROOM_REQUIRED")
        data = await self.json(request)
        meta = data["metadata"]
        require(isinstance(meta, dict) and set(meta) == {"title", "description", "package", "rules", "resourceVersion", "startupBytes", "totalBytes"}, "METADATA_INVALID")
        for key, limit in (("title", 64), ("description", 1024), ("rules", 8000), ("resourceVersion", 64)):
            require(isinstance(meta[key], str) and len(meta[key]) <= limit, "METADATA_INVALID")
        require(re.fullmatch(r"[0-9a-f]{64}", meta["resourceVersion"]), "METADATA_INVALID")
        package = meta["package"]
        require(isinstance(package, dict) and set(package) == {"id", "name", "version", "source", "description"})
        require(all(isinstance(v, str) and len(v) <= 1024 for v in package.values()))
        require(all(type(meta[k]) is int and 0 <= meta[k] <= 536870912 for k in ("startupBytes", "totalBytes")))
        require(len(canonical(meta)) < 20000, "METADATA_INVALID")
        policy = data.get("policy", {})
        require(set(policy) <= {"approvalRequired", "passwordVerifier", "invitationHash"})
        require(type(policy.get("approvalRequired", False)) is bool)
        # Reuse the existing strict Argon2 parameter validator.
        from onlinecoc_p2p.rooms import settings
        settings({"passwordVerifier": policy.get("passwordVerifier", "")})
        require(not policy.get("invitationHash") or re.fullmatch(r"[0-9a-f]{64}", policy["invitationHash"]))
        rooms = self.portal.data["rooms"]
        old = rooms.get(rid)
        require(not old or not old["closed"], "ROOM_CLOSED", 410)
        if old:
            require(old["metadata"]["resourceVersion"] == meta["resourceVersion"], "ROOM_VERSION_PINNED", 409)
            old.update(metadata=meta, updated=time.time())
            if not old.get("policyManaged"):
                old["policy"] = policy
        else:
            rooms[rid] = {"owner": None, "members": {}, "pending": {}, "banned": [], "closed": False,
                "metadata": meta, "policy": policy, "public": False, "updated": time.time()}
        claim_hash = data.get("claimHash", "")
        require(re.fullmatch(r"[0-9a-f]{64}", claim_hash), "CLAIM_INVALID")
        if not rooms[rid]["owner"]:
            rooms[rid].update(claimHash=claim_hash, claimExpires=time.time() + 600)
        self.portal.save()
        return web.json_response({"ok": True, "claimed": bool(rooms[rid]["owner"])})

    async def claim(self, request):
        aid, _, _ = self.auth(request, True)
        data = await self.json(request)
        self.join_rate.check("claim:" + aid)
        rid = self.store.resolve_code(data["roomCode"])
        room = self.portal.room(rid)
        self.check_claim(rid, room, data.get("claim"))
        self.assign_owner(room, aid)
        self.portal.save()
        return web.json_response({"roomId": rid})

    async def join_room(self, request):
        aid, _, _ = self.auth(request, True)
        self.join_rate.check("web:" + aid)
        self.join_rate.check("web-ip:" + (request.remote or "unknown"))
        data = await self.json(request)
        rid = self.store.resolve_code(data["roomCode"])
        room = self.portal.room(rid)
        require(aid not in room["banned"], "ROOM_UNAVAILABLE", 404)
        if aid in room["members"]:
            return web.json_response({"roomId": rid, "status": "member"})
        require(room["owner"] and self.online(rid) and self.store.rooms[rid]["settings"]["joinable"], "ROOM_UNAVAILABLE", 404)
        policy = dict(room["policy"])
        if policy.get("invitationHash"):
            invite = data.get("invitation", "")
            require(isinstance(invite, str) and len(invite) <= 256 and secrets.compare_digest(policy["invitationHash"], digest(invite.encode())), "ROOM_UNAVAILABLE", 404)
        if policy.get("passwordVerifier"):
            password = data.get("password", "")
            require(isinstance(password, str) and len(password) <= 128, "ROOM_UNAVAILABLE", 404)
            try:
                async with self.password_slots:
                    await asyncio.to_thread(PASSWORDS.verify, policy["passwordVerifier"], password)
            except VerificationError:
                raise Fault("ROOM_UNAVAILABLE", 404) from None
        room = self.portal.room(rid)
        require(room["policy"] == policy and aid not in room["banned"] and self.online(rid), "POLICY_CHANGED", 409)
        room["pending"] = {k: expiry for k, expiry in room["pending"].items() if expiry > time.time()}
        require(len(room["members"]) < 1000 and len(room["pending"]) < 100, "ROOM_LIMIT", 429)
        if policy.get("approvalRequired"):
            room["pending"][aid] = time.time() + 600
            status = "pending"
        else:
            room["members"][aid] = {"role": "player", "joined": time.time(), "groups": [], "revision": 1}
            status = "member"
        self.portal.save()
        return web.json_response({"roomId": rid, "status": status})

    async def room_info(self, request):
        aid, _, _ = self.auth(request, True)
        rid = request.match_info["rid"]
        room = self.portal.room(rid)
        if aid not in room["members"]:
            require(aid not in room["banned"] and room["pending"].get(aid, 0) > time.time(), "MEMBERSHIP_REQUIRED", 403)
            return web.json_response({"status": "pending"})
        room = self.portal.member(rid, aid)
        self.presence[(rid, aid)] = time.time()
        people = []
        for member, record in room["members"].items():
            if member in room["banned"]:
                continue
            playing = any(i.get("webAccountId") == member and i["roomId"] == rid and i["status"] == "ready" for i in self.store.intents.values())
            if playing or self.presence.get((rid, member), 0) > time.time() - 35:
                people.append({**self.portal.public_account(member), "role": record["role"], "state": "game" if playing else "room"})
        owner = room["owner"] == aid
        result = {"status": "member", "roomId": rid, "metadata": room["metadata"], "updated": room["updated"],
            "online": self.online(rid), "people": people, "owner": owner, "seats": self.store.count(rid),
            "maxPlayers": self.store.rooms[rid]["settings"]["maxPlayers"]}
        if owner:
            result.update(public=room.get("public", False), passwordRequired=bool(room["policy"].get("passwordVerifier")),
                roomCode=self.store.rooms[rid]["roomCode"], members=[{**self.portal.public_account(k), **v} for k, v in room["members"].items()],
                pending=[self.portal.public_account(k) for k, v in room["pending"].items() if v > time.time()],
                banned=[self.portal.public_account(k) for k in room["banned"]])
        return web.json_response(result)

    async def manage(self, request):
        aid, _, _ = self.auth(request, True)
        rid = request.match_info["rid"]
        room = self.portal.owner(rid, aid)
        data = await self.json(request)
        action, target = data.get("action"), data.get("accountId")
        require(action in {"settings", "approve", "reject", "ban", "unban", "remove", "grant", "close"})
        if action == "settings":
            self.join_rate.check("settings:" + aid)
            require(type(data.get("public")) is bool and data.get("passwordMode") in {"keep", "set", "clear"}, "INPUT_INVALID")
            mode = data["passwordMode"]
            if mode == "set":
                require(bool(data.get("password")), "ROOM_PASSWORD_INVALID")
            hashed = await self.room_password(data.get("password", "") if mode == "set" else "")
            self.auth(request, True)
            room = self.portal.owner(rid, aid)
            room.update(public=data["public"], policyManaged=True, updated=time.time())
            if mode != "keep":
                room["policy"] = {**room["policy"], "passwordVerifier": hashed}
                room["pending"].clear()
            self.portal.save()
            return web.json_response({"ok": True})
        if action == "close":
            room["closed"] = True
        else:
            require(target in self.portal.data["accounts"] and target != aid, "MEMBER_INVALID")
            if action == "approve":
                require(target not in room["banned"] and room["pending"].get(target, 0) > time.time(), "APPLICATION_EXPIRED", 409)
                room["members"][target] = {"role": "player", "joined": time.time(), "groups": [], "revision": 1}
            if action == "ban":
                require(target in room["members"] or target in room["pending"], "MEMBER_INVALID")
                room["banned"] = list(set(room["banned"] + [target]))
            if action == "unban":
                room["banned"] = [k for k in room["banned"] if k != target]
            if action in {"ban", "remove"}:
                room["members"].pop(target, None)
            if action == "grant":
                groups = data.get("groups")
                require(target in room["members"] and isinstance(groups, list) and len(groups) <= 32 and all(isinstance(g, str) and re.fullmatch(r"[a-z0-9-]{1,40}", g) for g in groups))
                room["members"][target]["groups"] = groups
                room["members"][target]["revision"] += 1
            room["pending"].pop(target, None)
        self.portal.save()
        if action in {"ban", "remove", "grant", "close"}:
            await self.revoke(target if action != "close" else None, rid)
        return web.json_response({"ok": True, "connectionRevocationDeadlineSeconds": 15})

    async def revoke(self, aid=None, rid=None, session_key=None):
        items = [v for v in self.store.intents.values() if "webAccountId" in v and
                 (aid is None or v["webAccountId"] == aid) and (rid is None or v["roomId"] == rid) and
                 (session_key is None or v["webSession"] == session_key)]
        for item in items:
            self.store.drop_intent(item["intentId"])
        await self.cancel(items, "MEMBERSHIP_REVOKED")

    def valid_game(self, item):
        require(item and "webAccountId" in item, "GAME_SESSION_INVALID", 403)
        self.portal.session(item["webSession"])
        room = self.portal.member(item["roomId"], item["webAccountId"])
        require(room["members"][item["webAccountId"]]["revision"] == item["webRevision"] and item["webPing"] > time.time() - 35, "MEMBERSHIP_REVOKED", 403)
        require(self.online(item["roomId"]), "ROOM_UNAVAILABLE", 404)
        return room

    async def guard(self, request):
        rid = request.match_info["rid"]
        self.store.lease(rid, bearer(request))
        data = await self.json(request)
        require(isinstance(data.get("intentIds"), list) and len(data["intentIds"]) <= 32)
        active = {}
        for iid in data["intentIds"]:
            item = self.store.intents.get(iid)
            try:
                require(item and item["roomId"] == rid, "INTENT_INVALID")
                room = self.valid_game(item)
                active[iid] = {"accountId": item["webAccountId"], "groups": room["members"][item["webAccountId"]]["groups"]}
            except Fault:
                pass
        return web.json_response({"active": active, "leaseSeconds": 10})

    async def game_session(self, request):
        aid, key, _ = self.auth(request, True)
        data = await self.json(request)
        result = self.store.new_client(data["publicKey"])
        client = self.store.client(result["clientToken"])
        client.update(webAccountId=aid, webSession=key)
        return web.json_response(result)

    async def game_join(self, request):
        aid, key, _ = self.auth(request, True)
        self.join_rate.check("seat:" + aid)
        data = await self.json(request)
        rid = data["roomId"]
        room = self.portal.member(rid, aid)
        require(data.get("resourceVersion") == room["metadata"]["resourceVersion"], "VERSION_CHANGED", 409)
        client = self.store.client(bearer(request))
        require(client.get("webAccountId") == aid and client.get("webSession") == key, "SESSION_MISMATCH", 403)
        self.store.purge()
        require(not any(i["roomId"] == rid and i.get("webAccountId") == aid for i in self.store.intents.values()), "GAME_ALREADY_OPEN", 409)
        _, invitation = self.store.precheck(rid, client, "", web_member=True)
        item = self.store.new_intent(rid, client, invitation, self.store.rooms[rid]["policyRevision"])
        item.update(webAccountId=aid, webSession=key, webRevision=room["members"][aid]["revision"], webPing=time.time())
        await self.send(self.hosts.get(rid), {"type": "join", "intent": item})
        return web.json_response(self.store.for_client(item))

    async def game_ping(self, request):
        aid, key, _ = self.auth(request, True)
        item = self.store.intents.get((await self.json(request))["intentId"])
        require(item and item.get("webAccountId") == aid and item.get("webSession") == key, "GAME_SESSION_INVALID", 403)
        self.valid_game(item)
        item["webPing"] = time.time()
        item["expires"] = time.time() + (86400 if item["status"] == "ready" else 600)
        return web.json_response({"ok": True})

    async def game_leave(self, request):
        aid, key, _ = self.auth(request, True)
        item = self.store.intents.get((await self.json(request))["intentId"])
        if item:
            require(item.get("webAccountId") == aid and item.get("webSession") == key, "GAME_SESSION_INVALID", 403)
            self.store.drop_intent(item["intentId"])
            await self.cancel([item], "GAME_LEFT")
        return web.json_response({"ok": True})

    async def redeem(self, request):
        # Validate before consuming a ticket, including attempts through the legacy route.
        data = await self.json(request)
        iid = self.store.tickets.get(digest(data.get("ticket", "").encode()))
        item = self.store.intents.get(iid)
        if item and "webAccountId" in item:
            self.valid_game(item)
        return await super().redeem(request)

    async def turn_credentials(self, request):
        item = self.store.intents.get((await self.json(request)).get("intentId"))
        if item and "webAccountId" in item:
            self.valid_game(item)
        return await super().turn_credentials(request)

    async def patch(self, request):
        rid = request.match_info["rid"]
        if rid in self.portal.data["rooms"] or self.store.rooms.get(rid, {}).get("settings", {}).get("visibility") == "code":
            data = await self.json(request)
            require(data["settings"].get("visibility") == "code", "WEB_ROOM_PRIVATE", 403)
        return await super().patch(request)

    async def publish(self, request):
        data = await self.json(request)
        rid = data.get("roomId")
        if rid in self.portal.data["rooms"]:
            require(not self.portal.data["rooms"][rid]["closed"], "ROOM_CLOSED", 410)
            require(data["settings"].get("visibility") == "code", "WEB_ROOM_PRIVATE", 403)
        return await super().publish(request)
