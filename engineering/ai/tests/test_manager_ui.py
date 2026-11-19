import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
import pytest
from playwright.sync_api import sync_playwright, expect


def allow_players(origin):
    with httpx.Client(base_url=origin,trust_env=False,headers={'Origin':origin}) as api:
        csrf=api.post('/api/v1/login',json={'loginName':'kp','password':'test-password'}).json()['csrf']
        access=api.get('/api/v1/ai/access').json();view=api.get('/api/v1/view').json()
        receipt=api.post('/api/v1/ai/commands',headers={'X-CSRF-Token':csrf},json={'requestId':'ui-enable-players','authorityEpoch':view['authorityEpoch'],
            'op':'ai.access.update','args':{'revision':access['revision'],'allowPlayerChat':True,'autoApproveBatches':False}}).json()
        assert receipt['status']=='committed',receipt


@pytest.fixture
def services(tmp_path):
    ports=[]
    for _ in range(2):
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));ports.append(sock.getsockname()[1])
    log=(tmp_path/'server.log').open('w',encoding='utf-8')
    process=subprocess.Popen([sys.executable,'-B',str(Path(__file__).with_name('manager_ui_server.py')),str(tmp_path/'data'),*map(str,ports)],stdout=log,stderr=log,creationflags=0x08000000 if os.name=='nt' else 0)
    origin=f'http://127.0.0.1:{ports[1]}'
    try:
        for _ in range(120):
            if process.poll() is not None:pytest.fail((tmp_path/'server.log').read_text())
            try:
                if httpx.get(origin,timeout=1,trust_env=False).status_code==200:break
            except httpx.HTTPError:pass
            time.sleep(.1)
        else:pytest.fail('Manager did not start')
        yield origin,json.loads((tmp_path/'data/entry.json').read_text()),tmp_path
    finally:process.terminate();process.wait(timeout=15);log.close()


