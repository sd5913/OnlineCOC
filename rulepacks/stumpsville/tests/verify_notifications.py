"""Timed notifications, owner clues and action results in isolated Edge/host rooms."""
import json
from datetime import datetime
from harness import PACK, running, provision
from playwright.sync_api import sync_playwright, expect


def presenter_checks(browser, origin, checks):
    page = browser.new_page(viewport={'width': 390, 'height': 844})
    page.route(origin + '/notice-fixture', lambda r: r.fulfill(content_type='text/html', body='<html><head><link rel="stylesheet" href="/styles.css"></head><body></body></html>'))
    page.goto(origin + '/notice-fixture')
    page.clock.install(time='2026-11-18T00:00:00Z')
    page.clock.pause_at('2026-11-18T00:00:01Z')
    page.evaluate('''async () => {
        const {effectsUI}=await import('/effects.js'),i18n=await import('/i18n.js');
        await i18n.initLocale(new URL('/',location.href));window.notices=effectsUI;window.opened=[];
        effectsUI.configure(i18n.t,cs=>cs.map(c=>`<li>${c.key}: ${c.before} → ${c.after}</li>`).join(''),()=>false,p=>opened.push(p),e=>e.result?.message||'');
        window.sample={storageScope:'A',accountId:'p',role:'player',character:{instanceId:'c',numbers:{hp:4}},items:{},events:[],locations:[{index:1,clues:[]}],autoSceneTasks:[]};
        notices.observe(sample);
        sample.character.numbers.hp=3;sample.events.push({id:'one',account:'p',status:'completed',title:'伤害',changes:[{key:'hp',before:4,after:3}]});
        notices.observe(sample);
    }''')
    popup = page.locator('.effects-popup')
    expect(popup).to_be_visible()
    page.clock.fast_forward(1000); page.evaluate('notices.observe(sample)')
    page.clock.fast_forward(1999); expect(popup).not_to_have_class('effects-popup fading')
    page.clock.fast_forward(1); expect(popup).to_have_class('effects-popup fading')
    expect(popup).to_be_visible()
    page.clock.fast_forward(280); expect(popup).to_be_hidden()
    page.clock.fast_forward(80); page.evaluate('notices.observe(sample)'); expect(popup).to_be_hidden()
    checks.append('notice stays 3 seconds then fades for 280ms; polling does not extend its lifetime or replay it')

    page.evaluate('''() => {
        sample.events.push({id:'two',account:'p',status:'completed',title:'观察结果',result:{message:'石门已经开启',clues:[{id:'new',location:1,title:'新记号',text:'通往庭院'}]}});
        sample.locations[0].clues=[{id:'new',title:'新记号',text:'通往庭院'}];notices.observe(sample);
        sample.events.push({id:'three',account:'p',status:'approved',title:'KP 回复',reason:'可以通过',result:{message:'可以通过'}});notices.observe(sample);
    }''')
    expect(popup).to_contain_text('石门已经开启'); expect(popup).to_contain_text('发现新线索')
    expect(popup.locator('.effects-clues article')).to_have_count(1)
    expect(popup.locator('.effects-count')).to_have_text('还有 1 条提示')
    page.clock.fast_forward(3000); page.clock.fast_forward(280); page.clock.fast_forward(80)
    expect(popup).to_be_visible(); expect(popup).to_contain_text('KP 回复')
    page.clock.fast_forward(2999); expect(popup).not_to_have_class('effects-popup fading')
    page.clock.fast_forward(1); page.clock.fast_forward(280); page.clock.fast_forward(80)
    expect(popup).to_be_hidden()
    checks.append('same-event result and clue merge, snapshot does not duplicate the clue; queued notice gets a fresh lifetime')

    page.evaluate('''() => {
        sample.locations[0].clues.push({id:'reveal',title:'<img src=x onerror=alert(1)>',text:'KP新揭示的线索'});notices.observe(sample);
    }''')
    expect(popup).to_be_visible(); expect(popup.locator('img')).to_have_count(0)
    expect(popup.locator('.effects-log')).to_be_hidden()
    popup.locator('.effects-clues-link').click()
    assert page.evaluate('opened') == ['clues']
    expect(popup).to_be_hidden(); page.clock.fast_forward(5000); expect(popup).to_be_hidden()
    checks.append('snapshot-only clues show safe text with a clue notebook link; manual close cancels expiry')

    page.evaluate('''() => {
        sample.events.push({id:'waiting',account:'p',status:'pending',title:'请求'});
        sample.events.push({id:'private',account:'other',status:'completed',title:'他人秘密',result:{message:'不可读取'}});
        notices.observe(sample);
    }''')
    expect(popup).to_be_hidden()
    page.evaluate('''() => {
        document.body.classList.add('reduce-motion');
        sample.events.find(e=>e.id==='waiting').status='rejected';notices.observe(sample);
    }''')
    expect(popup).to_be_visible(); expect(popup).to_contain_text('请求')
    page.clock.fast_forward(3000); page.clock.fast_forward(1); expect(popup).to_be_hidden()
    page.evaluate('''() => {
        sample.storageScope='B';notices.observe(sample);sample.events.push({id:'fresh',account:'p',status:'completed',title:'新房间结果'});notices.observe(sample);
    }''')
    expect(popup).to_be_visible()
    page.evaluate('notices.observe(null)'); page.clock.fast_forward(5000); expect(popup).to_be_hidden()
    checks.append('pending and other-owner events stay silent; final rejection notifies, reduced motion and scope/logout cleanup work')
    page.close()


