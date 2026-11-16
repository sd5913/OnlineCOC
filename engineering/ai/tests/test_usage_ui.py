"""Usage UI over real room/manager transports; no WAN or paid model requests."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from test_manager_ui import services
from test_embeds import login

OUTPUT=Path(__file__).resolve().parents[2]/'acceptance/ai-runtime'


def test_room_usage_metrics_filters_account_scope_and_mobile(services):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1280,'height':960});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(origin+'/ai-ui/conversation.html');login(page,'kp')
            page.locator('.review-open').click();page.get_by_text('服务与外发范围',exact=True).click()
            page.locator('#ai-enabled').check();page.locator('#ai-profile').select_option('deepseek-main');page.locator('#ai-public').check();page.locator('#ai-save-settings').click()
            expect(page.locator('#ai-result')).to_have_text('设置已保存');page.locator('.review-close').click()
            page.locator('#text').fill('将新建技能初值改为 15。');page.locator('#send').click()
            expect(page.locator('#history')).to_contain_text('离线验收：新技能默认值 15',timeout=40000)
            page.locator('.usage-open').click();expect(page.locator('.usage-status')).to_have_text('查询完成')
            expect(page.locator('.metric strong')).to_have_text(['20','10','10','1','0','0'])
            expect(page.locator('.budgets')).to_contain_text('每日不限额')
            expect(page.locator('.profiles')).to_contain_text('deepseek-main')
            page.locator('.session-only').check();page.locator('.usage-refresh').click();expect(page.locator('.usage-status')).to_have_text('查询完成')
            expect(page.locator('.scope')).to_have_value('mine');expect(page.locator('.metric strong').first).to_have_text('20')
            page.screenshot(path=str(OUTPUT/'usage-panel.png'),full_page=True)
            page.locator('.from').fill('2020-01-01');page.locator('.to').fill('2020-01-02');page.locator('.usage-refresh').click()
            expect(page.locator('.metric strong').first).to_have_text('0')
            page.locator('.period').select_option('1');page.locator('.usage-refresh').click();expect(page.locator('.metric strong').first).to_have_text('20')
            page.set_viewport_size({'width':390,'height':840});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.locator('.usage-close').click();page.locator('#logout').click();login(page,'player1');page.locator('.usage-open').click()
            expect(page.locator('.usage-status')).to_have_text('查询完成');expect(page.locator('.scope')).to_have_value('mine')
            expect(page.locator('.scope option[value=room]')).to_be_hidden();expect(page.locator('.metric strong').first).to_have_text('0')
            expect(page.locator('.budgets')).to_be_empty()
            late=page.evaluate('''async()=>{
              const {AiClient,mountUsage,createAITools}=await import('/ai-ui/pack.js');let release,calls=0;
              const client=new AiClient({request(){calls++;return new Promise(resolve=>release=resolve);}});client.connected=true;client.view={accountId:'private',role:'player',authorityEpoch:'one'};
              const host=document.createElement('div');document.body.append(host);const panel=mountUsage(host,client);panel.destroy();release({byProfile:[{profileId:'private-late'}]});await Promise.resolve();await panel.refresh();
              const tools=createAITools(client),pending=tools.usage().catch(e=>e.message);tools.destroy();release({secret:true});return {calls,late:await pending,leaked:host.textContent};
            }''')
            assert late=={'calls':2,'late':'VIEW_CHANGED','leaked':''}
            assert not errors,errors
        finally:browser.close()


def test_local_manager_budget_toggle_and_usage_proxy(services):
    origin,entry,_=services
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1280,'height':960});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(origin+'/#unlock='+entry['key']);page.locator('[data-page=providers]').click()
            page.get_by_role('button',name='编辑',exact=True).click()
            expect(page.locator('#budget-enabled')).not_to_be_checked();expect(page.locator('#budget')).to_be_disabled()
            page.get_by_text('预算、超时与调用限制',exact=True).click();page.locator('#budget-enabled').check();page.locator('#budget').fill('123456')
            page.get_by_role('button',name='保存配置',exact=True).click();expect(page.locator('#status')).to_contain_text('配置已保存')
            page.reload();page.locator('[data-page=providers]').click();page.get_by_role('button',name='编辑',exact=True).click()
            expect(page.locator('#budget-enabled')).to_be_checked();expect(page.locator('#budget')).to_have_value('123456')
            page.get_by_text('预算、超时与调用限制',exact=True).click();page.locator('#budget-enabled').uncheck();page.get_by_role('button',name='保存配置',exact=True).click()
            expect(page.locator('#status')).to_contain_text('配置已保存');expect(page.locator('#budget')).to_be_disabled()
            page.screenshot(path=str(OUTPUT/'budget-optional.png'),full_page=True)
            page.locator('#add').click();expect(page.locator('#budget-enabled')).not_to_be_checked()
            page.locator('#manage-rooms').click();page.locator('#room-name').fill('用量测试房间');page.locator('#room-url').fill(f'http://127.0.0.1:{entry["roomPort"]}')
            page.get_by_role('button',name='添加房间',exact=True).click();page.get_by_role('button',name='登录',exact=True).click()
            page.locator('#password').fill('test-password');page.get_by_role('button',name='连接',exact=True).click()
            page.locator('#usage-open').click();expect(page.locator('.usage-status')).to_have_text('查询完成');expect(page.locator('.budgets')).to_contain_text('每日不限额')
            page.locator('#usage-close').click();page.locator('#disconnect').click();expect(page.locator('#usage-open')).to_be_hidden()
            assert not errors,errors
        finally:browser.close()
