"""Real room pages, same-origin frames, reusable UI and headless composition."""
from pathlib import Path
import json
import re
import pytest
from playwright.sync_api import sync_playwright, expect
from test_manager_ui import services, allow_players

OUTPUT=Path(__file__).resolve().parents[2]/'acceptance/ai-runtime'


def test_package_manifest_covers_public_runtime_dependencies():
    base=Path(__file__).parents[1]/'web/components'
    manifest=json.loads((base/'pack-manifest.json').read_text(encoding='utf-8'))
    assert manifest['adminRoutes']==[] and manifest['entry']=='pack.js'
    files=set(manifest['runtimeFiles'])
    assert not {'providers.js','index.js'}.intersection(files)
    for name in files|set(manifest['types']):assert (base/name).is_file()
    for name in files:
        if name.endswith('.js'):
            for dependency in re.findall(r"(?:from\s+|new URL\()['\"]\./([^'\"]+)",(base/name).read_text(encoding='utf-8')):
                assert dependency in files,(name,dependency)


def login(page,account):
    page.locator('#account').fill(account);page.locator('#password').fill('test-password')
    page.locator('#connect').click();expect(page.locator('#room')).to_be_visible()


@pytest.mark.parametrize('variant',['page','conversation','collapsible'])
def test_real_room_page_variants(services,variant):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    allow_players(origin)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1360,'height':940});errors=[];queries=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:queries.append(request.url) if '/api/v1/ai/sessions' in request.url else None)
        try:
            response=page.goto(origin+'/ai-ui/'+variant+'.html')
            assert "frame-ancestors 'self'" in response.headers['content-security-policy']
            login(page,'kp' if variant=='page' else 'player1')
            if variant=='collapsible':
                expect(page.locator('.collapse-toggle')).to_have_attribute('aria-expanded','false')
                assert page.locator('.view-chat').count()==0 and not queries
                page.locator('.collapse-toggle').click()
            expect(page.locator('#text')).to_be_visible()
            if variant=='page':expect(page.locator('.view-sidebar')).to_be_visible()
            else:expect(page.locator('.session-select')).to_be_visible()
            if variant=='page':
                page.locator('.review-open').click();page.locator('[data-tab=settings]').click();page.get_by_text('服务与外发范围',exact=True).click()
                expect(page.locator('#ai-save-settings')).to_be_enabled()
                page.locator('#ai-enabled').check();page.locator('#ai-profile').select_option('deepseek-main');page.locator('#ai-public').check();page.locator('#ai-save-settings').click()
                expect(page.locator('#ai-result')).to_have_text('设置已保存');page.locator('.review-close').click()
            else:expect(page.locator('.review-open')).to_be_hidden()
            page.locator('.new-chat').click();expect(page.locator('#status')).to_have_text('新会话已创建')
            page.locator('#text').fill('将新建技能初值改为 15，已有技能保持原值。')
            if variant=='collapsible':
                page.locator('.collapse-toggle').click();expect(page.locator('.collapse-body')).to_be_hidden()
                page.screenshot(path=str(OUTPUT/'embed-collapsed.png'),full_page=True)
                count=len(queries);page.wait_for_timeout(1600);assert len(queries)==count
                page.locator('.collapse-toggle').click();expect(page.locator('#text')).to_contain_text('已有技能保持原值')
            page.locator('#send').click()
            if variant=='page':
                button=page.get_by_role('button',name='查看配置裁决',exact=True);expect(button).to_be_enabled(timeout=40000);button.click()
                expect(page.get_by_role('button',name='批准并执行',exact=True)).to_be_enabled()
                for field in page.locator('.batch-card textarea').all():field.fill('验收接受新建技能收益，已有技能保持原值。')
                page.get_by_role('button',name='批准并执行',exact=True).click()
                expect(page.locator('.batch-card')).to_contain_text('已执行',timeout=40000);page.locator('.review-close').click()
            else:
                expect(page.locator('#history')).to_contain_text('EXTERNAL_SCOPE_DISABLED')
                expect(page.locator('.task-error')).to_contain_text('尚未允许向 AI 外发本人已知资料')
                assert page.get_by_role('button',name='转交 AI',exact=True).count()==0
                expect(page.locator('.session-select')).not_to_have_value('')
            page.screenshot(path=str(OUTPUT/f'embed-{variant}.png'),full_page=True)
            page.set_viewport_size({'width':410,'height':820});expect(page.locator('#text')).to_be_visible()
            page.locator('#logout').click();expect(page.locator('#login')).to_be_visible()
            assert page.locator('.view-chat').count()==0
            assert not errors,errors
        finally:browser.close()


