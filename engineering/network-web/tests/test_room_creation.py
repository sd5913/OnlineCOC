import asyncio
import json
import os
import time

import pytest
from playwright.async_api import async_playwright, expect

from onlinecoc_p2p.common import Fault
from onlinecoc_web.creation import export_room_setup, make_room_setup, parse_room_setup
from onlinecoc_web.host import WebHost
from onlinecoc_web.store import PortalStore
from test_portal import User


@pytest.fixture
async def prepared(portal, upstream, resources, tmp_path):
    service, url, publisher = portal
    host = WebHost({"directory": url, "publisherToken": publisher, "statePath": str(tmp_path / "host"),
        "upstream": upstream[1], "webPackagePath": str(resources), "settings": {"title": "可导入房间"}})
    entry = await host.start()
    owner, player = User(url), User(url)
    await owner.register("owner")
    await player.register("player")
    try:
        yield host, service, owner, player, entry["creationString"]
    finally:
        await owner.http.close()
        await player.http.close()
        await host.close()


def test_setup_contract():
    value = make_room_setup("https://example.com/", "ABCD2345", "a" * 32)
    assert parse_room_setup(value, "https://example.com")["roomCode"] == "ABCD2345"
    for bad in ("wrong", value + "!", "OCOC-ROOM1.eA", "x" * 2049):
        with pytest.raises(Fault):
            parse_room_setup(bad, "https://example.com")
    with pytest.raises(Fault, match="SETUP_PLATFORM_MISMATCH"):
        parse_room_setup(value, "https://another.example")
    with pytest.raises(Fault):
        make_room_setup("https://user:password@example.com/", "ABCD2345", "a" * 32)


async def test_creation_public_password_policy_and_persistence(prepared):
    host, service, owner, player, value = prepared
    assert export_room_setup(host.state_path) == value
    assert (await player.call("/v1/web/public-rooms"))["items"] == []
    preview = await owner.call("/v1/web/rooms/preview", {"setupString": value})
    assert preview["metadata"]["title"] == "可导入房间"
    assert service.portal.room(host.room_id)["owner"] is None
    assert not host.peers and not service.store.intents
    created = await owner.call("/v1/web/rooms/create", {"setupString": value, "public": True, "password": "secret"})
    assert created["roomId"] == host.room_id
    await player.call("/v1/web/rooms/create", {"setupString": value, "public": True}, expected=403)
    async with player.http.get(player.url + "/v1/web/public-rooms") as response:
        items = (await response.json())["items"]
    assert len(items) == 1 and items[0]["passwordRequired"]
    assert set(items[0]) == {"roomCode", "title", "package", "passwordRequired", "approvalRequired", "invitationRequired", "seats", "maxPlayers"}
    assert "secret" not in json.dumps(items) and "claim" not in json.dumps(items)
    # Public web rooms remain inaccessible through legacy admission.
    assert (await player.call("/v1/rooms"))["items"] == []
    await player.call("/v1/web/join", {"roomCode": host.room["roomCode"], "password": "wrong"}, expected=404)
    await player.call("/v1/web/join", {"roomCode": host.room["roomCode"], "password": "secret"})
    path = "/v1/web/rooms/" + host.room_id + "/manage"
    await player.call(path, {"action": "settings", "public": False, "passwordMode": "clear"}, expected=403)
    await owner.call(path, {"action": "settings", "public": False, "passwordMode": "keep"})
    assert not (await player.call("/v1/web/public-rooms"))["items"]
    await host.configure()  # Host reconnect must not overwrite platform choices.
    store_path = service.portal.path
    service.portal.close()
    service.portal = PortalStore(store_path)
    room = service.portal.room(host.room_id)
    assert not room["public"] and room["policy"]["passwordVerifier"]
    assert (await owner.call("/v1/web/rooms"))["items"][0]["owner"]
    # Existing member shortcut does not need the password again.
    assert (await player.call("/v1/web/join", {"roomCode": host.room["roomCode"]}))["status"] == "member"
    await owner.call(path, {"action": "settings", "public": True, "passwordMode": "clear"})
    assert not (await player.call("/v1/web/public-rooms"))["items"][0]["passwordRequired"]
    await owner.call(path, {"action": "settings", "public": True, "passwordMode": "set", "password": "new"})
    assert (await player.call("/v1/web/public-rooms"))["items"][0]["passwordRequired"]
    await host.close()
    assert not (await player.call("/v1/web/public-rooms"))["items"]
    assert (await player.call("/v1/web/rooms"))["items"]


