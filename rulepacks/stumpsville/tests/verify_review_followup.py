"""ISSUE-017: real isolated host, deterministic provider, and package browser UI."""
import copy
import hashlib
import json
import secrets
import time
from datetime import datetime

from harness import PACK, Account, provision, running
from verify_integrations import ai, provider, result
from integrations import write_json
from playwright.sync_api import sync_playwright, expect


def wait_task(account, session_id, request_id):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        row = next((r for r in account.request('/api/v1/ai/sessions/' + session_id)['items'] if r['requestId'] == request_id), None)
        if row and row['status'] not in {'received', 'queued', 'generating', 'validating'}:
            return row
        time.sleep(.15)
    raise AssertionError({'waitingFor': request_id, 'last': row})


def submit(account, args):
    submitted = result(ai(account, 'ai.session.submit', args))
    if not submitted.get('taskId'):
        result(ai(account, 'ai.request.dispatch', {'requestId': submitted['requestId']}))
    return submitted


def main():
    output = PACK / 'tests/output' / ('review-followup-' + secrets.token_hex(4))
    output.mkdir(parents=True)
    prior = PACK / 'tests/review-followup-results.json'
    report = {'checkedAt': datetime.now().astimezone().isoformat(), 'checks': [], 'realSaveChanged': False,
              'realProviderCalls': 0, 'provider': 'deterministic loopback', 'evidenceDirectory': output.relative_to(PACK).as_posix()}
    if prior.exists():
        old = json.loads(prior.read_text(encoding='utf-8'))
        report['previousRuns'] = [*old.get('previousRuns', []), {k: old.get(k) for k in ['passed', 'error', 'checks', 'evidenceDirectory']}]
    mode, target, amount = ['plan'], [None], [1]
    errors, calls = [], []

    def respond(request):
        tools = [m for m in request['messages'] if m.get('role') == 'tool']
        def call(name, args):
            return {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'fixture-' + str(len(tools)), 'type': 'function',
                    'function': {'name': name, 'arguments': json.dumps(args)}}]}
        if mode[0] == 'plan':
            answer = {'kind': 'plan', 'text': '已核对该事件，原申请与后续方案仍需分别核对结果。'}
        elif mode[0] == 'known':
            if not tools:
                return call('room_search_knowledge', {'query': '入口隧道', 'limit': 10})
            latest = json.loads(tools[-1]['content'])
            items = latest.get('items', [])
            assert items, latest
            if not items[0].get('evidenceId'):
                return call('room_read_knowledge', {'refs': [i['ref'] for i in items[:3]]})
            answer = {'kind': 'known', 'evidence': [items[0]['evidenceId']], 'next': 'none'}
        else:
            if not tools:
                return call('room_search_data', {'types': ['entity'], 'query': '木栗', 'limit': 10})
            latest = json.loads(tools[-1]['content'])
            if len(tools) == 1:
                return call('room_read_data', {'refs': [i['ref'] for i in latest['items']]})
            answer = {'kind': 'batch', 'text': '保留的历史方案：给木栗增加' + str(amount[0]) + '枚钱币，仅修改目标角色。',
                      'actions': [{'target': 'host', 'op': 'entity.update', 'args': {'id': target[0]['instanceId'], 'numbers': {'pips': target[0]['numbers']['pips'] + amount[0]}}}]}
        return {'role': 'assistant', 'content': json.dumps(answer)}

    try:
        with provider(output, respond) as (config, calls):
            with running('review-followup', data=output / 'game', ai_config=config, no_browser=True) as (runtime, password):
                kp, p1, p2 = provision(runtime, password)
                result(ai(kp, 'ai.settings.update', {'enabled': True, 'profileId': 'offline', 'externalSources': {'public': True, 'kp': True, 'private': True}, 'auto': {'enabled': False, 'channelIds': [], 'prefix': '!ai '}}))
                access = kp.request('/api/v1/ai/access')
                result(ai(kp, 'ai.access.update', {'revision': access['revision'], 'allowPlayerChat': True, 'autoApproveBatches': False, 'autoApproveConfigurations': False}))
                req = p1.action('request', {'kind': 'free', 'manual': True, 'text': '同一机关事件：请说明如何处理奶酪机关'})
                review = kp.action('ai.review', {'kind': 'request', 'id': req['requestId']})
                original = wait_task(kp, review['sessionId'], review['requestId'])
                assert original.get('response'), original
                before_calls = len(calls)
                repeated = kp.action('ai.review', {'kind': 'request', 'id': req['requestId']})
                assert (repeated['sessionId'], repeated['requestId']) == (review['sessionId'], review['requestId'])
                event = next(e for e in kp.state()['events'] if e.get('requestId') == req['requestId'] and e['account'] == 'player1')
                related = kp.action('ai.review', {'kind': 'event', 'id': event['id'], 'account': 'player1'})
                assert (related['sessionId'], related['requestId']) == (review['sessionId'], review['requestId']), related
                assert len(calls) == before_calls
                report['checks'].append('重复转交与同request关联事件复用审核任务，无多余模型调用')

                mode[0] = 'batch'; target[0] = p1.state()['character']
                sid = result(ai(kp, 'ai.session.create', {'title': '历史正文与关联方案验收'}))['sessionId']
                args = {'sessionId': sid, 'text': '给木栗增加1枚钱币，准备待审方案', 'submissionKey': 'followup-first'}
                first = submit(kp, args)
                first_task = wait_task(kp, sid, first['requestId']); assert first_task.get('batchId'), first_task
                repeated = result(ai(kp, 'ai.session.submit', args)); assert repeated['requestId'] == first['requestId']
                amount[0] = 2
                second = submit(kp, {'sessionId': sid, 'text': '将同一方案改为增加2枚钱币', 'replyToRequestId': first['requestId'], 'submissionKey': 'followup-second'})
                second_task = wait_task(kp, sid, second['requestId']); assert second_task.get('batchId'), second_task
                rows = kp.request('/api/v1/ai/rulings')['items']
                first_row = next(r for r in rows if r['rulingId'] == 'batch:' + first_task['batchId'])
                second_row = next(r for r in rows if r['rulingId'] == 'batch:' + second_task['batchId'])
                assert first_row['queueStatus'] == 'superseded' and not first_row['canDecide'], first_row
                assert first_row['supersededBy'] == second_row['rulingId'] and second_row['canDecide']
                denied = ai(kp, 'ai.ruling.decide', {'rulingId': first_row['rulingId'], 'digest': first_row['digest'], 'decision': 'approve'}, allow_error=True)
                assert denied.get('status') != 'committed', denied
                report['checks'].append('提交键阻止重交；明确同事件新候选通过后替代旧项，旧裁决在服务端拒绝批准')

                archived = result(ai(kp, 'ai.request.create', {'sourceKind': 'manual', 'text': '无需继续处理的中间讨论'}))
                archive_id = archived['requestId']
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(channel='msedge', headless=True)
                    def login(account, route):
                        page = browser.new_page(viewport={'width': 1440, 'height': 960})
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.goto(runtime.origin + '/sessions/followup-ui-' + account + '/')
                        page.locator('[name=loginName]').fill(account); page.locator('[name=password]').fill(password)
                        page.get_by_role('button', name='进入冒险', exact=True).click(); page.locator('.identity').first.wait_for(state='attached')
                        page.goto(runtime.origin + '/sessions/followup-ui-' + account + '/#/' + route)
                        return page
                    page = login('kp', 'gm/rulings'); expect.set_options(timeout=30000)
                    try:
                        expect(page.locator('[data-ruling-id="' + first_row['rulingId'] + '"]')).to_have_count(0)
                        card = page.locator('[data-ruling-id="' + second_row['rulingId'] + '"]'); expect(card).to_be_visible()
                        card.get_by_role('button', name='查看并裁决', exact=True).click()
                        page.locator('.ruling-dialog [data-queue-archive]').click()
                        expect(page.locator('.ruling-dialog')).to_have_count(0); expect(card).to_have_count(0)
                        page.get_by_role('tab', name='已归档', exact=True).click(); expect(card).to_be_visible()
                        old = page.locator('[data-ruling-id="' + first_row['rulingId'] + '"]'); expect(old).to_contain_text('已由后续方案替代')
                        card.get_by_role('button', name='查看并裁决', exact=True).click()
                        page.locator('.ruling-dialog').get_by_role('button', name='恢复到裁决队列', exact=True).click()
                        page.get_by_role('tab', name=__import__('re').compile('裁决队列')).click(); expect(card).to_be_visible()
                        task_card = page.locator('[data-ai-request="' + archive_id + '"]'); expect(task_card).to_be_visible()
                        task_card.get_by_role('button', name='归档此项', exact=True).click(); expect(task_card).to_have_count(0)
                        page.reload(); expect(task_card).to_have_count(0)
                        page.get_by_role('tab', name='已归档', exact=True).click(); expect(task_card).to_be_visible()
                        page.set_viewport_size({'width': 390, 'height': 844})
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
                        page.screenshot(path=str(output / 'archived-390.png'), full_page=True)
                        report['checks'].append('包侧手动归档与恢复使用服务端记录，自动替代入历史，刷新保持且390px可达')

                        result(ai(kp, 'ai.ruling.decide', {'rulingId': second_row['rulingId'], 'digest': second_row['digest'], 'decision': 'approve'}))
                        history = next(r for r in kp.request('/api/v1/ai/sessions/' + sid)['items'] if r['requestId'] == second['requestId'])
                        assert history['response'] == second_task['response'] and history['sourceState'] == 'stale', history
                        history_row = next(r for r in kp.request('/api/v1/ai/rulings')['items'] if r['rulingId'] == second_row['rulingId'])
                        assert history_row['summary'] == second_row['summary'] and history_row['status'] == 'completed', history_row
                        fulfilled = next(r for r in kp.request('/api/v1/ai/rulings')['items'] if r['rulingId'] == first_row['rulingId'])
                        assert fulfilled['queueStatus'] == 'archived' and not fulfilled['canRestore'], fulfilled
                        assert fulfilled['resolution']['targetId'] == second_row['rulingId'] and fulfilled['resolution']['receiptRefs'], fulfilled
                        assert p1.state()['character']['numbers']['pips'] == target[0]['numbers']['pips'] + 2
                        page.set_viewport_size({'width': 1440, 'height': 960}); page.reload()
                        page.locator('#kp-ai-embedded .session-select').select_option(sid)
                        expect(page.locator('#kp-ai-embedded')).to_contain_text('保留的历史方案')
                        expect(page.locator('#kp-ai-embedded')).to_contain_text('资料依据已变化')
                        page.screenshot(path=str(output / 'retained-history.png'), full_page=True)
                        report['checks'].append('实际执行后原回复仍显示；核验成功回执后关联前驱标为需求已完成，保留完成批次定位且不能恢复重做')

                        mode[0] = 'known'
                        player_sid = result(ai(p1, 'ai.session.create', {'title': '奶酪机关资料的紧凑引用'}))['sessionId']
                        submitted = result(ai(p1, 'ai.session.submit', {'sessionId': player_sid, 'text': '这里的奶酪机关具体怎么连接的？'}))
                        known = wait_task(p1, player_sid, submitted['requestId'])
                        assert known.get('response') and '条目 1' not in known['response'] and '已记录行动' not in known['response'], known
                        player = login('player1', 'play/scene'); player.locator('#comm-tab-ai').click()
                        player.locator('.session-select').select_option(player_sid)
                        expect(player.locator('.reference-chip').first).to_be_visible()
                        player.locator('.reference-chip').first.click()
                        expect(player.locator('dialog .stumpsville-reference')).to_be_visible()
                        expect(player.locator('dialog .stumpsville-reference')).to_contain_text('入口隧道')
                        player.screenshot(path=str(output / 'player-reference-detail.png'), full_page=True)
                        player.locator('dialog[open]').evaluate('(dialog)=>dialog.close()')
                        player.set_viewport_size({'width': 390, 'height': 844})
                        player.locator('[data-action=workspace-column][data-args*=communication]').click()
                        assert player.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
                        player.screenshot(path=str(output / 'player-compact-390.png'), full_page=True)
                        report['checks'].append('PL真实知识回答只显示紧凑授权引用入口，点击复用语义详情，正文不铺行动树')
                        assert not errors, errors
                    except Exception:
                        page.screenshot(path=str(output / 'failure.png'), full_page=True)
                        raise
                    finally:
                        browser.close()
                report['loopbackCalls'] = len(calls)
            with running('review-followup-restart', data=output / 'game', ai_config=config, no_browser=True) as (runtime, _):
                kp = Account(runtime.origin, 'kp', password, 'restart')
                item = next(r for r in kp.request('/api/v1/ai/tasks?limit=100')['items'] if r['requestId'] == archive_id)
                assert item['archived'] and item['text'] == '无需继续处理的中间讨论'
                history = next(r for r in kp.request('/api/v1/ai/sessions/' + sid)['items'] if r['requestId'] == second['requestId'])
                assert history['response'] == second_task['response']
                report['checks'].append('同档重启保留手动归档及已执行旧回复，不重新调用模型')
        report['passed'] = True
    except Exception as error:
        report.update(passed=False, errorType=type(error).__name__, error=str(error)[:3500])
    root = PACK.parents[1]
    tracked = ['engineering/ai/src/onlinecoc_ai/' + name for name in ['api.py', 'rulings.py', 'sessions.py', 'review_queue.py', 'known_answers.py']]
    tracked += ['engineering/ai/web/components/chat.js', 'engineering/contracts/ai-operations.json', 'rulepacks/stumpsville/ui/keeper-queue.js', 'rulepacks/stumpsville/ui/keeper-rulings.js', 'rulepacks/stumpsville/tools/ai_review.py']
    report['sourceDigests'] = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in tracked}
    report.update(pageErrors=errors, passedCount=len(report['checks']), loopbackCalls=len(calls))
    write_json(output / 'report.json', report); write_json(prior, report)
    print(json.dumps({k: report.get(k) for k in ['passed', 'passedCount', 'errorType', 'error', 'evidenceDirectory']}, ensure_ascii=True), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
