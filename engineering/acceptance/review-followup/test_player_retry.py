"""Browser regression for a lost response to an explicit player request."""
import sys
from pathlib import Path
from playwright.sync_api import expect
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'ai/tests'),str(ROOT/'ai/src'),str(ROOT/'backend/src'),str(ROOT/'data-management')]
from test_manager_ui import services
from test_chat_polish import browser_page,BOOT


def test_player_creation_retry_reuses_key_and_new_intent_gets_new_key(browser_page):
    page=browser_page;page.evaluate(BOOT,{'rows':1})
    page.evaluate("""async()=>{
      records.s1.session.accessLevel='player';records.s1.session.owner='player1';client.view.accountId='player1';client.view.role='player';
      window.failPlayer=true;const original=client.aiCommand;
      client.aiCommand=async(op,args)=>{if(op!=='ai.player.request')return original(op,args);calls.push({op,args});
        if(failPlayer)throw Error('NETWORK_LOST');return {status:'committed',result:{requestId:'accepted'}};};
      await ui.select('s1');
    }""")
    page.locator('#text').fill('请制作带光的道具')
    page.locator('#player-request').click()
    expect(page.locator('#status')).to_contain_text('NETWORK_LOST')
    expect(page.locator('#text')).to_have_text('请制作带光的道具')
    first=page.evaluate("calls.filter(c=>c.op==='ai.player.request').at(-1).args")
    assert first.get('submissionKey')
    page.evaluate('failPlayer=false');page.locator('#player-request').click()
    expect(page.locator('#text')).to_have_text('')
    assert page.evaluate("calls.filter(c=>c.op==='ai.player.request').at(-1).args")==first
    page.locator('#text').fill('另一项独立创作');page.locator('#player-request').click()
    expect(page.locator('#text')).to_have_text('')
    last=page.evaluate("calls.filter(c=>c.op==='ai.player.request').at(-1).args")
    assert last['submissionKey']!=first['submissionKey']
