"""User-visible progress, dependency warning and deliberate regeneration."""
from pathlib import Path
from playwright.sync_api import expect
from test_manager_ui import services
from test_chat_polish import browser_page,BOOT


def test_progress_warning_and_regenerate(browser_page):
    page=browser_page;page.evaluate(BOOT,{'rows':1})
    page.evaluate("""async()=>{const row=records.s1.items[0];row.status='generating';row.events=[
      {seq:1,at:1700000000,stage:'provider_complete',status:'running',summary:'等待 AI 服务回复',durationMs:2300}];await ui.select('s1');}""")
    expect(page.locator('.task-progress')).to_have_attribute('open','')
    expect(page.locator('.task-progress li[data-status=running]')).to_contain_text('2.30 秒')
    page.evaluate("""async()=>{const row=records.s1.items[0];row.status='review_ready';row.events[0].status='completed';row.events.push(
      {seq:2,at:1700000003,stage:'dependency_check',status:'completed',summary:'核对发送后的资料变化',durationMs:100});
      row.dependencyCheck={status:'changed',canRegenerate:true,changes:[{kind:'entity',id:'actor-one',code:'DEPENDENCY_CHANGED',summary:'发送后该资料已变化'}]};await ui.select('s1');}""")
    expect(page.locator('.task-progress')).not_to_have_attribute('open','')
    expect(page.locator('.dependency-warning')).to_contain_text('actor-one')
    expect(page.locator('.assistant')).to_contain_text('先确定角色动机')
    before=page.evaluate('calls.length');page.locator('.regenerate-current').click()
    expect(page.locator('#text')).to_contain_text('请整理庭院向导的设计')
    assert page.evaluate('calls.length')==before
    page.locator('.task-progress summary').click();expect(page.locator('.task-progress li')).to_have_count(2)
    page.screenshot(path=str(Path(__file__).resolve().parents[2]/'acceptance/ai-snapshot-performance/progress.png'),full_page=True)
