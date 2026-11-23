"""Real browser KP and player over the optional web transport; no local KP page."""
import argparse
import json
import secrets
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, expect
from harness import PACK, Account, running
from verify_web import test_directory, owned_room, WebPlayer


def main(cloud=False, relay=False):
    expect.set_options(timeout=30000)
    suffix=secrets.token_hex(4)
    output=PACK/'tests/output'/('remote-kp-'+suffix);output.mkdir(parents=True)
    checks=[];errors=[]
    with test_directory(output,cloud,relay) as (config,url,ca),running('remote-kp',data=output/'game',web_config=config,no_browser=True) as (runtime,password):
        local=Account(runtime.origin,'kp',password,'remote-kp-setup')
        status=local.request('/package/web/status')
        with owned_room(url,ca,status,suffix) as owner,sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            def join(name,game_name,wrong_password=False):
                ctx=browser.new_context(ignore_https_errors=cloud,viewport={'width':1440,'height':960})
                page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(url);page.locator('#name').fill(name+suffix);page.locator('#password').fill('123456')
                page.get_by_role('button',name='注册',exact=True).click();page.locator('#lobby').wait_for()
                aid=ctx.request.get(url+'/v1/web/me').json()['accountId']
                page.locator('#room-code').fill(status['roomCode']);page.get_by_role('button',name='加入房间',exact=True).click();page.locator('#room-title').wait_for()
                with ctx.expect_page() as popup:page.locator('#enter-game').click()
                game=popup.value;game.on('pageerror',lambda e:errors.append(str(e)));game.wait_for_load_state();page.close()
                if relay:game.locator('#relay').check()
                game.locator('#connect').click();game.locator('#game-login').wait_for(timeout=60000)
                game.locator('#game-name').fill(game_name)
                if wrong_password:
                    game.locator('#game-password').fill('incorrect-password');game.locator('#game-login button[type=submit]').click()
                    expect(game.locator('#error')).not_to_be_empty();assert game.locator('#package-frame iframe').count()==0
                game.locator('#game-password').fill(password);game.locator('#game-login button[type=submit]').click()
                frame=game.frame_locator('#package-frame iframe')
                try:frame.locator('.identity').wait_for(timeout=180000 if cloud else 60000)
                except Exception:
                    game.screenshot(path=str(output/'failure.png'));print(json.dumps({'status':game.locator('#game-status').inner_text(),'error':game.locator('#error').inner_text(),'network':game.locator('#network').inner_text(),'progress':game.locator('#progress').evaluate('(e)=>[e.value,e.max]'),'frame':frame.locator('body').inner_text() if game.locator('#package-frame iframe').count() else None},ensure_ascii=False));raise
                if relay:expect(game.locator('#network')).to_contain_text('TURN 中继',timeout=20000)
                return ctx,game,WebPlayer(frame),aid
            kctx,kgame,kp,kid=join('keeper','kp',True)
            pctx,pgame,player,pid=join('participant','player1')
            assert owner.get('/v1/web/me').json()['accountId'] != kid
            assert kp.state()['role']=='kp' and kp.state()['accountId']=='kp'
            expect(kp.frame.locator('#room-overview')).to_be_visible()
            assert not kp.frame.locator('[data-action=web-room],#room-url').count()
            assert 'allLocations' in kp.state() and 'allLocations' not in player.state()
            assert player.state()['role']=='player'
            assert player.action('world',{'operation':'start'},error=True).get('failure')
            assert player.request('package/scene-executor',{},error=True).get('code')
            assert kp.request('package/web/status',error=True).get('code')=='ROUTE_NOT_EXPOSED'
            checks.append('non-owner platform member logs into configured KP; wrong password denied; player cannot obtain KP projection/actions; local host controls unexposed')
            player.action('draft',{'preset':'mul','name':'远程主持测试鼠'})
            kp.action('approve',{'account':'player1'});player.action('ready',{'ready':True});kp.action('world',{'operation':'start'})
            assert player.state()['roomStatus']=='active'
            kgame.screenshot(path=str(output/'remote-kp.png'))
            key='remote-kp-'+suffix;args={'action':'tunnel-ground','choice':'inspect'}
            deadline=time.monotonic()+90
            while True:
                result=player.action('scene.action',args,key)
                if result.get('status')=='completed':break
                assert time.monotonic()<deadline,result
                kgame.wait_for_timeout(400)
            checks.append('remote KP approves character and starts session; remote KP page alone executes automatic scene action')
            kp.frame.locator('a[href="#/gm/map"]').click()
            expect(kp.frame.locator('.sidebar')).to_be_visible()
            assert kp.state()['role']=='kp'
            # Same platform account can log into a different game identity with no inherited KP rights.
            kgame.locator('#leave').click();kgame.locator('#connect').click();kgame.locator('#game-login').wait_for(timeout=60000)
            kgame.locator('#game-name').fill('player2');kgame.locator('#game-password').fill(password);kgame.locator('#game-login button[type=submit]').click()
            kp.frame.locator('.identity').wait_for(timeout=180000 if cloud else 60000)
            assert kp.state()['role']=='player' and 'allLocations' not in kp.state()
            checks.append('reconnect as player on same platform account drops KP projection and privileges')
            assert not errors,errors
            browser.close()
        local.http.close()
    record={'passed':True,'checkedAt':datetime.now().astimezone().isoformat(),'cloud':cloud,'forcedTurn':relay,'checks':checks,'samePhysicalComputer':True,'noLocalKPBrowser':True,'temporaryRoomRemoved':True}
    target=PACK/'tests'/('remote-kp-cloud-results.json' if cloud else 'remote-kp-results.json')
    target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--cloud',action='store_true');parser.add_argument('--relay',action='store_true');args=parser.parse_args()
    main(args.cloud,args.relay)
