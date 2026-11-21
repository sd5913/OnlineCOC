"""Real Edge acceptance for permission controls, archive/delete stability and batch review."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from test_manager_ui import services
from test_embeds import login
OUTPUT=Path(__file__).resolve().parents[2]/'acceptance/ai-runtime'


def test_permissions_archive_delete_batches_and_mobile(services):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1380,'height':920});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(origin+'/ai-ui/conversation.html');login(page,'player1')
            expect(page.locator('#status')).to_contain_text('尚未允许')
            expect(page.locator('#send')).to_be_disabled()
            page.locator('#logout').click();login(page,'kp')
            page.locator('.review-open').click();page.locator('[data-tab=settings]').click()
            expect(page.locator('#ai-allow-player')).not_to_be_checked();expect(page.locator('#ai-auto-approve')).not_to_be_checked()
            page.locator('#ai-allow-player').check();page.locator('#ai-save-access').click();expect(page.locator('#ai-result')).to_have_text('权限设置已保存')
            page.get_by_text('服务与外发范围',exact=True).click();page.locator('#ai-enabled').check();page.locator('#ai-public').check();page.locator('#ai-private').check();page.locator('#ai-save-settings').click();expect(page.locator('#ai-result')).to_have_text('设置已保存')
            page.screenshot(path=str(OUTPUT/'access-settings.png'),full_page=True)
            page.locator('.review-close').click();page.locator('.new-chat').click();expect(page.locator('#session-access')).to_contain_text('管理员')
            page.locator('#text').fill('批次验收：请改名');page.locator('#send').click();expect(page.locator('#history')).to_contain_text('查看执行批次',timeout=30000)
            page.locator('.review-open').click();page.locator('[data-tab=batches]').click();expect(page.locator('.batch-card')).to_contain_text('等待 KP 裁决')
            page.get_by_role('button',name='批准并执行',exact=True).click();expect(page.locator('.batch-card')).to_contain_text('已执行')
            page.screenshot(path=str(OUTPUT/'execution-batches.png'),full_page=True);page.locator('.review-close').click()
            page.locator('.manage-sessions').click();expect(page.locator('.binding')).to_contain_text('创建者 kp')
            for _ in range(3):
                page.locator('.session-manager .archive').click();expect(page.locator('.session-manager .status')).to_have_text('会话已归档')
                expect(page.locator('[data-filter=archived]')).to_have_attribute('aria-pressed','true')
                page.wait_for_timeout(1400);expect(page.locator('.session-manager .archive')).to_have_text('恢复会话')
                page.locator('.session-manager .archive').click();expect(page.locator('.session-manager .status')).to_have_text('会话已恢复')
            page.locator('.session-manager .delete').click();page.locator('.confirm-delete').click();expect(page.locator('.session-manager .status')).to_have_text('会话已删除')
            expect(page.locator('.settings')).to_be_hidden();expect(page.locator('.session-manager .session-link')).to_have_count(0)
            page.locator('.session-close').click();page.wait_for_timeout(1500);expect(page.locator('#history')).not_to_contain_text('批次验收')
            page.locator('#logout').click();login(page,'player1');page.locator('.new-chat').click();expect(page.locator('#session-access')).to_contain_text('玩家 · player1')
            page.locator('#text').fill('玩家咨询验收');page.locator('#send').click();expect(page.locator('#history')).to_contain_text('暂未获得与问题匹配的本人已知资料',timeout=30000)
            expect(page.get_by_role('button',name='向 KP 申请披露',exact=True)).to_be_visible()
            page.locator('.manage-sessions').click();expect(page.locator('.level')).to_be_hidden();expect(page.locator('.binding')).to_contain_text('玩家权限')
            page.set_viewport_size({'width':390,'height':840});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(OUTPUT/'session-permissions-mobile.png'),full_page=True)
            page.locator('.session-close').click();page.locator('#logout').click();login(page,'kp');page.locator('.manage-sessions').click()
            expect(page.locator('.session-manager .session-link')).to_contain_text('player1');page.locator('.session-manager .session-link').click();expect(page.locator('.binding')).to_contain_text('创建者 player1')
            assert not errors,errors
        finally:browser.close()
