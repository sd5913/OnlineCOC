"""Chat UX acceptance: real DOM, bounded embeds and delayed writes/reads."""
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright, expect
from test_manager_ui import services

OUTPUT=Path(__file__).resolve().parents[2]/'acceptance/ai-runtime'
BOOT=r'''async ({variant='page',width=1100,rows=0})=>{
 const api=await import('/ai-ui/pack.js');document.body.replaceChildren();document.body.style.cssText='margin:0;background:#f7f8f6';
 const target=document.createElement('div');target.id='demo';target.style.cssText=`width:min(${width}px,100vw);height:calc(100dvh - 24px);margin:12px auto`;document.body.append(target);
 window.records={s1:{session:{sessionId:'s1',owner:'kp',accessLevel:'administrator',title:'庭院向导 · 方案讨论',revision:1,renderMode:'formatted',showDiagnostics:false,archived:false},items:[]}};
 for(let i=0;i<rows;i++)records.s1.items.push({requestId:'r'+i,text:'第 '+(i+1)+' 轮：请整理庭院向导的设计。',response:'### 庭院里的向导\n\n先确定角色动机，再选择与玩家互动的方式。\n\n- **身份**：守院人\n- **线索**：提灯上的刻字\n\n| 项目 | 建议 |\n| --- | --- |\n| 位置 | 庭院 |\n| 态度 | 友好 |\n\n参考 [[entity:lamp@1]]。',status:'review_ready'});
 window.calls=[];window.rejectSubmit=false;window.holdSend=false;window.holdRefs=false;window.pendingRefs=[];
 window.client={generation:1,connected:true,view:{accountId:'kp',role:'kp',authorityEpoch:1},subscribe:f=>()=>{},
 aiAccess:async()=>({canChat:true}),aiSessions:async()=>({items:Object.values(records).map(r=>r.session)}),aiSession:async id=>structuredClone(records[id]),
 aiReferences:async()=>({items:[{kind:'entity',id:'lamp',revision:'1',label:'提灯',visibility:'kp'}]}),
 aiResolve:async()=>{const result={items:[{kind:'entity',id:'lamp',revision:'1',label:'提灯',visibility:'kp',value:{name:'提灯'}}]};if(holdRefs)return new Promise(r=>pendingRefs.push(()=>r(result)));return result;},
 aiCommand:async(op,args)=>{calls.push({op,args});let result={};
 if(op==='ai.session.create'){result={...records.s1.session,sessionId:'s'+(Object.keys(records).length+1),title:args.title};records[result.sessionId]={session:result,items:[]};}
 if(op==='ai.session.submit'){if(rejectSubmit)return {status:'rejected',code:'CONNECTION_FAILED'};if(holdSend)await new Promise(r=>window.finishSend=r);records[args.sessionId].items.push({requestId:'sent'+calls.length,text:args.text,response:'已收到你的需求。',status:'review_ready'});result={requestId:'sent',taskId:'task'};}
 if(op==='ai.request.cancel')for(const r of Object.values(records))for(const item of r.items)if(item.requestId===args.requestId)item.status='cancelled';
 return {status:'committed',result};}};
 window.ui=(variant==='page'?api.mountAIPage:variant==='conversation'?api.mountAIConversation:api.mountAICollapsible)(target,client,{open:true,review:false});
 await ui.refresh();if(rows)await ui.select('s1');
}'''


@pytest.fixture
def browser_page(services):
    _,entry,_=services
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport={'width':1240,'height':920});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(f'http://127.0.0.1:{entry["roomPort"]}/ai-ui/conversation.html')
        yield page
        browser.close()
        assert not errors,errors


def test_composer_failure_keyboard_and_inflight_draft(browser_page):
    page=browser_page;page.evaluate(BOOT,{'rows':0})
    expect(page.locator('.starter')).to_have_count(3)
    expect(page.locator('#send')).to_be_disabled()
    page.locator('.starter').first.click();assert page.evaluate('calls.length')==0
    page.screenshot(path=str(OUTPUT/'chat-polish-empty.png'),full_page=True)
    page.evaluate('rejectSubmit=true');page.locator('#text').fill('创建失败仍保留的草稿');page.locator('#send').click()
    expect(page.locator('#status')).to_contain_text('CONNECTION_FAILED')
    expect(page.locator('#text')).to_have_text('创建失败仍保留的草稿')
    page.evaluate('rejectSubmit=false;holdSend=true');page.locator('#send').click()
    page.wait_for_function('!!window.finishSend');page.locator('#text').fill('发送期间写的下一条草稿');page.evaluate('finishSend()')
    expect(page.locator('#history')).to_contain_text('已收到你的需求')
    expect(page.locator('#text')).to_have_text('发送期间写的下一条草稿')
    page.evaluate('holdSend=false');page.locator('#text').fill('/entity');page.locator('#text').press('Enter')
    expect(page.locator('#text')).to_have_text('/entity ')
    page.locator('#text').fill('中文输入法');before=page.evaluate('calls.length')
    page.locator('#text').evaluate("el=>el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',isComposing:true,bubbles:true}))")
    assert page.evaluate('calls.length')==before
    page.locator('#send-mode').select_option('ctrl');page.locator('#text').press('Enter');assert page.evaluate('calls.length')==before
    page.locator('#text').fill('键盘发送');page.locator('#text').press('Control+Enter')
    expect(page.locator('#history')).to_contain_text('键盘发送')


