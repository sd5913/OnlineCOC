import asyncio
import os
from pathlib import Path

import pytest

from onlinecoc_p2p.host import Host
from onlinecoc_p2p.local_app import start_local
from test_real_host import real_upstream

pytestmark=pytest.mark.skipif(os.environ.get("P2P_REAL_HOST_TEST")!="1",reason="Explicit current SDK integration")


async def test_existing_client_sdk_with_webrtc(directory,real_upstream,tmp_path):
    from playwright.async_api import async_playwright
    _,url,publisher=directory
    host=Host({"directory":url,"publisherToken":publisher,"statePath":str(tmp_path/"sdk-host"),
               "upstream":real_upstream[0],"settings":{"visibility":"public","approvalRequired":False}})
    await host.start()
    shell,runner,entry=await start_local({"directory":url,"statePath":str(tmp_path/"shell")})
    sdk=Path(__file__).resolve().parents[2]/"client-sdk/client.js"
    try:
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=True,channel=os.environ.get('PLAYWRIGHT_CHANNEL'))
            page=await browser.new_page()
            await page.route("**/acceptance-sdk.js",lambda route: route.fulfill(content_type="text/javascript",body=sdk.read_text(encoding="utf-8")))
            await page.goto(entry)
            await page.wait_for_function("sessionStorage.getItem('onlinecoc-local-token')")
            await page.evaluate("""async roomId=>{
              const {WebRtcTransport}=await import('/web/transport.js');
              const {Client}=await import('/acceptance-sdk.js');
              const appToken=sessionStorage.getItem('onlinecoc-local-token');
              const api=async(action,data={},clientToken)=>{
                const response=await fetch('/control/'+action,{method:'POST',headers:{
                  'Authorization':'Bearer '+appToken,'Content-Type':'application/json',
                  ...(clientToken?{'X-Client-Token':clientToken}:{})},body:JSON.stringify(data)});
                const value=await response.json();if(!response.ok)throw new Error(value.code);return value;
              };
              const transport=new WebRtcTransport(api,appToken);
              await transport.connect({roomId});
              await transport.request('login',{method:'POST',body:{loginName:'player1',password:'p2p-test-only-password'}});
              await transport.sync(await transport.manifest(),()=>{});
              window.acceptanceClient=new Client(transport);
              await acceptanceClient.resume();
            }""",host.room_id)
            for _ in range(100):
                if await page.evaluate('acceptanceClient.connected'):break
                await asyncio.sleep(.05)
            else:raise AssertionError('SDK snapshot did not arrive')
            assert await page.evaluate("acceptanceClient.view.accountId")=="player1"
            assert not await page.evaluate("'secret-clue' in acceptanceClient.view.entities")
            receipt=await page.evaluate("async()=>await acceptanceClient.sendChat('general','SDK over WebRTC',{},'sdk-one')")
            assert receipt["status"]=="committed"
            assert await page.evaluate("async()=>await acceptanceClient.sendChat('general','SDK over WebRTC',{},'sdk-one')")==receipt
            history=await page.evaluate("async()=>await acceptanceClient.chatHistory('general')")
            assert len(history["items"])==1
            await page.evaluate("async()=>await acceptanceClient.logout()")
            assert await page.evaluate("acceptanceClient.view===null")
            await browser.close()
    finally:
        await runner.cleanup()
        await host.close()
