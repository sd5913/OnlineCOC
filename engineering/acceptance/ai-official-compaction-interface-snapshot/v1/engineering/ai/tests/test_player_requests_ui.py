"""Actual embedded-page intent submission and KP review navigation."""
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from test_manager_ui import services,allow_players
from test_embeds import login
OUTPUT=Path(__file__).resolve().parents[2]/'acceptance/ai-runtime'


def test_real_player_direct_request_without_knowledge_then_kp_queue(services):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}';allow_players(origin)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);context=browser.new_context(viewport={'width':390,'height':844});page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(origin+'/ai-ui/conversation.html');login(page,'player1')
            page.locator('#text').fill('我想用火把给针剑附魔，变成火焰针剑')
            page.locator('#player-request').click()
            expect(page.locator('.player-request-status')).to_contain_text('等待 KP 接收')
            expect(page.get_by_role('button',name='向 KP 申请披露',exact=True)).to_have_count(0)
            assert page.request.get(origin+'/api/v1/ai/sessions').json()['items'][0]['requestCount']==1
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            page.screenshot(path=str(OUTPUT/'player-requests-mobile.png'),full_page=True)
            tasks=page.request.get(origin+'/api/v1/ai/tasks').json()['items'];assert tasks[0]['playerRequest']['status']=='pending' and not tasks[0].get('taskId')
            kp=browser.new_context().new_page();kp.goto(origin+'/ai-ui/conversation.html');login(kp,'kp')
            data=kp.request.get(origin+'/api/v1/ai/rulings').json();assert data['items'][0]['kind']=='player_request'
            assert not errors
        finally:browser.close()


def test_player_error_is_visible_and_choice_forwards_original_request_once(services):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':390,'height':844})
        try:
            page.goto(origin+'/ai-ui/conversation.html')
            page.evaluate("""async()=>{
              const {mountChat}=await import('/ai-ui/pack.js');document.body.replaceChildren();window.sent=[];
              const session={sessionId:'s',owner:'player1',accessLevel:'player',title:'本人创作',revision:1,archived:false,renderMode:'formatted'};
              const item={requestId:'r',status:'blocked',text:'组合物品',error:'DATA_QUERIES_DISABLED',choices:{prompt:'提交创作吗',options:[{id:'ask_kp_change',label:'提交创作／配置申请',text:'generic generated text'},{id:'known_only',label:'只看已知',text:'只看已知'}]}};
              const c={connected:true,generation:1,view:{accountId:'player1',role:'player',authorityEpoch:'e'},subscribe:()=>()=>{},aiSessions:async()=>({items:[session],access:{canChat:true,allowPlayerRequests:true}}),aiAccess:async()=>({canChat:true}),aiSession:async()=>({session,items:[structuredClone(item)]}),aiResolve:async()=>({items:[]}),aiCommand:async(op,args)=>{sent.push({op,args});item.playerRequest={status:'pending'};return {status:'committed',result:item.playerRequest};}};
              window.panel=mountChat(document.body,c);await panel.select('s');
            }""")
            expect(page.locator('.task-error')).to_contain_text('KP 已关闭 AI 资料查询')
            assert page.evaluate('sent.length')==0
            page.get_by_role('button',name='提交创作／配置申请',exact=True).click()
            expect(page.locator('.player-request-status')).to_contain_text('等待 KP 接收')
            expect(page.get_by_role('button',name='提交创作／配置申请',exact=True)).to_be_disabled()
            assert page.evaluate('sent')==[{'op':'ai.player.request','args':{'sessionId':'s','requestId':'r'}}]
            page.evaluate('panel.destroy()')
        finally:browser.close()


def test_kp_accept_label_and_open_private_review_session(services):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page()
        try:
            page.goto(origin+'/ai-ui/conversation.html')
            page.evaluate("""async()=>{
              const {mountRulings}=await import('/ai-ui/pack.js');document.body.replaceChildren();window.sent=[];
              const item={rulingId:'player:p',kind:'player_request',sessionId:'player-session',summary:'火焰针剑',createdAt:100,status:'pending',digest:'digest',canDecide:true,risks:[]};
              const c={connected:true,generation:1,view:{accountId:'kp',role:'kp',authorityEpoch:'e'},subscribe:()=>()=>{},aiRulings:async()=>({items:[structuredClone(item)]}),aiResolve:async()=>({items:[]}),aiCommand:async(op,args)=>{sent.push({op,args});item.status='accepted';item.canDecide=false;item.reviewSessionId='private-review';return {status:'committed',result:item};}};
              window.panel=mountRulings(document.body,c,{compact:true,onOpenSession:id=>{window.opened=id;}});
            }""")
            page.get_by_role('button',name='查看并裁决').click()
            expect(page.get_by_role('button',name='批准并执行')).to_have_count(0)
            page.get_by_role('button',name='接收并生成方案').click()
            expect(page.locator('.ruling-row')).to_contain_text('已接收，方案另行审核')
            page.get_by_role('button',name='打开审核会话').click();assert page.evaluate('opened')=='private-review'
            assert page.evaluate('sent.length')==1
            page.evaluate('panel.destroy()')
        finally:browser.close()
