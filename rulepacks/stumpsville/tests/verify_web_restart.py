"""Existing exports, resource changes and repeated real-room startup; no real save."""
import json
import os
from pathlib import Path
import secrets
import subprocess
from datetime import datetime
from unittest.mock import patch

from harness import PACK, Account, running
from integrations import ROOT, WebStartError, export_tree, export_web_package
from build_web import build
from verify_integrations import directory
from verify_web import owned_room
from playwright.sync_api import sync_playwright, expect


def main():
    output=PACK/'tests/output'/('web-restart-'+secrets.token_hex(4));output.mkdir(parents=True)
    root=output/'导出 空格';build(root/'source')
    prefix=[str(ROOT/'engineering/network-p2p/.venv/Scripts/python.exe'),'-B','-m','onlinecoc_web']
    options={'cwd':ROOT/'engineering/network-web','env':{**os.environ,'PYTHONUTF8':'1','PYTHONDONTWRITEBYTECODE':'1'},'creationflags':getattr(subprocess,'CREATE_NO_WINDOW',0)}
    command=prefix+['export','--source',str(root/'source'),'--descriptor',str(root/'source/web.json'),'--output',str(root/'exports')]
    legacy=subprocess.run(command,**options,capture_output=True,text=True,encoding='utf-8',check=True)
    original=Path(legacy.stdout.strip());snapshot=export_tree(original)
    repeated=subprocess.run(command,**options,capture_output=True,text=True,encoding='utf-8')
    assert repeated.returncode!=0 and 'EXPORT_ALREADY_EXISTS' in repeated.stderr
    checks=['reproduced public CLI EXPORT_ALREADY_EXISTS when exporting twice into the same directory']
    before=(original/'web.json').stat().st_mtime_ns
    assert export_web_package(root,prefix,options)==original
    assert export_web_package(root,prefix,options)==original
    assert export_tree(original)==snapshot and (original/'web.json').stat().st_mtime_ns==before
    assert not list(root.glob('.export-*'))
    checks.append('existing legacy exports reused only after complete hash comparison; repeated start leaves immutable files unchanged and cleans temporary folders')
    source=root/'source/index.html';source.write_text(source.read_text(encoding='utf-8')+'\n<!-- revised UI -->',encoding='utf-8')
    revised=export_web_package(root,prefix,options)
    assert revised!=original and export_tree(original)==snapshot
    old=json.loads((original/'web.json').read_text(encoding='utf-8'));new=json.loads((revised/'web.json').read_text(encoding='utf-8'))
    assert [g['digest'] for g in old['groups'][1:]]==[g['digest'] for g in new['groups'][1:]]
    assert export_web_package(root,prefix,options)==revised
    checks.append('changed startup UI produces a new version despite unchanged language/portrait groups; old export preserved')
    cache_before=export_tree(root/'exports')
    def interrupted(args,**kwargs):
        stage=Path(args[args.index('--output')+1]);(stage/'partial').write_text('incomplete')
        raise subprocess.CalledProcessError(1,args,stderr='TEST_INTERRUPTED')
    with patch('integrations.run_owned',side_effect=interrupted):
        try:export_web_package(root,prefix,options)
        except subprocess.CalledProcessError:pass
        else:raise AssertionError('interruption ignored')
    assert export_tree(root/'exports')==cache_before and not list(root.glob('.export-*'))
    checks.append('interrupted export cannot publish a partial directory and does not alter prior versions')
    blob=next(revised.glob('*/blobs/*'));raw=blob.read_bytes();blob.write_bytes(raw+b'corrupt')
    try:export_web_package(root,prefix,options)
    except WebStartError as error:assert error.code=='WEB_EXPORT_CACHE_INVALID'
    else:raise AssertionError('corrupted export reused')
    assert blob.read_bytes()==raw+b'corrupt';blob.write_bytes(raw)
    checks.append('corrupted cached bytes are rejected with a specific error and preserved for diagnosis')
    with directory(output,web=True) as (config,url):
        data=output/'game'
        with running('web-restart',data=data,web_config=config,no_browser=True) as (runtime,password):
            original_password=password
            kp=Account(runtime.origin,'kp',password);p1=Account(runtime.origin,'player1',password)
            first=kp.request('/package/web/status');assert first['running'],first
            p1.action('draft',{'preset':'mul','name':'重启验证鼠'});kp.action('approve',{'account':'player1'})
            character=p1.state()['character']
            runtime.modules.stop_web();assert not kp.request('/package/web/status')['running']
            runtime.modules.start_web();second=kp.request('/package/web/status');assert second['running'],second
            assert (first['roomId'],first['roomCode'])==(second['roomId'],second['roomCode'])
            assert p1.state()['character']==character
        with running('web-restart',data=data,web_config=config,no_browser=True) as (runtime,_):
            kp=Account(runtime.origin,'kp',original_password);p1=Account(runtime.origin,'player1',original_password)
            third=kp.request('/package/web/status');assert third['running'],third
            assert (first['roomId'],first['roomCode'])==(third['roomId'],third['roomCode'])
            restored=p1.state()['character']
            # The host intentionally rotates its in-memory optimistic-view token.
            # Every persisted character field must remain identical.
            differences={key for key in character.keys()|restored.keys() if character.get(key)!=restored.get(key)}
            assert differences=={'viewToken'},differences
            with owned_room(url,None,third,'restart'),sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True)
                context=browser.new_context();page=context.new_page();errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(url);page.locator('#name').fill('restartplayer');page.locator('#password').fill('123456')
                page.get_by_role('button',name='注册',exact=True).click();page.locator('#lobby').wait_for()
                page.locator('#room-code').fill(third['roomCode']);page.get_by_role('button',name='加入房间',exact=True).click()
                with context.expect_page() as popup:page.locator('#enter-game').click()
                game=popup.value;game.on('pageerror',lambda e:errors.append(str(e)));game.wait_for_load_state()
                game.locator('#connect').click();game.locator('#game-login').wait_for(timeout=45000)
                game.locator('#game-name').fill('player1');game.locator('#game-password').fill(original_password)
                game.locator('#game-login button[type=submit]').click()
                frame=game.frame_locator('#package-frame iframe');expect(frame.locator('.identity')).to_contain_text('player1',timeout=40000)
                assert frame.locator('body').evaluate('async()=> (await stumpsvilleWeb.api("package/state")).character.name')=='重启验证鼠'
                game.screenshot(path=str(output/'restarted-player.png'))
                assert not errors,errors
                browser.close()
            runtime.modules.stop_web();assert kp.state()['initialized']
    checks.append('same adapter and full host restart reuse room ID/code and persisted character; actual Edge player loads reused export and authorized projection')
    record={'passed':True,'checkedAt':datetime.now().astimezone().isoformat(),'checks':checks,'cloudMutation':False,'realSaveModified':False}
    (PACK/'tests/web-restart-results.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False))


if __name__=='__main__':main()
