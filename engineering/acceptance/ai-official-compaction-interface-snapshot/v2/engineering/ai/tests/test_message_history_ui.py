"""Delivered labels, real timestamps and machine-readable transport failures."""
from pathlib import Path
from playwright.sync_api import expect
from test_manager_ui import services
from test_chat_polish import browser_page, BOOT


def test_unavailable_references_keep_label_and_disable_details(browser_page):
    page=browser_page;page.evaluate(BOOT,{'rows':1})
    chip=page.locator('.assistant .reference-chip')
    expect(chip).to_have_text('提灯')
    page.evaluate("client.aiResolve=async()=>{throw Object.assign(new Error('NOT_VISIBLE'),{code:'NOT_VISIBLE'});};ui.select('s1')")
    expect(chip).to_have_attribute('aria-disabled','true')
    expect(chip).to_have_text('提灯')
    expect(chip).to_be_disabled();chip.dispatch_event('click');expect(page.locator('.reference-details dialog')).not_to_be_visible()
    expect(page.locator('.assistant')).to_contain_text('先确定角色动机')
    assert chip.evaluate("el=>getComputedStyle(el).backgroundColor")=='rgb(236, 238, 236)'
    page.screenshot(path=str(Path(__file__).resolve().parents[2]/'acceptance/message-history/references.png'),full_page=True)


def test_timestamps_are_real_and_missing_history_is_explicit(browser_page):
    page=browser_page;page.evaluate(BOOT,{'rows':1})
    expect(page.locator('.assistant .message-time')).to_have_text('回复 · 时间未记录')
    page.evaluate("records.s1.items[0].createdAt=1700000000;records.s1.items[0].responseAt=1700000008;ui.select('s1')")
    expect(page.locator('.user .message-time')).to_have_attribute('datetime','2023-11-14T22:13:20.000Z')
    expect(page.locator('.assistant .message-time')).to_have_attribute('datetime','2023-11-14T22:13:28.000Z')
    page.evaluate("ui.select('s1')")
    expect(page.locator('.message-time')).to_have_count(2)


def test_transport_errors_keep_status_and_never_expose_body(browser_page):
    page=browser_page
    result=page.evaluate("""async()=>{
      const {HttpTransport}=await import('/ai-ui/client.js');const transport=new HttpTransport();const actual=window.fetch;const results=[];
      for(const mode of ['network','html','invalid','denied','business']){
        window.fetch=async()=>{if(mode==='network')throw new Error('SECRET_INTERNAL');return new Response(mode==='html'?'SECRET_PROXY':mode==='invalid'?'SECRET_BROKEN':mode==='denied'?JSON.stringify({code:'NOT_VISIBLE',detail:'SECRET_DETAIL'}):JSON.stringify({status:'unknown',code:'RESULT_UNKNOWN'}),{status:mode==='html'?502:mode==='denied'?403:200});};
        try{results.push(await transport.request('ai/commands',{method:'POST',body:{requestId:'id1',op:'ai.session.submit',args:{}}}));}catch(e){results.push({message:e.message,...e});}
      }window.fetch=actual;return results;
    }""")
    assert [x.get('code') for x in result]==['NETWORK_ERROR','HTTP_ERROR','INVALID_RESPONSE','NOT_VISIBLE','RESULT_UNKNOWN']
    assert [x.get('status') for x in result]==[None,502,200,403,'unknown']
    assert 'SECRET' not in str(result)
    assert all(x['requestId']=='id1' and x['operation']=='ai.session.submit' for x in result[:4])
