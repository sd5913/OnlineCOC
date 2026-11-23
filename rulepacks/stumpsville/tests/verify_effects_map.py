"""Owner effects and observed map routes through an isolated host and real browser."""
import json
from datetime import datetime
from harness import PACK, running, provision
from playwright.sync_api import sync_playwright, expect
from knowledge_client import locations


def presenter_lifecycle(browser, origin):
    page = browser.new_page()
    page.route(origin + '/effects-fixture', lambda r: r.fulfill(content_type='text/html', body='<html><body></body></html>'))
    page.goto(origin + '/effects-fixture')
    page.evaluate('''async () => {
        const {effectsUI}=await import('/effects.js');window.presenter=effectsUI;
        effectsUI.configure(k=>k,cs=>cs.map(c=>`<li>${c.key}: ${c.before} → ${c.after}</li>`).join(''),()=>false,()=>{});
        window.sample={storageScope:'A',accountId:'p',role:'player',character:{instanceId:'c',numbers:{hp:4}},items:{},events:[],autoSceneTasks:[{status:'queued'}]};
        effectsUI.observe(sample);
        sample.character.numbers.hp=3;effectsUI.observe(sample);
    }''')
    expect(page.locator('.effects-popup')).to_be_visible()
    expect(page.locator('.effects-popup')).to_contain_text('hp: 4 → 3')
    page.evaluate("sample.storageScope='B';presenter.observe(sample)")
    expect(page.locator('.effects-popup')).to_be_hidden()
    page.evaluate('sample.character.numbers.hp=2;presenter.observe(sample)')
    expect(page.locator('.effects-popup')).to_be_visible()
    page.evaluate('presenter.observe(null)')
    expect(page.locator('.effects-popup')).to_be_hidden()
    page.close()