async def test_creation_token_refresh_expiry_race_and_validation(prepared):
    host, service, owner, player, old = prepared
    value = await host.prepare_creation()
    assert value != old
    await owner.call("/v1/web/rooms/preview", {"setupString": old}, expected=403)
    await owner.call("/v1/web/rooms/create", {"setupString": value, "public": "false"}, expected=400)
    await owner.call("/v1/web/rooms/create", {"setupString": value, "public": False, "password": "a" * 129}, expected=400)
    assert not service.portal.room(host.room_id)["owner"]
    service.portal.room(host.room_id)["claimExpires"] = time.time() - 1
    await owner.call("/v1/web/rooms/preview", {"setupString": value}, expected=403)
    value = await host.prepare_creation()
    async def attempt(user):
        async with user.http.post(user.url + "/v1/web/rooms/create", headers={"X-CSRF-Token": user.csrf},
                json={"setupString": value, "public": False, "password": "secret"}) as response:
            await response.read()
            return response.status
    assert sorted(await asyncio.gather(attempt(owner), attempt(player))) == [200, 403]
    assert not (await owner.call("/v1/web/public-rooms"))["items"]
    with pytest.raises(Fault, match="ROOM_ALREADY_CLAIMED"):
        await host.prepare_creation()


async def test_closed_public_room_removed_and_old_private_default(prepared):
    host, service, owner, player, _ = prepared
    await owner.call("/v1/web/claim", {"roomCode": host.room["roomCode"], "claim": host.claim})
    service.portal.room(host.room_id).pop("public")  # Existing data has no new field.
    assert not (await player.call("/v1/web/public-rooms"))["items"]
    path = "/v1/web/rooms/" + host.room_id + "/manage"
    await owner.call(path, {"action": "settings", "public": True, "passwordMode": "keep"})
    assert len((await player.call("/v1/web/public-rooms"))["items"]) == 1
    await owner.call(path, {"action": "close"})
    assert not (await player.call("/v1/web/public-rooms"))["items"]


async def browser_workflow(host, service, owner, player, value, owner_name="owner", player_name="player", cloud=False):
    errors = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, channel=os.environ.get("WEB_BROWSER_CHANNEL"))
        owner_context = await browser.new_context(viewport={"width": 1280, "height": 1000}, ignore_https_errors=cloud)
        page = await owner_context.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(owner.url + "/create")
        await page.locator("#name").fill(owner_name)
        await page.locator("#password").fill("test-password-long")
        await page.get_by_role("button", name="登录", exact=True).click()
        await expect(page.locator("#create")).to_be_visible()
        await expect(page.locator("#lobby")).to_be_hidden()
        await page.locator("#setup-string").fill(value)
        await page.locator("#preview-setup").click()
        await expect(page.locator("#setup-preview")).to_contain_text("可导入房间")
        await page.locator("#create-public").check()
        await page.locator("#create-locked").check()
        await page.locator("#create-password").fill("secret")
        await page.locator("#create-submit").click()
        await expect(page).to_have_url(owner.url + "/manage/" + host.room_id)
        await expect(page.locator("#owner")).to_be_visible()
        await expect(page.locator("#password-status")).to_have_text("当前已设置房间密码")
        player_context = await browser.new_context(viewport={"width": 390, "height": 844}, ignore_https_errors=cloud)
        guest = await player_context.new_page()
        guest.on("pageerror", lambda e: errors.append(str(e)))
        await guest.goto(owner.url + "/join")
        await expect(guest.locator("#public-rooms")).to_contain_text("可导入房间")
        await guest.get_by_role("button", name="选择此房间").click()
        await guest.locator("#name").fill(player_name)
        await guest.locator("#password").fill("test-password-long")
        await guest.get_by_role("button", name="登录", exact=True).click()
        await expect(guest.locator("#lobby")).to_be_visible()
        await expect(guest.locator("#room-code")).to_have_value(host.room["roomCode"])
        await guest.locator("#room-password").fill("bad")
        await guest.get_by_role("button", name="加入房间", exact=True).click()
        await expect(guest.locator("#error")).to_be_visible()
        await guest.locator("#room-password").fill("secret")
        await guest.get_by_role("button", name="加入房间", exact=True).click()
        await expect(guest.locator("#room-title")).to_have_text("可导入房间")
        assert not host.peers and (service is None or not service.store.intents)
        await expect(guest.locator("#owner")).to_be_hidden()
        await page.locator("#manage-public").uncheck()
        await page.get_by_role("button", name="保存房间设置").click()
        await expect(page.locator("#notice")).to_contain_text("房间设置已保存")
        await guest.goto(owner.url + "/join")
        await expect(guest.locator("#public-rooms")).to_contain_text("暂无公开")
        await expect(guest.locator("#recent")).to_contain_text("可导入房间")
        await guest.goto(owner.url + "/manage/" + host.room_id)
        await expect(guest.locator("#error")).to_contain_text("只有房主")
        await expect(guest.locator("#owner")).to_be_hidden()
        output = __import__('pathlib').Path(__file__).resolve().parents[1] / 'local/acceptance'
        output.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(output / ('room-management-cloud-0.3.0.png' if cloud else 'room-management-0.3.0.png')), full_page=True)
        await browser.close()
    assert not errors


