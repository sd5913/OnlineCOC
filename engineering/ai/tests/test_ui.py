import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]


def wait_connected(page):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if page.evaluate('window.playtest?.connected'):return
        page.wait_for_timeout(50)
    raise AssertionError('Browser did not connect: ' + page.locator('#result').inner_text())


@pytest.fixture
def live(tmp_path):
    with socket.socket() as sock:sock.bind(('127.0.0.1', 0));port = sock.getsockname()[1]
    log = (tmp_path / 'server.log').open('w', encoding='utf-8')
    process = subprocess.Popen([sys.executable, str(Path(__file__).with_name('ui_server.py')), str(tmp_path / 'host'), str(port)], stdout=log, stderr=log)
    url = f'http://127.0.0.1:{port}'
    try:
        for _ in range(100):
            if process.poll() is not None:pytest.fail((tmp_path / 'server.log').read_text())
            try:
                if httpx.get(url + '/api/v1/capabilities', timeout=1, trust_env=False).status_code == 200:break
            except httpx.HTTPError:pass
            time.sleep(.1)
        else:pytest.fail('AI test server did not start')
        yield url
    finally:process.terminate();process.wait(timeout=10);log.close()


def test_browser_requests_review_revision_publish_and_cache_clear(live):
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        contexts = [browser.new_context() for _ in range(2)]
        try:
            pages = [context.new_page() for context in contexts]
            for page, account in zip(pages, ['kp', 'player1']):
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(live);page.locator('#username').fill(account);page.locator('#password').fill('test-password');page.locator('#login button').click()
                wait_connected(page)
                expect(page.locator('#ai-send')).to_be_enabled(timeout=15000)
            kp, player = pages
            expect(player.locator('#ai-kp')).to_be_hidden()
            kp.get_by_text('服务与外发范围', exact=True).click()
            expect(kp.locator('#ai-save-settings')).to_be_enabled(timeout=15000)
            kp.locator('#ai-enabled').check();kp.locator('#ai-public').check();kp.locator('#ai-save-settings').click()
            expect(kp.locator('#ai-result')).to_have_text('设置已保存')
            player.locator('#ai-request').fill('制作有限次数道具');player.locator('#ai-send').click()
            expect(player.locator('#ai-result')).to_contain_text('需求已提交')
            kp.locator('#ai-refresh').click();kp.get_by_role('button', name='转交 AI', exact=True).click()
            expect(kp.get_by_role('button', name='审核方案', exact=True)).to_be_visible(timeout=30000)
            kp.get_by_role('button', name='审核方案', exact=True).click()
            expect(kp.locator('#ai-summary')).to_contain_text('离线验收')
            assert 'changeSet' not in player.locator('#ai-tasks').inner_text()
            kp.locator('#ai-reject').click();expect(kp.locator('#ai-result')).to_have_text('已拒绝或撤销')
            kp.get_by_text('导入人工草稿', exact=True).click()
            kp.locator('#ai-file').set_input_files(str(ROOT / 'ai/examples/bonus-15.json'));kp.locator('#ai-import').click()
            expect(kp.locator('#ai-summary')).to_have_text('人工配置草稿', timeout=30000)
            kp.locator('#ai-approve').click();expect(kp.locator('#ai-result')).to_have_text('请填写每项风险判断理由')
            for field in kp.locator('#ai-risks textarea').all():field.fill('测试接受有限次数的收益，同时保留其他选择')
            kp.locator('#ai-approve').click();expect(kp.locator('#ai-result')).to_have_text('已批准，尚未加载到游戏')
            kp.get_by_text('配置和源码差异 / 编辑候选', exact=True).click()
            delta = json.loads(kp.locator('#ai-editor').input_value());delta['configurations'][0]['value']['defaults']['bonus'] = 5
            kp.locator('#ai-editor').fill(json.dumps(delta));kp.locator('#ai-revise').click()
            expect(kp.locator('#ai-review-status')).to_contain_text('修订 2', timeout=30000)
            expect(kp.locator('#ai-load')).to_be_disabled()
            for field in kp.locator('#ai-risks textarea').all():field.fill('降低收益后接受本次配置变更')
            kp.locator('#ai-approve').click();expect(kp.locator('#ai-load')).to_be_enabled()
            kp.locator('#ai-load').click();expect(kp.locator('#ai-result')).to_contain_text('加载成功', timeout=15000)
            loaded = kp.evaluate("async()=>await playtest.transport.request('admin')")
            # The authoritative receipt and host configuration prove publication.
            configurations = loaded.get('state', loaded).get('configurations')
            assert configurations['fixture.token']['defaults']['bonus'] == 5
            tasks = kp.evaluate('async()=>await playtest.aiTasks()')
            assert any(task['status'] == 'published' for task in tasks['items'])
            kp.evaluate('playtest.socket.close()');kp.wait_for_timeout(100);wait_connected(kp)
            kp.locator('#ai-refresh').click()
            kp.locator('#logout').click();expect(kp.locator('#ai-panel')).to_be_hidden()
            assert kp.locator('#ai-editor').input_value() == ''
            assert kp.locator('#ai-summary').text_content() == ''
            assert not errors, errors
            (ROOT / 'acceptance/ai-runtime/ai-5-browser.json').write_text(json.dumps({'browser': browser.version,
                'provider': 'deterministic-offline', 'pageErrors': errors, 'verified': ['player-request', 'KP-forward', 'ABC-review', 'risk-reasons', 'manual-revision', 'approval', 'publication-receipt', 'reconnect', 'logout-clear']}, ensure_ascii=False, indent=2), encoding='utf-8')
        finally:
            for context in contexts:context.close()
            browser.close()


def test_missing_optional_ai_script_keeps_ordinary_console_working(live):
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        try:
            page = browser.new_page()
            page.route('**/ai.js', lambda route: route.abort())
            page.goto(live);page.locator('#username').fill('player1');page.locator('#password').fill('test-password');page.locator('#login button').click()
            wait_connected(page)
            result = page.evaluate("async()=>await playtest.command('entity.patch',{id:'actor-one',name:'AI unavailable, normal game works'})")
            assert result['status'] == 'committed', result
        finally:browser.close()
