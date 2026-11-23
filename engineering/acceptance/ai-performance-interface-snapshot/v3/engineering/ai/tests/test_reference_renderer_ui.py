"""Package renderer handoff without any backend, game save or provider."""
from playwright.sync_api import sync_playwright, expect
import pytest
from test_debug_dialog_ui import static_ui


@pytest.mark.parametrize('width',[1100,390])
def test_view_chat_renderer_authorized_full_dto_preview_and_revocation(static_ui,width):
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport={'width':width,'height':850});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(static_ui+'/')
            page.evaluate("""async()=>{
                document.body.innerHTML='<main id="test" style="height:800px"></main>';window.listeners=[];window.calls=[];window.failure=null;
                window.refItem={kind:'entity',id:'actor',revision:'1',label:'小鼠向导',visibility:'kp',value:{instanceId:'actor',configurationId:'sv.npc',numbers:{hp:12},metadata:{description:'已授权的角色说明'}}};
                window.resolve=async()=>{if(failure)throw Object.assign(new Error(failure),{code:failure});return {items:[refItem]};};
                const session={sessionId:'s1',title:'Reference renderer',owner:'kp',accessLevel:'administrator',revision:1,archived:false};
                const access={canChat:true};
                window.client={connected:true,generation:1,view:{roomId:'room',accountId:'kp',role:'kp',authorityEpoch:'epoch'},
                    subscribe:fn=>{listeners.push(fn);return()=>{};},onChange:fn=>{listeners.push(fn);return()=>{};},
                    aiSessions:async()=>({items:[session],access}),aiAccess:async()=>access,
                    aiSession:async()=>({session,items:[{requestId:'r1',status:'review_ready',text:'查看角色',response:'[[entity:actor@1]]',createdAt:1}]}),aiResolve:tokens=>resolve(tokens)};
                const {mountAIConversation}=await import('./pack.js');
                window.panel=mountAIConversation(document.querySelector('#test'),client,{renderReference:(item,context)=>{
                    calls.push({item:structuredClone(item),context});const card=document.createElement('section');card.className='package-card';
                    card.textContent=item.label+'：生命 '+item.value.numbers.hp;item.value.numbers.hp=0;return card;
                }});await panel.select('s1');
            }""")
            chip=page.locator('#history .reference-chip');expect(chip).to_contain_text('小鼠向导');chip.click()
            dialog=page.get_by_role('dialog',name='小鼠向导');expect(dialog.locator('.package-card')).to_have_text('小鼠向导：生命 12')
            assert page.evaluate('calls[0].context')=={'audience':'administrator','readOnly':True}
            assert page.evaluate('calls[0].item.value.configurationId')=='sv.npc'
            assert page.evaluate('refItem.value.numbers.hp')==12
            expect(dialog.get_by_text('技术详情（原始数据）')).to_be_visible()
            dialog.get_by_role('button',name='关闭引用详情').click();expect(chip).to_be_focused()
            page.evaluate("panel.setDraft('[[entity:actor@1]]')")
            page.get_by_role('button',name='查看引用',exact=True).click()
            expect(page.locator('#reference-preview .package-card')).to_have_text('小鼠向导：生命 12')
            page.evaluate("failure='REFERENCE_STALE'");before=page.evaluate('calls.length');chip.click()
            stale=page.get_by_role('dialog',name='引用详情');expect(stale).to_contain_text('引用已过期')
            expect(stale.locator('.package-card')).to_have_count(0);assert page.evaluate('calls.length')==before
            stale.get_by_role('button',name='关闭引用详情').click()
            page.evaluate("failure='NOT_VISIBLE'");chip.click();expect(page.get_by_role('dialog',name='引用详情')).to_contain_text('失去权限')
            page.evaluate('client.connected=false;client.generation++;listeners.forEach(fn=>fn())')
            expect(page.get_by_role('dialog')).to_have_count(0)
            assert not errors,errors
        finally:browser.close()


