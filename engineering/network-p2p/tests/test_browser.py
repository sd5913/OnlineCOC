import asyncio
import json
import os
from pathlib import Path

import pytest

from onlinecoc_p2p.common import atomic_json
from onlinecoc_p2p.host import Host
from onlinecoc_p2p.local_app import start_local
from onlinecoc_p2p.packages import Package

pytestmark = pytest.mark.skipif(os.environ.get("P2P_BROWSER_TEST") != "1", reason="Explicit real-browser acceptance")


async def test_browser_room_login_download_sandbox_and_state(directory, upstream, tmp_path):
    from playwright.async_api import async_playwright, expect
    service, url, publisher = directory
    _, upstream_url = upstream
    cloud = url.startswith("https:")
    ca_file = str(Path("local/test-ca.pem").resolve()) if cloud else None
    source=tmp_path/"source"
    source.mkdir()
    (source/"index.html").write_text("""<!doctype html><html lang="zh"><body>
<h1>玩家配置包</h1><p id="result">正在请求授权数据</p><p id="isolation"></p>
<script>
try {parent.sessionStorage.getItem('onlinecoc-local-token'); document.querySelector('#isolation').textContent='FAILED';}
catch {document.querySelector('#isolation').textContent='隔离生效';}
window.addEventListener('message',event=>{
 if(event.data?.type!=='onlinecoc:port')return;
 const port=event.ports[0];
 port.onmessage=event=>{
   if(event.data.id==='me')document.querySelector('#result').textContent=JSON.stringify(event.data.result);
   if(event.data.id==='admin')document.body.dataset.denied=event.data.error?.code;
 };
 port.postMessage({id:'me',method:'request',params:{path:'me'}});
 port.postMessage({id:'admin',method:'request',params:{path:'host-control/accounts'}});
});
parent.postMessage({type:'onlinecoc:connect'},'*');
</script></body></html>""",encoding="utf-8")
    atomic_json(source/"distribution.json",{"packageId":"browser-test","version":"1","entry":"index.html","files":["index.html"]})
    exported=Package.export(source,source/"distribution.json",tmp_path/"exports")
    host=Host({"directory":url,"caFile":ca_file,"relayOnly":cloud,"publisherToken":publisher,"statePath":str(tmp_path/"host"),
               "upstream":upstream_url,"packagePath":str(exported),
               "settings":{"title":"浏览器验收房间","visibility":"public","approvalRequired":False}})
    await host.start()
    shell, runner, entry = await start_local({"directory":url,"caFile":ca_file,"statePath":str(tmp_path/"shell")})
    errors=[]
    try:
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=True)
            page=await browser.new_page(viewport={"width":1365,"height":1000})
            page.on("pageerror",lambda error: errors.append(str(error)))
            await page.goto(entry)
            card=page.locator(".room-card").filter(has_text="浏览器验收房间")
            await expect(card).to_have_count(1)
            await card.get_by_role("button",name="选择房间").click()
            if cloud: await page.locator("#relay-only").check()
            await page.get_by_role("button",name="连接房主").click()
            await expect(page.locator("#login-form")).to_be_visible(timeout=40000)
            await page.locator("#login-name").fill("alice")
            await page.locator("#login-password").fill("test-only")
            await page.get_by_role("button",name="登录并检查内容").click()
            await expect(page.locator("#content-confirm")).to_be_visible()
            await page.locator("#prepare").click()
            await expect(page.locator("#join-status")).to_contain_text("已进入房间",timeout=20000)
            frame=page.frame_locator("#package-frame iframe")
            await expect(frame.locator("#result")).to_have_text('{"accountId":"alice"}')
            await expect(frame.locator("#isolation")).to_have_text("隔离生效")
            await expect(frame.locator("body")).to_have_attribute("data-denied","ROUTE_NOT_EXPOSED")
            await expect(page.locator("#snapshot")).to_contain_text("alice")
            assert not errors,errors
            if cloud:
                await expect(page.locator("#network-info")).to_contain_text("TURN 中继")
                atomic_json(Path("local/acceptance/browser-cloud.json"),{"browser":browser.version,"forcedRelay":True,
                    "login":True,"download":True,"sandbox":True,"state":True,"pageErrors":errors})
            screenshot=Path("local/acceptance/browser-cloud.png" if cloud else "local/acceptance/browser-room.png")
            screenshot.parent.mkdir(parents=True,exist_ok=True)
            await page.screenshot(path=str(screenshot),full_page=True)
            await page.locator("#leave").click()
            await expect(page.locator("#play-panel")).to_be_hidden()
            await browser.close()
    finally:
        await runner.cleanup()
        await host.close()


