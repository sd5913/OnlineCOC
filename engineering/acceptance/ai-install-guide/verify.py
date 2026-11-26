"""Clean shared runtime + local UI onboarding. No external provider or real secrets."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import socket
import subprocess
import time
import uuid

import httpx
from playwright.sync_api import sync_playwright, expect

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORK = HERE / 'work' / uuid.uuid4().hex
FRESH = WORK / '全新工程 with spaces'
REPORT = {'externalModelCalls': 0, 'provider': 'deterministic-offline', 'checks': []}


def record(name, **details):
    REPORT['checks'].append({'name': name, 'passed': True, **details})
    print(name + ': passed', flush=True)


def setup(*args, success=True, project=FRESH):
    result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        str(FRESH / 'engineering/setup-game.ps1'), '-ProjectRoot', str(project), *map(str, args)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240, creationflags=0x08000000)
    (WORK / ('setup-' + str(len(REPORT['checks'])) + '.log')).write_bytes(result.stdout)
    assert (result.returncode == 0) == success, 'Unexpected installer exit; inspect isolated setup log.'
    return result


def main():
    (FRESH / 'engineering').mkdir(parents=True)
    for name in ['launcher-config.json', 'engineering/requirements-runtime.lock', 'engineering/setup-game.ps1', 'engineering/setup-game.cmd']:
        shutil.copyfile(ROOT / name, FRESH / name)
    archive = ROOT / 'engineering/.test-output/launcher-bootstrap/python-3.14.2-amd64.zip'
    wheels = ROOT / 'engineering/.test-output/wheels'
    empty = WORK / 'empty-wheels'; empty.mkdir()
    bad = WORK / 'bad-hash'; (bad / 'engineering').mkdir(parents=True)
    shutil.copyfile(FRESH / 'engineering/requirements-runtime.lock', bad / 'engineering/requirements-runtime.lock')
    config = json.loads((FRESH / 'launcher-config.json').read_bytes()); config['python']['sha256'] = '0' * 64
    (bad / 'launcher-config.json').write_text(json.dumps(config), encoding='utf-8')
    setup('-Offline', '-ArchivePath', archive, '-WheelDirectory', wheels, success=False, project=bad)
    assert not (bad / config['python']['directory']).exists()
    record('wrong_archive_hash_rejected_before_execution')
    marker = FRESH / 'engineering/.venv/onlinecoc-game-ready.txt'
    python = FRESH / 'engineering/.venv/Scripts/python.exe'
    assert not python.exists()
    setup('-Offline', '-ArchivePath', archive, '-WheelDirectory', empty, success=False)
    assert python.exists() and not marker.exists(), 'Failure must reach pip, not stop before environment creation.'
    record('missing_wheels_fails_without_ready_marker')
    sentinel = FRESH / 'saved-user-config.txt'; sentinel.write_text('preserve', encoding='utf-8')
    setup('-Offline', '-ArchivePath', archive, '-WheelDirectory', wheels)
    assert marker.exists() and sentinel.read_text() == 'preserve'
    record('retry_installs_runtime_and_preserves_user_file')
    setup('-Offline', '-ArchivePath', archive, '-WheelDirectory', wheels)
    setup('-VerifyOnly')
    record('repeat_install_and_verify')
    with (FRESH / 'engineering/.runtime/desktop-tools.lock').open('ab'):
        setup('-VerifyOnly', success=False)
    assert marker.exists()
    record('concurrent_installer_or_desktop_host_rejected')
    details = subprocess.check_output([str(python), '-I', '-c',
        'import sys,tkinter,json; r=tkinter.Tk();r.withdraw();print(json.dumps({"version":sys.version.split()[0],"tk":r.tk.call("info","patchlevel"),"isolated":sys.base_prefix}));r.destroy()'], creationflags=0x08000000)
    runtime = json.loads(details)
    assert str(FRESH).lower() in runtime.pop('isolated').lower()
    record('full_python_tk_and_fresh_base', **runtime)
    REPORT['pythonArchiveSha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
    REPORT['installationSource'] = 'cached official full archive and hash-locked local wheels; no download tested'
    ports = []
    for _ in range(2):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); ports.append(sock.getsockname()[1])
    serverlog = (WORK / 'services.log').open('wb')
    process = subprocess.Popen([str(python), '-B', str(ROOT / 'engineering/ai/tests/manager_ui_server.py'),
        str(WORK / 'data'), *map(str, ports)], stdout=serverlog, stderr=serverlog, creationflags=0x08000000)
    origin = f'http://127.0.0.1:{ports[1]}'
    try:
        for _ in range(150):
            assert process.poll() is None, 'Isolated services exited.'
            try:
                if httpx.get(origin, timeout=1, trust_env=False).status_code == 200: break
            except httpx.HTTPError: pass
            time.sleep(.1)
        else: raise AssertionError('Isolated services timed out.')
        entry = json.loads((WORK / 'data/entry.json').read_bytes())
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width':1280,'height':920})
            errors = []; page.on('pageerror', lambda error: errors.append(type(error).__name__))
            try:
                page.goto(origin + '/#unlock=' + entry['key'])
                expect(page.locator('#room-start')).to_be_visible()
                assert '#unlock' not in page.url
                page.locator('[data-page=providers]').click()
                page.get_by_role('button', name='编辑', exact=True).click()
                page.locator('#secret').fill('synthetic-local-onboarding-key')
                page.get_by_role('button', name='保存密钥', exact=True).click()
                expect(page.locator('#key-status')).to_have_text('密钥状态：已加密保存')
                page.get_by_role('button', name='测试连接（产生用量）', exact=True).click()
                expect(page.locator('#status')).to_contain_text('连接通过')
                record('manager_unlock_synthetic_key_and_offline_probe')
                page.locator('#manage-rooms').click(); page.locator('#room-name').fill('安装教学验收')
                page.locator('#room-url').fill(f'http://127.0.0.1:{ports[0]}')
                page.get_by_role('button', name='添加房间', exact=True).click()
                page.get_by_role('button', name='登录', exact=True).click()
                page.locator('#password').fill('test-password')
                page.get_by_role('button', name='连接', exact=True).click()
                expect(page.locator('#session-panel #text')).to_be_visible()
                page.locator('#review-open').click(); page.locator('[data-tab=settings]').click()
                page.get_by_text('服务与外发范围', exact=True).click()
                page.locator('#ai-enabled').check(); page.locator('#ai-profile').select_option('deepseek-main')
                page.locator('#ai-public').check(); page.locator('#ai-save-settings').click()
                expect(page.locator('#ai-result')).to_have_text('设置已保存')
                page.locator('#review-close').click(); page.locator('#new-chat').click()
                expect(page.locator('#session-panel #status')).to_have_text('新会话已创建')
                record('kp_room_connection_and_explicit_public_egress')
                attempts = []
                def intercept(route):
                    data = route.request.post_data_json.get('body') or {}
                    if data.get('op') == 'ai.session.submit':
                        attempts.append(data)
                        if len(attempts) == 1:
                            route.fulfill(status=503, content_type='application/json', body='{"code":"CONNECTION_FAILED"}')
                            return
                    route.continue_()
                page.route('**/manager/api/rooms/*/request', intercept)
                draft = '将新建技能初值改为 15，已有技能保持原值。'
                page.locator('#text').fill(draft); page.locator('#send').click()
                expect(page.locator('#session-panel #status')).to_contain_text('CONNECTION_FAILED')
                expect(page.locator('#text')).to_have_text(draft)
                page.locator('#send').click()
                expect(page.locator('#history')).to_contain_text('离线验收：新技能默认值 15', timeout=40000)
                assert len(attempts) == 2 and attempts[0]['args']['submissionKey'] == attempts[1]['args']['submissionKey']
                expect(page.get_by_role('button', name='查看配置裁决', exact=True)).to_be_enabled(timeout=20000)
                record('failed_submit_keeps_draft_and_retry_identity')
                record('one_offline_ai_request_reaches_review_without_approval')
                assert not errors
                REPORT['browserVersion'] = browser.version
                page.screenshot(path=str(HERE / 'onboarding.png'), full_page=True)
            finally: browser.close()
    finally:
        process.terminate(); process.wait(timeout=20); serverlog.close()
    REPORT['passed'] = True
    (HERE / 'results.json').write_text(json.dumps(REPORT, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__': main()