def test_markdown_renderer_fallback_option_change_and_late_result(static_ui):
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page();errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(static_ui+'/')
            page.evaluate("""async()=>{
                document.body.innerHTML='<main id="test"></main>';window.calls=[];
                window.item={kind:'knowledge',id:'k',revision:'1',label:'已知角色',visibility:'private',value:{mode:'observation',data:{description:'本人已知说明',owner:'hidden-technical-id'}}};
                window.resolve=async()=>({items:[item]});window.options={audience:'player',resolveReferences:tokens=>resolve(tokens),renderReference:(dto,context)=>{calls.push(context);return null;}};
                window.text='[[knowledge:k@1]]';const {mountMarkdown}=await import('./markdown.js');window.markdown=mountMarkdown(document.querySelector('#test'),text,options);
            }""")
            chip=page.locator('.reference-chip');expect(chip).to_contain_text('已知角色');chip.click()
            dialog=page.get_by_role('dialog',name='已知角色');expect(dialog).to_contain_text('本人已知说明')
            expect(dialog).not_to_contain_text('hidden-technical-id');expect(dialog.locator('details')).to_have_count(0)
            assert page.evaluate('calls[0]')=={'audience':'player','readOnly':True}
            page.evaluate("options={...options,renderReference:()=>{const n=document.createElement('b');n.textContent='包专用视图';return n;}};markdown.update(text,options)")
            expect(dialog).not_to_be_visible();chip.click();expect(page.get_by_role('dialog')).to_contain_text('包专用视图')
            page.evaluate("markdown.update(text,{...options,renderReference:()=>{throw new Error('renderer-failed')}})")
            chip.click();expect(page.get_by_role('dialog')).to_contain_text('本人已知说明')
            page.get_by_role('button',name='关闭引用详情').click()
            page.evaluate("()=>{resolve=()=>new Promise(done=>window.deliver=done);}");chip.click()
            expect(page.get_by_role('dialog')).to_contain_text('正在读取')
            page.evaluate("markdown.destroy();deliver({items:[item]})")
            expect(page.locator('#test')).to_be_empty();assert not errors,errors
        finally:browser.close()


def test_historical_notice_and_notification_candidate_are_visible(static_ui):
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page()
        try:
            page.goto(static_ui+'/')
            page.evaluate("""async()=>{
                document.body.innerHTML='<main id="chat" style="height:600px"></main><main id="queue"></main>';
                const session={sessionId:'s1',title:'History',owner:'kp',accessLevel:'administrator',revision:1,archived:false};const access={canChat:true};
                window.client={connected:true,generation:1,view:{roomId:'room',accountId:'kp',role:'kp',authorityEpoch:'epoch'},subscribe:()=>()=>{},onChange:()=>()=>{},
                    aiSessions:async()=>({items:[session],access}),aiAccess:async()=>access,aiResolve:async()=>({items:[]}),
                    aiSession:async()=>({session,items:[{requestId:'r1',status:'stale',text:'给玩家加护甲',response:'原先的方案仍可阅读',historicalReadOnly:true,sourceState:'stale',sourceError:'SOURCE_STALE',sourceNotice:'历史依据已变化；修改前重新查询',createdAt:1}]}),
                    aiRulings:async()=>({items:[{kind:'runtime',rulingId:'batch:b1',status:'pending',canDecide:true,risks:[],summary:'修改角色并通知',digest:'digest',actions:[
                        {target:'host',op:'entity.patch',args:{id:'actor',name:'改名'}},
                        {target:'host',op:'notification.send',args:{recipientAccountIds:['player1'],text:'角色修改已完成',sourceActionIndex:0}}]}]})};
                const {mountAIConversation,mountRulings}=await import('./pack.js');window.chat=mountAIConversation(document.querySelector('#chat'),client);await chat.select('s1');window.queue=mountRulings(document.querySelector('#queue'),client);
            }""")
            expect(page.locator('#history')).to_contain_text('原先的方案仍可阅读')
            expect(page.locator('.history-source-notice')).to_have_text('历史依据已变化；修改前重新查询')
            expect(page.locator('#history .error-detail')).to_have_count(0)
            expect(page.locator('.notification-plan')).to_contain_text('player1；绑定第 1 步 entity.patch')
            expect(page.locator('.notification-plan')).to_contain_text('仅原动作成功且流程完成后投递')
            expect(page.get_by_role('button',name='批准并执行',exact=True)).to_be_visible()
            page.evaluate('chat.destroy();queue.destroy()')
        finally:browser.close()
