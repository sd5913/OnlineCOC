import asyncio
import json
import os
import uuid
from pathlib import Path

import pytest
import aiohttp

from onlinecoc_p2p.common import atomic_json
from onlinecoc_web.host import WebHost
from test_portal import User

MODULE = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.environ.get("WEB_CLOUD_RESTART_TEST") != "1", reason="Explicit cloud service restart maintenance")


async def test_cloud_restart_keeps_accounts_membership_and_code(real_upstream, resources, tmp_path):
    config = json.loads((MODULE.parent / "network-p2p/local/client-config.json").read_text(encoding="utf-8"))
    config.update(statePath=str(tmp_path / "host"), upstream=real_upstream[0], webPackagePath=str(resources),
                  settings={"title": "重启持久化验收"})
    host = WebHost(config)
    users = [User(config["directory"], config["caFile"]) for _ in range(2)]
    owner, player = users
    prefix = uuid.uuid4().hex[:10]
    try:
        await host.start()
        await owner.register("o" + prefix)
        await player.register("p" + prefix)
        await owner.call("/v1/web/claim", {"roomCode": host.room["roomCode"], "claim": host.claim})
        await player.call("/v1/web/join", {"roomCode": host.room["roomCode"]})
        rid, code = host.room_id, host.room["roomCode"]
        process = await asyncio.create_subprocess_exec("pwsh.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(MODULE.parent / "network-p2p/scripts/server.ps1"), "-Command", "sudo systemctl restart onlinecoc-directory",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        # aiohttp gracefully drains existing WSS connections before systemd restart returns.
        stdout, stderr = await asyncio.wait_for(process.communicate(), 60)
        assert process.returncode == 0, stderr.decode(errors="replace")
        for _ in range(20):
            try:
                await player.call("/health")
                break
            except (aiohttp.ClientError, OSError):
                await asyncio.sleep(.5)
        assert (await player.call("/v1/web/me"))["accountId"] == player.account
        assert rid in [r["roomId"] for r in (await player.call("/v1/web/rooms"))["items"]]
        for _ in range(40):
            info = await player.call("/v1/web/rooms/" + rid + "/presence", {})
            if info["online"]:
                break
            await asyncio.sleep(1)
        assert info["online"]
        assert host.room["roomCode"] == code
        await owner.call("/v1/web/rooms/" + rid + "/manage", {"action": "ban", "accountId": player.account})
        await player.call("/v1/web/rooms/" + rid + "/presence", {}, expected=403)
        atomic_json(MODULE / "local/acceptance/cloud-restart.json", {"serviceRestart": True, "sessionSurvived": True,
            "membershipSurvived": True, "hostRepublished": True, "stableCode": True, "banEnforced": True})
    finally:
        try:
            if host.room:
                await owner.call("/v1/web/rooms/" + host.room_id + "/manage", {"action": "close"})
        finally:
            await host.close()
            for user in users:
                await user.http.close()
