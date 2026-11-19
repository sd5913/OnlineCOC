"""Player opts in; KP previews a real disclosure; permissions remain visible."""
from datetime import datetime
import json
import secrets
import time
from harness import PACK,running,provision
from integrations import write_json
from verify_integrations import provider,ai,result
from playwright.sync_api import sync_playwright,expect


def main():
    output=PACK/'tests/output'/('ai-permissions-'+secrets.token_hex(4));output.mkdir(parents=True)
    checks=[];errors=[];expect.set_options(timeout=20000)
    with provider(output,lambda request:{'role':'assistant','content':json.dumps({'kind':'known','evidence':[],'next':'ask_kp'})}) as (config,calls):
        with running('ai-permissions',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
            kp,p1,p2=provision(runtime,password)
            result(ai(kp,'ai.access.update',{'revision':1,'allowPlayerChat':True,'autoApproveBatches':False}))
            result(ai(kp,'ai.settings.update',{'enabled':True,'profileId':'offline','externalSources':{'public':True,'kp':True,'private':True},'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}))
            session=result(ai(p1,'ai.session.create',{'title':'侧门资料申请'}))
            task=result(ai(p1,'ai.session.submit',{'sessionId':session['sessionId'],'text':'想知道奶酪工厂的公开描述，请让我选择是否向 KP 申请。'}))
            assert not any(v['kind']=='knowledge_request' for v in kp.request('/api/v1/ai/rulings')['items'])
            def knowledge(account):
                return account.request('/api/v1/knowledge/search',{'query':'奶酪工厂','limit':50})['items']
            assert not knowledge(p1) and not knowledge(p2)
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True)
                def login(account,route):
                    page=browser.new_page(viewport={'width':1440,'height':900})
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    page.goto(runtime.origin+'/sessions/ui-'+account+'/')
                    page.locator('[name=loginName]').fill(account);page.locator('[name=password]').fill(password)
                    page.get_by_role('button',name='进入冒险',exact=True).click();page.locator('.identity').wait_for()
                    page.goto(runtime.origin+'/sessions/ui-'+account+'/#/'+route)
                    return page
                plpage=login('player1','play/scene')
                plpage.locator('#comm-tab-ai').click()
                plpage.locator('.session-select').select_option(session['sessionId'])
                plpage.get_by_role('button',name='向 KP 申请披露',exact=True).first.click()
                expect(plpage.locator('.knowledge-request-status')).to_contain_text('等待 KP')
                requests=[v for v in kp.request('/api/v1/ai/rulings')['items'] if v['kind']=='knowledge_request']
                assert len(requests)==1 and requests[0]['initiator']=='player1'
                duplicate=result(ai(p1,'ai.knowledge.request',{'sessionId':session['sessionId'],'requestId':task['requestId']}))
                assert duplicate['rulingId']==requests[0]['rulingId']
                checks.append('PL 主动点击后才入队，重复申请复用同一请求')
                page=login('kp','gm/rulings')
                row=page.locator('.ruling-row').filter(has_text='资料申请')
                row.get_by_role('button',name='查看并裁决',exact=True).click()
                row.get_by_role('button',name='选择披露资料',exact=True).click()
                expect(page.locator('#dialog')).to_contain_text('批准资料申请')
                view=kp.request('/api/v1/view')
                entity=next(e for e in view['entities'].values() if e['configurationId']=='sv.location' and e['numbers']['index']==8)
                page.locator('[name=disclose-resource]').select_option(entity['instanceId'])
                expect(page.locator('[data-knowledge-preview]')).to_contain_text('屋内的器具')
                assert 'Jack' not in page.locator('[data-knowledge-preview]').inner_text()
                page.screenshot(path=str(output/'knowledge-preview.png'),full_page=True)
                page.get_by_role('button',name='批准并披露',exact=True).click()
                expect(page.locator('#dialog')).not_to_be_visible()
                expect(plpage.locator('.knowledge-request-status')).to_contain_text('已披露',timeout=25000)
                assert knowledge(p1) and not knowledge(p2)
                checks.append('KP 先预览具体分面再执行 observe；只有申请者获得内容与完成状态')
                page.goto(runtime.origin+'/sessions/ui-kp/#/gm/ai-settings')
                settings=page.locator('#kp-ai-settings')
                for selector in ('#enabled','#public','#private','#kp','#auto','#admin-room','#data-queries','#runtime-changes','#config-changes','#knowledge-requests','#player-requests','#allow-player','#auto-batches','#auto-config'):
                    expect(settings.locator(selector)).to_have_count(1)
                expect(settings).to_contain_text('高危修改始终需 KP')
                expect(settings.locator('#knowledge-requests')).to_be_visible()
                page.screenshot(path=str(output/'permissions-desktop.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                settings.locator('#knowledge-requests').scroll_into_view_if_needed()
                expect(settings.locator('#knowledge-requests')).to_be_visible()
                page.screenshot(path=str(output/'permissions-mobile.png'),full_page=True)
                checks.append('独立设置页显示全部 14 个服务、外发、读取和执行开关，390px 可操作且无横向溢出')
                assert not errors,errors
                browser.close()
    report={'checkedAt':datetime.now().astimezone().isoformat(),'passed':len(checks),'checks':checks,
            'realSaveChanged':False,'evidenceDirectory':str(output.relative_to(PACK)).replace('\\','/')}
    write_json(PACK/'tests/ai-permissions-results.json',report)
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
