"""Browser checks: revision-bound inspection, race safety and stable history reconciliation."""
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from test_manager_ui import services

OUTPUT=Path(__file__).resolve().parents[2]/'acceptance/ai-runtime'

def test_inspector_authorization_races_and_keyboard(services):
    _,entry,_=services
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page()
        try:
            page.goto(f'http://127.0.0.1:{entry["roomPort"]}/ai-ui/conversation.html')
            page.evaluate('''async()=>{
              const {renderMarkdown,bindReferenceDetails}=await import('/ai-ui/pack.js');document.body.replaceChildren();
              const content=document.createElement('div');document.body.append(content);renderMarkdown(content,'[[entity:lamp@1]] [[entity:other@1]]');
              window.mode='ok';window.pending=[];window.allowed=true;window.calls=[];
              window.item=id=>({kind:'entity',id,revision:'1',label:id==='lamp'?'提灯':'另一个物品',visibility:'private',value:{name:'提灯',numbers:{hp:4},metadata:{note:'<img src=x onerror=alert(1)>'}}});
              window.inspector=bindReferenceDetails(content,async tokens=>{calls.push(tokens);if(mode==='stale')throw {code:'REFERENCE_STALE'};if(mode==='deny')throw {code:'NOT_VISIBLE'};
                if(mode==='slow')return new Promise(resolve=>pending.push(resolve));return {items:[item(tokens[0].split(':')[1].split('@')[0])]};},{valid:()=>allowed});
            }''')
            chip=page.locator('.reference-chip').first;chip.focus();chip.press('Enter')
            expect(page.get_by_role('dialog')).to_be_visible();expect(page.locator('h2')).to_have_text('提灯')
            expect(page.locator('.reference-value')).to_contain_text('生命');assert not page.locator('img').count()
            expect(page.get_by_role('dialog')).to_have_css('border-radius','16px')
            page.keyboard.press('Escape');expect(page.get_by_role('dialog')).not_to_be_visible();expect(chip).to_be_focused()
            page.evaluate("mode='stale'");chip.click();expect(page.get_by_role('status')).to_contain_text('引用已过期')
            assert not page.locator('.reference-value').inner_text()
            page.evaluate("mode='deny';inspector.refresh()");expect(page.get_by_role('status')).to_contain_text('无法读取')
            page.evaluate("()=>{mode='slow';inspector.open('[[entity:lamp@1]]');inspector.open('[[entity:other@1]]');}")
            page.evaluate("pending[1]({items:[item('other')]})");expect(page.locator('h2')).to_have_text('另一个物品')
            page.evaluate("pending[0]({items:[item('lamp')]})");expect(page.locator('h2')).to_have_text('另一个物品')
            page.evaluate("()=>{inspector.refresh();allowed=false;pending[2]({items:[item('other')]});}")
            expect(page.get_by_role('dialog')).not_to_be_visible()
            assert not page.locator('.reference-value').inner_text()
            page.evaluate("allowed=true;inspector.open('[[entity:lamp@1]]');inspector.destroy();pending[3]({items:[item('lamp')]})")
            assert not page.locator('.reference-details').count()
        finally:browser.close()

def test_chat_repeated_refresh_keeps_chips_and_dialog(services):
    _,entry,_=services
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1000,'height':800})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(f'http://127.0.0.1:{entry["roomPort"]}/ai-ui/conversation.html')
            page.evaluate('''async()=>{
              const {mountChat}=await import('/ai-ui/pack.js');document.body.replaceChildren();
              window.record={session:{sessionId:'s1',owner:'kp',accessLevel:'administrator',title:'庭院 NPC 设计',revision:1,renderMode:'markdown',archived:false},items:[
                {requestId:'r1',text:'查看提灯',response:'**提灯**可作为照明道具。\\n\\n- 对象：[[entity:lamp@1]]\\n- 状态：生命 4，可继续使用。',status:'review_ready'}]};
              window.resolutions=0;window.client={generation:1,connected:true,view:{accountId:'kp',role:'kp',authorityEpoch:1},subscribe:f=>{window.changed=f;return()=>{};},
                aiAccess:async()=>({canChat:true}),aiSessions:async()=>({items:[record.session]}),aiSession:async()=>structuredClone(record),
                aiReferences:async()=>({items:[]}),aiResolve:async()=>{resolutions++;return {items:[{kind:'entity',id:'lamp',revision:'1',label:'提灯',visibility:'kp',value:{name:'提灯',numbers:{hp:4},metadata:{description:'庭院守护者携带的照明道具'}}}]};}};
              window.chat=mountChat(document.body,client);await chat.refresh();await chat.select('s1');
            }''')
            chip=page.locator('.assistant .reference-chip');expect(chip).to_have_text('提灯')
            page.evaluate("window.original=[...document.querySelectorAll('div')].find(n=>n.shadowRoot?.querySelector('#history')).shadowRoot.querySelector('.assistant .reference-chip')")
            chip.click();expect(page.get_by_role('dialog')).to_be_visible();expect(page.locator('h2')).to_have_text('提灯')
            page.evaluate("window.mutations=[];new MutationObserver(m=>mutations.push(...m.map(x=>x.type))).observe(original,{childList:true,subtree:true,characterData:true});")
            page.evaluate("async()=>{for(let i=0;i<4;i++)await chat.select('s1');}")
            assert page.evaluate("original.isConnected && mutations.length===0")
            expect(page.get_by_role('dialog')).to_be_visible();expect(page.locator('h2')).to_have_text('提灯')
            page.evaluate("record.items[0].status='validating';chat.select('s1')")
            expect(page.locator('#history')).to_contain_text('正在校验');assert page.evaluate('original.isConnected && mutations.length===0')
            page.evaluate("record.items[0].status='review_ready';chat.select('s1')")
            expect(page.locator('#history')).to_contain_text('待审核');expect(page.get_by_role('dialog')).to_be_visible()
            page.screenshot(path=str(OUTPUT/'reference-details.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':840});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.get_by_role('button',name='关闭引用详情').click()
            page.evaluate("record.items.push({requestId:'r2',text:'继续',response:'后续回答',status:'review_ready'});chat.select('s1')")
            expect(page.locator('#history')).to_contain_text('后续回答');assert page.evaluate('original.isConnected')
            chip.click();page.evaluate("client.generation++;client.view.accountId='player';changed()")
            expect(page.get_by_role('dialog')).not_to_be_visible();expect(page.locator('#history')).to_be_empty()
            assert not page.locator('.reference-value').inner_text();page.evaluate('chat.destroy()');assert not errors,errors
        finally:browser.close()
