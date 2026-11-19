import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from test_manager_ui import services
from test_embeds import login

OUTPUT=Path(__file__).resolve().parents[2]/'acceptance/ai-runtime'


def test_room_settings_page_saves_permissions_and_denies_player(services):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1100,'height':820});calls=[];errors=[]
        page.on('request',lambda r:calls.append(r.url));page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(origin+'/ai-ui/settings.html');login(page,'kp')
            expect(page.locator('#allow-player')).to_be_visible()
            assert not any('/ai/tasks' in url or '/ai/rulings' in url for url in calls)
            page.locator('#allow-player').check();page.locator('#auto-batches').check();page.locator('#access button').click()
            expect(page.locator('#status')).to_have_text('设置已保存')
            access=page.request.get(origin+'/api/v1/ai/access').json();assert access['allowPlayerChat'] and access['autoApproveBatches']
            page.locator('#profile').select_option('deepseek-main');page.locator('#public').check();page.locator('#service button').click()
            expect(page.locator('#status')).to_have_text('设置已保存')
            assert page.request.get(origin+'/api/v1/ai/settings').json()['settings']['profileId']=='deepseek-main'
            page.screenshot(path=str(OUTPUT/'workbench-settings.png'))
            page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            page.screenshot(path=str(OUTPUT/'workbench-settings-mobile.png'),full_page=True)
            page.locator('#logout').click();login(page,'player1')
            expect(page.locator('#status')).to_contain_text('仅 KP')
            expect(page.locator('#settings')).to_be_hidden()
            assert page.request.get(origin+'/api/v1/ai/settings').status==403
            assert not errors,errors
        finally:browser.close()


def test_compact_ruling_modal_retains_risks_and_decides_once(services):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1000,'height':800})
        try:
            page.goto(origin+'/ai-ui/conversation.html')
            page.evaluate('''async()=>{
              const {mountRulings}=await import('/ai-ui/pack.js');document.body.replaceChildren();
              window.item={rulingId:'r1',kind:'configuration',sessionId:'s1',requestId:'q1',initiator:'kp',summary:'添加一名 NPC。'+ '补充说明。'.repeat(60),status:'pending',digest:'digest',createdAt:1000,canDecide:true,risks:[{id:'risk',question:'接受风险的理由',required:true}],receipts:[],changeSet:{configurations:[]},reports:[]};
              window.commands=[];window.client={connected:true,generation:1,view:{accountId:'kp',role:'kp',authorityEpoch:'epoch'},subscribe(fn){window.changed=fn;return ()=>{};},aiRulings:async()=>({items:[structuredClone(item)]}),aiResolve:async()=>({items:[]}),aiCommand:async(op,args)=>{commands.push({op,args});item.status='completed';return {status:'committed',result:structuredClone(item)};}};
              window.panel=mountRulings(document.body,client,{compact:true,onOpenSession:id=>window.opened=id});
            }''')
            expect(page.locator('.ruling-row')).to_have_count(1)
            expect(page.locator('textarea')).to_be_hidden()
            assert len(page.locator('.ruling-summary').inner_text())<180
            page.get_by_role('button',name='打开对话').click();assert page.evaluate('opened')=='s1'
            page.get_by_role('button',name='查看并裁决').click();page.locator('textarea').fill('接受已核对影响')
            page.evaluate('panel.refresh()');expect(page.locator('textarea')).to_have_value('接受已核对影响')
            expect(page.locator('details')).not_to_have_attribute('open','')
            page.screenshot(path=str(OUTPUT/'workbench-ruling-detail.png'))
            page.get_by_role('button',name='批准并执行').click();expect(page.locator('.ruling-summary')).to_contain_text('已执行')
            sent=page.evaluate('commands');assert len(sent)==1 and sent[0]['args']['riskDecisions']=={'risk':'接受已核对影响'}
            page.get_by_role('button',name='查看详情').click();page.locator('.ruling-dialog').press('Escape');expect(page.locator('.ruling-dialog')).not_to_be_visible()
            page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            assert page.locator('.ruling-excerpt').evaluate('e=>e.getBoundingClientRect().height<=parseFloat(getComputedStyle(e).lineHeight)*2+1')
            page.screenshot(path=str(OUTPUT/'workbench-rulings-mobile.png'))
            page.evaluate("client.view={accountId:'player1',role:'player',authorityEpoch:'new'};changed();panel.destroy()")
            assert not page.locator('.ruling-row').count()
        finally:browser.close()


def test_resume_loads_target_in_parallel_without_redundant_access_or_old_session(services):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page()
        try:
            page.goto(origin+'/ai-ui/conversation.html')
            result=page.evaluate('''async()=>{
              const {mountAIConversation}=await import('/ai-ui/pack.js');document.body.replaceChildren();
              let calls=[],gates=[],delay=false;const sessions=['a','b'].map(id=>({sessionId:id,title:id,owner:'kp',accessLevel:'administrator',revision:1,archived:false}));
              const wait=()=>delay?new Promise(r=>gates.push(r)):Promise.resolve();
              const c={connected:true,generation:1,view:{accountId:'kp',role:'kp',authorityEpoch:'epoch'},subscribe:()=>()=>{},aiSessions:async()=>{calls.push('list');await wait();return {items:sessions,access:{canChat:true}}},aiAccess:async()=>{calls.push('access');return {canChat:true}},aiSession:async id=>{calls.push(id);await wait();return {session:sessions.find(s=>s.sessionId===id),items:[]}},aiResolve:async()=>({items:[]})};
              const view=mountAIConversation(document.body,c,{review:false});await view.select('a');await new Promise(r=>setTimeout(r,0));
              const initial=[...calls];view.setDraft('未发送的草稿');view.suspend();calls=[];delay=true;const started=performance.now(),pending=view.resume({sessionId:'b'});
              await new Promise(r=>setTimeout(r,0));const concurrent=[...calls];delay=false;gates.forEach(r=>r());await pending;
              const elapsed=performance.now()-started;await view.select('a');const draft=document.querySelector('body>div').shadowRoot.querySelector('.view-chat>div').shadowRoot.querySelector('#text').textContent;
              view.destroy();return {initial,concurrent,elapsed,draft,connected:c.connected};
            }''')
            assert result['initial']==['list','a']
            assert result['concurrent']==['list','b']
            assert result['draft']=='未发送的草稿' and result['connected']
            (OUTPUT/'workbench-load-measurement.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        finally:browser.close()
