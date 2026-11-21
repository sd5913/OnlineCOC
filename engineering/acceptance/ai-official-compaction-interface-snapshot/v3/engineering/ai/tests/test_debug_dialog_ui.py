"""Real Edge tests for the top-level debug modal; static UI and deterministic transport."""
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from threading import Thread
import pytest
from playwright.sync_api import sync_playwright, expect

@pytest.fixture
def static_ui():
    SimpleHTTPRequestHandler.extensions_map={**SimpleHTTPRequestHandler.extensions_map,'.js':'text/javascript','.css':'text/css'}
    folder=Path(__file__).parents[1]/'web/components'
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(folder)))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{server.server_port}'
    finally:server.shutdown();server.server_close();thread.join()

@pytest.mark.parametrize('width',[1100,390])
def test_header_debug_modal_scope_export_close_and_identity(static_ui,width):
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport={'width':width,'height':850},accept_downloads=True);errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(static_ui+'/')
            page.evaluate("""async()=>{
                document.body.innerHTML='<div id="test" style="height:800px"></div>';window.calls=[];window.listeners=[];
                const session={sessionId:'s1',title:'Review session',owner:'kp',accessLevel:'administrator',revision:1,archived:false,historyTurns:4};
                const access={canChat:true,allowPlayerChat:true,allowPlayerRequests:true};
                window.client={connected:true,generation:1,view:{roomId:'room',accountId:'kp',role:'kp',authorityEpoch:'epoch'},
                    subscribe:fn=>{listeners.push(fn);return()=>{};},onChange:fn=>{listeners.push(fn);return()=>{};},
                    aiSessions:async()=>({items:[session],access}),aiAccess:async()=>access,
                    aiSession:async()=>({session,items:[{requestId:'r1',status:'review_ready',text:'Original request',response:'Prepared advice',createdAt:1}]}),
                    aiResolve:async()=>({items:[]}),aiDebug:async options=>{calls.push(options);return {schemaVersion:1,items:[]};}};
                const {mountAIConversation}=await import('./pack.js');window.panel=mountAIConversation(document.querySelector('#test'),client);await panel.select('s1');
            }""")
            button=page.locator('.view-header .debug-open');expect(button).to_be_enabled()
            assert page.locator('#history .ai-debug-tools').count()==0
            assert page.locator('.session-debug').count()==0
            button.click();dialog=page.get_by_role('dialog',name='引用与调试');expect(dialog).to_be_visible()
            expect(dialog.get_by_label('调试范围')).to_have_value('')
            assert not dialog.get_by_role('checkbox').is_checked()
            with page.expect_download():dialog.get_by_role('button',name='导出调试 JSON').click()
            assert page.evaluate('calls[0]')=={'sessionId':'s1','includeContent':False}
            dialog.get_by_label('调试范围').select_option('r1');dialog.get_by_role('checkbox').check()
            with page.expect_download():dialog.get_by_role('button',name='导出调试 JSON').click()
            assert page.evaluate('calls[1]')=={'sessionId':'s1','requestId':'r1','includeContent':True}
            box=dialog.bounding_box();assert box['x']>=0 and box['x']+box['width']<=width+1
            page.screenshot(path=str(Path(__file__).parents[2]/'acceptance/ai-runtime'/f'debug-modal-{width}.png'))
            page.keyboard.press('Escape');expect(dialog).not_to_be_visible();expect(button).to_be_focused()
            button.click();expect(dialog.get_by_role('checkbox')).not_to_be_checked()
            page.evaluate("client.connected=false;client.generation++;for(const fn of listeners)fn()")
            expect(page.get_by_role('dialog',name='引用与调试')).to_have_count(0)
            assert len(page.evaluate('calls'))==2
            assert not errors,errors
        finally:browser.close()


def test_failure_guidance_and_retry_do_not_replay_completed_work(static_ui):
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page()
        try:
            page.goto(static_ui+'/')
            page.evaluate("""async()=>{
                document.body.innerHTML='<div id="test" style="height:800px"></div>';window.commands=[];
                const session={sessionId:'s1',title:'Recovery',owner:'kp',accessLevel:'administrator',revision:1,archived:false};
                const access={canChat:true};
                const items=[
                    {requestId:'blocked',status:'blocked',text:'Prepare configuration',proposalId:'p1',error:'RULE_INVALID'},
                    {requestId:'stale',status:'stale',text:'Read fresh evidence',error:'SOURCE_STALE'},
                    {requestId:'done',status:'completed',text:'Already executed',error:'SOURCE_STALE'}];
                const client={connected:true,generation:1,view:{roomId:'room',accountId:'kp',role:'kp'},
                    subscribe:()=>()=>{},onChange:()=>()=>{},aiSessions:async()=>({items:[session],access}),
                    aiAccess:async()=>access,aiSession:async()=>({session,items}),aiResolve:async()=>({items:[]}),
                    aiCommand:async(...args)=>{commands.push(args);throw new Error('Unexpected automatic command');}};
                const {mountAIConversation}=await import('./pack.js');window.panel=mountAIConversation(document.querySelector('#test'),client);await panel.select('s1');
            }""")
            blocked=page.locator('[data-status=blocked]')
            expect(blocked).to_contain_text('A/B/C')
            expect(blocked).to_contain_text('当前未发布')
            expect(blocked.get_by_role('button',name='查看配置裁决')).to_be_enabled()
            blocked.get_by_role('button',name='编辑后重试').click()
            expect(page.locator('#text')).to_have_text('Prepare configuration')
            expect(page.locator('#status')).to_contain_text('不会自动重复执行')
            stale=page.locator('[data-status=stale]')
            expect(stale).to_contain_text('重新读取相关资料')
            stale.get_by_role('button',name='编辑后重试').click()
            expect(page.locator('#text')).to_have_text('Read fresh evidence')
            completed=page.locator('[data-status=completed]')
            expect(completed).to_contain_text('勿重复执行')
            expect(completed.get_by_role('button',name='编辑后重试')).to_have_count(0)
            assert page.evaluate('commands')==[]
        finally:browser.close()