def main():
    checks, errors = [], []
    with running('notifications') as (runtime, password):
        kp, p1, p2 = provision(runtime, password)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            presenter_checks(browser, runtime.origin, checks)

            def login(name):
                page = browser.new_page(viewport={'width': 1440, 'height': 900})
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(runtime.origin + '/sessions/' + name + '/')
                page.locator('[name=loginName]').fill(name); page.locator('[name=password]').fill(password)
                page.get_by_role('button', name='进入冒险', exact=True).click(); page.locator('.identity').wait_for()
                page.goto(runtime.origin + '/sessions/' + name + '/#/play/scene'); page.locator('.available-actions').wait_for()
                return page

            pl, other = login('player1'), login('player2')
            popup = pl.locator('.effects-popup')

            def resolve_scene():
                tasks = kp.request('/package/scene-executor', {})['jobs']
                for task in tasks: kp.action('scene.autorun', {'jobId': task['id']}, task['commandId'])

            p1.action('scene.action', {'action': 'tunnel-ground', 'choice': 'inspect'})
            resolve_scene()
            expect(popup).to_be_visible(timeout=15000)
            expect(popup).to_contain_text('入口地面的压痕')
            expect(popup.locator('.effects-result')).not_to_be_empty()
            expect(popup.locator('.change-list')).to_be_hidden()
            expect(popup.locator('.effects-clues article')).to_have_count(1)
            expect(other.locator('.effects-popup')).to_be_hidden()
            screen = PACK / 'tests/output/screenshots'; screen.mkdir(parents=True, exist_ok=True)
            pl.screenshot(path=str(screen / 'clue-result-notice.png'))
            popup.locator('.effects-clues-link').click()
            expect(pl.locator('#notebook-body').get_by_role('heading', name='入口地面的压痕', exact=True)).to_be_visible()
            expect(popup).to_be_hidden()
            checks.append('real safe observation shows narrative and one new clue without resource changes; only its owner is notified')

            p1.action('scene.action', {'action': 'tunnel-ground', 'choice': 'inspect'})
            resolve_scene()
            expect(popup).to_be_visible(timeout=15000)
            expect(popup.locator('#effects-title')).to_have_text('行动结果')
            expect(popup.locator('.effects-clues article')).to_have_count(0)
            expect(popup.locator('.effects-result')).not_to_be_empty()
            expect(popup).to_be_hidden(timeout=5000)
            pl.wait_for_timeout(2800); expect(popup).to_be_hidden()
            pl.reload(); pl.locator('.available-actions').wait_for(); pl.wait_for_timeout(2800)
            expect(popup).to_be_hidden()
            checks.append('repeat observation still reports its result but not an old clue; automatic expiry and reload do not replay it')

            # Publishing changes the source only. Explicit revelation grants the clue.
            # Use the package's actual clue ID rather than assuming content labels.
            place = next(p for p in kp.state()['allLocations'].values() if p['clues'] and p['index'] != 1)
            kp.action('location.publish', {'index': place['index'], 'clues': [place['clues'][0]['id']]})
            # Discard the ordinary publication-result notice before checking revelation.
            expect(popup).to_be_visible(timeout=10000)
            expect(popup).to_be_hidden(timeout=12000)
            kp.action('location.reveal', {'index': place['index'], 'accounts': ['player1']})
            expect(popup).to_be_visible(timeout=10000)
            expect(popup).to_contain_text(place['clues'][0]['title'])
            expect(popup.locator('.effects-log')).to_be_hidden()
            assert all(c['id'] != place['clues'][0]['id'] for l in p2.state()['locations'] for c in l.get('clues', []))
            popup.locator('.effects-close').click()
            checks.append('KP explicit disclosure creates a clue-only notification; another player receives no clue')

            request = p1.action('request', {'kind': 'free', 'text': '观察无法预设的细节'})
            kp.action('resolve', {'requestId': request['requestId'], 'approve': False, 'reason': '先点亮火把，再检查高处'})
            expect(popup).to_be_visible(timeout=10000)
            expect(popup).to_contain_text('先点亮火把，再检查高处')
            popup.locator('.effects-log').click(); expect(pl.locator('#notebook-body')).to_be_visible()
            checks.append('a manual refusal with no attribute change still shows the keeper reply and opens the log')

            # Dice also use 3 seconds of actual result, followed by the summary.
            p1.action('check', {'attribute': 'dex', 'mode': 'normal'})
            dice = pl.locator('.dice-popup')
            expect(dice).to_be_visible(timeout=10000); expect(dice).to_have_attribute('data-phase', 'result')
            expect(popup).to_be_hidden()
            expect(dice).to_be_hidden(timeout=4500)
            expect(popup).to_be_visible(timeout=3000)
            expect(popup).to_contain_text('敏捷')
            expect(popup).to_be_hidden(timeout=5000)
            checks.append('actual dice result expires before the no-attribute-change action summary appears')
            browser.close()
    assert not errors, errors
    checks.append('no uncaught browser errors')
    record = {'checkedAt': datetime.now().astimezone().isoformat(), 'passed': len(checks), 'checks': checks, 'realSaveChanged': False, 'realModelCalled': False}
    (PACK / 'tests/notifications-results.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
