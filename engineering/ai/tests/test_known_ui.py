"""A2: long opaque snapshot tokens stay atomic and open authorized detail."""
from playwright.sync_api import sync_playwright,expect
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
