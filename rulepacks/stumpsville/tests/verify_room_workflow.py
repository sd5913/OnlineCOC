"""One-click room opening and executable rulings, using isolated host + Edge."""
from datetime import datetime
import json
import secrets
from unittest.mock import patch
from harness import PACK, running, Account
from package import Package
from playwright.sync_api import sync_playwright, expect


def main():
    output = PACK/'tests/output'/('room-workflow-'+secrets.token_hex(4))
    output.mkdir(parents=True)
    checks, errors = [], []
    # Simulate setup completing before the package installation, then use the UI
    # to recover the real installation and opening in one durable operation.
    skipped = patch.object(Package, 'initialize', return_value={'message': 'deferred installation'})
    skipped.start()
    try:
        with running('room-workflow', data=output/'game', no_browser=True) as (runtime, password):
            skipped.stop()
            kp, p1, p2 = [Account(runtime.origin, name, password, name) for name in ('kp','player1','player2')]
            assert not kp.state()['initialized']
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel='msedge', headless=True)
                page = browser.new_page(viewport={'width':1440,'height':1000})
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(runtime.origin+'/sessions/kp/')
                page.locator('[name=loginName]').fill('kp')
                page.locator('[name=password]').fill(password)
                page.get_by_role('button',name='进入冒险',exact=True).click()
                expect(page.locator('#room-overview')).to_be_visible()
                page.get_by_role('button',name='一键开场',exact=True).click()
                expect(page.get_by_role('button',name='已开场',exact=True)).to_be_disabled(timeout=30000)
                state=kp.state()
                assert state['initialized'] and state['session']['numbers']['phase']==1 and state['knowledge']['status']=='ready'
                checks.append('uninstalled room opens and initializes through one room-page action')
                entity_count=len(kp.request('/api/v1/view')['entities'])
                first=kp.action('session.start',action_id='opening-repeat-01')
                assert kp.action('session.start',action_id='opening-repeat-01')==first
                kp.action('session.start')
                assert len(kp.request('/api/v1/view')['entities'])==entity_count
                assert 'failure' in p1.action('session.start',allow_error=True)
                checks.append('opening is repeat-safe and KP-only')
                for account,preset in [(p1,'mul'),(p2,'dou')]:
                    account.action('draft',{'preset':preset,'name':account.name})
                    kp.action('approve',{'account':account.name})
                p1.action('ready',{'ready':True})
                kp.action('world',{'operation':'round','round':0})
                kp.action('room',{'status':'paused'})
                page.reload()
                def lose_opening_reply(route):
                    if route.request.post_data_json.get('operation')=='session.start':
                        route.fetch();route.abort('failed')
                    else:route.continue_()
                page.route('**/package/action*',lose_opening_reply)
                page.get_by_role('button',name='恢复开场',exact=True).click()
                expect(page.locator('#toast')).to_be_visible()
                page.wait_for_function("Object.keys(localStorage).some(k=>k.startsWith('stumpsville.pending.')&&localStorage.getItem(k).includes('session.start'))")
                page.wait_for_timeout(1000)
                page.unroute('**/package/action*',lose_opening_reply)
                page.reload()
                page.locator('[data-action=recover]').click()
                expect(page.locator('[data-action=recover]')).to_have_count(0)
                assert kp.state()['session']['numbers']['round']==1
                assert not p2.state()['character']['numbers']['ready']
                checks.append('resume preserves round and player readiness; does not auto-approve or ready players')
                checks.append('lost opening response recovers the original persisted command without repeating effects')
                page.reload();expect(page.locator('#room-overview')).to_contain_text('1 / 2')
                page.screenshot(path=str(output/'room-overview.png'),full_page=True)
                page.goto(runtime.origin+'/sessions/kp/#/gm/console')
                expect(page.locator('[data-action=start]')).to_have_count(0)
                page.goto(runtime.origin+'/sessions/kp/#/gm/session')
                expect(page.locator('[data-action=backup]')).to_have_count(0)
                checks.append('global controls and statistics are centralized in room page')
                request=p1.action('request',{'kind':'free','text':'请给予一件针剑','manual':True})
                bad=kp.action('resolve',{'requestId':request['requestId'],'approve':True,'resolution':{'operation':'entity.archive','input':{}}},allow_error=True)
                assert 'failure' in bad
                assert next(r for r in kp.state()['requests'] if r['id']==request['requestId'])['status']=='pending'
                page.goto(runtime.origin+'/sessions/kp/#/gm/rulings')
                page.locator('[data-request-id="'+request['requestId']+'"] [data-action=console-request]').last.click()
                form=page.locator('#ruling-form')
                expect(form).to_be_visible()
                assert not form.locator('details').evaluate('(e)=>e.open')
                form.locator('[name=resolution]').select_option('grant')
                form.locator('[name=resolution-slot]').fill('7')
                form.locator('summary').click();form.locator('[name=reason]').fill('获准取得针剑。')
                page.wait_for_timeout(3000)
                expect(form.locator('[name=reason]')).to_have_value('获准取得针剑。')
                page.screenshot(path=str(output/'ruling-execution.png'),full_page=True)
                form.locator('[data-ruling-submit]').click()
                expect(form).to_have_count(0)
                own=p1.state();assert own['character']['numbers']['item7']==1
                resolved=next(r for r in own['requests'] if r['id']==request['requestId'])
                assert resolved['status']=='approved' and resolved['resolution']['operation']=='grant'
                assert any(e.get('requestId')==request['requestId'] and e['mechanical'] and e['changes'] for e in own['events'])
                assert not any(e.get('requestId')==request['requestId'] for e in p2.state()['events'])
                kp.action('resolve',{'requestId':request['requestId'],'approve':True,'resolution':{'operation':'grant','input':{'item':1,'slot':8,'uses':3}}})
                assert p1.state()['character']['numbers']['item8']==0
                checks.append('free request executes configured rule, preserves reply, isolates effects and cannot execute twice')
                check=p1.action('request',{'kind':'check','input':{'attribute':'dex','mode':'normal'},'manual':True})
                row=page.locator('[data-request-id="'+check['requestId']+'"]')
                expect(row).to_be_visible();row.get_by_role('button',name='执行',exact=True).click()
                expect(row).to_have_count(0)
                assert p1.state()['character']['numbers']['checks']==1
                checks.append('structured request executes directly from its queue card')
                page.goto(runtime.origin+'/sessions/kp/#/gm/room');page.set_viewport_size({'width':390,'height':844})
                expect(page.locator('#room-overview')).to_be_visible()
                assert page.locator('#room-overview').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
                page.screenshot(path=str(output/'room-mobile.png'),full_page=True)
                assert not errors,errors
                browser.close()
            checks.append('Edge desktop/mobile and JavaScript error checks passed')
    finally:
        skipped.stop()
    report={'passed':True,'checkedAt':datetime.now().astimezone().isoformat(),'checks':checks,'output':str(output),'scope':'isolated local host; no real model calls'}
    (PACK/'tests/room-workflow-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
