"""Real package source -> checked candidate -> explicit KP adoption, isolated HTTP/UI."""
import argparse
import copy
from datetime import datetime
import json
from pathlib import Path
import secrets
import time
import traceback

import harness
import launch
import verify_integrations as integration
from harness import PACK, provision, running
from verify_integrations import ai, result
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--staged', action='store_true', help='Follow one original request through configuration publication, grant and notification')
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    source = args.source.resolve()
    output = PACK/'tests/output'/('context-autonomy-'+secrets.token_hex(4)); output.mkdir(parents=True)
    report = {'at': datetime.now().astimezone().isoformat(), 'source': str(source), 'output': str(output),
              'baseline': args.baseline, 'staged': args.staged, 'checks': [], 'externalApiCalls': 0, 'realSaveChanged': False}
    original_runtime, original_root, original_provider_root = harness.Runtime, launch.ROOT, integration.ROOT
    def runtime(options):
        options.host_control_dir = output/'host-control'
        value = original_runtime(options)
        value.command[2] = str(source/'engineering/backend/scripts/run.py')
        return value
    harness.Runtime = runtime; launch.ROOT = source; integration.ROOT = source
    new_item = {}
    mode, actor = ['configuration'], {}
    errors = []
    def respond(request):
        tools = {m['tool_call_id']: json.loads(m['content']) for m in request['messages'] if m.get('role') == 'tool'}
        def call(key, name, arguments):
            return {'role': 'assistant', 'content': None, 'tool_calls': [{'id': key, 'type': 'function',
                    'function': {'name': name, 'arguments': json.dumps(arguments, ensure_ascii=False)}}]}
        if 'source-search' not in tools:
            return call('source-search', 'room_search_data', {'types': ['config'], 'query': '地图地点与主持秘密', 'limit': 2})
        if 'source-read' not in tools:
            refs = [item['ref'] for item in tools['source-search']['items'] if item['ref']['sourceId'] == 'stumpsville']
            assert refs, tools['source-search']
            return call('source-read', 'room_read_data', {'refs': refs})
        if mode[0] == 'runtime':
            if 'actor-search' not in tools:
                return call('actor-search', 'room_search_data', {'types': ['room'], 'query': '/entities/'+actor['instanceId'], 'limit': 4})
            if 'actor-read' not in tools:
                return call('actor-read', 'room_read_data', {'refs': [item['ref'] for item in tools['actor-search']['items']]})
            if args.staged:
                if 'published-items' not in tools:
                    return call('published-items', 'pack_read_config_data', {'file':'game.json','path':['items'],'offset':20,'limit':20})
                page = tools['published-items']
                index = next(i for i, value in enumerate(page['value'], page['offset']+1) if value['id']==new_item['id'])
                return {'role':'assistant','content':json.dumps({'kind':'batch','text':'按已发布编号发放验收盾，并定向通知接收者。',
                    'actions':[{'target':'host','op':'action.invoke','args':{'actionId':'sv.grant','input':{'actor':actor['instanceId'],'item':index,'slot':11,'uses':new_item['uses']}}},
                               {'target':'host','op':'notification.send','args':{'recipientAccountIds':['player1'],'text':'context-reference-runtime：已收到验收盾。','sourceActionIndex':0}}]}, ensure_ascii=False)}
            return {'role': 'assistant', 'content': json.dumps({'kind': 'batch', 'text': '参考主持资料，按当前角色值增加一枚钱币并通知，等待KP接受参考评估。',
                'actions': [{'target': 'host', 'op': 'entity.update', 'args': {'id': actor['instanceId'], 'numbers': {'pips': actor['numbers']['pips']+1}}},
                            {'target': 'host', 'op': 'notification.send', 'args': {'recipientAccountIds': ['player1'], 'text': 'context-reference-runtime：你获得一枚钱币。', 'sourceActionIndex': 0}}]}, ensure_ascii=False)}
        if 'current-items' not in tools:
            return call('current-items', 'pack_read_config_data', {'file': 'game.json', 'path': ['items'], 'limit': 20})
        data = tools['current-items']
        assert data.get('editRef'), data
        return {'role': 'assistant', 'content': json.dumps({'kind': 'draft',
                'text': '已参考主持地图资料，并读取当前活动物品表；建议新增验收盾，待KP核对来源评估后发布。',
                'changeSet': {'schemaVersion': 1, 'configurations': [], 'sources': {}, 'data': {}, 'suggestions': []},
                **({'afterPublish':{'text':'发布后给 player1 发放新盾并定向通知。'}} if args.staged else {}),
                'dataEdits': [{'op': 'append', 'ref': data['editRef'], 'keyField': 'id', 'value': new_item}]}, ensure_ascii=False)}
    try:
        with integration.provider(output, respond) as (config, calls), running('context-autonomy', data=output/'game', ai_config=config, no_browser=True) as (runtime_value, password):
            kp, p1, p2 = provision(runtime_value, password)
            result(ai(kp, 'ai.settings.update', {'enabled': True, 'profileId': 'offline',
                'externalSources': {'public': True, 'kp': True, 'private': True}, 'auto': {'enabled': False, 'channelIds': [], 'prefix': '!ai '}}))
            before = copy.deepcopy(kp.request('/package/bundle')['data']['game.json']['items'])
            new_item.update(copy.deepcopy(next(item for item in before if item['kind'] == 'armor')))
            new_item.update(id='context-source-shield', name='参考资料验收盾', description='隔离验收：依据资料只作为设计参考，批准前不生效。')
            session = result(ai(kp, 'ai.session.create', {'title': '独立资料与当前配置联合验收'}))['sessionId']
            actor.update(p1.state()['character'])
            submitted = result(ai(kp, 'ai.session.submit', {'sessionId': session, 'text': '参考当前主持地图说明，在实际物品表追加参考资料验收盾。先读取独立资料，再读取活动items；先提交配置，等我裁决。'+('发布后向 player1 发放该盾并通知。' if args.staged else '')}))
            if not submitted.get('taskId'):
                result(ai(kp, 'ai.request.dispatch', {'requestId': submitted['requestId']}))
            deadline = time.monotonic()+120
            while time.monotonic() < deadline:
                task = next(t for t in kp.request('/api/v1/ai/sessions/'+session)['items'] if t['requestId'] == submitted['requestId'])
                if task['status'] not in ('received', 'queued', 'generating', 'validating'): break
                time.sleep(.15)
            report['task'] = {k: task.get(k) for k in ('status', 'error', 'proposalId', 'response')}
            report['loopbackModelCalls'] = len(calls)
            assert task.get('proposalId'), task
            row = next(item for item in kp.request('/api/v1/ai/rulings')['items'] if item['rulingId'] == 'proposal:'+task['proposalId'])
            report['ruling'] = {k: row.get(k) for k in ('status', 'blockingReason', 'canDecide', 'consultationAssessment')}
            assert kp.request('/package/bundle')['data']['game.json']['items'] == before
            if args.baseline:
                assert row['status'] == 'blocked' and row['blockingReason'] == 'CONSULTATION_ONLY' and not row['canDecide'], row
                report['checks'].append('old frozen runtime reproduces CONSULTATION_ONLY after authorized package reference + current host item read; no publication')
            else:
                assert row['status'] == 'pending' and row['canDecide'] and row['consultationAssessment']['requiresAcceptance'], row
                assert row['consultationAssessment']['sourceCount'] > 0
                report['checks'].append('real package reference and current artifact read produce pending source-risk candidate with no mutation')
                decision = {'rulingId': row['rulingId'], 'digest': row['digest'], 'decision': 'approve',
                            'riskDecisions': {risk['id']: '隔离验收：已核对资料差异与完整候选' for risk in row['risks']}}
                if row.get('highRisk'): decision['explicitHighRiskDigest'] = row['digest']
                c = row.get('cAssessment')
                if c and c['requiresAcceptance']:
                    decision['cReview'] = {key: c[key] for key in ('basisRevision', 'basisDigest', 'reportDigest')}
                failures = []
                for proof in (None, {'sourceDigest': '0'*64}):
                    attempt = {**decision, **({'consultationReview': proof} if proof else {})}
                    failed = ai(kp, 'ai.ruling.decide', attempt, allow_error=True)
                    assert failed.get('status') == 'rejected', failed
                    failures.append(failed.get('code'))
                decision['consultationReview'] = {'sourceDigest': row['consultationAssessment']['sourceDigest']}
                denied = ai(p1, 'ai.ruling.decide', decision, allow_error=True)
                assert denied.get('status') == 'rejected', denied
                assert kp.request('/package/bundle')['data']['game.json']['items'] == before
                report['negativeCodes'] = failures+[denied.get('code')]
                report['checks'].append('missing/wrong source proof and player approval are rejected by actual server without changing the item table')
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(channel='msedge', headless=True)
                    page = browser.new_page(viewport={'width': 1440, 'height': 960})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    commands = []
                    def record(request):
                        if request.method == 'POST' and request.url.endswith('/api/v1/ai/commands'):
                            body = request.post_data_json
                            if body.get('op') == 'ai.ruling.decide': commands.append(body)
                    page.on('request', record)
                    page.goto(runtime_value.origin+'/sessions/source-review/')
                    page.locator('[name=loginName]').fill('kp'); page.locator('[name=password]').fill(password)
                    page.get_by_role('button', name='进入冒险', exact=True).click(); page.locator('.identity').first.wait_for()
                    page.goto(runtime_value.origin+'/sessions/source-review/#/gm/rulings')
                    page.locator('[data-ruling-id="'+row['rulingId']+'"] [data-open]').click()
                    dialog = page.locator('dialog.ruling-dialog')
                    expect(dialog.locator('.consultation-assessment')).to_be_visible()
                    if args.staged:
                        details=dialog.locator('details.ruling-changes')
                        assert not details.evaluate('e=>e.open')
                        details.locator('summary').click()
                        expect(details).to_contain_text('config/game.json')
                        assert 'scene-actions.json' not in details.inner_text()
                        assert row['continuation']['status']=='waiting_publication'
                        assert len(kp.request('/api/v1/ai/sessions/'+session)['items'])==1
                        mode[0]='runtime'
                    page.screenshot(path=str(output/'actual-source-review.png'), full_page=True)
                    dialog.get_by_role('button', name='采纳评估并发布', exact=True).click()
                    expect(dialog).to_have_count(0)
                    deadline = time.monotonic()+40
                    while time.monotonic() < deadline:
                        after = kp.request('/package/bundle')['data']['game.json']['items']
                        if any(item['id'] == new_item['id'] for item in after): break
                        time.sleep(.2)
                    assert after == before+[new_item], {'count': len(after), 'expected': len(before)+1}
                    assert commands and commands[-1]['args']['consultationReview'] == decision['consultationReview']
                    replay = kp.request('/api/v1/ai/commands', commands[-1])
                    assert replay['status'] == 'committed', replay
                    assert kp.request('/package/bundle')['data']['game.json']['items'] == after
                    assert not errors, errors
                    browser.close()
                report['checks'].append('actual package dialog submits exact source proof and high-risk/C acceptance; item published once and same request replay is idempotent')
                if args.staged:
                    deadline = time.monotonic()+120
                    while time.monotonic()<deadline:
                        rows=kp.request('/api/v1/ai/sessions/'+session)['items']
                        following=[r for r in rows if r.get('continuationOrigin',{}).get('proposalId')==task['proposalId']]
                        if following and following[0]['status'] not in ('received','queued','generating','validating'):break
                        time.sleep(.2)
                    assert len(following)==1 and len(rows)==2, rows
                    runtime_task=following[0]
                else:
                    mode[0] = 'runtime'; actor.update(p1.state()['character'])
                    access = kp.request('/api/v1/ai/access')
                    result(ai(kp, 'ai.access.update', {'revision': access['revision'], 'allowPlayerChat': access['allowPlayerChat'], 'autoApproveBatches': True}))
                    runtime_session = result(ai(kp, 'ai.session.create', {'title': '参考资料的运行时裁决'}))['sessionId']
                    runtime_request = result(ai(kp, 'ai.session.submit', {'sessionId': runtime_session,
                        'text': '参考当前主持地图说明，给player1现有角色增加1枚钱币并通知。先读取当前角色，只准备待审批次。'}))
                    if not runtime_request.get('taskId'):
                        result(ai(kp, 'ai.request.dispatch', {'requestId': runtime_request['requestId']}))
                    deadline = time.monotonic()+120
                    while time.monotonic() < deadline:
                        runtime_task = next(t for t in kp.request('/api/v1/ai/sessions/'+runtime_session)['items'] if t['requestId'] == runtime_request['requestId'])
                        if runtime_task['status'] not in ('received', 'queued', 'generating', 'validating'): break
                        time.sleep(.15)
                assert runtime_task.get('batchId'), runtime_task
                runtime_row = next(item for item in kp.request('/api/v1/ai/rulings')['items'] if item['rulingId'] == 'batch:'+runtime_task['batchId'])
                assert runtime_row['status'] == 'pending' and runtime_row['consultationAssessment']['requiresAcceptance'], runtime_row
                assert p1.state()['character']['numbers'] == actor['numbers']
                runtime_decision = {'rulingId': runtime_row['rulingId'], 'digest': runtime_row['digest'], 'decision': 'approve',
                    'riskDecisions': {risk['id']: '隔离验收：接受参考资料风险' for risk in runtime_row.get('risks', [])}}
                assert ai(kp, 'ai.ruling.decide', runtime_decision, allow_error=True).get('status') == 'rejected'
                runtime_decision['consultationReview'] = {'sourceDigest': runtime_row['consultationAssessment']['sourceDigest']}
                done = result(ai(kp, 'ai.ruling.decide', runtime_decision))
                assert done['status'] == 'completed', done
                if args.staged:
                    assert p1.state()['character']['numbers']['item11'] == len(before)+1
                    assert not any('context-reference-runtime' in item.get('text', '') for item in p2.request('/api/v1/notifications?after=0&limit=100')['items'])
                else:
                    assert p1.state()['character']['numbers']['pips'] == actor['numbers']['pips']+1
                notifications = p1.request('/api/v1/notifications?after=0&limit=100')['items']
                assert len([item for item in notifications if 'context-reference-runtime' in item.get('text', '')]) == 1, notifications
                if args.staged:
                    report['stagedEvidence'] = {
                        'sessionId': session, 'proposalId': task['proposalId'], 'changeOverview': row['changeOverview'],
                        'continuationOrigin': runtime_task['continuationOrigin'], 'runtimeBatchId': runtime_task['batchId'],
                        'recipient': 'player1', 'slot': 11, 'receivedItemIndex': len(after), 'matchingNotifications': 1,
                    }
                    report['checks'].append('single original request, published item path, automatic follow-up in same session, grant to player1, one targeted notice')
                else:
                    report['checks'].append('source-risk runtime batch stays pending even with auto-approval enabled, requires acceptance, then changes current money and delivers one actual notification')
                report['loopbackModelCalls'] = len(calls)
            report['passed'] = True
    except Exception as exc:
        report.update(passed=False, error=repr(exc), failingLine=traceback.extract_tb(exc.__traceback__)[-1].line)
    finally:
        harness.Runtime, launch.ROOT, integration.ROOT = original_runtime, original_root, original_provider_root
    report.update(passedCount=len(report['checks']), pageErrors=errors)
    canonical = PACK/'tests'/('context-autonomy-baseline-results.json' if args.baseline else 'context-autonomy-results.json')
    if canonical.exists():
        old = json.loads(canonical.read_text(encoding='utf-8'))
        report['previousRuns'] = old.get('previousRuns', [])+[{key: value for key, value in old.items() if key != 'previousRuns'}]
    for path in (canonical, output/'results.json'):
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: report.get(key) for key in ('passed', 'passedCount', 'error', 'output', 'ruling')}, ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
