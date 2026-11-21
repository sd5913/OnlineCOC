"""Real browser source cards and explicit diagnostic export."""
from playwright.sync_api import sync_playwright,expect
from test_manager_ui import services

def test_source_card_and_export_opt_in_guard(services):
    _,entry,_=services
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(accept_downloads=True);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(f'http://127.0.0.1:{entry["roomPort"]}/ai-ui/conversation.html')
            page.evaluate("""async()=>{
              const {appendDebugTools,appendReviewSource}=await import('/ai-ui/pack.js');
              document.body.replaceChildren();window.calls=[];window.alive=true;
              const client={view:{roomId:'test-room'},aiDebug:async options=>{calls.push(options);return {schemaVersion:1,items:[]};}};
              const target=document.createElement('section');document.body.append(target);
              appendReviewSource(target,{kind:'package',title:'原申请',requestedBy:'player1',summary:'我希望获得火焰剑',id:'one'},{onOpenSource:source=>window.opened=source.id});
              appendDebugTools(target,client,{requestId:'one'},{valid:()=>alive});
            }""")
            page.get_by_text('来源 · 原申请 · player1').click()
            expect(page.get_by_text('我希望获得火焰剑')).to_be_visible()
            page.get_by_role('button',name='查看原裁决').click();assert page.evaluate('opened')=='one'
            page.get_by_text('引用与调试',exact=True).click()
            page.evaluate("Object.defineProperty(navigator,'clipboard',{value:undefined,configurable:true});document.execCommand=()=>false")
            page.get_by_role('button',name='复制定位').click()
            expect(page.get_by_label('可复制的调试定位')).to_have_value('{"roomId":"test-room","requestId":"one"}')
            expect(page.get_by_role('status')).to_contain_text('Ctrl+C')
            assert page.get_by_label('可复制的调试定位').evaluate('(e)=>e.selectionEnd-e.selectionStart===e.value.length')
            with page.expect_download():page.get_by_role('button',name='导出调试 JSON').click()
            assert page.evaluate('calls[0]')=={'requestId':'one','includeContent':False}
            page.get_by_role('checkbox').check()
            with page.expect_download():page.get_by_role('button',name='导出调试 JSON').click()
            assert page.evaluate('calls[1].includeContent') is True
            page.evaluate('alive=false');page.get_by_role('button',name='导出调试 JSON').click();assert page.evaluate('calls.length')==2
            assert not errors,errors
        finally:browser.close()
