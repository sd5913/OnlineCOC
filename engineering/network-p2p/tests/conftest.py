import asyncio
from pathlib import Path

import pytest
from aiohttp import web

from onlinecoc_p2p.common import digest, token
from onlinecoc_p2p.directory import Directory
from onlinecoc_p2p.host import Host


async def serve(app):
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, f"http://127.0.0.1:{port}"


@pytest.fixture
async def directory(tmp_path):
    publisher = token()
    service = Directory({"publishers": {"test": digest(publisher.encode())}}, tmp_path / "directory.json")
    runner, url = await serve(service.app())
    yield service, url, publisher
    await runner.cleanup()


class ContractHost:
    """Contract test double; real backend validation is a separate acceptance test."""
    def __init__(self):
        self.sessions, self.receipts, self.count = {}, {}, 0

    def auth(self, request, write=False):
        entry = self.sessions.get(request.cookies.get("onlinecoc"))
        if not entry:
            raise web.HTTPUnauthorized(text='{"code":"AUTH_REQUIRED"}', content_type="application/json")
        if write and request.headers.get("X-CSRF-Token") != entry["csrf"]:
            raise web.HTTPForbidden(text='{"code":"PERMISSION_DENIED"}', content_type="application/json")
        return entry

    def app(self):
        app = web.Application()
        async def capabilities(_):
            return web.json_response({"protocolVersion": 1})
        app.router.add_get("/api/v1/capabilities", capabilities)
        async def login(request):
            data = await request.json()
            if data.get("password") != "test-only" or data.get("loginName") not in {"alice", "bob", "kp"}:
                raise web.HTTPUnauthorized(text='{"code":"AUTH_INVALID"}', content_type="application/json")
            credential, csrf = token(), token()
            self.sessions[credential] = {"accountId": data["loginName"], "csrf": csrf}
            response = web.json_response({"csrf": csrf})
            response.set_cookie("onlinecoc", credential, httponly=True)
            return response
        async def me(request):
            return web.json_response(self.auth(request))
        async def view(request):
            return web.json_response({"accountId": self.auth(request)["accountId"], "counter": self.count})
        async def command(request):
            account = self.auth(request, True)["accountId"]
            body = await request.json()
            if body.get("op") == "kp-only" and account != "kp":
                raise web.HTTPForbidden(text='{"code":"PERMISSION_DENIED"}', content_type="application/json")
            key = (account, body["commandId"])
            if key not in self.receipts:
                self.count += 1
                self.receipts[key] = {"count": self.count, "accountId": account}
            return web.json_response(self.receipts[key])
        async def connect(request):
            account = self.auth(request)["accountId"]
            socket = web.WebSocketResponse()
            await socket.prepare(request)
            await socket.send_json({"type": "snapshot.begin", "id": "a", "parts": 1})
            await socket.send_json({"type": "snapshot.part", "id": "a", "index": 0,
                                    "data": '{"accountId":"' + account + '"}'})
            await socket.send_json({"type": "snapshot.end", "id": "a"})
            async for _ in socket:
                pass
            return socket
        app.router.add_post("/api/v1/login", login)
        app.router.add_get("/api/v1/me", me)
        app.router.add_get("/api/v1/view", view)
        app.router.add_post("/api/v1/commands", command)
        app.router.add_get("/api/v1/connect", connect)
        return app


@pytest.fixture
async def upstream():
    fixture = ContractHost()
    runner, url = await serve(fixture.app())
    yield fixture, url
    await runner.cleanup()


@pytest.fixture
async def hosted(directory, upstream, tmp_path):
    service, url, publisher = directory
    fixture, upstream_url = upstream
    host = Host({"directory": url, "publisherToken": publisher, "statePath": str(tmp_path / "host"),
                 "upstream": upstream_url, "settings": {"title": "测试房间", "visibility": "public", "approvalRequired": False}})
    await host.start()
    yield host, service, url, fixture
    await host.close()
