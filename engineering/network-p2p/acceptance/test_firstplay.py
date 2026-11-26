"""Local first-play acceptance against the real host; never reads cloud credentials.

Run from network-p2p with its development runtime and Playwright Chromium.
All host data uses pytest's tmp_path; evidence uses FIRSTPLAY_OUTPUT when set.
"""
import asyncio
import json
import os
import socket
import sys
from pathlib import Path

import aiohttp
import pytest

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / "tests"))
sys.path.insert(0, str(MODULE.parent / "network-lan/src"))
from conftest import directory  # noqa: E402,F401
from test_real_host import command, real_upstream  # noqa: E402,F401
from onlinecoc_lan.gateway import Config, Gateway  # noqa: E402
from onlinecoc_p2p.client import Player  # noqa: E402
from onlinecoc_p2p.common import atomic_json  # noqa: E402
from onlinecoc_p2p.local_app import start_local  # noqa: E402
from onlinecoc_p2p.packages import Package  # noqa: E402

OUT = Path(os.environ.get("FIRSTPLAY_OUTPUT", str(MODULE / "local/acceptance/2026-11-26-firstplay")))
PASSWORD = "p2p-test-only-password"


async def test_real_host_browser_firstplay(directory, real_upstream, tmp_path):
    from playwright.async_api import async_playwright, expect

    _, url, publisher = directory
    upstream, process = real_upstream
    source = tmp_path / "source"
    source.mkdir()
    (source / "index.html").write_text("<!doctype html><title>First play</title><p>本地真实宿主验收配置包</p>", encoding="utf-8")
    atomic_json(source / "distribution.json", {"packageId": "firstplay", "version": "1", "entry": "index.html", "files": ["index.html"]})
    package = Package.export(source, source / "distribution.json", tmp_path / "exports")
    host_shell, host_runner, host_entry = await start_local({
        "directory": url, "publisherToken": publisher, "statePath": str(tmp_path / "publisher"),
        "upstream": upstream, "hostDiscoveryPath": str(tmp_path / "discovery"), "packagePath": str(package)})
    _, player_runner, player_entry = await start_local({"directory": url, "statePath": str(tmp_path / "player")})
    observer = Player(url)
    errors = []
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            host_page = await browser.new_page()
            player_page = await browser.new_page()
            for page in (host_page, player_page):
                page.on("pageerror", lambda error: errors.append(str(error)))
            await host_page.goto(host_entry)
            await host_page.locator('[data-tab="host"]').click()
            await expect(host_page.locator("#local-hosts")).to_have_value(upstream)
            await host_page.locator("#host-title").fill("本机真实宿主验收")
            await host_page.locator("#host-password").fill("firstplay-room")
            await host_page.locator("#host-approval").uncheck()
            await host_page.locator("#host-start").click()
            await expect(host_page.locator("#host-running")).to_have_text("已发布")
            join = await host_page.locator("#share-join").input_value()
            assert join.startswith("OCOC1:")
            listing = await host_shell.host.control.request("GET", "/v1/rooms")
            assert host_shell.host.room_id not in [room["roomId"] for room in listing["items"]]
            await player_page.goto(player_entry)
            await player_page.locator("#room-id").fill(join)
            await player_page.locator("#room-password").fill("wrong-password")
            await player_page.locator("#join-button").click()
            await expect(player_page.locator("#global-error")).to_contain_text("房间不可加入")
            await player_page.locator("#room-password").fill("firstplay-room")
            await player_page.locator("#join-button").click()
            await expect(player_page.locator("#login-form")).to_be_visible(timeout=40000)
            await player_page.locator("#login-name").fill("player1")
            await player_page.locator("#login-password").fill("wrong-password")
            await player_page.locator("#login-form button").click()
            await expect(player_page.locator("#global-error")).to_contain_text("AUTH_FAILED")
            await player_page.locator("#login-password").fill(PASSWORD)
            await player_page.locator("#login-form button").click()
            await expect(player_page.locator("#prepare")).to_be_visible()
            await player_page.locator("#prepare").click()
            await expect(player_page.locator("#join-status")).to_contain_text("已进入房间", timeout=20000)
            await expect(player_page.frame_locator("#package-frame iframe").locator("p")).to_have_text("本地真实宿主验收配置包")
            await expect(player_page.locator("#snapshot")).to_contain_text('"accountId": "player1"')
            initial = json.loads(await player_page.locator("#snapshot").text_content())
            assert "secret-clue" not in initial["entities"]
            await player_page.locator("#chat-text").fill("First play: browser to real host")
            await player_page.locator("#send-chat").click()
            await expect(player_page.locator("#chat-status")).to_contain_text('"status":"committed"')

            await observer.join(host_shell.host.room_id, password="firstplay-room", invitation=join.split(":", 2)[2])
            await observer.request("login", "POST", {"loginName": "player2", "password": PASSWORD})
            downloaded = await observer.prepare(tmp_path / "cache")
            cached = await observer.prepare(tmp_path / "cache")
            assert downloaded["downloadedBytes"] > 0 and cached["downloadedBytes"] == 0
            assert (await observer.request("view"))["accountId"] == "player2"
            history = await observer.request("chat/history", "POST", {"channelId": "general", "limit": 10})
            assert any(item["text"] == "First play: browser to real host" for item in history["items"])
            OUT.mkdir(parents=True, exist_ok=True)
            await player_page.screenshot(path=str(OUT / "p2p-real-host-player.png"), full_page=True)
            await host_page.locator("#host-stop").click()
            await expect(host_page.locator("#host-running")).to_have_text("未发布")
            assert process.poll() is None
            async with aiohttp.ClientSession() as http:
                async with http.get(upstream + "/api/v1/capabilities") as response:
                    assert response.status == 200
            assert not errors, errors
            atomic_json(OUT / "p2p-real-host.json", {
                "samePhysicalComputer": True, "directory": "isolated loopback HTTP", "cloudAccess": False,
                "browser": browser.version, "hostDiscovered": True, "hostPublishedFromUI": True,
                "privateRoomHidden": True, "wrongRoomPasswordThenRetry": True, "wrongLoginThenRetry": True,
                "playerDownloadedAndMountedPackage": True, "cachedDownloadBytes": cached["downloadedBytes"],
                "browserChatCommittedAndObservedBySecondPlayer": True, "separatePlayerAccounts": True,
                "hiddenEntityAbsent": True, "borrowedHostSurvivesStop": True, "pageErrors": errors})
            await browser.close()
    finally:
        await observer.close()
        await player_runner.cleanup()
        await host_runner.cleanup()


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