def main():
    checks, errors = [], []
    # Old observations remain unknown and reverse-only exits retain placeholders.
    old = {'facetId': 'scene', 'data': {'index': 8, 'exits': [3, 7, 9]}, 'ref': {}, 'observedAt': 1}
    new = {**old, 'data': {**old['data'], 'doors': {'3': 'open', '7': 'locked'}}, 'observedAt': 2}
    assert next(x for x in locations([old]) if x['index'] == 8)['doors']['3'] == 'unknown'
    projected = locations([new, old])
    assert next(x for x in projected if x['index'] == 8)['doors']['7'] == 'locked'
    assert next(x for x in projected if x['index'] == 3)['exits'] == []
    checks.append('old snapshots stay unknown; latest observation wins without revealing placeholder lore')
    with running('effects-map') as (runtime, password):
        kp, p1, p2 = provision(runtime, password)
        actor = p1.state()['character']['instanceId']
        kp.action('actor.update', {'id': actor, 'numbers': {'armor': 0, 'hp': 6, 'maxHp': 6, 'str': 20, 'strMax': 20}})
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            def login(name):
                page = browser.new_page(viewport={'width': 1440, 'height': 900})
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(runtime.origin + '/sessions/' + name + '/')
                page.locator('[name=loginName]').fill(name)
                page.locator('[name=password]').fill(password)
                page.get_by_role('button', name='进入冒险', exact=True).click()
                page.locator('.identity').wait_for()
                if name != 'kp':
                    page.goto(runtime.origin + '/sessions/' + name + '/#/play/scene')
                    page.locator('.available-actions').wait_for()
                return page
            pl, other = login('player1'), login('player2')
            popup, other_popup = pl.locator('.effects-popup'), other.locator('.effects-popup')
            expect(popup).to_be_hidden()
            expect(pl.locator('[data-route="1-2"]')).to_have_attribute('data-status', 'open')
            # Pure graph cases use the production module and the actual node sizes.
            routes = pl.evaluate('''async rows => {
                const m=await import('./map.js');
                return m.mapRoutes(rows).map(e=>({...e,path:m.mapRoutePath(e)}));
            }''', projected)
            assert [x['key'] for x in routes] == ['3-8', '7-8', '8-9'], routes
            assert routes[0]['path'] == 'M270 180 V248 H550 V196 H640'
            assert routes[1]['status'] == 'locked' and routes[2]['status'] == 'unknown'
            checks.append('real initial PL route is open; reverse-only routes render once and 03–08 avoids the expanded room 07 card')

            def acknowledge(page=pl):
                page.locator('.effects-popup .effects-ok').click()
                expect(page.locator('.effects-popup')).to_be_hidden()

            kp.action('grant', {'actor': actor, 'item': 2, 'slot': 8, 'uses': 3})
            expect(popup).to_be_visible(timeout=10000)
            expect(popup).to_contain_text('火把 · 用量 3')
            expect(popup).to_contain_text('空')
            expect(other_popup).to_be_hidden()
            screen = PACK / 'tests/output/screenshots'
            screen.mkdir(parents=True, exist_ok=True)
            pl.screenshot(path=str(screen / 'persistent-effects.png'))
            acknowledge()
            pl.wait_for_timeout(3000)
            expect(popup).to_be_hidden()
            pl.reload(); pl.locator('.available-actions').wait_for()
            pl.wait_for_timeout(2800)
            expect(popup).to_be_hidden()
            checks.append('KP grants notify only the affected player, once; initial history and reload do not replay')

            p1.action('inventory', {'operation': 'use', 'slot': 8, 'value': 0})
            expect(popup).to_be_visible(timeout=10000)
            expect(popup).to_contain_text('火把 · 用量 2')
            acknowledge()
            transfer = p1.action('request', {'kind': 'transfer', 'slot': 8, 'targetAccount': 'player2', 'destination': 8, 'text': '交接火把'})
            pl.wait_for_timeout(2800); expect(popup).to_be_hidden()
            kp.action('resolve', {'requestId': transfer['requestId'], 'approve': True, 'reason': '同场景交接'})
            expect(popup).to_be_visible(timeout=10000); expect(other_popup).to_be_visible(timeout=10000)
            expect(popup.locator('b')).to_have_text('→ 空')
            expect(other_popup).to_contain_text('火把 · 用量 2')
            acknowledge(); acknowledge(other)
            checks.append('consumption shows remaining uses; a pending transfer waits, then both owners see their own loss/gain')

            p2.action('inventory', {'operation': 'light', 'slot': 8, 'value': 0})
            expect(other_popup).to_be_visible(timeout=10000); acknowledge(other)
            kp.action('world', {'operation': 'round'})
            expect(other_popup).to_be_visible(timeout=10000)
            expect(other_popup).to_contain_text('槽位 8 燃烧进度')
            acknowledge(other)
            expect(popup).to_be_visible(timeout=10000)
            expect(popup).to_contain_text('探索进度已更新'); acknowledge()
            checks.append('light-source changes and persistent burn progress notify their owner on exploration rounds')

            pl.evaluate("localStorage.setItem('sv.desktop.dice.enabled','0')")
            kp.action('damage', {'actor': actor, 'amount': 2, 'attribute': 'str'})
            expect(popup).to_be_visible(timeout=10000)
            expect(popup).to_contain_text('生命')
            expect(popup.locator('del')).to_have_text('6')
            expect(popup.locator('b')).to_have_text('→ 4')
            expect(pl.locator('.dice-popup')).to_be_hidden()
            acknowledge()
            kp.command('entity.update', {'id': actor, 'numbers': {'pips': 99}})
            expect(popup).to_be_visible(timeout=10000)
            expect(popup).to_contain_text('角色状态已更新')
            expect(popup).to_contain_text('钱币')
            expect(popup.locator('.effects-log')).to_be_hidden()
            acknowledge()
            checks.append('damage still notifies with dice disabled; direct host changes use the authorized snapshot without inventing a cause or log')

            kp.action('actor.update', {'id': actor, 'numbers': {'pips': 98}})
            kp.action('actor.update', {'id': actor, 'numbers': {'pips': 99}})
            expect(popup).to_be_visible(timeout=10000)
            expect(popup.locator('b')).to_have_text('→ 98'); acknowledge()
            expect(popup).to_be_visible(timeout=10000)
            expect(popup.locator('b')).to_have_text('→ 99'); acknowledge()
            pl.wait_for_timeout(2800); expect(popup).to_be_hidden()
            pl.locator('select[name=locale]').select_option('en')
            pl.wait_for_timeout(2800); expect(popup).to_be_hidden()
            pl.locator('select[name=locale]').select_option('zh-CN')
            pl.wait_for_timeout(2800); expect(popup).to_be_hidden()
            checks.append('opposite committed changes retain both queued notifications; polling and language changes do not add false inventory effects')

            pl.evaluate("localStorage.setItem('sv.desktop.dice.enabled','1')")
            kp.action('damage', {'actor': actor, 'amount': 5, 'attribute': 'str'})
            dice = pl.locator('.dice-popup')
            expect(dice).to_be_visible(timeout=10000)
            expect(popup).to_be_hidden()
            dice.locator('.dice-close').click()
            expect(popup).to_be_visible(timeout=10000)
            expect(popup).to_contain_text('生命'); expect(popup).to_contain_text('力量')
            pl.set_viewport_size({'width': 390, 'height': 844})
            bounds = popup.bounding_box()
            assert 0 <= bounds['x'] and bounds['x'] + bounds['width'] <= 390, bounds
            pl.screenshot(path=str(screen / 'persistent-effects-mobile.png'))
            popup.locator('.effects-log').click()
            expect(pl.locator('#notebook-body')).to_be_visible()
            pl.wait_for_timeout(3000); expect(popup).to_be_hidden()
            checks.append('committed injury roll precedes the effect summary; small screen fits and log link opens the notebook without a duplicate')

            # Per-player scene observations do not follow secret KP door changes.
            kp.command('entity.update', {'id': actor, 'numbers': {'location': 8}})
            state = p1.state()
            room = next(l for l in state['locations'] if l['index'] == 8)
            observed = room['doors']['3']
            changed = 'locked' if observed != 'locked' else 'open'
            kp.action('door', {'edge': '3-8', 'status': changed})
            assert next(l for l in p1.state()['locations'] if l['index'] == 8)['doors']['3'] == observed
            assert 'doors' not in p2.state()
            kp.command('entity.update', {'id': actor, 'numbers': {'location': 1}})
            kp.command('entity.update', {'id': actor, 'numbers': {'location': 8}})
            assert next(l for l in p1.state()['locations'] if l['index'] == 8)['doors']['3'] == changed
            expect(pl.locator('[data-route="3-8"]')).to_have_attribute('data-status', changed, timeout=10000)
            checks.append('PL sees observed door state, not hidden KP updates; revisiting refreshes the observation and reverse route')
            gm = login('kp'); gm.goto(runtime.origin + '/sessions/kp/#/gm/map')
            expect(gm.locator('[data-route="3-8"]')).to_have_attribute('data-status', changed)
            paths = gm.locator('.node-map path[data-route]').evaluate_all('(es)=>es.map(e=>e.dataset.route)')
            assert set(paths) == set(kp.state()['doors']) and len(paths) == len(set(paths)), paths
            gm.screenshot(path=str(screen / 'map-routes.png'))
            checks.append('KP full map renders all configured routes with current door truth')
            presenter_lifecycle(browser, runtime.origin)
            checks.append('a queued preset does not hide direct host effects; room changes and logout clear visible notifications')
            browser.close()
    assert not errors, errors
    checks.append('no uncaught browser errors')
    result = {'checkedAt': datetime.now().astimezone().isoformat(), 'passed': len(checks), 'checks': checks, 'realSaveChanged': False}
    (PACK / 'tests/effects-map-results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
