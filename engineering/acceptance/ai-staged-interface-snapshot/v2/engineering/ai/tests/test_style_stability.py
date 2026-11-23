from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from test_manager_ui import services

def test_style_reparent_and_failed_load_retry(services):
    origin,_,_=services
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page()
        try:
            page.goto(origin+'/session-prototype.html')
            page.route('**/components/test-sheet.css',lambda r:r.fulfill(status=503,body='unavailable'))
            page.evaluate('''async()=>{const {mountStyle}=await import('/components/styles.js');document.body.replaceChildren();window.host=document.createElement('div');document.body.append(host);window.root=host.attachShadow({mode:'open'});root.innerHTML='<p class="sample">稳定正文</p>';mountStyle(root,new URL('/components/test-sheet.css',location.href));}''')
            expect(page.get_by_text('样式加载失败，点击重试')).to_be_visible()
            expect(page.locator('.sample')).not_to_be_visible()
            page.unroute('**/components/test-sheet.css');page.route('**/components/test-sheet.css',lambda r:r.fulfill(body='.sample{font-size:23px;color:rgb(20,70,40)}',content_type='text/css'))
            page.get_by_text('样式加载失败，点击重试').click();expect(page.locator('.sample')).to_have_css('font-size','23px');expect(page.locator('.sample')).to_be_visible()
            samples=page.evaluate('''()=>{const sizes=[];for(let i=0;i<30;i++){host.remove();document.body.append(host);sizes.push(getComputedStyle(root.querySelector('.sample')).fontSize);}return sizes;}''')
            assert set(samples)=={'23px'}
        finally:browser.close()

def test_session_management_prototype(services):
    origin,_,_=services
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1440,'height':960})
        try:
            page.goto(origin+'/session-prototype.html');expect(page.locator('.session')).to_have_count(3)
            page.get_by_role('button',name='归档',exact=True).click();expect(page.locator('.session')).to_have_count(2)
            page.get_by_role('button',name='撤销',exact=True).click();expect(page.locator('.session')).to_have_count(3)
            page.locator('#edit-title').fill('庭院向导 · 等待裁决');page.get_by_role('button',name='保存设置',exact=True).click()
            output=Path(__file__).resolve().parents[2]/'acceptance/ai-runtime';page.screenshot(path=str(output/'session-prototype.png'),full_page=True)
            page.locator('#role').select_option('pl');expect(page.locator('.session')).to_have_count(1)
            page.locator('#new').click();expect(page.locator('[name=level]')).to_be_disabled();page.locator('[name=title]').fill('个人线索');page.get_by_role('button',name='创建会话',exact=True).click()
            expect(page.locator('.owner')).to_contain_text('木栗');page.get_by_role('button',name='删除',exact=True).click();page.get_by_role('button',name='保留会话').click();expect(page.locator('#edit-title')).to_have_value('个人线索')
            page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(output/'session-prototype-mobile.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        finally:browser.close()