def test_real_manager_providers_sessions_review_and_embed(services):
    origin,entry,tmp=services;errors=[];timings=[]
    allow_players(f'http://127.0.0.1:{entry["roomPort"]}')
    output=Path(__file__).resolve().parents[2]/'acceptance/ai-runtime'
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1440,'height':960});page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(origin+'/#unlock='+entry['key'])
            expect(page.locator('#room-start')).to_be_visible()
            assert '#unlock' not in page.url
            page.locator('[data-page=providers]').click()
            page.get_by_role('button',name='编辑',exact=True).click()
            page.locator('#secret').fill('browser-offline-test-key');page.get_by_role('button',name='保存密钥',exact=True).click()
            expect(page.locator('#key-status')).to_have_text('密钥状态：已加密保存')
            page.get_by_role('button',name='测试连接（产生用量）',exact=True).click();expect(page.locator('#status')).to_contain_text('连接通过')
            page.locator('#manage-rooms').click();page.locator('#room-name').fill('周五调查团');page.locator('#room-url').fill(f'http://127.0.0.1:{entry["roomPort"]}')
            page.get_by_role('button',name='添加房间',exact=True).click();page.get_by_role('button',name='登录',exact=True).click()
            page.locator('#password').fill('test-password');page.get_by_role('button',name='连接',exact=True).click()
            expect(page.locator('#session-panel #text')).to_be_visible()
            expect(page.locator('#folders .folder-head')).to_contain_text('周五调查团')
            page.locator('#review-open').click();page.locator('[data-tab=settings]').click();page.get_by_text('服务与外发范围',exact=True).click()
            expect(page.locator('#ai-save-settings')).to_be_enabled()
            page.locator('#ai-enabled').check();page.locator('#ai-profile').select_option('deepseek-main');page.locator('#ai-public').check();page.locator('#ai-private').check();page.locator('#ai-save-settings').click()
            expect(page.locator('#ai-result')).to_have_text('设置已保存');page.locator('#review-close').click()
            start=time.perf_counter();page.locator('#new-chat').click();expect(page.locator('#session-panel #status')).to_have_text('新会话已创建');timings.append(round((time.perf_counter()-start)*1000,2))
            page.locator('#rename').fill('提灯与技能讨论');page.locator('#save').click();expect(page.locator('#folders .session-link')).to_have_text('提灯与技能讨论')
            page.locator('#session-manage').click();expect(page.locator('.settings [name=title]')).to_have_value('提灯与技能讨论')
            page.locator('[name=historyTurns]').select_option('2');page.locator('.save').click();expect(page.locator('.session-manager .status')).to_have_text('设置已保存')
            page.locator('#session-close').click()
            page.locator('#session-panel #text').fill('/config demo.skill')
            expect(page.locator('#completion').get_by_role('option')).to_have_count(1)
            page.locator('#session-panel #text').press('ArrowDown');page.locator('#session-panel #text').press('Enter')
            token=page.locator('#session-panel #text .reference-chip').get_attribute('data-token');assert token.startswith('[[config:demo.skill@')
            page.locator('#preview').click();expect(page.locator('#reference-preview')).to_contain_text('demo.skill')
            page.locator('#session-panel #text').fill('参考 '+token+'，将新建技能初值改为 15，保留已有技能。')
            page.locator('#send').click();expect(page.locator('#history')).to_contain_text('新建技能初值')
            expect(page.locator('#history')).to_contain_text('离线验收：新技能默认值 15',timeout=40000)
            page.screenshot(path=str(output/'reference-ui-room.png'),full_page=True)
            page.get_by_role('button',name='查看配置裁决',exact=True).click(timeout=40000)
            expect(page.locator('.batch-card')).to_contain_text('等待 KP 裁决')
            for field in page.locator('.batch-card textarea').all():field.fill('验收接受新技能初值提升，保留已有技能投入的价值。')
            page.screenshot(path=str(output/'ai-rulings.png'),full_page=True)
            page.get_by_role('button',name='批准并执行',exact=True).click();expect(page.locator('.batch-card')).to_contain_text('已执行',timeout=20000)
            page.locator('#review-close').click()
            page.locator('#archive').click();expect(page.locator('#session-panel #status')).to_contain_text('已归档')
            page.locator('#archived').click();expect(page.locator('#folders .session-link')).to_have_text('提灯与技能讨论')
            page.reload();page.locator('#folders .folder-head').click();expect(page.locator('#session-panel #text')).to_be_visible()
            page.locator('#archived').click();page.locator('#folders .session-link').click();expect(page.locator('#rename')).to_have_value('提灯与技能讨论')
            page.locator('#disconnect').click();expect(page.locator('#room-workspace')).to_be_hidden()
            page.locator('#folders .folder-head').click();page.locator('#account').fill('player1');page.locator('#password').fill('test-password');page.get_by_role('button',name='连接',exact=True).click()
            expect(page.locator('#session-panel #text')).to_be_visible();expect(page.locator('#review-open')).to_be_hidden()
            assert page.locator('#folders .session-link').count()==0
            page.locator('#session-panel #text').fill('希望有一盏灯');page.locator('#send').click();expect(page.locator('#history')).to_contain_text('本人已知资料不足',timeout=30000)
            assert page.get_by_role('button',name='转交 AI',exact=True).count()==0
            page.set_viewport_size({'width':780,'height':800});expect(page.locator('#lock')).to_be_visible()
            page.locator('#lock').click();expect(page.locator('#locked')).to_be_visible();assert page.locator('#folders .session-link').count()==0
            page.goto(origin+'/prototype.html');page.set_viewport_size({'width':1440,'height':960});page.locator('#insert').click();page.locator('#chat #send').click()
            expect(page.locator('#checks')).to_be_visible();page.locator('#risk').check();page.locator('#approve').click();expect(page.locator('#result')).to_contain_text('尚未加载');page.locator('#apply').click();expect(page.locator('#result')).to_contain_text('真实游戏没有发生改变')
            page.screenshot(path=str(output/'reference-ui-pack-prototype.png'),full_page=True)
            page.locator('#role').select_option('player');expect(page.locator('#checks')).to_be_hidden()
            assert not errors,errors
            (output/'reference-ui-browser.json').write_text(json.dumps({'passed':True,'provider':'deterministic-offline','createSessionEndToEndMs':timings,'consoleErrors':errors,'checks':['room-folder sidebar','provider key/probe','keyboard reference autocomplete and preview','KP send/generate/ABC/approve/load','archive and reload','PL ownership and no dispatch','lock and responsive layout','package prototype approval/load separation']},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        finally:context.close();browser.close()
