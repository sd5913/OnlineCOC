"""Single-viewport player workspace and authorized content localization acceptance."""
import json
import re
from datetime import datetime
from harness import PACK, running, provision
from playwright.sync_api import sync_playwright, expect
from localization import localize_projection, localize_result


def main():
    checks, errors = [], []
    screenshots = PACK / 'tests/output/screenshots'
    screenshots.mkdir(parents=True, exist_ok=True)
    source = json.loads((PACK/'locales/zh-CN/content.json').read_text(encoding='utf-8'))
    target = json.loads((PACK/'locales/en/content.json').read_text(encoding='utf-8'))
    definitions = json.loads((PACK/'config/scene-actions.json').read_text(encoding='utf-8'))['actions']
    assert source.keys() == target.keys()
    for action in definitions:
        for row in [action, *action['choices']]:
            for key in ('label','hint','process'):
                if key in row:
                    assert row[key] in source.values(), (action['id'], key)
    checks.append('all 18 preset labels, hints, choices and processes have restricted bilingual entries')
    with running('screen-06') as (runtime,password):
        kp,p1,p2=provision(runtime,password)
        initial=p1.request('/package/state?locale=en')
        assert initial['locations'][0]['name']=='Entrance Tunnel'
        assert 'northKnown' not in json.dumps(initial) and 'Aging Cave' not in json.dumps(initial)
        for path in ['/locales/en/content.json','/locales/zh-CN/content.json','/locales/meta/catalog/content.json']:
            assert p1.http.get(p1.prefix+path).status_code==404
        sample={'note':'HP 玩家手记','character':{'name':'DEX'},'events':[{'title':'属性检定','text':'HP 原文','mode':'kp','reason':'HP 主持原文','result':{'message':'扣除护甲后受到 3 点伤害，HP 剩余 0。'}}]}
        en=localize_projection(sample,'en')
        assert en['note']==sample['note'] and en['character']==sample['character']
        assert en['events'][0]['text']=='HP 原文' and en['events'][0]['reason']=='HP 主持原文'
        assert en['events'][0]['result']['message']=='After armour, took 3 damage; 0 HP remaining.'
        assert sample['events'][0]['result']['message'].startswith('扣除')
        assert localize_result({'message':'扣除护甲后受到 3 点伤害，HP 剩余 0。'},'zh-CN')['message']=='扣除护甲后受到 3 点伤害，生命 剩余 0。'
        custom={'locations':[{'name':'HP 小屋','description':'DEX 主持自定义地点'}]}
        assert localize_projection(custom,'zh-CN')['locations']==custom['locations']
        checks.append('locale follows authorized projection; secret catalogs return 404; user text and saved results remain unchanged')
        for i in range(2,11): kp.action('location.publish',{'index':i})
        kp.action('door',{'edge':'2-3','status':'open'})
        for i in (2,3,6):p1.action('request',{'kind':'travel','destination':i})
        actor=p1.state()['character']['instanceId']
        kp.action('actor.update',{'id':actor,'numbers':{'dexMax':20,'dex':20}})
        for _ in range(18):p1.action('check',{'attribute':'dex','mode':'normal'})
        for i in range(12):p2.action('chat',{'operation':'chat.message.send','input':{'channelId':'general','text':f'联机聊天记录 {i+1}'}})
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            context=browser.new_context(viewport={'width':1440,'height':900})
            def login(name):
                page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(runtime.origin+'/sessions/'+name+'/')
                page.locator('[name=loginName]').fill(name);page.locator('[name=password]').fill(password)
                page.get_by_role('button',name='进入冒险',exact=True).click();page.locator('.identity').wait_for()
                return page
            gm=login('kp');page=login('player1')
            page.goto(runtime.origin+'/sessions/player1/#/play/scene')
            page.locator('.chat-pinned .messenger').wait_for()
            assert not page.locator('.sidebar,.desktop-dock,.pane-records,[data-action=open-chat]').count()
            for key in ('check','request','review'):expect(page.locator('.generic-actions [data-action='+key+']')).to_have_count(1)
            expect(page.locator('.top-nav')).to_contain_text('入场大厅')
            page.locator('#chat-form textarea').fill('保留的聊天草稿 HP DEX')
            page.locator('[data-action=notebook-toggle][data-args*=records]').click()
            page.get_by_role('button',name='呼唤屋内',exact=True).click()
            page.locator('[name=scene-choice]').select_option('rescue')
            page.get_by_role('button',name='执行行动',exact=True).click()
            page.locator('dialog').wait_for(state='hidden')
            expect(page.locator('.log-entry').first).to_contain_text('两名村民沿梯子撤到庭院',timeout=25000)
            expect(page.locator('.log-entry').first).to_contain_text('敏捷 ≤ 20')
            expect(page.locator('.log-entry').first).to_contain_text('被困 → 已脱困')
            assert page.locator('#chat-form textarea').input_value()=='保留的聊天草稿 HP DEX'
            checks.append('map/actions, notebook roll narrative and state changes, and chat coexist; action refresh preserves draft')
            page.locator('[data-action=notebook-toggle][data-args*=records]').click()
            for width,height in [(1920,1080),(1440,900),(1366,768)]:
                page.set_viewport_size({'width':width,'height':height})
                assert page.evaluate('document.documentElement.scrollHeight<=innerHeight+1 && document.documentElement.scrollWidth<=innerWidth+1')
                for selector in ['.character-column','.scene-column','.communication-column']:
                    box=page.locator(selector).bounding_box()
                    assert box and box['y']+box['height']<=height+1,(selector,box)
                page.screenshot(path=str(screenshots/f'screen-{width}.png'),full_page=True)
            page.locator('[data-action=notebook-toggle][data-args*=records]').click()
            log=page.locator('#action-feedback')
            assert log.evaluate('(n)=>n.scrollHeight>n.clientHeight')
            log.evaluate('(n)=>n.scrollTop=150')
            page.wait_for_timeout(2800)
            assert log.evaluate('(n)=>n.scrollTop')>=140
            assert page.evaluate('scrollY')==0
            page.locator('[name=log-filter]').select_option('checks')
            expect(page.locator('.log-entry').first).to_contain_text('敏捷')
            page.locator('.log-entry').first.locator('summary').click()
            page.wait_for_timeout(2800)
            assert not page.locator('.log-entry').first.evaluate('(n)=>n.open')
            page.locator('[name=log-filter]').select_option('pending')
            expect(page.locator('#action-feedback')).to_contain_text('还没有符合条件')
            page.locator('[name=log-filter]').select_option('all')
            checks.append('1920/1440/1366 viewports fit without page scrolling; log scroll, filters and expansion survive polling')
            page.locator('[name=locale]').select_option('en')
            expect(page.locator('.scene-heading')).to_contain_text('Webbed House')
            expect(page.locator('.available-actions')).to_contain_text('Call into the house')
            page.locator('.log-entry').first.locator('summary').click()
            expect(page.locator('.log-entry').first).to_contain_text('Both villagers descend')
            assert not re.search('[\u4e00-\u9fff]',page.locator('.scene-column').inner_text().replace('木栗','').replace('豆叶',''))
            assert not re.search('[\u4e00-\u9fff]',page.locator('.log-entry').first.inner_text())
            assert '[Text unavailable]' not in page.locator('body').inner_text()
            assert page.locator('#chat-form textarea').input_value()=='保留的聊天草稿 HP DEX'
            page.get_by_role('button',name='Call into the house',exact=True).click()
            assert not re.search('[\u4e00-\u9fff]',page.locator('dialog').inner_text())
            page.keyboard.press('Escape')
            page.screenshot(path=str(screenshots/'screen-english.png'),full_page=True)
            checks.append('language switch updates scene, preset dialog, dice and results; chat draft keeps original text')
            page.locator('[name=locale]').select_option('zh-CN')
            page.locator('[data-action=notebook-toggle][data-args*=records]').click()
            page.set_viewport_size({'width':390,'height':844})
            for column in ['character','scene','communication']:
                page.locator(f'.workspace-tabs [data-action=workspace-column][data-args*=\"{column}\"]').click()
                assert page.evaluate('document.documentElement.scrollHeight<=innerHeight+1 && document.documentElement.scrollWidth<=innerWidth+1')
                expect(page.locator('#scene-desktop>.workspace-column:visible')).to_have_count(1)
                page.wait_for_timeout(200)
                page.screenshot(path=str(screenshots/f'screen-mobile-{column}.png'),full_page=True)
            page.locator('[data-chat=group][data-channel=direct]').click()
            assert not page.locator('.messenger #chat-form').count()
            expect(page.locator('.messenger')).to_contain_text('暂无会话')
            page.locator('[data-chat=group][data-channel=room]').click()
            assert page.locator('#chat-form textarea').input_value()=='保留的聊天草稿 HP DEX'
            checks.append('390px character/scene/conversation tabs remain in one viewport; empty private list never shows a global composer')
            browser.close()
    assert not errors,errors
    report={'passed':True,'checkedAt':datetime.now().astimezone().isoformat(),'checks':checks,'consoleErrors':errors}
    (PACK/'tests/screen-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