def test_same_origin_iframe_entry_and_csp_scope(services):
    manager,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    allow_players(origin)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page()
        try:
            response=page.goto(origin+'/')
            assert "frame-ancestors 'none'" in response.headers['content-security-policy']
            logged=page.request.post(origin+'/api/v1/login',data={'loginName':'player1','password':'test-password'},headers={'Origin':origin})
            assert logged.status==200
            for variant in ('page','conversation','collapsible'):
                page.evaluate("url=>{document.querySelector('#embedded-ai')?.remove();const f=document.createElement('iframe');f.id='embedded-ai';f.src=url;f.style.cssText='width:100%;height:700px';document.body.append(f);}",origin+'/ai-ui/'+variant+'.html?role=kp')
                frame=page.frame_locator('#embedded-ai');expect(frame.locator('#room')).to_be_visible()
                if variant=='collapsible':frame.locator('.collapse-toggle').click()
                expect(frame.locator('#text')).to_be_visible();expect(frame.locator('.review-open')).to_be_hidden()
            assert "frame-ancestors 'none'" in page.request.get(origin+'/api/v1/capabilities').headers['content-security-policy']
            assert "frame-ancestors 'none'" in page.request.get(manager+'/').headers['content-security-policy']
        finally:browser.close()


def test_headless_tools_and_shared_client_ownership(services):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    allow_players(origin)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page()
        try:
            page.goto(origin+'/ai-ui/conversation.html')
            result=page.evaluate("""async()=>{
              const api=await import('/ai-ui/pack.js');if('mountProviders' in api)throw new Error('ADMIN_EXPORT_LEAK');const client=new api.AiClient();await client.login('player1','test-password');
              const tools=api.createAITools(client);const dataPage=await tools.data.search({types:['knowledge']});if(!dataPage.items.length)throw new Error('DATA_QUERY_EMPTY');await tools.data.read({refs:[dataPage.items[0].ref]});const created=await tools.sessions.create('开发者自行装配','tool-create');
              const replay=await tools.sessions.create('开发者自行装配','tool-create');
              const selected=(await tools.references.search('knowledge','')).items[0];
              const sent=await tools.sessions.submit(created.result.sessionId,'参考 '+tools.references.token(selected),'tool-submit');
              const detail=await tools.sessions.get(created.result.sessionId);
              const denied=await tools.requests.dispatch(sent.result.requestId);
              const one=document.createElement('div'),two=document.createElement('div');one.id='one';two.id='two';one.style.height=two.style.height='600px';document.body.append(one,two);
              const view=api.mountAIConversation(one,client,{review:false}),fold=api.mountAICollapsible(two,client,{open:true});
              view.setDraft('第一份草稿');fold.setDraft('第二份草稿');view.destroy();tools.destroy();
              window.embeddedClient=client;window.embeddedFold=fold;
              return {created:created.status,replay:replay.result.sessionId===created.result.sessionId,submitted:sent.status,status:detail.items[0].status,
                allowedCommands:api.referenceCommands(client.view.role).map(x=>x.kind),denied:denied.status,connected:client.connected,
                contracts:!!(await client.aiContracts()).operations['ai.session.submit']};
            }""")
            assert result=={'created':'committed','replay':True,'submitted':'committed','status':'blocked','allowedCommands':['knowledge'],'denied':'rejected','connected':True,'contracts':True}
            expect(page.locator('#two #text')).to_have_text('第二份草稿')
            late=page.evaluate("""async()=>{
              const {AiClient,createAITools}=await import('/ai-ui/pack.js');let release,calls=0;
              const fake=new AiClient({request(){calls++;return new Promise(resolve=>release=resolve);}});fake.connected=true;fake.view={accountId:'player1',role:'player',authorityEpoch:'test'};
              const tools=createAITools(fake),read=tools.sessions.list().catch(e=>e.message);tools.destroy();release({items:[{title:'late private title'}]});
              const result=await read;await tools.sessions.list().catch(()=>{});return {result,calls,connected:embeddedClient.connected};
            }""")
            assert late=={'result':'VIEW_CHANGED','calls':1,'connected':True}
            page.evaluate('embeddedFold.destroy();embeddedClient.destroy()')
        finally:browser.close()