def test_reading_anchor_directory_and_stop(browser_page):
    page=browser_page;page.evaluate(BOOT,{'rows':12})
    history=page.locator('#history');expect(page.locator('.assistant')).to_have_count(12)
    page.locator('.session-link').focus()
    page.evaluate('window.beforeLink=document.querySelector("#demo").firstElementChild.shadowRoot.querySelector(".session-link")')
    history.evaluate('el=>el.scrollTop=100');expect(page.locator('#latest')).to_be_visible()
    page.evaluate("async()=>{for(let i=0;i<3;i++){await ui.refresh();await ui.select('s1');}}")
    assert page.evaluate('beforeLink.isConnected')
    assert history.evaluate('el=>el.scrollTop')<150
    page.evaluate("holdRefs=true;records.s1.items.push({requestId:'late',text:'新增信息',response:'[[entity:lamp@1]]',status:'review_ready'});ui.select('s1')")
    page.wait_for_function('pendingRefs.length>0');history.evaluate('el=>el.scrollTop=160')
    page.evaluate('pendingRefs.forEach(r=>r());holdRefs=false')
    assert history.evaluate('el=>el.scrollTop')<220
    page.locator('#latest').click();expect(page.locator('#latest')).to_be_hidden()
    page.evaluate("records.s1.items.push({requestId:'active',text:'继续',status:'generating'});ui.select('s1')")
    expect(page.locator('#stop')).to_be_visible();page.locator('#text').fill('稍后再发的草稿');page.locator('#stop').click()
    expect(page.locator('#history')).to_contain_text('已取消');expect(page.locator('#history')).not_to_contain_text('正在整理资料并生成回答');expect(page.locator('#text')).to_have_text('稍后再发的草稿')
    assert page.evaluate("calls.filter(c=>c.op==='ai.request.cancel').length")==1
    page.evaluate("records.s1.session.archived=true;ui.select('s1')")
    expect(page.locator('#text')).to_have_attribute('aria-disabled','true')


@pytest.mark.parametrize('variant',['page','conversation','collapsible'])
def test_embed_readability_at_container_width(browser_page,variant):
    page=browser_page;page.evaluate(BOOT,{'variant':variant,'rows':2,'width':1100})
    expect(page.locator('.assistant')).to_have_count(2)
    page.screenshot(path=str(OUTPUT/f'chat-polish-{variant}.png'),full_page=True)
    # Embed can be narrow inside a wide desktop, without changing the viewport.
    page.locator('#demo').evaluate("el=>el.style.width='390px'")
    expect(page.locator('#send')).to_be_visible()
    if variant=='page':expect(page.locator('.view-sidebar')).to_be_hidden()
    assert page.locator('#demo').evaluate('el=>el.scrollWidth<=el.clientWidth')
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(OUTPUT/f'chat-polish-{variant}-mobile.png'),full_page=True)


def test_delayed_send_does_not_switch_session_or_erase_other_draft(browser_page):
    page=browser_page;page.evaluate(BOOT,{'rows':1})
    page.evaluate("records.s2={session:{...records.s1.session,sessionId:'s2',title:'另一场景'},items:[]};holdSend=true")
    page.locator('#text').fill('原会话的需求');page.locator('#send').click()
    page.wait_for_function('!!window.finishSend');page.evaluate("ui.select('s2')")
    expect(page.locator('#rename')).to_have_value('另一场景');page.locator('#text').fill('另一个会话的草稿')
    page.evaluate('finishSend()');expect(page.locator('#send')).to_be_enabled()
    expect(page.locator('#rename')).to_have_value('另一场景');expect(page.locator('#text')).to_have_text('另一个会话的草稿')
    assert page.evaluate("calls.filter(c=>c.op==='ai.session.submit').map(c=>c.args.sessionId)")==['s1']
    page.evaluate("ui.select('s1')");expect(page.locator('#history')).to_contain_text('原会话的需求')
    expect(page.locator('#text')).to_be_empty()
    page.evaluate("ui.select('s2')");expect(page.locator('#text')).to_have_text('另一个会话的草稿')
