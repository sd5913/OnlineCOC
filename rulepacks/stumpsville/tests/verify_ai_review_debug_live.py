"""Opt-in DeepSeek replay from player intent to a KP source review and item candidate."""
import argparse
import copy
from datetime import datetime
import json
import secrets
import time

from harness import PACK, running, provision
from integrations import ROOT, write_json
from verify_integrations import ai, result
from verify_ai_rulings_live import observed_provider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    if not args.live:
        parser.error('--live is required for billable calls')
    path = ROOT/'engineering/ai/config/ai-providers.json'; original = path.read_bytes()
    profile = next(p for p in json.loads(original)['profiles'] if p['profileId'] == 'deepseek-main')
    output = PACK/'tests/output'/('ai-review-debug-live-'+secrets.token_hex(4)); output.mkdir(parents=True)
    report = {'checkedAt': datetime.now().astimezone().isoformat(), 'requestedModel': profile['model'],
              'realSaveChanged': False, 'calls': [], 'turns': [], 'evidenceDirectory': output.relative_to(PACK).as_posix()}
    prior = PACK/'tests/ai-review-debug-live-results.json'
    if prior.exists():
        previous = json.loads(prior.read_text(encoding='utf-8'))
        report['previousRuns'] = [*previous.get('previousRuns', []), {k: previous.get(k) for k in ('checkedAt', 'passed', 'realCalls', 'confirmedTokens', 'evidenceDirectory')}]
    outputs = []; evidence = []
    try:
        with observed_provider(profile, report['calls'], outputs, inject_fault=False, call_limit=24, tool_evidence=evidence) as selected:
            # Exercise the current service's actual output/thinking settings.
            selected['request'] = copy.deepcopy(profile['request'])
            report['requestSettings'] = {k: selected['request'].get(k) for k in ('maxOutputTokens', 'thinking')}
            config = output/'ai-providers.json'; write_json(config, {'schemaVersion': 1, 'profiles': [selected]})
            with running('ai-review-live', data=output/'game', ai_config=config, no_browser=True) as (runtime, password):
                kp, p1, p2 = provision(runtime, password)
                result(ai(kp, 'ai.settings.update', {'enabled': True, 'profileId': selected['profileId'],
                    'externalSources': {'public': True, 'kp': True, 'private': True}, 'auto': {'enabled': False, 'channelIds': [], 'prefix': '!ai '}}))
                access = kp.request('/api/v1/ai/access')
                result(ai(kp, 'ai.access.update', {'revision': access['revision'], 'allowPlayerChat': True,
                    'autoApproveBatches': True, 'autoApproveConfigurations': True, 'allowAdminRoomRead': True,
                    'allowRuntimeChanges': True, 'allowConfigurationChanges': True, 'allowPlayerRequests': True}))
                before = kp.request('/package/bundle')['data']['game.json']; actor = p1.state()['character']
                baseline = copy.deepcopy(actor['numbers'])
                text = '我想用火把给针剑附魔，让其可以施加火焰伤害'
                sid = result(ai(p1, 'ai.session.create', {'title': '火焰针剑来源申请'}))['sessionId']
                application = result(ai(p1, 'ai.player.request', {'sessionId': sid, 'text': text}))
                ruling = next(r for r in kp.request('/api/v1/ai/rulings')['items'] if r['rulingId'] == application['rulingId'])
                accepted = result(ai(kp, 'ai.ruling.decide', {'rulingId': ruling['rulingId'], 'digest': ruling['digest'], 'decision': 'approve'}))
                review = accepted['reviewSessionId']; report['reviewSessionId'] = review
                def settle(prompt):
                    start = time.monotonic()
                    print(json.dumps({'phase': 'KP review', 'prompt': prompt}, ensure_ascii=False), flush=True)
                    while time.monotonic()-start < 320:
                        task = kp.request('/api/v1/ai/sessions/'+review)['items'][-1]
                        if task['status'] not in {'received', 'queued', 'generating', 'validating'}:
                            break
                        time.sleep(1)
                    report['turns'].append({'prompt': prompt, 'task': task, 'seconds': round(time.monotonic()-start, 2)})
                    write_json(output/'progress.json', report)
                    return task
                task = settle('KP 接收所引用的玩家申请')
                assert task['text'] != text and task.get('reviewSource'), task
                assert task.get('error') is None and task['status'] not in {'failed', 'blocked'}, task
                def candidate():
                    return next((r for r in kp.request('/api/v1/ai/rulings')['items'] if r.get('sessionId') == review and r['kind'] == 'configuration'), None)
                proposal = candidate()
                if not proposal:
                    instruction = ('KP 选择先新增一个独立物品定义：id 为 flame-needle，名称火焰针剑，沿用针剑的槽数、用量、基础伤害和用量检查，'
                        '描述写明点燃后造成火焰属性伤害；当前规则没有元素抗性时不虚构额外结算字段。'
                        '请读取当前活动 game.json 并在 items 末尾追加，保留其余完整配置，提交高危候选供我审核。'
                        '本步不发放、不替换、不消耗角色已有物品，也不执行修改。')
                    submitted = result(ai(kp, 'ai.session.submit', {'sessionId': review, 'text': instruction}))
                    if not submitted.get('taskId'):
                        result(ai(kp, 'ai.request.dispatch', {'requestId': submitted['requestId']}))
                    task = settle(instruction); proposal = candidate()
                assert proposal, {'task': task, 'queue': kp.request('/api/v1/ai/rulings')['items']}
                deadline = time.monotonic()+90
                while proposal['status'] in {'draft', 'validating'} and time.monotonic() < deadline:
                    time.sleep(.5); proposal = candidate()
                report['proposal'] = proposal
                assert proposal['status'] == 'pending' and proposal['highRisk'], proposal
                assert kp.request('/package/bundle')['data']['game.json'] == before
                assert p1.state()['character']['numbers'] == baseline
                assert p1.request('/api/v1/ai/sessions/'+review, allow_error=True).get('code')
                assert p2.request('/api/v1/ai/sessions/'+sid, allow_error=True).get('code')
                # Require actual read-tool evidence of the held items and active game data.
                tool_messages = [m for e in evidence for m in e['request']['messages'] if m.get('role') == 'tool']
                decoded = []
                for message in tool_messages:
                    content = message.get('content', '')
                    try: content = json.loads(content)
                    except (ValueError, TypeError): pass
                    decoded.append(json.dumps(content, ensure_ascii=False))
                read_text = '\n'.join(decoded)
                report['actualItemsRead'] = all(word in read_text for word in ['针剑', '火把', 'sv.character', 'game.json'])
                assert report['actualItemsRead'], 'missing actual item/character reads'
                report['decision'] = result(ai(kp, 'ai.ruling.decide', {'rulingId': proposal['rulingId'], 'digest': proposal['digest'],
                    'explicitHighRiskDigest': proposal['digest'], 'decision': 'approve',
                    'riskDecisions': {r['id']: '仅隔离测试：核对原数据保留、物品追加与风险说明' for r in proposal.get('risks', [])}}))
                kp.state(); after = kp.request('/package/bundle')['data']['game.json']
                assert after['items'][:len(before['items'])] == before['items'] and len(after['items']) > len(before['items'])
                assert any('火焰' in i['name'] for i in after['items'][len(before['items']):])
                assert p1.state()['character']['numbers'] == baseline
                report['debug'] = kp.request('/api/v1/ai/debug?sessionId='+review)
                report['passed'] = True
    except Exception as error:
        report.update(passed=False, errorType=type(error).__name__, error=str(error)[:1800])
    finally:
        report['persistentProviderConfigUnchanged'] = path.read_bytes() == original
        report['realCalls'] = sum(not c.get('injected') for c in report['calls'])
        report['confirmedTokens'] = sum(c.get('usage', {}).get('total_tokens', 0) for c in report['calls'])
        report['returnedModels'] = sorted({e['response']['model'] for e in evidence if isinstance(e['response'].get('model'), str)})
        write_json(output/'fixture-model-tools.json', evidence); write_json(output/'fixture-model-outputs.json', outputs)
        write_json(output/'report.json', report); write_json(prior, report)
        print(json.dumps({k: report.get(k) for k in ('passed', 'realCalls', 'confirmedTokens', 'returnedModels', 'errorType', 'evidenceDirectory')}, ensure_ascii=False), flush=True)
    return 0 if report.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
