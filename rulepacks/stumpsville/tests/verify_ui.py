"""Real Chromium interaction and screenshot checks for the local package."""
import json
from datetime import datetime
from harness import PACK, running, provision
from playwright.sync_api import sync_playwright, expect


def main():
    errors, checks = [], []
    screenshots = PACK / 'tests/output/screenshots'
    screenshots.mkdir(parents=True, exist_ok=True)
    with running('browser') as (runtime, password):
        kp, p1, p2 = provision(runtime, password)
        kp.action('location.publish', {'index': 2})
        kp.action('location.publish', {'index': 3})
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            context = browser.new_context(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
            pages = {}
            for account in ('kp', 'player1', 'player2'):
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(runtime.origin + '/sessions/' + account + '/')
                page.locator('input[name=loginName]').fill(account)
                page.locator('input[name=password]').fill(password)
                page.get_by_role('button', name='进入冒险', exact=True).click()
                page.locator('.identity').wait_for()
                assert account in page.locator('.identity').inner_text()
                pages[account] = page
            checks.append('three same-browser session slots retain separate authenticated identities')
            routes = {'player1': ['lobby', 'character/new', 'ready', 'play/scene', 'play/character', 'play/journal', 'play/records', 'recap'],
                      'kp': ['gm/console', 'gm/overview', 'gm/locations', 'gm/encounters', 'gm/library', 'gm/session']}
            for account, paths in routes.items():
                page = pages[account]
                for route in paths:
                    page.goto(runtime.origin + '/sessions/' + account + '/#/' + route)
                    page.locator('.rulings-grid' if route=='gm/encounters' else 'h1').wait_for()
                    page.wait_for_timeout(200)
                    assert page.locator('#main').inner_text()
                    assert not page.get_by_text('页面不存在', exact=True).count()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), route
                    if route in ('play/character', 'gm/console', 'gm/locations'):
                        page.screenshot(path=str(screenshots / (route.replace('/', '-') + '.png')), full_page=True)
            checks.append('canonical pages and legacy routes render without JavaScript errors or desktop overflow')
            keeper=pages['kp'];keeper.goto(runtime.origin+'/sessions/kp/#/gm/rulings')
            keeper.get_by_role('button',name='收起顶栏',exact=True).click()
            keeper.locator('a[href="#/gm/map"]').click();keeper.reload()
            keeper.get_by_role('button',name='展开顶栏',exact=True).wait_for()
            assert keeper.locator('.topbar').bounding_box()['height']==30
            assert pages['player1'].get_by_role('button',name='收起顶栏',exact=True).is_visible()
            keeper.get_by_role('button',name='展开顶栏',exact=True).click()
            checks.append('global top menu folding persists across navigation/reload and stays isolated by login identity')
            player = pages['player1']
            player.goto(runtime.origin + '/sessions/player1/#/play/character')
            player.locator('.resident-status').wait_for()
            if player.locator('#notebook-body').is_visible():
                player.locator('[data-action=notebook-toggle][aria-expanded=true]').click()
            player.get_by_role('button', name='敏捷', exact=True).click()
            player.locator('dialog[open]').wait_for()
            player.get_by_role('button', name='投骰', exact=True).click()
            player.locator('dialog').wait_for(state='hidden')
            assert p1.state()['character']['numbers']['checks'] == 1
            player.locator('[data-action=notebook-toggle][data-args*=records]').click()
            player.locator('#action-feedback .log-entry').first.locator('.dice-result').wait_for()
            assert '检定' in player.locator('#action-feedback').inner_text()
            player.locator('[data-action=notebook-toggle][data-args*=records]').click()
            player.get_by_role('button', name='火把', exact=False).first.click()
            player.get_by_role('button', name='移动物品', exact=True).click()
            player.locator('dialog input[name=value]').fill('8')
            player.get_by_role('button', name='移动', exact=True).click()
            player.locator('dialog').wait_for(state='hidden')
            assert p1.state()['character']['numbers']['item8'] == 2
            player.locator('[data-action=notebook-toggle][data-args*=records]').click()
            assert '槽位 8' in player.locator('#action-feedback').inner_text()
            checks.append('browser check and item move commit through real host rules')
            request = p2.action('request', {'kind': 'free', 'text': 'UI拒绝裁定验收'})
            gm = pages['kp']
            gm.goto(runtime.origin + '/sessions/kp/#/gm/encounters')
            gm.get_by_role('button', name='查看并裁决', exact=True).first.click()
            gm.locator('#ruling-form select[name=approve]').select_option('no')
            gm.locator('#ruling-form textarea').fill('UI验证：这个行动暂不可行')
            gm.get_by_role('button', name='保存裁决并通知玩家', exact=True).click()
            gm.locator('#ruling-form').wait_for(state='hidden')
            assert next(x for x in kp.state()['requests'] if x['id'] == request['requestId'])['status'] == 'rejected'
            recipient = pages['player2']
            recipient.goto(runtime.origin + '/sessions/player2/#/play/scene')
            recipient.locator('[data-action=notebook-toggle][data-args*=records]').click()
            recipient.get_by_text('裁决说明：UI验证：这个行动暂不可行', exact=True).wait_for()
            checks.append('unified KP console sends a visible rejection and explanation to the requesting player')
            player.goto(runtime.origin + '/sessions/player1/#/play/scene')
            if player.locator('#notebook-body').is_visible():
                player.locator('[data-action=notebook-toggle][aria-expanded=true]').click()
            # A navigation exit need not disclose the destination's name yet.
            player.locator('[data-action=travel][data-args=\'{"destination":2}\']').click()
            player.get_by_role('button', name='确认移动', exact=True).click()
            player.locator('dialog').wait_for(state='hidden')
            assert p1.state()['character']['numbers']['location'] == 2
            player.get_by_role('button', name='请求 KP 裁决', exact=True).click()
            player.locator('dialog textarea[name=text]').fill('请裁决刚才主门处的事件')
            player.get_by_role('button', name='提交申请', exact=True).click()
            player.locator('dialog').wait_for(state='hidden')
            assert any(x['kind']=='review' and x['status']=='pending' for x in kp.state()['requests'])
            player.locator('[data-action=notebook-toggle][data-args*=records]').click()
            expect(player.locator('#action-feedback')).to_contain_text('等待 KP')
            player.locator('[data-action=notebook-toggle][data-args*=records]').click()
            gm.goto(runtime.origin + '/sessions/kp/#/gm/console')
            gm.get_by_role('button', name='关闭自动裁决', exact=True).click()
            gm.get_by_role('button', name='保存设置', exact=True).click()
            gm.locator('dialog').wait_for(state='hidden')
            assert p1.state()['automation']['enabled'] is False
            gm.screenshot(path=str(screenshots / 'automation-settings.png'), full_page=True)
            gm.get_by_role('button', name='开启自动裁决', exact=True).click()
            gm.get_by_role('button', name='保存设置', exact=True).click()
            gm.locator('dialog').wait_for(state='hidden')
            checks.append('automatic move, explicit event request and KP automation toggle work in browser')
            # A manual die roll remains pending until KP approves. The live scene updates
            # without navigating away, including while a note draft blocks a full rerender.
            player.get_by_role('button', name='属性检定', exact=True).click()
            player.locator('dialog select[name=ruling]').select_option('manual')
            player.get_by_role('button', name='投骰', exact=True).click()
            player.locator('dialog').wait_for(state='hidden')
            count = p1.state()['character']['numbers']['checks']
            manual = next(r for r in reversed(kp.state()['requests']) if r['kind']=='check' and r['status']=='pending')
            player.get_by_role('button', name='线索手记', exact=True).click()
            player.locator('#note-form textarea').fill('未保存的手记草稿')
            kp.action('resolve', {'requestId':manual['id'],'approve':True,'reason':'继续你的调查'})
            page_badge=player.locator('[data-log-badge]')
            player.wait_for_timeout(3000)
            assert int(page_badge.inner_text())>0
            assert p1.state()['character']['numbers']['checks'] == count+1
            assert player.locator('#note-form textarea').input_value() == '未保存的手记草稿'
            player.get_by_role('button', name='保存手记', exact=True).click()
            expect(player.locator('#note-form textarea')).to_have_text('未保存的手记草稿')
            player.locator('[data-action=notebook-toggle][data-args*=records]').click()
            player.get_by_text('裁决说明：继续你的调查', exact=True).wait_for(timeout=15000)
            if player.locator('#notebook-body').is_visible():
                player.locator('[data-action=notebook-toggle][aria-expanded=true]').click()
            checks.append('manual roll process and KP result update in-place without discarding unsaved notes')
            player.goto(runtime.origin + '/sessions/player1/#/play/records')
            player.locator('#chat-form textarea').fill('UI联机消息')
            player.get_by_role('button', name='发送', exact=True).click()
            player.get_by_text('UI联机消息', exact=True).wait_for()
            kp.action('chat', {'operation':'chat.message.send','input':{'channelId':'general','text':'主持消息自动到达'}})
            player.get_by_text('主持消息自动到达', exact=True).wait_for(timeout=15000)
            assert '/#/play/scene' in player.url
            gm.goto(runtime.origin + '/sessions/kp/#/gm/rulings')
            gm.locator('#chat-history').get_by_text('UI联机消息', exact=True).wait_for()
            gm.screenshot(path=str(screenshots / 'gm-console-messages.png'), full_page=True)
            checks.append('resident player chat and pinned KP rulings chat receive live messages')
            player.locator('[data-action=notebook-toggle][data-args*=records]').click()
            player.reload()
            assert player.locator('#notebook-body').is_hidden()
            player.locator('[data-action=notebook-toggle][data-args*=records]').click()
            player.get_by_text('主持消息自动到达', exact=True).wait_for()
            assert player.locator('.resident-status,.resident-inventory').count()==2
            player.screenshot(path=str(screenshots / 'scene-floating-panels.png'), full_page=True)
            checks.append('notebook collapses and persists after reload while character and inventory remain resident')
            player.set_viewport_size({'width': 390, 'height': 844})
            player.goto(runtime.origin + '/sessions/player1/#/play/character')
            player.locator('.inventory').wait_for()
            assert player.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            player.screenshot(path=str(screenshots / 'mobile-character.png'), full_page=True)
            checks.append('390px player layout remains within viewport')
            independent = []
            for account in ('player1','player2'):
                tab=context.new_page()
                tab.on('pageerror', lambda error: errors.append(str(error)))
                tab.goto(runtime.origin + '/')
                tab.locator('input[name=loginName]').fill(account)
                tab.locator('input[name=password]').fill(password)
                tab.get_by_role('button',name='进入冒险',exact=True).click()
                tab.locator('.identity').wait_for()
                assert '/sessions/tab-' in tab.url
                independent.append(tab)
            assert independent[0].url != independent[1].url
            independent[0].reload()
            independent[0].locator('.identity').wait_for()
            assert 'player1' in independent[0].locator('.identity').inner_text()
            independent[0].get_by_role('button',name='退出',exact=True).click()
            independent[0].locator('input[name=loginName]').wait_for()
            independent[1].reload()
            independent[1].locator('.identity').wait_for()
            assert 'player2' in independent[1].locator('.identity').inner_text()
            pages['kp'].reload()
            pages['kp'].locator('.identity').wait_for()
            assert 'kp' in pages['kp'].locator('.identity').inner_text()
            checks.append('two root pages create independent login slots; reload and one-page logout leave other accounts signed in')
            browser.close()
    assert not errors, errors
    result = {'passed': True, 'checkedAt': datetime.now().astimezone().isoformat(), 'browser': 'Microsoft Edge / Playwright', 'checks': checks, 'consoleErrors': errors}
    (PACK / 'tests/ui-results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
