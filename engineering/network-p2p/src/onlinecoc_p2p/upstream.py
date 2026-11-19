from __future__ import annotations

import asyncio
import json
import re
from http.cookies import SimpleCookie

import aiohttp

from .common import Fault, MAX_REQUEST, MAX_RESPONSE, canonical, loopback_url, require

READ = re.compile(r"^(capabilities|me|view|contracts|catalog|chat/members|knowledge/capabilities|receipts/[A-Za-z0-9_.-]{1,128})$")
WRITE = re.compile(r"^(login|logout|query|commands|calculate|chat/history|knowledge/(preview|search|read|grants/query))$")


class Upstream:
    """One isolated cookie/CSRF context per admitted WebRTC peer."""
    def __init__(self, url):
        self.url = loopback_url(url)
        self.cookie, self.csrf, self.account_id = "", "", None
        self.session = aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar(), trust_env=False,
                                             timeout=aiohttp.ClientTimeout(total=15, connect=3))
        self.lock = asyncio.Lock()

    async def close(self):
        await self.session.close()
        self.cookie, self.csrf, self.account_id = "", "", None

    async def request(self, path, options=None):
        options = options or {}
        require(isinstance(options, dict) and set(options) <= {"method", "body", "csrf"}, "REQUEST_INVALID")
        method = options.get("method", "GET")
        require(isinstance(path, str) and len(path) <= 200 and
                ((method == "GET" and READ.fullmatch(path)) or (method == "POST" and WRITE.fullmatch(path))),
                "ROUTE_NOT_EXPOSED", 404)
        body = options.get("body")
        if body is not None:
            require(isinstance(body, dict), "REQUEST_INVALID")
        payload = canonical(body) if body is not None else b""
        require(len(payload) <= MAX_REQUEST, "LIMIT_EXCEEDED", 413)
        require(path in {"capabilities", "contracts", "login"} or self.cookie, "AUTH_REQUIRED", 401)
        supplied_csrf = options.get("csrf")
        require(supplied_csrf is None or supplied_csrf == self.csrf, "SESSION_MISMATCH", 403)
        headers = {"Origin": self.url, "Content-Type": "application/json"}
        if path != "login":
            headers.update(Cookie="onlinecoc=" + self.cookie, **{"X-CSRF-Token": self.csrf})
        try:
            async with self.lock:
                if path == "login":
                    self.cookie, self.csrf, self.account_id = "", "", None
                async with self.session.request(method, self.url + "/api/v1/" + path, data=payload or None,
                                                headers=headers, allow_redirects=False) as response:
                    require(not 300 <= response.status < 400, "UPSTREAM_REDIRECT", 502)
                    data = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        data.extend(chunk)
                        require(len(data) <= MAX_RESPONSE - 8192, "UPSTREAM_TOO_LARGE", 502)
                    try:
                        value = json.loads(data)
                    except (ValueError, UnicodeError):
                        raise Fault("UPSTREAM_RESPONSE_INVALID", 502) from None
                    if response.status >= 400:
                        if response.status == 401:
                            self.cookie, self.csrf, self.account_id = "", "", None
                        raise Fault(value.get("code", "UPSTREAM_REJECTED"), response.status)
                    if path == "login":
                        cookies = SimpleCookie()
                        for entry in response.headers.getall("Set-Cookie", []):
                            cookies.load(entry)
                        require("onlinecoc" in cookies and isinstance(value.get("csrf"), str), "UPSTREAM_RESPONSE_INVALID", 502)
                        self.cookie, self.csrf = cookies["onlinecoc"].value, value["csrf"]
                    if path == "me":
                        self.account_id = value["accountId"]
                    if path == "logout":
                        self.cookie, self.csrf, self.account_id = "", "", None
                    return value
        except (aiohttp.ClientError, TimeoutError, OSError):
            raise Fault("UPSTREAM_UNAVAILABLE", 502) from None

    async def stream(self):
        require(self.cookie, "AUTH_REQUIRED", 401)
        try:
            async with self.session.ws_connect(self.url + "/api/v1/connect",
                    headers={"Origin": self.url, "Cookie": "onlinecoc=" + self.cookie},
                    max_msg_size=262144, heartbeat=20, compress=0) as socket:
                async for message in socket:
                    if message.type == aiohttp.WSMsgType.TEXT:
                        yield json.loads(message.data)
        except (aiohttp.ClientError, TimeoutError, OSError):
            raise Fault("UPSTREAM_UNAVAILABLE", 502) from None

    async def service_request(self, url, path, method, query, body):
        """Trusted host adapter only: caller validates its declared service contract.

        Reuse this peer's real game session, never a room owner's credential.
        This method is deliberately not exposed by the generic request RPC.
        """
        url = loopback_url(url)
        require(self.cookie and self.csrf, "AUTH_REQUIRED", 401)
        require(method in {"GET", "POST"} and re.fullmatch(r"package/[a-z/-]{1,60}", path), "ROUTE_NOT_EXPOSED", 404)
        payload = canonical(body) if body is not None else b""
        require(len(payload) <= MAX_REQUEST, "LIMIT_EXCEEDED", 413)
        try:
            async with self.lock:
                headers = {"Origin": url, "Content-Type": "application/json", "Cookie": "onlinecoc=" + self.cookie, "X-CSRF-Token": self.csrf}
                async with self.session.request(method, url + '/' + path, params=query, data=payload or None, headers=headers, allow_redirects=False) as response:
                    require(not 300 <= response.status < 400, "UPSTREAM_REDIRECT", 502)
                    raw = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        raw.extend(chunk)
                        require(len(raw) <= MAX_RESPONSE - 8192, "UPSTREAM_TOO_LARGE", 502)
                    try: value = json.loads(raw)
                    except (ValueError, UnicodeError): raise Fault("UPSTREAM_RESPONSE_INVALID", 502) from None
                    if response.status >= 400:
                        raise Fault(value.get('code', 'UPSTREAM_REJECTED'), response.status)
                    return value
        except (aiohttp.ClientError, TimeoutError, OSError):
            raise Fault("UPSTREAM_UNAVAILABLE", 502) from None
