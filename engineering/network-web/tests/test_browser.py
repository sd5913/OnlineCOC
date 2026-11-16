import asyncio
import json
import os
import uuid
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect

from onlinecoc_p2p.common import atomic_json
from onlinecoc_web.host import WebHost
from test_portal import User

MODULE = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("cloud", [False, pytest.param(True, marks=pytest.mark.skipif(os.environ.get("WEB_CLOUD_TEST") != "1", reason="Explicit cloud browser test"))])
async def test_real_browser_two_players_lazy_resources_blacklist(portal, real_upstream, resources, tmp_path, cloud):
    service, url, publisher = portal
    config = {"directory": url, "publisherToken": publisher, "statePath": str(tmp_path / "host"),
        "upstream": real_upstream[0], "webPackagePath": str(resources), "settings": {"title": "首测规则浏览器房间"}}
    ca_file = None
    prefix = uuid.uuid4().hex[:8]
    if cloud:
        live = json.loads((MODULE.parent / "network-p2p/local/client-config.json").read_text(encoding="utf-8"))
        url, publisher, ca_file = live["directory"], live["publisherToken"], live["caFile"]
        config.update(directory=url, publisherToken=publisher, caFile=ca_file, relayOnly=True)
    host = WebHost(config)
    await host.start()
    owner = User(url, ca_file)
    await owner.register("owner" + prefix)
    await owner.call("/v1/web/claim", {"roomCode": host.room["roomCode"], "claim": host.claim})
    errors = []
    chunks = []
    original_chunk = host.resources.groups["startup"]["package"].chunk
    def counted(*args):
        chunks.append(args)
        return original_chunk(*args)
    host.resources.groups["startup"]["package"].chunk = counted
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, channel=os.environ.get("WEB_BROWSER_CHANNEL"))
            contexts, games, accounts = [], [], []
            for index in (1, 2):
                # Test CA only: acceptance explicitly records this exception; normal players
                # must trust the supplied CA until a public certificate is configured.
                context = await browser.new_context(viewport={"width": 1365, "height": 1000}, ignore_https_errors=cloud)
                contexts.append(context)
                page = await context.new_page()
                page.on("pageerror", lambda e: errors.append(str(e)))
                await page.goto(url)
                await page.locator("#name").fill("p" + str(index) + prefix)
                await page.locator("#password").fill("browser-password-long")
                await page.get_by_role("button", name="注册", exact=True).click()
                await expect(page.locator("#lobby")).to_be_visible()
                accounts.append((await (await context.request.get(url + "/v1/web/me")).json())["accountId"])
                await page.locator("#room-code").fill(host.room["roomCode"])
                await page.get_by_role("button", name="加入房间", exact=True).click()
                await expect(page.locator("#room-title")).to_have_text("首测规则浏览器房间")
                if index == 1:
                    assert not host.peers and not chunks
                async with context.expect_page() as new_page:
                    await page.locator("#enter-game").click()
                game = await new_page.value
                games.append(game)
                game.on("pageerror", lambda e: errors.append(str(e)))
                await game.wait_for_load_state()
                await page.close()
                if cloud:
                    await game.locator("#relay").check()
                await game.locator("#connect").click()
                await expect(game.locator("#game-login")).to_be_visible(timeout=45000)
                await game.locator("#game-name").fill("player" + str(index))
                await game.locator("#game-password").fill("p2p-test-only-password")
                await game.locator("#remember-game-login").check()
                await game.locator('#game-login button[type="submit"]').click()
                await expect(game.locator("#game-status")).to_have_text("已进入游戏", timeout=30000)
                frame = game.frame_locator("#package-frame iframe")
                await expect(frame.locator("#account")).to_have_text("游戏账号：player" + str(index))
                saved = await game.evaluate("key=>JSON.parse(localStorage.getItem(key))", "onlinecoc-web:remember:game:" + accounts[-1] + ":" + host.room_id)
                assert saved == {"name": "player" + str(index), "password": "p2p-test-only-password"}
                await expect(frame.locator("#isolation")).to_have_text("游戏界面已隔离平台账号")
                await expect(frame.locator("#state")).to_contain_text("actor-player1")
                assert "secret-clue" not in await frame.locator("#state").inner_text()
                if cloud:
                    await expect(game.locator("#network")).to_contain_text("TURN 中继", timeout=10000)
            assert len(host.peers) == 2
            first = games[0].frame_locator("#package-frame iframe")
            await first.locator("#args").fill('{"actor":"actor-player1","amount":7}')
            await first.locator("#invoke").click()
            await expect(first.locator("#result")).to_contain_text('"status": "committed"')
            await first.locator("#chat-text").fill("网页联机真实宿主验收")
            await first.locator("#chat-send").click()
            await expect(first.locator("#chat")).to_contain_text("网页联机真实宿主验收")
            await first.locator("#reference").click()
            await expect(first.locator("#resource")).to_contain_text("此文件仅在点击")
            await first.locator("#note").click()
            await expect(first.locator("#error")).to_have_text("RESOURCE_FORBIDDEN")
            # Closing the room page did not stop either independent game connection.
            assert all(p.ready for p in host.peers.values())
            await owner.call("/v1/web/rooms/" + host.room_id + "/manage", {"action": "ban", "accountId": accounts[0]})
            await expect(games[0].locator("#package-frame iframe")).to_have_count(0, timeout=15000)
            await expect(games[1].locator("#game-status")).to_have_text("已进入游戏")
            assert not errors, errors
            output = MODULE / "local/acceptance"
            output.mkdir(parents=True, exist_ok=True)
            await games[1].screenshot(path=str(output / ("game-cloud.png" if cloud else "game.png")), full_page=True)
            atomic_json(output / ("browser-cloud.json" if cloud else "browser-local.json"), {"browser": browser.version, "players": 2, "realBackend": True,
                "cloud": cloud, "forcedRelay": cloud, "browserPrivateCATestException": cloud,
                "roomPageNoPeerOrResources": True, "independentGamePage": True, "command": True, "chat": True,
                "lazyReference": True, "privateGroupDenied": True, "blacklistDisconnect": True, "pageErrors": errors})
            await browser.close()
        assert real_upstream[1].poll() is None
    finally:
        await owner.call("/v1/web/rooms/" + host.room_id + "/manage", {"action": "close"})
        await owner.http.close()
        await host.close()
