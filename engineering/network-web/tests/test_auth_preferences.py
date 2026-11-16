import os
import json

import pytest
from playwright.async_api import async_playwright, expect

from test_portal import User


@pytest.mark.parametrize("password", ["123456", "abcdef", "      ", "中文中文中文", "x" * 129])
async def test_password_only_requires_six_characters(portal, password):
    service, url, _ = portal
    user = User(url)
    try:
        registered = await user.call("/v1/web/auth/register", {"name": "sixchars", "password": password})
        user.csrf = registered["csrf"]
        await user.call("/v1/web/auth/logout", {})
        login = await user.call("/v1/web/auth/login", {"name": "sixchars", "password": password})
        assert login["accountId"] == registered["accountId"]
        assert service.portal.data["accounts"][registered["accountId"]]["password"].startswith("$argon2id$")
        recovery = await user.call("/v1/web/auth/recover", {"name": "sixchars", "password": "654321", "recovery": registered["recovery"]})
        assert recovery["accountId"] == registered["accountId"]
        await user.call("/v1/web/auth/login", {"name": "sixchars", "password": "654321"})
    finally:
        await user.http.close()


async def test_five_character_password_is_rejected(portal):
    _, url, _ = portal
    user = User(url)
    try:
        result = await user.call("/v1/web/auth/register", {"name": "tooshort", "password": "12345"}, expected=400)
        assert result["code"] == "PASSWORD_LENGTH"
    finally:
        await user.http.close()


async def test_remember_credentials_persist_locally_and_can_be_forgotten(portal, tmp_path):
    _, url, _ = portal
    key = "onlinecoc-web:remember:platform"
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(str(tmp_path / "browser-profile"), headless=True, channel=os.environ.get("WEB_BROWSER_CHANNEL"))
        try:
            page = await context.new_page()
            await page.goto(url)
            await expect(page.locator("#auth")).to_be_visible()
            assert await page.locator("#password").get_attribute("maxlength") is None
            await expect(page.locator("#remember-login")).not_to_be_checked()
            await page.locator("#name").fill("rememberme")
            await page.locator("#password").fill("123456")
            async with page.expect_response(lambda r: r.url.endswith("/auth/register")) as response:
                await page.get_by_role("button", name="注册", exact=True).click()
            registered = await (await response.value).json()
            await expect(page.locator("#lobby")).to_be_visible()
            assert await page.evaluate("key=>localStorage.getItem(key)", key) is None
            await page.get_by_role("button", name="退出账号", exact=True).click()
            await expect(page.locator("#auth")).to_be_visible()
            await page.locator("#name").fill("rememberme")
            await page.locator("#password").fill("123456")
            await page.locator("#remember-login").check()
            await page.get_by_role("button", name="登录", exact=True).click()
            await expect(page.locator("#lobby")).to_be_visible()
            assert json.loads(await page.evaluate("key=>localStorage.getItem(key)", key)) == {"name": "rememberme", "password": "123456"}
            await page.get_by_role("button", name="退出账号", exact=True).click()
            await expect(page.locator("#password")).to_have_value("123456")
            await page.locator("#password").fill("wrongpass")
            await page.get_by_role("button", name="登录", exact=True).click()
            await expect(page.locator("#error")).to_contain_text("不正确")
            assert json.loads(await page.evaluate("key=>localStorage.getItem(key)", key))["password"] == "123456"
            await page.locator("#recover-toggle").click()
            await page.locator("#recovery").fill(registered["recovery"])
            await page.locator("#password").fill("abcdef")
            await page.locator("#recover-submit").click()
            await expect(page.locator("#lobby")).to_be_visible()
            assert json.loads(await page.evaluate("key=>localStorage.getItem(key)", key))["password"] == "abcdef"
            await page.get_by_role("button", name="退出账号", exact=True).click()
            await expect(page.locator("#auth")).to_be_visible()
        finally:
            await context.close()
        # The browser process itself restarts with the same visitor profile.
        context = await p.chromium.launch_persistent_context(str(tmp_path / "browser-profile"), headless=True, channel=os.environ.get("WEB_BROWSER_CHANNEL"))
        try:
            page = await context.new_page()
            await page.goto(url)
            await expect(page.locator("#name")).to_have_value("rememberme")
            await expect(page.locator("#password")).to_have_value("abcdef")
            await expect(page.locator("#remember-login")).to_be_checked()
            await page.locator("#remember-login").uncheck()
            assert await page.evaluate("key=>localStorage.getItem(key)", key) is None
            await page.reload()
            await expect(page.locator("#password")).to_have_value("")
            await page.locator("#name").fill("rememberme")
            await page.locator("#password").fill("abcdef")
            await page.locator("#remember-login").check()
            await page.get_by_role("button", name="登录", exact=True).click()
            await expect(page.locator("#lobby")).to_be_visible()
            await page.get_by_role("button", name="退出账号", exact=True).click()
            await page.locator("#forget-login").click()
            await expect(page.locator("#name")).to_have_value("")
            await expect(page.locator("#password")).to_have_value("")
            assert await page.evaluate("key=>localStorage.getItem(key)", key) is None
        finally:
            await context.close()


async def test_other_browser_does_not_get_credentials_and_disabled_storage_still_logs_in(portal, tmp_path):
    _, url, _ = portal
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, channel=os.environ.get("WEB_BROWSER_CHANNEL"))
        context = await browser.new_context()
        other = await browser.new_context()
        try:
            page = await context.new_page()
            await page.goto(url)
            await page.evaluate("localStorage.setItem('onlinecoc-web:remember:platform',JSON.stringify({name:'localonly',password:'123456'}))")
            second = await other.new_page()
            await second.add_init_script("Storage.prototype.setItem=function(){throw new DOMException('disabled','SecurityError');};")
            await second.goto(url)
            await expect(second.locator("#auth")).to_be_visible()
            await expect(second.locator("#name")).to_have_value("")
            await expect(second.locator("#password")).to_have_value("")
            await second.locator("#name").fill("nostorage")
            await second.locator("#password").fill("abcdef")
            await second.locator("#remember-login").check()
            await second.get_by_role("button", name="注册", exact=True).click()
            await expect(second.locator("#lobby")).to_be_visible()
            await expect(second.locator("#notice")).to_contain_text("不允许保存账密")
        finally:
            await browser.close()