async def test_real_host_lan_firstplay(real_upstream):
    upstream, process = real_upstream
    gateway = Gateway(Config(upstream, "127.0.0.1", free_port()))
    occupied = socket.socket()
    occupied.bind(("127.0.0.1", gateway.config.port))
    occupied.listen()
    try:
        with pytest.raises(RuntimeError):
            await asyncio.to_thread(gateway.start)
    finally:
        occupied.close()
    await asyncio.to_thread(gateway.start)
    origin = gateway.config.url
    clients = [aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True), headers={"Origin": origin}) for _ in range(2)]
    ws = None
    try:
        async def call(client, method, path, body=None, csrf=None):
            async with client.request(method, origin + "/api/v1/" + path, json=body,
                                      headers={"X-CSRF-Token": csrf} if csrf else {}) as response:
                return response.status, await response.json()

        status, _ = await call(clients[0], "POST", "login", {"loginName": "player1", "password": "wrong"})
        assert status == 401
        tokens = []
        for index, client in enumerate(clients, 1):
            status, login = await call(client, "POST", "login", {"loginName": f"player{index}", "password": PASSWORD})
            assert status == 200
            tokens.append(login["csrf"])
            status, view = await call(client, "GET", "view")
            assert status == 200 and view["accountId"] == f"player{index}"
            assert "secret-clue" not in view["entities"]
        ws = await clients[1].ws_connect(origin + "/api/v1/connect")
        assert (await ws.receive_json(timeout=10))["type"] == "snapshot.begin"
        _, view = await call(clients[0], "GET", "view")
        envelope = command(view, "chat.message.send", {"channelId": "general", "text": "First play via LAN"})
        status, receipt = await call(clients[0], "POST", "commands", envelope, tokens[0])
        assert status == 200 and receipt["status"] == "committed"
        _, repeated = await call(clients[0], "POST", "commands", envelope, tokens[0])
        assert repeated == receipt
        _, history = await call(clients[1], "POST", "chat/history", {"channelId": "general", "limit": 10}, tokens[1])
        assert any(item["text"] == "First play via LAN" for item in history["items"])
        status, _ = await call(clients[0], "GET", "host-control/accounts")
        assert status == 404
        await ws.close()
        await asyncio.to_thread(gateway.stop)
        assert process.poll() is None
        await asyncio.to_thread(gateway.start)
        status, view = await call(clients[0], "GET", "view")
        assert status == 200 and view["accountId"] == "player1"
        atomic_json(OUT / "lan-real-host.json", {
            "samePhysicalComputer": True, "bind": "127.0.0.1", "cloudAccess": False,
            "portConflictThenRetry": True, "wrongLoginThenRetry": True, "separatePlayerAccounts": True,
            "httpChatCommittedAndObservedBySecondPlayer": True, "webSocketSnapshot": True,
            "idempotentCommand": True, "hostControlDenied": True, "borrowedHostSurvivesStop": True,
            "gatewayRestartPreservesHostSession": True})
    finally:
        if ws:
            await ws.close()
        for client in clients:
            await client.close()
        await asyncio.to_thread(gateway.stop)
