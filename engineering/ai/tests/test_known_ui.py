"""A2: long opaque snapshot tokens stay atomic and open authorized detail."""
from playwright.sync_api import sync_playwright,expect
import pytest
from test_manager_ui import services
from onlinecoc_ai.known_answers import reference_token


def test_known_snapshot_completion_atomic_chip_and_revoked_inspector(services):
    _,entry,_=services
    token=reference_token({'schemaVersion':1,'scopeId':'room-scope','id':'i'*200,'revision':'v'*200,'digest':'d'*64})
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page()
        try:
            page.goto(f'http://127.0.0.1:{entry["roomPort"]}/ai-ui/conversation.html')
            page.evaluate('''async token=>{
              const {renderMarkdown,hydrateReferences,bindReferenceDetails,referenceCommands,createReferenceEditor}=await import('/ai-ui/pack.js');
              document.body.replaceChildren();window.commands=referenceCommands('player');
              const content=document.createElement('div');document.body.append(content);renderMarkdown(content,'观察记录 · '+token);
              window.revoked=false;const item={kind:'knowledge',id:token.split(':')[1].split('@')[0],revision:'1',label:'庭院',visibility:'private',value:{mode:'observed_snapshot',observedAt:100,data:{description:'当时有一张空长椅'}}};
              window.resolve=async()=>{if(revoked)throw {code:'NOT_VISIBLE'};return {items:[item]};};
              await hydrateReferences(content,resolve);window.refreshLabels=()=>hydrateReferences(content,resolve);window.inspector=bindReferenceDetails(content,resolve);
              const input=document.createElement('div');input.id='edit';document.body.append(input);window.editor=createReferenceEditor(input,{resolveReferences:resolve});editor.setValue(token,[item]);
            }''',token)
            assert page.evaluate('commands.map(x=>x.kind)')==['knowledge']
            chip=page.locator('body > div').first.locator('.reference-chip')
            expect(chip).to_have_text('庭院');assert len(page.evaluate('editor.value'))==len(token)
            chip.click();expect(page.get_by_role('dialog')).to_be_visible()
            expect(page.get_by_role('status')).to_contain_text('观察记录')
            expect(page.locator('.reference-value')).to_contain_text('空长椅')
            page.evaluate('revoked=true;inspector.refresh()')
            expect(page.get_by_role('status')).to_contain_text('无法读取')
            assert not page.locator('.reference-value').inner_text()
            page.evaluate('refreshLabels()');expect(chip).to_have_text('不可用引用')
            page.get_by_role('button',name='关闭引用详情').click()
            page.locator('#edit .reference-remove').click();assert page.evaluate('editor.value')==''
        finally:browser.close()


def test_data_views_separate_player_and_administrator_and_avoid_raw_fallback(services):
    from pathlib import Path
    _,entry,_=services
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1100,'height':850})
        try:
            page.goto(f'http://127.0.0.1:{entry["roomPort"]}/ai-ui/conversation.html')
            page.evaluate('''async()=>{
              const {renderMarkdown,bindReferenceDetails}=await import('/ai-ui/pack.js');document.body.replaceChildren();
              const content=document.createElement('div');document.body.append(content);renderMarkdown(content,'[[entity:factory@1]]');
              window.level='player';window.data={entityId:'INTERNAL_ID',name:'奶酪工厂',actions:[{id:'factory',label:'检查器具',hint:'观察设备',choices:[{id:'inspect',label:'访问 Jack',process:'无需投骰；记录设备和人物回应。'}]}],clues:[{text:'提灯有刻字'}]};
              window.inspector=bindReferenceDetails(content,async()=>({items:[{kind:'entity',id:'factory',revision:'1',label:'奶酪工厂',value:data}]}),{audience:()=>level});
            }''')
            page.locator('.reference-chip').click()
            expect(page.locator('.reference-value')).to_contain_text('行动选项')
            expect(page.locator('.reference-value')).to_contain_text('处理说明')
            expect(page.locator('.reference-value')).not_to_contain_text('INTERNAL_ID')
            expect(page.locator('.reference-value pre')).to_have_count(0)
            page.screenshot(path=str(Path(__file__).resolve().parents[2]/'acceptance/ai-runtime/data-presentation-player.png'))
            page.evaluate("level='administrator';inspector.refresh()")
            expect(page.locator('.reference-value')).to_contain_text('INTERNAL_ID')
            expect(page.get_by_text('技术详情（原始数据）',exact=True)).to_be_visible()
            page.get_by_text('技术详情（原始数据）',exact=True).click()
            expect(page.locator('.reference-value pre')).to_contain_text('"actions"')
            page.screenshot(path=str(Path(__file__).resolve().parents[2]/'acceptance/ai-runtime/data-presentation-keeper.png'))
            page.evaluate("level='player';inspector.refresh()")
            expect(page.locator('.reference-value pre')).to_have_count(0)
            expect(page.locator('.reference-value')).not_to_contain_text('INTERNAL_ID')
            page.set_viewport_size({'width':390,'height':844})
            assert page.get_by_role('dialog').evaluate('el=>el.scrollWidth<=el.clientWidth')
        finally:browser.close()


