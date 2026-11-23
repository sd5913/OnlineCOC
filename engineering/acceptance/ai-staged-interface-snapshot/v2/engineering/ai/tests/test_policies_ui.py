"""Browser checks for explicit settings, high-risk fingerprints and voluntary PL requests."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from test_manager_ui import services
from test_embeds import login

OUTPUT=Path(__file__).resolve().parents[2]/'acceptance/ai-runtime'


def test_permission_switches_save_and_high_risk_policy_is_fixed(services):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1100,'height':900})
        try:
            page.goto(origin+'/ai-ui/settings.html');login(page,'kp')
            ids=['admin-room','data-queries','runtime-changes','config-changes','knowledge-requests']
            keys=['allowAdminRoomRead','allowDataQueries','allowRuntimeChanges','allowConfigurationChanges','allowKnowledgeRequests']
            for identifier in ids:expect(page.locator('#'+identifier)).to_be_checked();page.locator('#'+identifier).uncheck()
            page.locator('#access button').click();expect(page.locator('#status')).to_have_text('设置已保存')
            state=page.request.get(origin+'/api/v1/ai/access').json();assert all(state[k] is False for k in keys)
            expect(page.locator('#access')).to_contain_text('高危修改始终需 KP')
            page.screenshot(path=str(OUTPUT/'policies-settings.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            page.screenshot(path=str(OUTPUT/'policies-settings-mobile.png'),full_page=True)
        finally:browser.close()


def test_high_risk_click_binds_digest_and_knowledge_callback_does_not_auto_approve(services):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1050,'height':820})
        try:
            page.goto(origin+'/ai-ui/conversation.html')
            page.evaluate('''async()=>{
              const {mountRulings}=await import('/ai-ui/pack.js');document.body.replaceChildren();window.sent=[];
              window.items=[{rulingId:'proposal:test',kind:'configuration',summary:'新增物品与入口',highRisk:true,riskTags:['map-or-game-data'],diff:[{target:'data',id:'game.json',before:{},after:{entry:11}}],createdAt:100,status:'pending',digest:'fingerprint',canDecide:true,risks:[{id:'high-risk',question:'填写高危判断',required:true}],receipts:[]},
                {rulingId:'knowledge:test',kind:'knowledge_request',summary:'玩家请求说明',createdAt:101,status:'pending',digest:'knowledge-fingerprint',canDecide:true,risks:[],receipts:[]}];
              const c={connected:true,generation:1,view:{accountId:'kp',role:'kp',authorityEpoch:'epoch'},subscribe:()=>()=>{},aiRulings:async()=>({items:structuredClone(items)}),aiResolve:async()=>({items:[]}),aiCommand:async(op,args)=>{sent.push({op,args});const item=items.find(i=>i.rulingId===args.rulingId);item.status='completed';return {status:'committed',result:item};}};
              window.panel=mountRulings(document.body,c,{compact:true,onKnowledgeRequest:item=>{window.selectedKnowledge=item;}});
            }''')
            expect(page.locator('.ruling-row')).to_have_count(2)
            assert page.evaluate('sent.length')==0
            page.locator('.ruling-row').nth(0).get_by_role('button',name='查看并裁决').click()
            page.get_by_label('填写高危判断').fill('已核对结构与差异')
            page.get_by_role('button',name='批准并执行').click()
            expect(page.locator('.ruling-row').nth(0)).to_contain_text('已执行')
            assert page.evaluate('sent[0].args.explicitHighRiskDigest')=='fingerprint'
            page.locator('.ruling-row').nth(1).get_by_role('button',name='查看并裁决').click()
            page.get_by_role('button',name='选择披露资料').click()
            assert page.evaluate('selectedKnowledge.digest')=='knowledge-fingerprint'
            assert page.evaluate('sent.length')==1
            page.screenshot(path=str(OUTPUT/'policies-knowledge-review.png'))
            page.evaluate('panel.destroy()')
        finally:browser.close()


def test_player_disclosure_requires_a_click_and_reports_pending(services):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':390,'height':844})
        try:
            page.goto(origin+'/ai-ui/conversation.html')
            page.evaluate('''async()=>{
              const {mountChat}=await import('/ai-ui/pack.js');document.body.replaceChildren();window.sent=[];
              const session={sessionId:'s',owner:'player1',accessLevel:'player',title:'本人资料',revision:1,archived:false,renderMode:'formatted'};
              const item={requestId:'r',status:'review_ready',text:'前方有哪些未知场景？',response:'目前可核验的本人已知资料不足。',choices:{prompt:'需要请求说明吗？',options:[{id:'ask_kp',label:'向 KP 申请披露',text:'请 KP 说明'},{id:'known_only',label:'只看已知',text:'只看已知'}]}};
              const c={connected:true,generation:1,view:{accountId:'player1',role:'player',authorityEpoch:'epoch'},subscribe:()=>()=>{},aiSessions:async()=>({items:[session],access:{canChat:true}}),aiAccess:async()=>({canChat:true}),aiSession:async()=>({session,items:[structuredClone(item)]}),aiResolve:async()=>({items:[]}),aiCommand:async(op,args)=>{sent.push({op,args});item.knowledgeRequest={status:'pending',rulingId:'knowledge:k'};return {status:'committed',result:item.knowledgeRequest};}};
              window.panel=mountChat(document.body,c);await panel.select('s');
            }''')
            assert page.evaluate('sent.length')==0
            expect(page.locator('.response-choices')).to_contain_text('会提交申请')
            expect(page.get_by_role('button',name='向 KP 申请披露',exact=True)).to_have_count(1)
            page.get_by_role('button',name='向 KP 申请披露',exact=True).click()
            expect(page.locator('.knowledge-request-status')).to_have_text('资料申请：等待 KP 处理')
            expect(page.get_by_role('button',name='向 KP 申请披露',exact=True)).to_be_disabled()
            assert page.evaluate('sent')==[{'op':'ai.knowledge.request','args':{'sessionId':'s','requestId':'r'}}]
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            page.screenshot(path=str(OUTPUT/'policies-player-request.png'))
            page.evaluate('panel.destroy()')
        finally:browser.close()
