import json
import os
import uuid

from aiohttp import ClientSession, web

from conftest import serve
from onlinecoc_p2p.discovery import discover, process_matches
from onlinecoc_p2p.local_app import start_local


def registration(folder, url, **extra):
    iid = uuid.uuid4().hex
    record = {"version": 1, "instanceId": iid, "pid": os.getpid(), "url": url,
              "dataDirectory": str(folder / "save"), "protectedKey": "must-not-leak", **extra}
    path = folder / (iid + ".json")
    path.write_text(json.dumps(record))
    return path


def test_process_liveness_and_reused_pid():
    assert process_matches(os.getpid(), __import__("time").time())
    assert not process_matches(2**32 - 1, 0)
    assert not process_matches(True, 0)
    if os.name == "nt":
        assert not process_matches(os.getpid(), 1)


async def test_discovery_filters_stale_external_redirect_and_secrets(upstream, tmp_path):
    _, url = upstream
    good = registration(tmp_path, url)
    registration(tmp_path, "https://example.invalid")
    registration(tmp_path, "http://169.254.169.254")
    registration(tmp_path, url + "/admin")
    registration(tmp_path, "http://127.0.0.1:1", pid=2**32-1)
    (tmp_path / "broken.json").write_text("{")
    app = web.Application()
    async def redirect(_):
        raise web.HTTPFound(location=url + "/unexpected")
    app.router.add_get("/api/v1/capabilities", redirect)
    runner, redirect_url = await serve(app)
    registration(tmp_path, redirect_url)
    try:
        items = await discover({"hostDiscoveryPath": str(tmp_path), "upstream": url})
        assert len(items) == 1 and items[0]["url"] == url and items[0]["source"] == "registered"
        assert "protectedKey" not in json.dumps(items) and "must-not-leak" not in json.dumps(items)
        # PID reuse / old record cannot supply a misleading saved-room label.
        os.utime(good, (1, 1))
        if os.name == "nt":
            items = await discover({"hostDiscoveryPath": str(tmp_path), "upstream": url})
            assert items[0]["source"] == "configured"
    finally:
        await runner.cleanup()


async def test_discovery_local_capability_publisher_and_origin_boundary(directory, upstream, tmp_path):
    _, url, publisher = directory
    _, upstream_url = upstream
    registration(tmp_path, upstream_url)
    config = {"directory": url, "publisherToken": publisher, "upstream": upstream_url,
              "statePath": str(tmp_path / "host"), "hostDiscoveryPath": str(tmp_path)}
    shell, runner, _ = await start_local(config)
    try:
        async with ClientSession() as http:
            endpoint = shell.origin + "/local/hosts"
            async with http.get(endpoint) as response:
                assert response.status == 401
            headers = {"Authorization": "Bearer " + shell.capability, "Origin": "https://foreign.invalid"}
            async with http.get(endpoint, headers=headers) as response:
                assert response.status == 403
            headers["Origin"] = shell.origin
            async with http.get(endpoint, headers=headers) as response:
                assert response.status == 200 and len((await response.json())["items"]) == 1
            shell.config.pop("publisherToken")
            async with http.get(endpoint, headers=headers) as response:
                assert response.status == 403
    finally:
        await runner.cleanup()
