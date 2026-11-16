"""Real host/browser acceptance for separate KP play, scoped chat and localization."""
import json
from datetime import datetime
from harness import running, provision, Account, PACK
from playwright.sync_api import sync_playwright, expect


def main():
    checks=[]
    errors=[]
    with running('workspace-05') as (runtime,password):
        kp,p1,p2=provision(runtime,password)
        kp.action('draft.roll')
        kp.action('draft',{'preset':'mul','name':'主持的小鼠'})
        kp.action('approve',{'account':'kp'})
        kp.action('ready',{'ready':True})
        view=kp.request('/package/state?player=1')
        assert view['role']=='player' and view['character']['owner']=='kp' and view['canManage']
        assert not {'allLocations','network','members','world','encounters','recapPrivate'} & view.keys()
        assert not any(r['operation'] in {'approve','initialize','backup','world'} for r in view['receipts'])
        assert not p1.request('/package/state?player=1')['canManage']
        kp.action('check',{'attribute':'dex','mode':'normal'})
        assert kp.request('/package/state?player=1')['character']['numbers']['checks']==1
        checks.append('KP can create, approve, ready and play own character; player projection excludes management data')
        message='<img src=x onerror=alert(1)> scene secret'
        payload={'operation':'chat.message.send','input':{'channelId':'sv-scene-1','text':message}}
        first=p1.action('chat',payload,action_id='scene-chat-idempotent')
        assert p1.action('chat',payload,action_id='scene-chat-idempotent')==first
        assert len(p2.request('/package/chat/history',{'channelId':'sv-scene-1'})['items'])==1
        assert p1.request('/package/chat/history',{'channelId':'sv-scene-2'},allow_error=True)['code']=='NOT_VISIBLE'
        kp.action('location.publish',{'index':2,'clues':[]})
        p1.action('request',{'kind':'travel','destination':2})
        assert p1.request('/package/chat/history',{'channelId':'sv-scene-1'},allow_error=True)['code']=='NOT_VISIBLE'
        assert p1.action('chat',payload,allow_error=True)['code']=='NOT_VISIBLE'
        p1.action('chat',{'operation':'chat.message.send','input':{'channelId':'sv-party','text':'队伍持久消息'}})
        assert p2.request('/package/chat/history',{'channelId':'sv-party'})['items'][0]['text']=='队伍持久消息'
        dm=p1.action('chat',{'operation':'chat.direct.open','input':{'accountId':'player2'}})['channelId']
        assert kp.request('/package/chat/history',{'channelId':dm},allow_error=True)['code']=='NOT_VISIBLE'
        checks.append('scene access checked on every read/write after movement; team messages, idempotence and private-chat isolation')
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            context=browser.new_context(viewport={'width':1440,'height':1000})
            def login(name):
                page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(runtime.origin+'/sessions/'+name+'/')
                page.locator('[name=loginName]').fill(name);page.locator('[name=password]').fill(password)
                page.get_by_role('button',name='进入冒险',exact=True).click();page.locator('.identity').wait_for()
                return page
            gm=login('kp');gm.goto(runtime.origin+'/sessions/kp/#/gm/console')
            assert not gm.locator('.desktop-dock').count()
            with context.expect_page() as opened:gm.get_by_role('link',name='打开PL视窗').click()
            own=opened.value;own.on('pageerror',lambda e:errors.append(str(e)));own.locator('.workspace-toolbar').wait_for()
            assert not own.locator('.kp-console').count() and not own.locator('a[href="#/gm/locations"]').count()
            before=kp.request('/package/state?player=1')['character']['numbers']['checks']
            own.get_by_role('button',name='属性检定',exact=True).click();own.get_by_role('button',name='投骰',exact=True).click()
            own.locator('dialog').wait_for(state='hidden')
            assert kp.request('/package/state?player=1')['character']['numbers']['checks']==before+1
            checks.append('separate KP management and own PL windows; real PL check commits from shared player component')
            player=login('player2');player.goto(runtime.origin+'/sessions/player2/#/play/scene')
            player.locator('[data-chat=group][data-channel=scene]').click()
            expect(player.locator('#chat-history')).to_contain_text(message)
            assert not player.locator('#chat-history img').count()
            player.locator('#chat-form textarea').fill('场景草稿')
            player.locator('[data-chat=group][data-channel=party]').click()
            player.locator('#chat-form textarea').fill('队伍草稿')
            player.locator('[data-chat=group][data-channel=scene]').click()
            assert player.locator('#chat-form textarea').input_value()=='场景草稿'
            player.locator('#chat-form textarea').press('Control+Enter')
            expect(player.locator('#chat-history')).to_contain_text('场景草稿')
            for account in ['player1','kp']:
                player.locator('[data-chat=direct]').click()
                player.locator('[data-contact="'+account+'"]').click()
                expect(player.locator('.dm-window')).to_have_count(1 if account=='player1' else 2)
            windows=player.locator('.dm-window')
            windows.nth(0).locator('textarea').fill('私聊草稿一')
            windows.nth(1).locator('textarea').fill('私聊草稿二')
            player.wait_for_timeout(2800)
            assert windows.nth(0).locator('textarea').input_value()=='私聊草稿一'
            assert windows.nth(1).locator('textarea').input_value()=='私聊草稿二'
            windows.nth(1).locator('[type=submit]').click()
            expect(windows.nth(1).locator('.chat-history')).to_contain_text('私聊草稿二')
            assert '私聊草稿二' not in windows.nth(0).locator('.chat-history').inner_text()
            player.screenshot(path=str(PACK/'tests/output/screenshots/workspace-chat.png'),full_page=True)
            checks.append('QQ-style chat lists, scene/team drafts, safe text, Ctrl+Enter and two independent DM windows')
            player.locator('[name=locale]').select_option('en')
            expect(player.locator('.workspace-toolbar')).to_contain_text('Inventory')
            expect(player.locator('.messenger-title').first).to_contain_text('Chat')
            assert player.locator('.dm-window').nth(0).locator('textarea').input_value()=='私聊草稿一'
            result=player.evaluate("async()=>{const m=await import('./i18n.js');return [m.resolve({projectId:'stumpsville',namespace:'ui',key:'chat.send'},'fr'),m.resolve({projectId:'other',namespace:'ui',key:'chat.send'}),m.resolve({projectId:'stumpsville',namespace:'ui',key:'missing',fallback:'safe'})]}")
            assert result[0]['resolvedLocale']=='zh-CN' and result[1]['status']=='error' and result[2]['text']=='safe'
            player.reload();expect(player.locator('.workspace-toolbar')).to_contain_text('Inventory')
            player.set_viewport_size({'width':390,'height':844})
            player.locator('.workspace-tabs [data-args*=chat]').click()
            assert player.evaluate('document.documentElement.scrollWidth<=innerWidth+1 && document.documentElement.scrollHeight<=innerHeight+1')
            player.screenshot(path=str(PACK/'tests/output/screenshots/workspace-mobile.png'),full_page=True)
            checks.append('Chinese/English resources, scope isolation, missing-text fallback, language persistence and mobile chat')
            browser.close()
        data=runtime.data
    with running('workspace-restart',data=data) as (runtime,_):
        p2=Account(runtime.origin,'player2',password,'player2')
        assert p2.request('/package/chat/history',{'channelId':'sv-party'})['items'][0]['text']=='队伍持久消息'
        assert any(m['text']=='场景草稿' for m in p2.request('/package/chat/history',{'channelId':'sv-scene-1'})['items'])
    assert not errors,errors
    checks.append('scoped chat survives restart without changing actual play saves')
    report={'passed':True,'checkedAt':datetime.now().astimezone().isoformat(),'checks':checks,'consoleErrors':errors}
    (PACK/'tests/workspace-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