async def test_three_pages_browser_create_manage_join(prepared):
    await browser_workflow(*prepared)


@pytest.mark.skipif(os.environ.get("WEB_CREATION_CLOUD_TEST") != "1", reason="Explicit cloud room creation test")
async def test_cloud_creation_browser(upstream, resources, tmp_path):
    from pathlib import Path
    import uuid
    module = Path(__file__).resolve().parents[1]
    config = json.loads((module.parent / "network-p2p/local/client-config.json").read_text(encoding="utf-8"))
    host = WebHost({"directory": config["directory"], "publisherToken": config["publisherToken"], "caFile": config["caFile"],
        "statePath": str(tmp_path / "cloud-host"), "upstream": upstream[1], "webPackagePath": str(resources),
        "settings": {"title": "可导入房间"}})
    owner, player = User(config["directory"], config["caFile"]), User(config["directory"], config["caFile"])
    suffix = uuid.uuid4().hex[:10]
    try:
        entry = await host.start()
        await owner.register("flowowner" + suffix)
        await player.register("flowplayer" + suffix)
        await browser_workflow(host, None, owner, player, entry["creationString"], "flowowner" + suffix, "flowplayer" + suffix, True)
        await owner.call("/v1/web/rooms/" + host.room_id + "/manage", {"action": "close"})
        assert (await owner.call("/v1/web/capabilities"))["roomRetentionSeconds"] == 86400
        assert not (await owner.call("/v1/web/rooms"))["items"]
        assert not (await player.call("/v1/web/rooms"))["items"]
        result = await owner.call("/v1/web/public-rooms")
        assert host.room["roomCode"] not in [x["roomCode"] for x in result["items"]]
        (module / "local/acceptance/creation-cloud.json").write_text(json.dumps({
            "version":__import__("onlinecoc_web").__version__, "defaultRetentionSeconds":86400, "closedShortcutsRemoved":True, "publicCreate":True, "passwordJoin":True, "privateHidden":True,
            "shortcutRetained":True, "nonOwnerDenied":True, "roomClosed":True,
            "browserPrivateCAException":True, "hostAndAPITrustedCA":True,
            "roomPagesNoGameConnection":True}, indent=2), encoding="utf-8")
    finally:
        if host.room_id and owner.account:
            try:
                await owner.call("/v1/web/rooms/" + host.room_id + "/manage", {"action": "close"}, expected=404)
            except Exception:
                # If the browser failed before closing, close any claimed test room.
                try:
                    await owner.call("/v1/web/rooms/" + host.room_id + "/manage", {"action": "close"})
                except Exception:
                    pass
        await owner.http.close()
        await player.http.close()
        await host.close()
