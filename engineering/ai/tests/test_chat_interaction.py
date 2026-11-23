"""Real Edge regressions for live updates, reader activity and native composition."""
from pathlib import Path
import json

import pytest
from playwright.sync_api import expect
from test_chat_polish import BOOT, browser_page
from test_manager_ui import services

OUTPUT = Path(__file__).resolve().parents[2] / 'acceptance/ai-chat-interaction'


def boot(page, variant='page'):
    page.evaluate(BOOT, {'rows': 24, 'variant': variant})
    page.locator('#history').evaluate("el=>{window.historyElement=el;window.chatRoot=el.getRootNode();}")
    page.locator('#text').evaluate('el=>window.originalEditor=el')
    page.evaluate(r"""()=>{
      window.updateChat=async()=>{records.s1.items.at(-1).response+='\n\n新增进度。';await ui.select('s1');};
      window.bottomGap=()=>historyElement.scrollHeight-historyElement.clientHeight-historyElement.scrollTop;
    }""")


@pytest.mark.parametrize('variant', ['page', 'conversation', 'collapsible'])
def test_idle_update_follows_latest_from_long_history(browser_page, variant):
    page = browser_page; boot(page, variant)
    page.evaluate('historyElement.scrollTop=140')
    page.wait_for_timeout(1100)
    page.evaluate('updateChat()')
    assert page.evaluate('bottomGap()') < 3


@pytest.mark.parametrize('event', ['wheel', 'keydown', 'pointerdown', 'touchstart', 'input'])
def test_recent_activity_preserves_position_then_expires(browser_page, event):
    page = browser_page; boot(page)
    page.evaluate(r"""event=>{
      historyElement.scrollTop=140;
      const target=event==='input'?originalEditor:historyElement;
      const constructors={wheel:WheelEvent,keydown:KeyboardEvent,pointerdown:PointerEvent,touchstart:TouchEvent,input:InputEvent};
      target.dispatchEvent(new constructors[event](event,{bubbles:true,key:'ArrowUp',pointerId:5}));
    }""", event)
    page.evaluate('updateChat()')
    assert abs(page.evaluate('historyElement.scrollTop') - 140) < 3
    page.evaluate("historyElement.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,composed:true,pointerId:5}));historyElement.dispatchEvent(new TouchEvent('touchend',{bubbles:true,composed:true}))")
    page.wait_for_timeout(1100)
    page.evaluate('updateChat()')
    assert page.evaluate('bottomGap()') < 3


def test_async_reference_completion_respects_new_activity(browser_page):
    page = browser_page; boot(page)
    page.evaluate("holdRefs=true;updateChat()")
    page.wait_for_function('pendingRefs.length>0')
    page.locator('#history').hover(); page.mouse.wheel(0, -600)
    page.wait_for_timeout(200)
    before = page.evaluate('historyElement.scrollTop')
    assert page.evaluate('bottomGap()') > 100
    page.evaluate('pendingRefs.forEach(r=>r());holdRefs=false')
    page.wait_for_timeout(100)
    assert abs(page.evaluate('historyElement.scrollTop') - before) < 3


def test_updates_keep_editor_caret_and_native_composition(browser_page):
    page = browser_page; boot(page)
    editor = page.locator('#text'); editor.fill('前文后文')
    editor.evaluate("el=>{const r=document.createRange();r.setStart(el.firstChild,2);r.collapse(true);const s=el.getRootNode().getSelection();s.removeAllRanges();s.addRange(r);window.editorText=el.firstChild;}")
    page.evaluate("async()=>{for(let i=0;i<4;i++){await ui.refresh();await updateChat();}}")
    assert editor.evaluate('el=>el===originalEditor&&el.firstChild===editorText&&el.getRootNode().activeElement===el')
    assert editor.evaluate('el=>el.getRootNode().getSelection().anchorOffset') == 2
    page.keyboard.insert_text('插入'); expect(editor).to_have_text('前文插入后文')
    cdp = page.context.new_cdp_session(page)
    cdp.send('Input.imeSetComposition', {'text': '测试', 'selectionStart': 2, 'selectionEnd': 2})
    expect(editor).to_have_text('前文插入测试后文')
    page.evaluate('historyElement.scrollTop=140')
    page.wait_for_timeout(1100)
    page.evaluate('updateChat()')
    assert abs(page.evaluate('historyElement.scrollTop') - 140) < 3
    cdp.send('Input.insertText', {'text': '测试'})
    page.keyboard.insert_text('完成'); expect(editor).to_have_text('前文插入测试完成后文')
    assert page.evaluate('calls.length') == 0
    OUTPUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUTPUT / 'long-history-editor.png'), full_page=True)
    (OUTPUT / 'browser.json').write_text(json.dumps({'browser': page.context.browser.version, 'nativeComposition': True, 'unchangedEditor': True}, ensure_ascii=False, indent=2), encoding='utf-8')


