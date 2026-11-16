"""Validate the public HTTPS entry and compare installed cloud sources to this checkout."""
import asyncio
import hashlib
import json
import ssl
from pathlib import Path

import aiohttp

module = Path(__file__).resolve().parents[1]


async def main():
    config = json.loads((module.parent / "network-p2p/local/client-config.json").read_text(encoding="utf-8"))
    deployed = json.loads((module / "local/acceptance/deployment.json").read_text(encoding="utf-8"))
    for relative, checksum in deployed["sources"].items():
        assert hashlib.sha256((module.parent / relative).read_bytes()).hexdigest() == checksum, relative
    tls = ssl.create_default_context(cafile=config["caFile"])
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=tls)) as http:
        for path in ("/", "/assets/app.js", "/assets/game.js", "/health"):
            async with http.get(config["directory"] + path) as response:
                assert response.status == 200, (path, response.status)
                assert response.headers["Cache-Control"] == "no-store"
                if path == "/":
                    assert "房间代号" in await response.text()
                    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
        async with http.get(config["directory"] + "/v1/web/rooms") as response:
            assert response.status == 401
    print(json.dumps({"trustedCAHTTPS": True, "staticAndAPI": True, "anonymousShortcutsDenied": True,
        "deployedSourcesMatch": len(deployed["sources"]), "webVersion": deployed["webVersion"],
        "p2pVersion": deployed["p2pVersion"]}))


if __name__ == "__main__":
    asyncio.run(main())