async def test_browser_host_publish_lock_stop(directory, upstream, tmp_path):
    from playwright.async_api import async_playwright, expect
    _, url, publisher=directory
    _, upstream_url=upstream
    shell,runner,entry=await start_local({"directory":url,"publisherToken":publisher,
        "upstream":upstream_url,"statePath":str(tmp_path/"ui-host")})
    try:
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=True)
            page=await browser.new_page()
            await page.goto(entry)
            await page.locator('[data-tab="host"]').click()
            await page.locator("#host-visibility").select_option("public")
            await page.get_by_text("连接设置",exact=True).click()
            await page.locator("#host-upstream").fill(upstream_url)
            await page.locator("#host-start").click()
            await expect(page.locator("#host-running")).to_have_text("已发布")
            await page.locator("#host-lock").click()
            await expect(page.locator("#host-details")).to_contain_text("已锁定新加入")
            await page.locator("#host-stop").click()
            await expect(page.locator("#host-running")).to_have_text("未发布")
            assert not shell.host
            await browser.close()
    finally:
        await runner.cleanup()


async def test_browser_discover_host_copy_private_code_and_join(directory, upstream, tmp_path):
    from playwright.async_api import async_playwright, expect
    from test_discovery import registration
    _, url, publisher = directory
    _, upstream_url = upstream
    records = tmp_path / "registry"
    records.mkdir()
    registration(records, upstream_url)
    host_shell, host_runner, host_entry = await start_local({
        "directory": url, "publisherToken": publisher, "upstream": "http://127.0.0.1:1",
        "hostDiscoveryPath": str(records), "statePath": str(tmp_path / "publisher")})
    _, player_runner, player_entry = await start_local({"directory": url, "statePath": str(tmp_path / "player")})
    errors = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            host_page = await browser.new_page(viewport={"width": 1365, "height": 1050})
            player_page = await browser.new_page(viewport={"width": 1365, "height": 1050})
            for page in (host_page, player_page):
                page.on("pageerror", lambda error: errors.append(str(error)))
            await host_page.add_init_script("Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.copiedJoin=text;}}});")
            await host_page.goto(host_entry)
            await host_page.locator('[data-tab="host"]').click()
            await expect(host_page.locator("#local-hosts")).to_have_value(upstream_url)
            await expect(host_page.locator("#host-upstream")).to_have_value(upstream_url)
            await host_page.locator("#host-password").fill("room-code-password")
            await host_page.locator("#host-start").click()
            await expect(host_page.locator("#host-running")).to_have_text("已发布")
            await expect(host_page.locator("#share-code")).to_have_value(__import__("re").compile(r"^[A-Z2-9]{4}-[A-Z2-9]{4}$"))
            code = await host_page.locator("#share-code").input_value()
            invitation = await host_page.locator("#share-join").input_value()
            assert invitation.startswith("OCOC1:" + code + ":")
            await host_page.locator("#copy-join").click()
            assert await host_page.evaluate("window.copiedJoin") == invitation
            await host_page.reload()
            await host_page.locator('[data-tab="host"]').click()
            await expect(host_page.locator("#share-join")).to_have_value(invitation)
            await expect(host_page.locator("#local-hosts")).to_be_disabled()
            await player_page.goto(player_entry)
            await player_page.locator("#room-id").fill(code.lower())
            await player_page.locator("#room-password").fill("room-code-password")
            await player_page.locator("#join-button").click()
            await expect(player_page.locator("#global-error")).to_contain_text("房间不可加入")
            assert not host_shell.host.pending
            await player_page.locator("#room-id").fill(invitation)
            await player_page.locator("#join-button").click()
            await expect(host_page.locator("#pending button").filter(has_text="批准")).to_have_count(1, timeout=10000)
            await host_page.get_by_role("button", name="批准", exact=True).click()
            await expect(player_page.locator("#login-form")).to_be_visible(timeout=40000)
            await player_page.locator("#login-name").fill("alice")
            await player_page.locator("#login-password").fill("test-only")
            await player_page.locator("#login-form button").click()
            await expect(player_page.locator("#prepare")).to_be_visible()
            await player_page.locator("#prepare").click()
            await expect(player_page.locator("#join-status")).to_contain_text("已进入房间", timeout=20000)
            await expect(player_page.locator("#snapshot")).to_contain_text("alice")
            screenshots = Path("local/acceptance")
            screenshots.mkdir(parents=True, exist_ok=True)
            await host_page.screenshot(path=str(screenshots / "room-code-host.png"), full_page=True)
            await player_page.screenshot(path=str(screenshots / "room-code-player.png"), full_page=True)
            assert not errors
            await host_page.locator("#host-stop").click()
            await expect(host_page.locator("#host-share")).to_be_hidden()
            await browser.close()
    finally:
        await player_runner.cleanup()
        await host_runner.cleanup()
