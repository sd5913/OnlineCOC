"""Real package/host/AI roundtrip with an explicitly synthetic repair provider."""
import copy
import hashlib
import json
import secrets
import time
from datetime import datetime

from harness import PACK, running, provision
from verify_integrations import ai, result, provider
from playwright.sync_api import expect, sync_playwright


def main():
    output = PACK / 'tests/output' / ('batch-workflow-' + secrets.token_hex(4))
    output.mkdir(parents=True)
    report = {'checkedAt': datetime.now().astimezone().isoformat(), 'checks': [],
              'realProviderCalls': 0, 'realSaveChanged': False,
              'scope': 'real isolated host and UI, synthetic model outputs',
              'evidenceDirectory': output.relative_to(PACK).as_posix()}
    report['packageSourceSha256'] = {rel: hashlib.sha256((PACK / rel).read_bytes()).hexdigest() for rel in ('ui/batch-details.js', 'ui/keeper-rulings.js', 'ui/app.js', 'ui/styles.css', 'tools/build_web.py', 'tools/launch.py')}
    generated = {'actions': []}
    page_errors = []
    calls = []

    def respond(request):
        actions = copy.deepcopy(generated['actions'])
        # The first output reproduces the original item-number/slot confusion.
        if len(calls) == 1:
            actions[0]['args']['input']['slot'] = 3
        return {'role': 'assistant', 'content': json.dumps({'kind': 'batch', 'text': '消耗第5槽口粮一次，短休后通知 player1。', 'actions': actions})}

    try:
        with provider(output, respond) as (config, calls):
            local = json.loads(config.read_text(encoding='utf-8'))
            local['profiles'][0]['limits'].update(maxRepairAttempts=2, maxTransportRetries=0, taskTimeoutMs=120000)
            config.write_text(json.dumps(local), encoding='utf-8')
            with running('batch-workflow', data=output / 'game', ai_config=config, no_browser=True) as (runtime, password):
                kp, p1, p2 = provision(runtime, password)
                actor = p1.state()['character']['instanceId']
                numbers = {'hp': 1, 'maxHp': 4, 'litSlot': 0}
                for slot in range(1, 21):
                    numbers.update({f'item{slot}': 0, f'uses{slot}': 0, f'ticks{slot}': 0})
                numbers.update(item3=6, uses3=0, item5=3, uses5=3)
                kp.command('entity.update', {'id': actor, 'numbers': numbers})
                for player in (p1, p2):
                    for notice in player.request('/api/v1/notifications?after=0&limit=100')['items']:
                        player.action('notification.ack', {'notificationId': notice['notificationId']})
                before = copy.deepcopy(p1.state()['character']['numbers'])
                generated['actions'] = [
                    {'target': 'host', 'op': 'action.invoke', 'args': {'actionId': 'sv.inventory', 'input': {'actor': actor, 'operation': 'use', 'slot': 5, 'value': 1}}},
                    {'target': 'host', 'op': 'action.invoke', 'args': {'actionId': 'sv.rest', 'input': {'actor': actor, 'kind': 'short', 'attribute': ''}}},
                    {'target': 'host', 'op': 'notification.send', 'args': {'recipientAccountIds': ['player1'], 'text': '口粮消耗和短休已完成，请查看角色状态。', 'sourceActionIndex': 1}}]
                result(ai(kp, 'ai.access.update', {'revision': 1, 'allowPlayerChat': False, 'allowRuntimeChanges': True, 'autoApproveBatches': False}))
                result(ai(kp, 'ai.settings.update', {'enabled': True, 'profileId': 'offline', 'externalSources': {'public': True, 'kp': True, 'private': True}, 'auto': {'enabled': False, 'channelIds': [], 'prefix': '!ai '}}))
                sid = result(ai(kp, 'ai.session.create', {'title': '口粮槽位与原子批次联合验收'}))['sessionId']
                submitted = result(ai(kp, 'ai.session.submit', {'sessionId': sid, 'text': f'对 player1 的角色 {actor} 消耗第5槽口粮一次并短休，然后通知。第3槽是奶酪，不可消耗；只准备待审指令。'}))
                if not submitted.get('taskId'):
                    result(ai(kp, 'ai.request.dispatch', {'requestId': submitted['requestId']}))
                deadline = time.monotonic() + 130
                while time.monotonic() < deadline:
                    task = kp.request('/api/v1/ai/sessions/' + sid)['items'][-1]
                    if task['status'] not in ('received', 'queued', 'generating', 'validating'):
                        break
                    time.sleep(.2)
                assert task['status'] == 'review_ready' and task.get('batchId'), task
                assert 2 <= len(calls) <= 3, len(calls)
                ruling_id = 'batch:' + task['batchId']
                item = next(x for x in kp.request('/api/v1/ai/rulings')['items'] if x['rulingId'] == ruling_id)
                assert item['actions'][0]['args']['input']['slot'] == 5
                assert item['preflight']['status'] in ('passed', 'runtime_required'), item
                assert p1.state()['character']['numbers'] == before
                assert not p1.request('/api/v1/notifications?after=0&limit=100')['items']
                report['checks'].append('wrong-slot-repaired-without-human-input-or-game-mutation')

                with sync_playwright() as pw:
                    browser = pw.chromium.launch(channel='msedge', headless=True)
                    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
                    page.on('pageerror', lambda e: page_errors.append(str(e)))
                    submitted_commands = []
                    def collect(request):
                        if request.method == 'POST' and request.url.endswith('/api/v1/ai/commands'):
                            body = request.post_data_json
                            if body and body.get('op') == 'ai.ruling.decide':
                                submitted_commands.append(body)
                    page.on('request', collect)
                    expect.set_options(timeout=25000)
                    page.goto(runtime.origin + '/sessions/batch-browser/')
                    page.locator('[name=loginName]').fill('kp')
                    page.locator('[name=password]').fill(password)
                    page.get_by_role('button', name='进入冒险', exact=True).click()
                    page.locator('.identity').first.wait_for()
                    page.goto(runtime.origin + '/sessions/batch-browser/#/gm/rulings')
                    page.locator('[data-ruling-id="' + ruling_id + '"] [data-open]').click()
                    dialog = page.locator('dialog.ruling-dialog')
                    expect(dialog.locator('.batch-action-list>li')).to_have_count(3)
                    expect(dialog.locator('.batch-action-list>li').first).to_contain_text('槽位 5')
                    expect(dialog).to_contain_text('需运行判定')
                    page.screenshot(path=str(output / 'before-approval.png'), full_page=True)
                    report['checks'].append('real-ruling-displays-three-actions-and-preflight')
                    dialog.get_by_role('button', name='接受并执行', exact=True).click()
                    expect(page.locator('dialog.ruling-dialog')).to_have_count(0)
                    notice_ready = "() => Object.keys(localStorage).filter(k=>k.startsWith('sv.desktop.rulingNotices.')).some(k=>JSON.parse(localStorage[k]).some(n=>n.status==='completed'&&n.batch?.execution?.committedCount===3))"
                    deadline = time.monotonic() + 25
                    while not page.evaluate(notice_ready) and time.monotonic() < deadline:
                        time.sleep(.1)
                    assert page.evaluate(notice_ready), 'committed batch notification not received'
                    final = next(x for x in kp.request('/api/v1/ai/rulings')['items'] if x['rulingId'] == ruling_id)
                    assert final['status'] == 'completed', final
                    assert [x['status'] for x in final['execution']['items']] == ['committed'] * 3
                    changed = p1.state()['character']['numbers']
                    assert changed['uses5'] == 2 and 3 <= changed['hp'] <= 4, changed
                    assert changed['uses3'] == 0
                    report['checks'].append('approved-batch-commits-consumption-rest-and-notification')
                    notices = p1.request('/api/v1/notifications?after=0&limit=100')['items']
                    assert len(notices) == 1, notices
                    assert not p2.request('/api/v1/notifications?after=0&limit=100')['items']
                    assert submitted_commands
                    replay = kp.request('/api/v1/ai/commands', submitted_commands[-1])
                    assert replay['status'] == 'committed', replay
                    assert p1.state()['character']['numbers'] == changed
                    assert len(p1.request('/api/v1/notifications?after=0&limit=100')['items']) == 1
                    report['checks'].append('same-command-replay-has-no-extra-consumption-roll-or-notice')
                    page.locator('[data-action="queue-tab"][data-args*="messages"]').click()
                    page.locator('#message-queue-list [data-action="ruling-notice"]').first.click()
                    notice_dialog = page.locator('#dialog')
                    expect(notice_dialog.locator('.batch-action-list>li')).to_have_count(3)
                    expect(notice_dialog).to_contain_text('已提交 3 · 失败 0 · 未执行 0')
                    expect(notice_dialog.locator('.batch-action-reason')).to_have_count(0)
                    expect(notice_dialog).not_to_contain_text('BATCH_RUNTIME_REQUIRED')
                    page.screenshot(path=str(output / 'execution-notice.png'), full_page=True)
                    assert not page_errors, page_errors
                    report['checks'].append('local-notice-displays-persisted-outcomes-without-browser-errors')
                    browser.close()
                report['passed'] = True
    except Exception as exc:
        report.update(passed=False, errorType=type(exc).__name__, error=str(exc)[:4000])
    report.update(passedCount=len(report['checks']), syntheticProviderCalls=len(calls), pageErrors=page_errors)
    canonical = PACK / 'tests/batch-workflow-results.json'
    if canonical.exists():
        previous = json.loads(canonical.read_text(encoding='utf-8'))
        report['previousRuns'] = [*previous.get('previousRuns', []), {k: previous.get(k) for k in ('passed', 'checks', 'error', 'evidenceDirectory')}]
    for path in (output / 'report.json', canonical):
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report.get(k) for k in ('passed', 'passedCount', 'syntheticProviderCalls', 'error', 'evidenceDirectory')}, ensure_ascii=True))
    return 0 if report.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
