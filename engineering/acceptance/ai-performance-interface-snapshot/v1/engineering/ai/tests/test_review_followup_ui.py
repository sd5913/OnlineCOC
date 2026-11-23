"""Real browser checks for explicit continuation and queue-only mutations."""
from pathlib import Path
from playwright.sync_api import expect
from test_manager_ui import services
from test_chat_polish import browser_page,BOOT


def test_continue_request_and_retry_keep_identity_without_linking_new_topic(browser_page):
    page=browser_page;page.evaluate(BOOT,{'rows':1})
    page.get_by_role('button',name='继续此请求',exact=True).click()
    expect(page.locator('#reply-target')).to_be_visible()
    page.locator('#text').fill('按这些要求修正方案')
    page.evaluate('rejectSubmit=true');page.locator('#send').click()
    expect(page.locator('#status')).to_contain_text('CONNECTION_FAILED')
    first=page.evaluate("calls.filter(c=>c.op==='ai.session.submit').at(-1).args")
    assert first['replyToRequestId']=='r0' and first['submissionKey']
    page.evaluate('rejectSubmit=false');page.locator('#send').click()
    expect(page.locator('#history')).to_contain_text('按这些要求修正方案')
    assert page.evaluate("calls.filter(c=>c.op==='ai.session.submit').at(-1).args")==first
    expect(page.locator('#reply-target')).to_be_hidden()
    page.locator('#text').fill('独立的新任务');page.locator('#send').click()
    expect(page.locator('#history')).to_contain_text('独立的新任务')
    last=page.evaluate("calls.filter(c=>c.op==='ai.session.submit').at(-1).args")
    assert 'replyToRequestId' not in last and last['submissionKey']!=first['submissionKey']


def test_history_notice_does_not_replace_response(browser_page):
    page=browser_page;page.evaluate(BOOT,{'rows':1})
    page.evaluate("records.s1.items[0].status='stale';records.s1.items[0].sourceNotice='历史资料已变化，请重新查询';records.s1.items[0].historicalReadOnly=true;ui.select('s1')")
    expect(page.locator('.assistant')).to_contain_text('先确定角色动机')
    expect(page.locator('.history-source-notice')).to_have_text('历史资料已变化，请重新查询')
    expect(page.get_by_role('button',name='编辑后重试')).to_have_count(0)
    page.screenshot(path=str(Path(__file__).resolve().parents[2]/'acceptance/review-followup/history-ui.png'),full_page=True)


def test_queue_archive_needs_reason_and_preserves_receipt_content(browser_page):
    page=browser_page
    page.evaluate("""async()=>{
      const {mountRulings}=await import('/ai-ui/pack.js');document.body.replaceChildren();window.commands=[];
      const item={rulingId:'batch:'+'a'.repeat(32),queueTargetId:'batch:'+'a'.repeat(32),queueDigest:'b'.repeat(64),queueStatus:'active',archived:false,canArchive:true,canRestore:false,
        kind:'runtime',summary:'保留旧方案内容',status:'pending',canDecide:false,risks:[],receipts:[],actions:[],createdAt:1};
      const client={generation:1,connected:true,view:{accountId:'kp'},subscribe:()=>()=>{},aiResolve:async()=>({items:[]}),aiRulings:async()=>({items:[structuredClone(item)]}),
        aiCommand:async(op,args)=>{commands.push({op,args});Object.assign(item,{archived:args.archived,queueStatus:args.archived?'archived':'active',canArchive:!args.archived,canRestore:args.archived,archiveReason:args.reason});return {status:'committed',result:structuredClone(item)};}};
      window.panel=mountRulings(document.body,client);
    }""")
    page.get_by_role('button',name='归档记录',exact=True).click()
    expect(page.get_by_role('status')).to_have_text('请填写归档理由')
    assert page.evaluate('commands.length')==0
    page.get_by_label('归档理由').fill('已由实际新需求替代')
    page.get_by_role('button',name='归档记录',exact=True).click()
    expect(page.get_by_role('button',name='恢复记录',exact=True)).to_be_visible()
    expect(page.get_by_text('保留旧方案内容',exact=True)).to_be_visible()
    assert page.evaluate('commands[0].op')=='ai.queue.archive'
    page.get_by_role('button',name='恢复记录',exact=True).click()
    expect(page.get_by_role('button',name='归档记录',exact=True)).to_be_visible()
    assert page.evaluate('commands.length')==2
