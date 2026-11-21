"""Real browser acceptance for command completion and atomic semantic references."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from test_manager_ui import services


def test_prototype_commands_semantic_tokens_and_atomic_editing(services):
    origin,_,_=services
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':960});errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        try:
            page.goto(origin+'/prototype.html')
            editor=page.locator('#chat #text');chips=editor.locator('.reference-chip')
            editor.fill('/')
            expect(page.locator('#chat').locator('#completion').get_by_role('option')).to_have_count(7)
            editor.fill('/en')
            expect(page.locator('#chat').locator('#completion').get_by_role('option')).to_have_count(1)
            expect(page.locator('#chat').locator('#completion').get_by_role('option')).to_contain_text('/entity')
            editor.press('Tab')
            expect(page.locator('#chat').locator('#completion').get_by_role('option')).to_contain_text('旅行提灯')
            editor.press('Enter')
            expect(chips).to_have_count(1)
            expect(chips.locator('.reference-label')).to_have_text('旅行提灯')
            assert '[[entity:' not in editor.inner_text()
            assert chips.get_attribute('data-token')=='[[entity:travel-lantern@3]]'
            # Undo and redo insert/remove the complete reference, including its hidden identity.
            editor.press('Control+z');expect(chips).to_have_count(0)
            editor.press('Control+y');expect(chips).to_have_count(1)
            editor.press('Backspace');expect(chips).to_have_count(0)
            assert '[[' not in editor.inner_text()
            page.locator('#insert').click();expect(chips).to_have_count(1)
            # Deleting just before a chip removes the whole reference, not its name letters.
            editor.evaluate("el=>{const r=document.createRange();r.setStartBefore(el.querySelector('.reference-chip'));r.collapse(true);const s=el.getRootNode().getSelection();s.removeAllRanges();s.addRange(r);el.focus();}")
            editor.press('Delete');expect(chips).to_have_count(0)
            expect(editor).to_contain_text('我想改良')
            page.locator('#insert').click()
            editor.get_by_role('button',name='移除引用：旅行提灯').click();expect(chips).to_have_count(0)
            page.locator('#insert').click()
            # A deliberately partial selection inside a chip expands to the complete token on cut.
            clipboard=editor.evaluate("""el=>{
              const text=el.querySelector('.reference-label').firstChild,r=document.createRange();r.setStart(text,1);r.setEnd(text,2);
              const s=el.getRootNode().getSelection();s.removeAllRanges();s.addRange(r);
              const data=new DataTransfer();el.dispatchEvent(new ClipboardEvent('cut',{clipboardData:data,bubbles:true,cancelable:true}));
              window.referenceClipboard=data;return {plain:data.getData('text/plain'),wire:data.getData('application/x-onlinecoc-ai-references')};
            }""")
            assert clipboard=={'plain':'旅行提灯','wire':'[[entity:travel-lantern@3]]'}
            expect(chips).to_have_count(0)
            editor.evaluate("el=>el.dispatchEvent(new ClipboardEvent('paste',{clipboardData:window.referenceClipboard,bubbles:true,cancelable:true}))")
            expect(chips).to_have_count(1)
            editor.evaluate("el=>{const text=el.querySelector('.reference-label').firstChild,r=document.createRange();r.setStart(text,1);r.setEnd(text,2);const s=el.getRootNode().getSelection();s.removeAllRanges();s.addRange(r);}")
            editor.press('x');expect(chips).to_have_count(0)
            expect(editor).to_contain_text('我想改良 x')
            # Completion replaces only the command at the cursor, preserving the suffix.
            editor.fill('前文 /en 后文')
            editor.evaluate("el=>{const text=[...el.childNodes].find(n=>n.nodeType===3&&n.data.includes('/en'));const r=document.createRange();r.setStart(text,6);r.collapse(true);const s=el.getRootNode().getSelection();s.removeAllRanges();s.addRange(r);el.dispatchEvent(new Event('mouseup'));}")
            expect(page.locator('#chat').locator('#completion').get_by_role('option')).to_have_count(1)
            editor.press('Enter');expect(page.locator('#chat').locator('#completion').get_by_role('option')).to_contain_text('旅行提灯')
            editor.press('Enter');expect(chips).to_have_count(1)
            expect(editor).to_contain_text('后文')
            # IME composition must not accept an option or turn Enter into a command.
            editor.fill('/en');expect(page.locator('#chat').locator('#completion').get_by_role('option')).to_have_count(1)
            editor.evaluate("el=>{el.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true}));el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',isComposing:true,bubbles:true,cancelable:true}));}")
            assert editor.inner_text()=='/en'
            editor.evaluate("el=>el.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true,data:'实体'}))")
            page.locator('#insert').click();page.locator('#chat #send').click()
            expect(page.locator('#chat #history .reference-label')).to_have_text('旅行提灯')
            expect(page.locator('#session-list')).not_to_contain_text('[[')
            expect(page.locator('#checks')).to_be_visible()
            page.locator('#insert').click()
            page.screenshot(path=str(Path(__file__).resolve().parents[2]/'acceptance/ai-runtime/reference-ui-semantic.png'),full_page=True)
            page.locator('#role').select_option('player')
            editor.fill('/');expect(page.locator('#chat').locator('#completion').get_by_role('option')).to_have_count(1)
            assert page.locator('#chat').locator('#completion').get_by_role('option').filter(has_text='/data').count()==0
            assert not errors,errors
        finally:browser.close()


def test_reference_editor_serialization_unavailable_and_late_labels(services):
    origin,_,_=services
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page()
        try:
            page.goto(origin+'/prototype.html')
            page.evaluate("""async()=>{
              const {createReferenceEditor}=await import('/components/index.js');
              const el=document.createElement('div');el.id='test-editor';document.body.append(el);
              window.refPending=[];window.refEditor=createReferenceEditor(el,{resolveReferences:tokens=>new Promise(resolve=>refPending.push({tokens,resolve}))});
              refEditor.setValue('改良 [[entity:travel-lantern@3]] 好吗');
            }""")
            editor=page.locator('#test-editor')
            assert page.evaluate('refEditor.value')=='改良 [[entity:travel-lantern@3]] 好吗'
            page.evaluate("refPending.shift().resolve({items:[{kind:'entity',id:'travel-lantern',revision:'3',label:'<img src=x onerror=alert(1)>'}]})")
            expect(editor.locator('.reference-label')).to_have_text('<img src=x onerror=alert(1)>')
            assert editor.locator('img').count()==0
            # Pasting plain HTML cannot create active content or fabricated chip DOM.
            editor.evaluate("el=>{const data=new DataTransfer();data.setData('text/plain','<script>bad</script>');data.setData('text/html','<img src=x onerror=alert(1)>');el.dispatchEvent(new ClipboardEvent('paste',{clipboardData:data,bubbles:true,cancelable:true}));}")
            assert editor.locator('script,img').count()==0
            page.evaluate("""()=>{
              document.getElementById('test-editor').focus();
              refEditor.setValue('[[entity:a@1]][[entity:b@1]]',[{kind:'entity',id:'a',revision:'1',label:'甲'},{kind:'entity',id:'b',revision:'1',label:'乙'}]);
              document.getElementById('test-editor').dispatchEvent(new InputEvent('beforeinput',{inputType:'deleteContentBackward',bubbles:true,cancelable:true}));
            }""")
            assert page.evaluate('refEditor.value')=='[[entity:a@1]]'
            expect(editor.locator('.reference-label')).to_have_text('甲')
            # A response arriving after replacement or destruction cannot restore a private label.
            page.evaluate("refEditor.setValue('[[entity:old@1]]');refEditor.setValue('安全草稿');refPending.shift().resolve({items:[{kind:'entity',id:'old',revision:'1',label:'过期私密名称'}]})")
            expect(editor).to_have_text('安全草稿')
            page.evaluate("refEditor.setValue('[[entity:old@1]]');refEditor.destroy();refPending.shift().resolve({items:[{kind:'entity',id:'old',revision:'1',label:'过期私密名称'}]})")
            expect(editor).to_have_text('')
            draft=page.locator('#chat #text');draft.fill('参考 [[entity:travel-lantern@2]]')
            expect(draft.locator('.reference-label')).to_have_text('已过期引用')
            assert '[[' not in draft.inner_text()
        finally:browser.close()
