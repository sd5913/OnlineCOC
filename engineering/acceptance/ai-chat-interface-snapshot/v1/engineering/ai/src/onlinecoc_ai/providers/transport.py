"""Verify DNS addresses at connection time and connect to the verified literal."""
import asyncio
import ipaddress
import socket

import httpcore
import httpx

from .base import ProviderError


class VerifiedBackend(httpcore.AsyncNetworkBackend):
    def __init__(self, allow_private=False, *, backend=None, resolver=None):
        self.allow_private = allow_private
        self.backend = backend or httpcore.AnyIOBackend()
        self.resolver = resolver

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        async def addresses():
            if self.resolver:
                return await self.resolver(host, port)
            records = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
            return list(dict.fromkeys(record[4][0] for record in records))
        try:
            async with asyncio.timeout(timeout):
                resolved = await addresses()
                if not resolved or any(not self.allow_private and not ipaddress.ip_address(ip).is_global for ip in resolved):
                    raise ProviderError("ENDPOINT_FORBIDDEN")
                last = None
                for ip in resolved:
                    try:
                        # HTTPcore keeps the original origin for TLS SNI and
                        # certificate verification; only TCP uses the literal.
                        return await self.backend.connect_tcp(ip, port, timeout, local_address, socket_options)
                    except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                        last = exc
                raise last or httpcore.ConnectError("connection failed")
        except TimeoutError as exc:
            raise httpcore.ConnectTimeout() from exc

    async def connect_unix_socket(self, *args, **kwargs):
        raise ProviderError("ENDPOINT_FORBIDDEN")

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)


class VerifiedTransport(httpx.AsyncHTTPTransport):
    def __init__(self, allow_private=False):
        super().__init__(trust_env=False, retries=0,
                         limits=httpx.Limits(max_connections=4, max_keepalive_connections=2))
        # Small pinned integration point: HTTPX 0.28.1 / HTTPCore 1.0.9.
        # No connection exists yet. Other HTTPX handling stays unchanged.
        self._pool._network_backend = VerifiedBackend(allow_private)
