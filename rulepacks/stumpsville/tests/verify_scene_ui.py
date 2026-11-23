"""Real browser PL -> existing KP page automatic executor -> visible PL results."""
import json
import time
from datetime import datetime
from harness import PACK, running, provision
from playwright.sync_api import sync_playwright, expect


def main():
    errors, checks = [], []
    screenshots = PACK / 'tests/output/screenshots'
    screenshots.mkdir(parents=True, exist_ok=True)
    with running('scene-ui') as (runtime, password):
        kp, p1, _ = provision(runtime, password)
        actor = p1.state()['character']['instanceId']
        kp.action('actor.update', {'id': actor, 'numbers': {'dexMax': 20, 'dex': 20}})
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            def login(account):
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(runtime.origin + '/sessions/' + account + '/')
                page.locator('input[name=loginName]').fill(account)
                page.locator('input[name=password]').fill(password)
                page.get_by_role('button', name='进入冒险', exact=True).click()
                page.locator('.identity').wait_for()
                return page
            gm, player = login('kp'), login('player1')
            gm.goto(runtime.origin + '/sessions/kp/#/gm/console')
            deadline = time.monotonic() + 15
            while not kp.state()['sceneAutomation']['executorOnline'] and time.monotonic() < deadline:
                player.wait_for_timeout(250)
            assert kp.state()['sceneAutomation']['executorOnline']
            player.goto(runtime.origin + '/sessions/player1/#/play/scene')
            log_button=player.locator('[data-action=notebook-toggle]').filter(has_text='行动日志')
            def log_open(show):
                if (log_button.get_attribute('aria-expanded')=='true') != show:
                    log_button.click()
            def action(label, choice=None, manual=False):
                log_open(False)
                player.get_by_role('button', name=label, exact=True).click()
                if choice:
                    player.locator('dialog select[name=scene-choice]').select_option(choice)
                if manual:
                    player.locator('dialog select[name=ruling]').select_option('manual')
                player.get_by_role('button', name='执行行动', exact=True).click()
                player.locator('dialog').wait_for(state='hidden')
                log_open(True)
            action('观察地面')
            expect(player.locator('#action-feedback .log-entry').first.locator('.scene-narrative')).to_contain_text('找到了通往主门的路线', timeout=20000)
            assert not any(r['status'] == 'pending' for r in kp.state()['requests'])
            action('检查奶酪', 'careful')
            expect(player.locator('#action-feedback .log-entry').first.locator('.scene-narrative')).to_contain_text('获得整轮奶酪', timeout=20000)
            expect(player.locator('#action-feedback .log-entry').first.locator('.scene-check')).to_contain_text('敏捷 ≤ 20')
            expect(player.locator('#action-feedback .log-entry').first.locator('.scene-result')).to_contain_text('待处理 → 已解除')
            expect(player.locator('#action-feedback .log-entry').first.locator('.change-list').last).to_contain_text('整轮奶酪')
            player.screenshot(path=str(screenshots/'scene-action-check.png'), full_page=True)
            checks.append('PL preset automatically runs through idle authenticated KP page, displaying real save, narrative, inventory and trap changes')
            log_open(False)
            player.get_by_role('button', name='前往 主门', exact=True).click()
            player.get_by_role('button', name='确认移动', exact=True).click()
            player.locator('dialog').wait_for(state='hidden')
            action('检查把手')
            expect(player.locator('#action-feedback .log-entry').first.locator('.scene-narrative')).to_contain_text('门框上有可以绑绳固定的位置', timeout=20000)
            action('尝试开门', 'brace')
            expect(player.locator('#action-feedback .log-entry').first.locator('.scene-narrative')).to_contain_text('石板门已经打开', timeout=20000)
            assert p1.state()['character']['numbers']['uses6'] == 2
            assert kp.state()['doors']['2-3'] == 'open'
            player.screenshot(path=str(screenshots/'scene-action-result.png'), full_page=True)
            checks.append('inspection plus prepared opening consumes rope, reveals courtyard and updates live scene facts')

            log_open(False)
            player.get_by_role('button', name='前往 庭院', exact=True).click()
            player.get_by_role('button', name='确认移动', exact=True).click()
            player.locator('dialog').wait_for(state='hidden')
            gm.close()
            expect(player.get_by_role('status').filter(has_text='离线待结算')).to_be_visible(timeout=30000)
            action('观察梯子')
            expect(player.locator('#action-feedback')).to_contain_text('等待自动结算')
            assert not any(r['status'] == 'pending' for r in kp.state()['requests'])
            assert not any(p['index'] == 5 and p.get('known') for p in p1.state()['locations'])
            player.screenshot(path=str(screenshots/'scene-action-waiting.png'), full_page=True)
            gm = context.new_page()
            gm.on('pageerror', lambda error: errors.append(str(error)))
            gm.goto(runtime.origin + '/sessions/kp/#/gm/console')
            expect(player.locator('#action-feedback .log-entry').first.locator('.scene-narrative')).to_contain_text('这些地点已加入地图', timeout=20000)
            checks.append('executor offline is shown as automatic waiting, never KP adjudication; reopening a KP page completes queued action')

            action('调查池塘', 'inspect', manual=True)
            expect(player.locator('#action-feedback')).to_contain_text('等待 KP')
            player.wait_for_timeout(3000)
            assert any(r['kind'] == 'scene' and r['status'] == 'pending' for r in kp.state()['requests'])
            gm.goto(runtime.origin + '/sessions/kp/#/gm/rulings')
            request = next(r for r in kp.state()['requests'] if r['kind']=='scene' and r['status']=='pending')
            gm.locator('[data-request-id="'+request['id']+'"] [data-action=console-request]').last.click()
            try:
                gm.locator('#ruling-form').wait_for(timeout=8000)
            except Exception:
                gm.screenshot(path=str(screenshots/'scene-kp-failure.png'), full_page=True)
                (screenshots/'scene-kp-failure.txt').write_text(gm.locator('body').inner_text()+'\nToast: '+gm.locator('#toast').text_content()+'\nErrors: '+repr(errors), encoding='utf-8')
                raise
            gm.locator('#ruling-form [data-ruling-reply] > summary').click()
            gm.locator('#ruling-form [name=reason]').fill('按你选择的预设做法执行')
            gm.screenshot(path=str(screenshots/'scene-kp-console.png'), full_page=True)
            gm.locator('#ruling-form button[type=submit]').click()
            expect(player.locator('#action-feedback .log-entry').first.locator('.scene-narrative')).to_contain_text('金叶鼠像：1 尊', timeout=20000)
            checks.append('explicit manual choice stays in KP queue; approval executes recipe and delivers its actual discoveries')
            player.set_viewport_size({'width': 390, 'height': 844})
            player.evaluate('window.scrollTo(0, 0)')
            assert player.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            player.screenshot(path=str(screenshots/'scene-action-mobile.png'), full_page=True)
            browser.close()
    assert not errors, errors
    report = {'passed': True, 'checkedAt': datetime.now().astimezone().isoformat(), 'checks': checks, 'consoleErrors': errors}
    (PACK/'tests/scene-ui-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
