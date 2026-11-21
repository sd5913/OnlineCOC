"""Real Edge: shared embed choices compose text, never execute or auto-submit."""
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright,expect
from test_manager_ui import services,allow_players
from test_embeds import login

OUTPUT=Path(__file__).resolve().parents[2]/'acceptance/ai-runtime'

@pytest.mark.parametrize('variant',['page','conversation','collapsible'])
def test_answer_choices_in_all_embeds(services,variant):
    import httpx
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    allow_players(origin)
    with httpx.Client(base_url=origin,trust_env=False) as http:
        csrf=http.post('/api/v1/login',json={'loginName':'kp','password':'test-password'},headers={'Origin':origin}).json()['csrf']
        epoch=http.get('/api/v1/view').json()['authorityEpoch']
        response=http.post('/api/v1/ai/commands',headers={'Origin':origin,'X-CSRF-Token':csrf},json={'requestId':'enable-choices',
            'authorityEpoch':epoch,'op':'ai.settings.update','args':{'enabled':True,'profileId':'deepseek-main',
            'externalSources':{'public':True,'kp':False,'private':True},'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}})
        assert response.json()['status']=='committed'
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1100,'height':850})
        errors=[];writes=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:writes.append(r.post_data_json) if r.url.endswith('/ai/commands') and r.method=='POST' else None)
        try:
            page.goto(origin+'/ai-ui/'+variant+'.html');login(page,'kp')
            if variant=='collapsible':page.locator('.collapse-toggle').click()
            ref=page.evaluate("async()=> (await (await fetch('/api/v1/ai/references?kind=entity&q=')).json()).items[0]")
            page.locator('#text').fill('选项验收 '+ref['token']);page.locator('#send').click()
            expect(page.get_by_role('button',name='友好医师',exact=True)).to_be_enabled(timeout=20000)
            expect(page.locator('.assistant .reference-chip')).to_have_text(ref['label'])
            page.locator('.assistant .reference-chip').click()
            expect(page.get_by_role('dialog')).to_be_visible()
            expect(page.get_by_role('dialog').locator('h2')).to_have_text(ref['label'])
            expect(page.get_by_role('dialog').locator('.reference-value')).to_contain_text('数值')
            page.get_by_role('button',name='关闭引用详情').click()
            expect(page.locator('.response-choices fieldset')).to_have_css('border-radius','12px')
            count=len(writes);page.locator('#text').fill('保留我的要求')
            page.get_by_role('button',name='友好医师',exact=True).click()
            expect(page.locator('#text')).to_contain_text('保留我的要求\n采用友好医师方案')
            page.get_by_role('button',name='神秘访客',exact=True).click()
            expect(page.locator('#text')).to_contain_text('保留我的要求\n采用神秘访客方案')
            assert len(writes)==count
            if variant=='conversation':page.screenshot(path=str(OUTPUT/'answer-choices.png'),full_page=True)
            page.locator('#text').fill('采用神秘访客方案');page.locator('#send').click()
            expect(page.locator('#history')).to_contain_text('已按你的选择继续设计。',timeout=20000)
            expect(page.get_by_role('button',name='友好医师',exact=True)).to_be_disabled()
            page.set_viewport_size({'width':390,'height':840});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert not errors,errors
        finally:browser.close()

def test_standalone_choices_and_inline_citation(services):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page()
        try:
            page.goto(origin+'/ai-ui/conversation.html')
            page.evaluate('''async()=>{
              const {mountChoices,mountMarkdown}=await import('/ai-ui/pack.js');document.body.replaceChildren();
              const detached=document.createElement('section');
              mountMarkdown(detached,'参考 `[[entity:lantern@1]]`。代码示例：\\n```\\n[[entity:lantern@1]]\\n```',{
                resolveReferences:async()=>({items:[{kind:'entity',id:'lantern',revision:'1',label:'提灯'}]})});
              document.body.append(detached);
              window.choice=mountChoices(document.body,{prompt:'选择',options:[{id:'a',label:'<img src=x onerror=alert(1)>',text:'文字'},
                {id:'b',label:'继续',text:'继续设计'}]},{onSelect:o=>window.chosen=o.text});
            }''')
            expect(page.locator('.reference-chip')).to_have_text('提灯')
            expect(page.locator('pre')).to_contain_text('[[entity:lantern@1]]')
            assert not page.locator('img').count()
            page.get_by_role('button',name='继续',exact=True).click();assert page.evaluate('window.chosen')=='继续设计'
            page.evaluate('choice.destroy()');assert not page.locator('.response-choices').count()
        finally:browser.close()
