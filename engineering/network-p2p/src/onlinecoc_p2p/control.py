from __future__ import annotations

import asyncio

import aiohttp

from .common import Fault, MAX_RESPONSE, directory_tls, require


class Control:
    def __init__(self, url, ca_file=None):
        self.url = url.rstrip("/")
        self.ssl = directory_tls(url, ca_file) or True
        self.session = aiohttp.ClientSession(trust_env=False, cookie_jar=aiohttp.DummyCookieJar(),
            timeout=aiohttp.ClientTimeout(total=30, connect=10))

    async def close(self):
        await self.session.close()

    async def request(self, method, path, credential=None, data=None):
        require(path.startswith("/v1/") or path == "/health", "CONTROL_PATH_INVALID")
        headers = {"Authorization": "Bearer " + credential} if credential else {}
        try:
            async with self.session.request(method, self.url + path, headers=headers, json=data,
                                            ssl=self.ssl, allow_redirects=False) as response:
                require(not 300 <= response.status < 400, "DIRECTORY_REDIRECT", 502)
                raw = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    raw.extend(chunk)
                    require(len(raw) <= MAX_RESPONSE, "DIRECTORY_LIMIT", 502)
                import json
                value = json.loads(raw)
                if response.status >= 400:
                    raise Fault(value.get("code", "DIRECTORY_ERROR"), response.status)
                return value
        except (aiohttp.ClientError, TimeoutError, OSError):
            raise Fault("DIRECTORY_UNAVAILABLE", 502) from None

    async def socket(self, credential, role, room_id=None):
        socket = await self.session.ws_connect(self.url.replace("http", "ws", 1) + "/v1/signaling",
                                               ssl=self.ssl, heartbeat=20, max_msg_size=65536, compress=0)
        await socket.send_json({"type": "auth", "role": role, "token": credential, **({"roomId": room_id} if room_id else {})})
        reply = await asyncio.wait_for(socket.receive_json(), 10)
        if reply.get("type") != "authenticated":
            await socket.close()
            raise Fault(reply.get("code", "SIGNAL_AUTH_FAILED"), 401)
        return socket
