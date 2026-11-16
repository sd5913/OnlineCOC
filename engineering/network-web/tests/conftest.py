import importlib.util
import asyncio
import os
import socket
import subprocess
from pathlib import Path

import pytest
from onlinecoc_p2p.common import digest, token
from onlinecoc_web.portal import WebDirectory
from onlinecoc_web.resources import Resources

MODULE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("p2p_test_fixtures", MODULE.parent / "network-p2p/tests/conftest.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
serve, upstream = fixtures.serve, fixtures.upstream


@pytest.fixture
def resources(tmp_path):
    source = MODULE / "examples/core-table"
    return Resources.export(source, source / "web.json", tmp_path / "exports")


@pytest.fixture
async def portal(tmp_path):
    publisher = token()
    service = WebDirectory({"publishers": {"test": digest(publisher.encode())}, "webStateFile": str(tmp_path / "portal.json")}, tmp_path / "directory.json")
    runner, url = await serve(service.app())
    yield service, url, publisher
    await runner.cleanup()


@pytest.fixture
async def real_upstream(tmp_path):
    import aiohttp
    engineering = MODULE.parent
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    log = (tmp_path / "backend.log").open("w", encoding="utf-8")
    process = subprocess.Popen([str(engineering / ".venv/Scripts/python.exe"),
        str(engineering / "network-p2p/scripts/real_host_fixture.py"), "--snapshot", str(engineering),
        "--data-dir", str(tmp_path / "game-data"), "--port", str(port)], stdout=log, stderr=log,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    url = f"http://127.0.0.1:{port}"
    try:
        async with aiohttp.ClientSession() as http:
            for _ in range(150):
                assert process.poll() is None, (tmp_path / "backend.log").read_text()
                try:
                    async with http.get(url + "/api/v1/capabilities") as response:
                        if response.status == 200:
                            break
                except aiohttp.ClientError:
                    pass
                await asyncio.sleep(.1)
            else:
                raise AssertionError("Real backend startup timed out")
        yield url, process
    finally:
        process.terminate()
        await asyncio.to_thread(process.wait, 10)
        log.close()
