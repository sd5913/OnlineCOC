from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import time
from pathlib import Path

from aiohttp import WSMsgType, web

from .common import Fault, MAX_REQUEST, digest, require, token
from .control import Control
from .discovery import discover
from .host import Host
from .rooms import PASSWORDS

WEB = Path(__file__).parent / "web"


class LocalApp:
    """Trusted loopback shell; its capability is separate from publisher/game credentials."""
    def __init__(self, config):
        self.config, self.capability = config, token()
        self.origin = None
        self.control = Control(config["directory"], config.get("caFile"))
        self.host = None
        self.host_lock = asyncio.Lock()
        self.discovery_lock = asyncio.Lock()
        self.discovery_cache = None
        self.invitation = ""
        self.sockets = set()
        self.views = {}

    @web.middleware
    async def boundary(self, request, handler):
        try:
            require(self.origin is not None and request.host == self.origin.split("//", 1)[1], "HOST_REJECTED", 403)
            incoming = request.headers.get("Origin")
            require(not incoming or incoming == self.origin, "ORIGIN_REJECTED", 403)
            if request.path.startswith(("/local/", "/control/")):
                credential = request.headers.get("Authorization", "")
                require(hmac.compare_digest(credential, "Bearer " + self.capability), "LOCAL_AUTH_REQUIRED", 401)
            if request.method != "GET":
                require(incoming == self.origin, "ORIGIN_REJECTED", 403)
            response = await handler(request)
            if not response.prepared:
                response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                    "Referrer-Policy": "no-referrer"})
                response.headers.setdefault("Content-Security-Policy",
                    "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
                    "img-src 'self' blob: data:; frame-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            return response
        except Fault as exc:
            return web.json_response({"code": exc.code}, status=exc.status)
        except (KeyError, TypeError, ValueError):
            return web.json_response({"code": "INPUT_INVALID"}, status=400)

    def app(self):
        app = web.Application(client_max_size=MAX_REQUEST, middlewares=[self.boundary])
        app.router.add_get("/", self.page)
        app.router.add_get("/web/{name}", self.asset)
        app.router.add_get("/local/status", self.status)
        app.router.add_get("/local/hosts", self.local_hosts)
        app.router.add_post("/local/package-view", self.package_view)
        app.router.add_get("/view/{view}", self.view)
        app.router.add_post("/local/host/{action}", self.host_action)
        app.router.add_post("/control/{action}", self.control_action)
        app.router.add_get("/signal", self.signal)
        app.on_cleanup.append(self.cleanup)
        return app

    async def page(self, request):
        return web.FileResponse(WEB / "index.html")

    async def asset(self, request):
        name = request.match_info["name"]
        require(name in {"app.js", "transport.js", "style.css", "bridge.js", "join.js"}, "NOT_FOUND", 404)
        response = web.FileResponse(WEB / name)
        response.content_type = "text/css" if name.endswith(".css") else "text/javascript"
        return response

    async def package_view(self, request):
        # Payload stays within the shell's existing 64 KiB request bound.
        value = await request.json()
        require(isinstance(value.get("html"), str), "INPUT_INVALID")
        now = time.monotonic()
        self.views = {k: v for k, v in self.views.items() if v[0] > now}
        require(len(self.views) < 8, "VIEW_LIMIT", 429)
        key = token()
        self.views[key] = (now + 300, value["html"])
        return web.json_response({"url": "/view/" + key})

    async def view(self, request):
        entry = self.views.pop(request.match_info["view"], None)
        require(entry and entry[0] > time.monotonic(), "VIEW_EXPIRED", 404)
        # Header sandbox also applies if this one-use URL is opened top-level.
        policy = ("sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline' blob:; "
                  "style-src 'unsafe-inline' blob:; img-src blob: data:; connect-src 'none'; "
                  "frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'")
        return web.Response(text=entry[1], content_type="text/html",
                            headers={"Content-Security-Policy": policy})

    async def local_hosts(self, request):
        require(self.config.get("publisherToken"), "PUBLISHER_NOT_CONFIGURED", 403)
        async with self.discovery_lock:
            if self.discovery_cache is None or time.monotonic() - self.discovery_cache[0] > 3:
                self.discovery_cache = (time.monotonic(), await discover(self.config))
            return web.json_response({"items": self.discovery_cache[1]})

    async def status(self, request):
        return web.json_response({"directory": self.config["directory"], "hostEnabled": bool(self.config.get("publisherToken")),
            "host": self.host.status() if self.host else None, "protocolVersion": 1,
            "upstream": (self.host.config if self.host else self.config).get("upstream", "http://127.0.0.1:8765"),
            "invitation": self.invitation if self.host else ""})

    async def control_action(self, request):
        action, data = request.match_info["action"], await request.json()
        require(isinstance(data, dict))
        credential = request.headers.get("X-Client-Token")
        if action == "rooms":
            result = await self.control.request("GET", "/v1/rooms")
        elif action == "session":
            require(set(data) == {"publicKey"})
            result = await self.control.request("POST", "/v1/client-sessions", data=data)
        elif action == "join":
            result = await self.control.request("POST", "/v1/join-intents", credential, data)
        elif action == "turn":
            require(data.get("role") == "client")
            result = await self.control.request("POST", "/v1/turn-credentials", credential, data)
        else:
            raise Fault("NOT_FOUND", 404)
        return web.json_response(result)

    async def host_action(self, request):
        require(self.config.get("publisherToken"), "PUBLISHER_NOT_CONFIGURED", 403)
        action, data = request.match_info["action"], await request.json()
        require(isinstance(data, dict))
        async with self.host_lock:
            if action == "start":
                require(self.host is None, "ALREADY_RUNNING", 409)
                require(set(data) <= {"title", "summary", "visibility", "password", "approvalRequired", "maxPlayers", "upstream", "relayOnly"})
                password = data.get("password", "")
                require(isinstance(password, str) and len(password) <= 128)
                config = dict(self.config)
                config["settings"] = {k: data[k] for k in ("title", "summary", "visibility", "approvalRequired", "maxPlayers") if k in data}
                config["settings"]["passwordVerifier"] = await asyncio.to_thread(PASSWORDS.hash, password) if password else ""
                invitation = token() if data.get("visibility", "private") == "private" else ""
                if invitation:
                    config["settings"]["invites"] = {digest(invitation.encode()): {"expires": time.time() + 86400, "remaining": 100}}
                config["upstream"] = data.get("upstream", config.get("upstream", "http://127.0.0.1:8765"))
                config["relayOnly"] = data.get("relayOnly", False)
                host = Host(config)
                try:
                    result = await host.start()
                except Exception:
                    await host.close()
                    raise
                self.host = host
                self.invitation = invitation
                result["invitation"] = invitation
            elif action == "stop":
                require(self.host is not None, "NOT_RUNNING", 409)
                await self.host.close()
                self.host = None
                self.invitation = ""
                result = {"stopped": True}
            elif action == "decide":
                require(self.host is not None, "NOT_RUNNING", 409)
                result = await self.host.decide(data["intentId"], data["approve"])
            elif action == "kick":
                require(self.host is not None, "NOT_RUNNING", 409)
                result = await self.host.kick(data["intentId"], data.get("ban", False))
            elif action == "lock":
                require(self.host is not None, "NOT_RUNNING", 409)
                config = dict(self.host.settings)
                config["joinable"] = not data["locked"]
                result = await self.host.patch(config, self.host.room["revision"])
            else:
                raise Fault("NOT_FOUND", 404)
        return web.json_response(result)

    async def signal(self, request):
        require(request.headers.get("Origin") == self.origin, "ORIGIN_REJECTED", 403)
        require(len(self.sockets) < 16, "CAPACITY", 503)
        downstream = web.WebSocketResponse(max_msg_size=MAX_REQUEST, heartbeat=20, compress=0)
        await downstream.prepare(request)
        self.sockets.add(downstream)
        upstream = None
        try:
            hello = await asyncio.wait_for(downstream.receive_json(), 8)
            require(hmac.compare_digest(hello.get("appToken", ""), self.capability), "LOCAL_AUTH_REQUIRED", 401)
            upstream = await self.control.socket(hello["clientToken"], "client")
            await downstream.send_json({"type": "authenticated", "role": "client"})
            async def relay(source, target):
                async for message in source:
                    if message.type == WSMsgType.TEXT:
                        await asyncio.wait_for(target.send_str(message.data), 5)
                    else:
                        break
            tasks = [asyncio.create_task(relay(downstream, upstream)), asyncio.create_task(relay(upstream, downstream))]
            try:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        except (Fault, TimeoutError, ValueError, KeyError):
            await downstream.close(code=1008)
        finally:
            if upstream is not None:
                await upstream.close()
            await downstream.close()
            self.sockets.discard(downstream)
        return downstream

    async def cleanup(self, app):
        if self.host:
            await self.host.close()
        for socket in tuple(self.sockets):
            await socket.close()
        await self.control.close()


async def start_local(config, port=0):
    shell = LocalApp(config)
    runner = web.AppRunner(shell.app(), access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    actual = site._server.sockets[0].getsockname()[1]
    shell.origin = f"http://127.0.0.1:{actual}"
    return shell, runner, shell.origin + "/#token=" + shell.capability
