"""Real-browser semantic chat references in all three packaged views."""
import pytest
from playwright.sync_api import sync_playwright, expect
from test_manager_ui import services, allow_players
from test_embeds import login


@pytest.mark.parametrize('account',['kp','player1'])
@pytest.mark.parametrize('error_code',['AI_TASK_FAILED','PROVIDER_REQUEST_INVALID'])
def test_task_diagnostics_are_visible_only_in_keeper_conversation(services,account,error_code):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    allow_players(origin)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page();errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        try:
            page.goto(origin+'/ai-ui/conversation.html');login(page,account)
            def response(route):
                reply=route.fetch();data=reply.json()
                for item in data.get('items',[]):
                    # Deliberately also inject this into PL transport: role guard
                    # must still suppress diagnostics even with an extra field.
                    item.update(status='failed',error=error_code,diagnostics={
                        'schemaVersion':1,'stage':'tool_execute','turn':0,
                        'toolCalls':[{'name':'room_search_data','status':'completed'}],
                        'errors':[{'stage':'tool_execute','code':error_code,'exceptionType':'KeyError','httpStatus':400,
                            'frames':[{'module':'onlinecoc_ai.data_queries','function':'execute','line':1}]}]})
                route.fulfill(response=reply,json=data)
            page.route('**/api/v1/ai/sessions/*',response)
            page.locator('.new-chat').click();expect(page.locator('#status')).to_have_text('新会话已创建')
            page.locator('#text').fill('诊断显示验收');page.locator('#send').click()
            expect(page.locator('#history')).to_contain_text('诊断显示验收')
            if account=='kp':
                expect(page.locator('.task-error')).to_contain_text(error_code)
                page.locator('.task-diagnostics summary').click()
                expect(page.locator('.task-diagnostics')).to_contain_text('资料查询：已完成 1 次')
                expect(page.locator('.task-diagnostics')).to_contain_text('执行查询 · KeyError · '+error_code+' · HTTP 400')
                expect(page.locator('.task-diagnostics')).to_contain_text('onlinecoc_ai.data_queries.execute:1')
            else:
                expect(page.locator('.task-error,.task-diagnostics')).to_have_count(0)
            if error_code=='PROVIDER_REQUEST_INVALID':expect(page.locator('.error-detail')).to_contain_text('AI 服务商拒绝了请求参数')
            assert not errors,errors
        finally:browser.close()


@pytest.mark.parametrize('variant',['page','conversation','collapsible'])
def test_chat_evidence_reference_and_preview(services,variant):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    allow_players(origin)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page()
        try:
            page.goto(origin+'/ai-ui/'+variant+'.html');login(page,'kp')
            if variant=='collapsible':page.locator('.collapse-toggle').click()
            outcome=page.evaluate('''async()=>{
              const {AiClient}=await import('/ai-ui/client.js');const c=new AiClient();await c.resume();
              try{return await c.command('chat.message.send',{channelId:'general',text:'查询验收：观察提灯'});}finally{c.destroy();}
            }''')
            assert outcome['status']=='committed',outcome
            editor=page.locator('#text');editor.fill('/chat 查询验收')
            expect(page.locator('.reference-options [role=option]')).to_have_count(1);editor.press('Enter')
            expect(editor.locator('.reference-label')).to_have_text('查询验收：观察提灯')
            assert '[[chat:' not in editor.inner_text()
            page.locator('#preview').click();expect(page.locator('#reference-preview')).to_contain_text('查询验收：观察提灯')
            editor.locator('.reference-remove').click();expect(editor.locator('.reference-chip')).to_have_count(0)
            page.locator('#logout').click();expect(page.locator('#login')).to_be_visible()
        finally:browser.close()