def test_reader_anchor_and_selected_answer_survive_changed_rows(browser_page):
    page = browser_page; boot(page)
    page.evaluate(r"""()=>{
      const answer=chatRoot.querySelectorAll('.assistant')[8];
      historyElement.scrollTop=answer.offsetTop-100;
      window.readingAnswer=answer;window.readingBody=answer.children[1];
      const text=readingBody.querySelector('p').firstChild,r=document.createRange();r.setStart(text,0);r.setEnd(text,5);
      const s=chatRoot.getSelection();s.removeAllRanges();s.addRange(r);
      window.selectedAnswerText=s.toString();window.anchorTop=answer.getBoundingClientRect().top;
      historyElement.dispatchEvent(new KeyboardEvent('keydown',{bubbles:true,key:'Shift'}));
      records.s1.items[0].response+='\n\n'+('上方新增内容。'.repeat(80));
      records.s1.items[8].task={events:[{eventId:'new',kind:'read',status:'completed',message:'读取完成'}]};
    }""")
    page.evaluate("ui.select('s1')")
    assert page.evaluate('readingAnswer.isConnected&&readingBody.isConnected')
    assert page.evaluate('chatRoot.getSelection().toString()') == page.evaluate('selectedAnswerText')
    assert abs(page.evaluate('readingAnswer.getBoundingClientRect().top-anchorTop')) < 3


def test_session_switch_discards_old_read_without_overwriting_current_draft(browser_page):
    page = browser_page; boot(page)
    page.locator('#text').fill('第一会话草稿')
    page.evaluate(r"""()=>{
      records.s2={session:{...records.s1.session,sessionId:'s2',title:'第二会话'},items:[]};
      const read=client.aiSession;client.aiSession=async id=>{if(id==='s1')return new Promise(r=>window.finishRead=async()=>r(await read(id)));return read(id);};
      ui.select('s1');
    }""")
    page.evaluate("ui.select('s2')")
    page.locator('#text').fill('第二会话草稿')
    page.evaluate('finishRead()')
    expect(page.locator('#rename')).to_have_value('第二会话')
    expect(page.locator('#text')).to_have_text('第二会话草稿')
    assert page.locator('#text').evaluate('el=>el===originalEditor&&el.getRootNode().activeElement===el')
    page.keyboard.insert_text('仍可输入')
    expect(page.locator('#text')).to_have_text('第二会话草稿仍可输入')


@pytest.mark.parametrize('gesture', ['mouse', 'touch'])
def test_native_held_gesture_and_release_outside_chat(browser_page, gesture):
    page = browser_page; boot(page)
    page.evaluate('historyElement.scrollTop=140')
    box = page.locator('#history').bounding_box()
    x, y = box['x'] + 20, box['y'] + 80
    cdp = page.context.new_cdp_session(page)
    if gesture == 'mouse':
        page.mouse.move(x, y); page.mouse.down()
    else:
        cdp.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
    page.wait_for_timeout(1100)
    page.evaluate('updateChat()')
    assert abs(page.evaluate('historyElement.scrollTop') - 140) < 3
    if gesture == 'mouse':
        page.mouse.move(2, 2); page.mouse.up()
    else:
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    page.wait_for_timeout(1100)
    page.evaluate('updateChat()')
    assert page.evaluate('bottomGap()') < 3


def test_actual_poll_keeps_typing_and_selection(browser_page):
    page = browser_page; boot(page)
    page.evaluate("records.s1.items.at(-1).status='generating';ui.select('s1')")
    editor = page.locator('#text'); editor.fill('持续输入')
    page.evaluate(r"""()=>{
      window.editableMutations=[];new MutationObserver(items=>editableMutations.push(...items.map(i=>i.attributeName))).observe(originalEditor,{attributes:true,attributeFilter:['contenteditable']});
      records.s1.items.at(-1).response+='\n\n真实轮询回包';historyElement.scrollTop=140;
    }""")
    for _ in range(9):
        page.keyboard.insert_text('中'); page.wait_for_timeout(150)
    expect(page.locator('#history')).to_contain_text('真实轮询回包')
    expect(editor).to_have_text('持续输入' + '中' * 9)
    assert editor.evaluate('el=>el===originalEditor&&el.getRootNode().activeElement===el')
    assert abs(page.evaluate('historyElement.scrollTop') - 140) < 3
    assert page.evaluate('editableMutations') == []


def test_typing_while_new_session_loads_returns_to_original_draft(browser_page):
    page = browser_page; boot(page)
    page.locator('#text').fill('旧会话')
    page.evaluate(r"""()=>{
      records.s2={session:{...records.s1.session,sessionId:'s2',title:'第二会话'},items:[]};
      const read=client.aiSession;client.aiSession=async id=>id==='s2'?new Promise(r=>window.finishNewRead=async()=>r(await read(id))):read(id);
      ui.select('s2');
    }""")
    page.keyboard.insert_text('加载期间补充')
    page.evaluate('finishNewRead()');expect(page.locator('#rename')).to_have_value('第二会话')
    page.evaluate("ui.select('s1')")
    expect(page.locator('#text')).to_have_text('旧会话加载期间补充')
