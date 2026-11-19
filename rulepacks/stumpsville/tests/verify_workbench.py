"""Compact KP workspace, configuration coverage and warm AI navigation."""
from datetime import datetime
import json
import secrets
import time
from urllib.parse import urlsplit
from harness import PACK, running, Account
from verify_integrations import provider, ai, result
from playwright.sync_api import sync_playwright, expect


def main():
    expect.set_options(timeout=25000)
    output = PACK/'tests/output'/('workbench-'+secrets.token_hex(4))
    output.mkdir(parents=True)
    checks, errors, timing = [], [], {}
    with provider(output, lambda request: {'role':'assistant','content':'测试回答'}) as (config, calls), running('workbench', data=output/'game', ai_config=config, no_browser=True) as (runtime, password):
        kp, pl = [Account(runtime.origin, name, password, name) for name in ('kp','player1')]
        pl.action('draft', {'preset':'mul','name':'资料验收鼠'})
        kp.action('approve', {'account':'player1'})
        pl.action('ready', {'ready':True})
        kp.action('session.start')
        request = pl.action('request', {'kind':'free','manual':True,'text':'需要详细核对的长申请。'*50})
        result(ai(kp,'ai.access.update',{'revision':1,'allowPlayerChat':True,'autoApproveBatches':False}))
        session = result(ai(pl,'ai.session.create',{'title':'直接定位的玩家会话'}))
        task = result(ai(pl,'ai.session.submit',{'sessionId':session['sessionId'],'text':'请主持明确本次可见的信息范围。'}))
        assert 'requestId' in request, request
        admin = kp.request('/api/v1/admin')
        bundle = kp.request('/package/bundle')
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge',headless=True)
            page = browser.new_page(viewport={'width':1440,'height':900})
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(runtime.origin+'/sessions/kp/')
            page.locator('[name=loginName]').fill('kp')
            page.locator('[name=password]').fill(password)
            page.get_by_role('button',name='进入冒险',exact=True).click()
            expect(page.locator('#room-overview')).to_be_visible()
            assert page.evaluate('document.documentElement.scrollHeight<=innerHeight+2')
            checks.append('desktop room overview and member summary fit one viewport')
            cold_start=time.perf_counter()
            page.locator('.sidebar a[href="#/gm/rulings"]').click()
            row = page.locator('[data-request-id="'+request['requestId']+'"]')
            expect(row).to_be_visible()
            assert row.bounding_box()['height'] < 125
            assert row.locator('time').inner_text() != '—'
            expect(page.locator('#ruling-form')).to_have_count(0)
            expect(page.locator('[data-ai-request="'+task['requestId']+'"]')).to_be_visible()
            timing['coldQueueReadyMs']=round((time.perf_counter()-cold_start)*1000)
            row.locator('.queue-summary').click()
            expect(page.locator('#dialog')).to_contain_text('需要详细核对的长申请。'*50)
            assert not page.locator('#ruling-form details').evaluate('(e)=>e.open')
            page.keyboard.press('Escape')
            expect(page.locator('#dialog')).not_to_be_visible()
            checks.append('long game requests stay compact; full content opens in a modal with reply folded')
            ai_row = page.locator('[data-ai-request="'+task['requestId']+'"]')
            expect(ai_row).to_be_visible()
            ai_row.locator('.queue-summary').click()
            expect(page.locator('.ai-request-detail')).to_contain_text('请主持明确')
            page.keyboard.press('Escape')
            expect(page.locator('.ai-request-detail')).to_have_count(0)
            requests = []
            page.on('request',lambda req: requests.append(urlsplit(req.url).path))
            start = time.perf_counter()
            ai_row.get_by_role('button',name='查看对应会话',exact=True).click()
            expect(page.locator('#kp-ai-embedded #session-access')).to_contain_text('player1')
            timing['requestToSessionMs'] = round((time.perf_counter()-start)*1000)
            reads = [path for path in requests if '/ai/sessions/' in path]
            assert reads and all(path.endswith('/'+session['sessionId']) for path in reads), reads
            checks.append('AI request opens its own session directly without scanning other sessions')
            page.evaluate('window.retainedAI=document.querySelector(".embedded-ai-root")')
            page.locator('.sidebar a[href="#/gm/room"]').click()
            start = time.perf_counter()
            page.locator('.sidebar a[href="#/gm/rulings"]').click()
            expect(page.locator('#kp-ai-embedded #session-access')).to_contain_text('player1')
            timing['warmNavigationMs'] = round((time.perf_counter()-start)*1000)
            assert page.evaluate('window.retainedAI===document.querySelector(".embedded-ai-root")')
            checks.append('warm KP navigation preserves the AI component and selected session')
            page.screenshot(path=str(output/'compact-rulings.png'))
            page.locator('.sidebar a[href="#/gm/ai-settings"]').click()
            expect(page.locator('#kp-ai-settings #allow-player')).to_be_visible()
            expect(page.locator('#kp-ai-settings #allow-player')).to_be_checked()
            expect(page.locator('.ai-dialog')).to_have_count(0)
            page.screenshot(path=str(output/'ai-settings.png'))
            permission=page.locator('#kp-ai-settings #allow-player')
            for enabled in (False,True):
                permission.set_checked(enabled)
                with page.expect_response(lambda r: '/api/v1/ai/commands' in r.url and r.request.method=='POST' and r.request.post_data_json.get('op')=='ai.access.update') as saved:
                    page.get_by_role('button',name='保存权限设置',exact=True).click()
                assert saved.value.json()['status']=='committed'
                assert kp.request('/api/v1/ai/access')['allowPlayerChat'] is enabled
            page.set_viewport_size({'width':390,'height':844})
            expect(permission).to_be_visible()
            page.get_by_role('button',name='保存权限设置',exact=True).scroll_into_view_if_needed()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
            assert page.evaluate('document.documentElement.scrollHeight<=innerHeight+2')
            page.screenshot(path=str(output/'mobile-settings.png'))
            page.set_viewport_size({'width':1440,'height':900})
            checks.append('dedicated AI settings saves real player permissions; desktop and mobile controls remain accessible')
            page.locator('.sidebar a[href="#/gm/library"]').click()
            expect(page.locator('.library-content')).to_be_visible()
            for configuration in admin['configurations']:
                expect(page.locator('.library-table')).to_contain_text(configuration)
            for file,data in bundle['data'].items():
                if isinstance(data,dict):
                    for key,value in data.items():
                        tab='data:'+file+(':'+key if isinstance(value,(dict,list)) else ':about')
                        assert page.locator('[role=tab]').evaluate_all('(els,id)=>els.some(e=>JSON.parse(e.dataset.args).id===id)',tab), tab
                else:
                    assert page.locator('[role=tab]').evaluate_all('(els,id)=>els.some(e=>JSON.parse(e.dataset.args).id===id)','data:'+file)
            page.get_by_role('tab',name='规则与流程',exact=True).click()
            for name in bundle['sources']:
                expect(page.locator('.library-table')).to_contain_text(name)
            page.locator('[name=library-search]').fill('layout.lua')
            expect(page.locator('.library-table tbody tr')).to_have_count(1)
            page.locator('.library-table [data-action=library-detail]').click()
            expect(page.locator('#dialog')).to_contain_text(bundle['sources']['layout.lua'])
            page.keyboard.press('Escape')
            assert page.evaluate('document.documentElement.scrollHeight<=innerHeight+2')
            page.screenshot(path=str(output/'library.png'))
            checks.append('all current configuration definitions, source files and data categories are reachable; search and full detail work')
            page.set_viewport_size({'width':390,'height':844})
            page.locator('.sidebar a[href="#/gm/rulings"]').click()
            for pane in ('queue','ai','chat'):
                page.locator('.ruling-switch [data-args=\'{"pane":"'+pane+'"}\']').click()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
                assert page.evaluate('document.documentElement.scrollHeight<=innerHeight+2')
            page.screenshot(path=str(output/'mobile-rulings.png'))
            checks.append('390px ruling tabs show queue, AI and chat within one viewport without horizontal overflow')
            assert 'configurations' not in pl.request('/api/v1/admin',allow_error=True)
            assert 'sources' not in pl.request('/package/bundle',allow_error=True)
            page.locator('[data-action=logout]').click()
            expect(page.locator('#entry-form')).to_be_visible()
            assert page.evaluate('!window.retainedAI.isConnected')
            assert not errors,errors
            checks.append('KP-only data remains denied to players; logout removes the retained UI; browser has no script errors')
            browser.close()
        assert not calls, 'No model invocation is expected for UI-only acceptance'
    report={'passed':True,'checkedAt':datetime.now().astimezone().isoformat(),'checks':checks,'timing':timing,'output':str(output),'scope':'isolated loopback host, headless Edge; no real provider or live room'}
    (PACK/'tests/workbench-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