@pytest.mark.parametrize('role,access',[('kp','administrator'),('kp','player'),('pl','player')])
def test_chat_evidence_and_preview_use_session_audience(services,role,access):
    from pathlib import Path
    from test_chat_polish import BOOT
    from onlinecoc_ai.known_answers import register,render
    _,entry,_=services
    record={'ref':{'schemaVersion':1,'scopeId':'scope-player','id':'factory','revision':'1','digest':'digest'},
        'label':'奶酪工厂','facetId':'scene','mode':'observed_snapshot','observedAt':100,
        'data':{'entityId':'INTERNAL_ID','name':'奶酪工厂','description':'观察时设备安静。',
            'clues':[{'text':'提灯有刻字'}],
            'actions':[{'label':'检查器具','choices':[{'label':'访问 Jack','process':'记录设备和人物回应。'}]}]}}
    pool={};issued=register(pool,[record]);text=render({'evidence':[issued[0]['evidenceId']],'next':'none'},pool)['text']
    token=reference_token(record['ref'])
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':580,'height':900})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(f'http://127.0.0.1:{entry["roomPort"]}/ai-ui/conversation.html')
            boot=BOOT.replace("view:{accountId:'kp',role:'kp',", "view:{accountId:"+repr('kp' if role=='kp' else 'player1')+",role:"+repr(role)+",")
            page.evaluate(boot,{'variant':'conversation','rows':0,'width':560})
            page.evaluate('''async ({role,access,record,text,token})=>{
              client.view.role=role;client.view.accountId=role==='kp'?'kp':'player1';
              records.s1.session.owner=client.view.accountId;records.s1.session.accessLevel=access;
              records.s1.items=[{requestId:'known',text:'整理我已经发现的线索与行动。',response:text,status:'review_ready'}];
              const ref={kind:'knowledge',id:token.split(':')[1].split('@')[0],revision:'1',label:record.label,visibility:'private',value:record};
              client.aiResolve=async()=>({items:[ref]});await ui.select('s1');ui.setDraft(token,[ref]);
            }''',{'role':role,'access':access,'record':record,'text':text,'token':token})
            history=page.locator('#history')
            expect(history).to_contain_text('已知线索');expect(history).to_contain_text('行动选项')
            expect(history).not_to_contain_text('INTERNAL_ID');expect(history).not_to_contain_text('"choices"')
            expect(history.locator('.reference-chip')).to_have_text('奶酪工厂')
            assert history.locator('ul li ul').count()>0
            if role=='pl':page.screenshot(path=str(Path(__file__).resolve().parents[2]/'acceptance/ai-runtime/data-presentation-chat.png'))
            page.locator('#preview').click()
            preview=page.locator('#reference-preview');expect(preview).to_be_visible()
            expect(preview).to_contain_text('访问 Jack');expect(preview.locator('pre')).to_have_count(0)
            if access=='administrator':expect(preview).to_contain_text('INTERNAL_ID')
            else:expect(preview).not_to_contain_text('INTERNAL_ID')
            history.locator('.reference-chip').click()
            expect(page.locator('.reference-value')).to_contain_text('访问 Jack')
            expect(page.locator('.reference-value pre')).to_have_count(1 if access=='administrator' else 0)
            page.get_by_role('button',name='关闭引用详情').click()
            assert not errors,errors
        finally:browser.close()
