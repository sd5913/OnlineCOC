"""Isolated public-HTTP configuration CRUD matrix; no live model calls."""
import argparse
import copy
from datetime import datetime
import json
from pathlib import Path
import secrets
import time

from harness import PACK, running, provision, Account
from integrations import write_json
from verify_integrations import provider, ai, result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch',choices=['all','npc','items','map','rules','restart'],default='all')
    parser.add_argument('--output-root',type=Path,default=PACK/'tests/output')
    args=parser.parse_args()
    output = args.output_root.resolve()/('ai-config-matrix-'+args.batch+'-'+secrets.token_hex(4))
    output.mkdir(parents=True)
    report = {'checkedAt': datetime.now().astimezone().isoformat(), 'realSaveChanged': False,
              'realProviderCalls': 0, 'batch':args.batch, 'cases': [], 'operations':[], 'evidenceDirectory': output.relative_to(PACK).as_posix()}
    prior = PACK/'tests'/('ai-config-matrix'+('' if args.batch=='all' else '-'+args.batch)+'-results.json')
    if prior.exists():
        old = json.loads(prior.read_text(encoding='utf-8'))
        report['previousRuns'] = [*old.get('previousRuns', []), {k: old.get(k) for k in ('checkedAt', 'passed', 'rates', 'evidenceDirectory')}]
    entities = {}
    groups={'npc':{'npc-add','npc-update','npc-delete-in-use','npc-delete-unused'},
            'items':{'item-add','weapon-add','container-as-item-add','item-update','item-delete','item-duplicate-id','container-undeclared-capacity'},
            'map':{'map-add','map-update','map-delete','map-dangling-exit','scene-player-text-update'},
            'rules':{'npc-add','rule-add','rule-update','core-check-update','rule-source-delete-unsupported'},'restart':{'item-add'}}

    def case(key, expectation, fn):
        if args.batch!='all' and key!='same-save-restart-session' and key not in groups[args.batch]:return
        row = {'id': key, 'expectation': expectation, 'passed': False}
        report['cases'].append(row)
        started=time.monotonic()
        try:
            row['evidence'] = fn()
            row['passed'] = True
        except Exception as error:
            row.update(errorType=type(error).__name__, error=str(error)[:3500])
        row['seconds']=round(time.monotonic()-started,2)
        write_json(output/'progress.json', report)
        print(json.dumps({k: row[k] for k in ('id', 'expectation', 'passed')}, ensure_ascii=False), flush=True)

    try:
        with provider(output) as (config, calls):
            with running('ai-config-matrix', data=output/'game', ai_config=config, no_browser=True) as (runtime, password):
                kp, p1, p2 = provision(runtime, password)
                def current(): return kp.request('/package/bundle')
                def game(): return copy.deepcopy(current()['data']['game.json'])
                def configuration(key): return copy.deepcopy(kp.request('/api/v1/admin')['configurations'][key])
                def measured_ai(key,op,args):
                    operation={'case':key,'op':op};report['operations'].append(operation);started=time.monotonic()
                    try:
                        value=result(ai(kp,op,args));operation['passed']=True;return value
                    except Exception as error:
                        operation.update(passed=False,error=str(error)[:500]);raise
                    finally:operation['seconds']=round(time.monotonic()-started,2)
                def proposal(key, delta, reject=False):
                    candidate = {'schemaVersion': 1, 'configurations': [], 'sources': {}, 'data': {}, 'suggestions': [], **delta}
                    draft = measured_ai(key, 'ai.draft.create', {'text': '隔离矩阵 '+key, 'changeSet': candidate})
                    checked = measured_ai(key, 'ai.proposal.validate', {'proposalId': draft['proposalId'], 'revision': 1})
                    write_json(output/(key+'-validation.json'), checked)
                    feedback={'status':checked['proposal']['status'],'reports':[
                        {'level':r['level'],'status':r['status'],'findings':r['findings']} for r in checked['reports']]}
                    if reject:
                        assert checked['proposal']['status'] == 'blocked', feedback
                        return {'status': 'blocked', 'reports': checked['reports']}
                    assert checked['proposal']['status'] == 'review_ready', feedback
                    row = next(r for r in kp.request('/api/v1/ai/rulings')['items'] if r['rulingId'] == 'proposal:'+draft['proposalId'])
                    assert row['status'] == 'pending', row
                    decision = {'rulingId': row['rulingId'], 'digest': row['digest'], 'decision': 'approve',
                                'riskDecisions': {r['id']: '隔离矩阵：核对完整候选与存量影响' for r in row['risks']}}
                    if row.get('highRisk'): decision['explicitHighRiskDigest'] = row['digest']
                    assessment = row.get('cAssessment') or {}
                    if assessment.get('requiresAcceptance'):
                        assert assessment['adoptable'] and not assessment.get('stale')
                        decision['cReview'] = {key: assessment[key] for key in ('basisRevision', 'basisDigest', 'reportDigest')}
                    done = measured_ai(key, 'ai.ruling.decide', decision)
                    assert done['status'] == 'completed', done
                    kp.state()
                    return {'status': done['status'], 'highRisk': row.get('highRisk'), 'proposalId': draft['proposalId']}

                def npc_add():
                    value = configuration('sv.npc')
                    value.update(configurationId='sv.ext.npc.matrix', revision='1')
                    value['defaults'].update(hp=6, maxHp=6, isNpc=1)
                    proof = proposal('npc-add', {'configurations': [{'kind': 'add', 'id': value['configurationId'], 'expectedRevision': None, 'value': value}]})
                    entities['npc'] = result(kp.command('entity.create', {'configurationId': value['configurationId'], 'name': '矩阵向导', 'owner': 'kp', 'visibility': 'kp'}))
                    assert any(n['instanceId'] == entities['npc'] for n in kp.state()['npcs'])
                    return proof
                case('npc-add', 'supported', npc_add)

                def npc_update():
                    value = configuration('sv.ext.npc.matrix'); revision = value['revision']
                    before = kp.request('/api/v1/view')['entities'][entities['npc']]['numbers']
                    value['revision'] = str(int(revision)+1); value['defaults']['armor'] = 1
                    proof = proposal('npc-update', {'configurations': [{'kind': 'replace', 'id': value['configurationId'], 'expectedRevision': revision, 'value': value}]})
                    assert kp.request('/api/v1/view')['entities'][entities['npc']]['numbers'] == before
                    assert configuration(value['configurationId'])['defaults']['armor'] == 1
                    return proof
                case('npc-update', 'supported', npc_update)

                def npc_in_use():
                    value = configuration('sv.ext.npc.matrix')
                    proof = proposal('npc-delete-in-use', {'configurations': [{'kind': 'remove', 'id': value['configurationId'], 'expectedRevision': value['revision'], 'value': None}]}, True)
                    assert configuration(value['configurationId']) == value
                    return proof
                case('npc-delete-in-use', 'expected-rejection', npc_in_use)

                def npc_delete_unused():
                    value = configuration('sv.npc'); value.update(configurationId='sv.ext.npc.disposable', revision='1'); value['defaults']['isNpc'] = 1
                    proposal('npc-unused-add', {'configurations': [{'kind': 'add', 'id': value['configurationId'], 'expectedRevision': None, 'value': value}]})
                    proof = proposal('npc-delete-unused', {'configurations': [{'kind': 'remove', 'id': value['configurationId'], 'expectedRevision': '1', 'value': None}]})
                    assert value['configurationId'] not in kp.request('/api/v1/admin')['configurations']
                    return proof
                case('npc-delete-unused', 'supported', npc_delete_unused)

                def item_add(key, kind, slots, slot, **extra):
                    before = game(); value = copy.deepcopy(before)
                    value['items'].append({'id': key, 'name': {'matrix-item':'矩阵灯笼','matrix-weapon':'矩阵短矛','matrix-container':'矩阵布袋'}[key],
                        'kind': kind, 'slots': slots, 'uses': 3, 'description': '隔离测试普通占槽物品；无嵌套库存机制。', **extra})
                    proof = proposal(key, {'data': {'game.json': value}})
                    assert game() == value and value['items'][:-1] == before['items']
                    actor = p1.state()['character']['instanceId']
                    result(kp.command('action.invoke', {'actionId': 'sv.grant', 'input': {'actor': actor, 'item': len(value['items']), 'slot': slot, 'uses': 3}}))
                    state = p1.state(); assert state['character']['numbers']['item'+str(slot)] == len(value['items'])
                    assert state['items'][str(len(value['items']))]['id'] == key
                    return proof
                case('item-add', 'supported', lambda: item_add('matrix-item', 'item', 1, 11))
                case('weapon-add', 'supported', lambda: item_add('matrix-weapon', 'weapon', 1, 12, damage='d8', useDie=True))
                case('container-as-item-add', 'supported', lambda: item_add('matrix-container', 'item', 2, 13))

                def item_update():
                    value = game(); index = next(i for i,v in enumerate(value['items']) if v['id']=='matrix-item')
                    before = copy.deepcopy(p1.state()['character']['numbers'])
                    value['items'][index].update(name='矩阵提灯', uses=5)
                    proof = proposal('item-update', {'data': {'game.json': value}})
                    assert p1.state()['character']['numbers'] == before
                    assert game()['items'][index]['uses'] == 5
                    return proof
                case('item-update', 'supported', item_update)

                def invalid_game(key, edit):
                    before = game(); value = copy.deepcopy(before); edit(value)
                    proof = proposal(key, {'data': {'game.json': value}}, True)
                    assert game() == before
                    return proof
                case('item-delete', 'expected-rejection', lambda: invalid_game('item-delete', lambda v: v['items'].pop(0)))
                case('item-duplicate-id', 'expected-rejection', lambda: invalid_game('item-duplicate-id', lambda v: v['items'].append(copy.deepcopy(v['items'][0]))))
                case('container-undeclared-capacity', 'expected-rejection', lambda: invalid_game('container-undeclared-capacity', lambda v: v['items'][-1].update(capacity=20)))

                def map_add():
                    value = game(); index = len(value['locations'])+1
                    value['locations'].append({'index':index,'name':'矩阵侧门','description':'隔离新增地点','truth':'KP 内部验收','exits':[1],'features':[],'stock':[],'clues':[]})
                    value['locations'][0]['exits'].append(index)
                    proof = proposal('map-add', {'data': {'game.json': value}})
                    state = kp.state(); assert state['allLocations'][str(index)]['name'] == '矩阵侧门'
                    assert str(index) not in state['published'] and state['doors']['1-'+str(index)] == 'closed'
                    actor = p1.state()['character']['instanceId']
                    result(kp.command('action.invoke', {'actionId':'sv.travel','input':{'actor':actor,'location':index}}))
                    assert p1.state()['character']['numbers']['location'] == index
                    result(kp.command('action.invoke', {'actionId':'sv.travel','input':{'actor':actor,'location':1}}))
                    return proof
                case('map-add', 'supported', map_add)

                def map_update():
                    value = game(); value['locations'][-1]['description'] = '更新后的隔离地点'
                    proof = proposal('map-update', {'data': {'game.json': value}})
                    assert kp.state()['allLocations'][str(len(value['locations']))]['description'] == value['locations'][-1]['description']
                    return proof
                case('map-update', 'supported', map_update)
                case('map-delete', 'expected-rejection', lambda: invalid_game('map-delete', lambda v: v['locations'].pop()))
                case('map-dangling-exit', 'expected-rejection', lambda: invalid_game('map-dangling-exit', lambda v: v['locations'][0]['exits'].append(999)))

                def scene_update():
                    value = copy.deepcopy(current()['data']['scene-actions.json'])
                    value['actions'][0]['player']['hint'] = '隔离验收：查看地面痕迹。'
                    proof = proposal('scene-player-text-update', {'data': {'scene-actions.json': value}})
                    kp.action('location.reveal', {'index':1,'accounts':['player1']})
                    assert p1.state()['sceneActions'][0]['hint'] == value['actions'][0]['player']['hint']
                    return proof
                case('scene-player-text-update', 'supported', scene_update)

                def rule_update(add):
                    amount = 1 if add else 2
                    source = "return rule('sv.ext.matrix_heal', {'actor'}, function(r, actor) r.set(actor, 'hp', math.min(r.number(actor, 'maxHp'), r.number(actor, 'hp') + %d)); return r.number(actor, 'hp') end, {kp=true})" % amount
                    key = 'rule-add' if add else 'rule-update'
                    proof = proposal(key, {'sources': {'matrix-heal.lua': source}})
                    result(kp.command('entity.update', {'id':entities['npc'],'numbers':{'hp':1}}))
                    actual = result(kp.command('action.invoke', {'actionId':'sv.ext.matrix_heal','input':{'actor':entities['npc']}}))
                    assert actual == 1+amount
                    return proof
                case('rule-add', 'supported', lambda: rule_update(True))
                case('rule-update', 'supported', lambda: rule_update(False))

                def source_delete():
                    before=current()
                    candidate={'schemaVersion':1,'configurations':[],'sources':{'matrix-heal.lua':None},'data':{},'suggestions':[]}
                    rejected=ai(kp,'ai.draft.create',{'text':'隔离负例：无公开规则源删除操作','changeSet':candidate},allow_error=True)
                    assert rejected.get('code')=='INPUT_INVALID',rejected
                    assert current()==before
                    return {'code':rejected['code'],'boundary':'ChangeSet.sources only accepts Lua strings; no removal operation'}
                case('rule-source-delete-unsupported','expected-rejection',source_delete)

                def core_rule():
                    source = current()['sources']['check-core.lua'].replace('rolled <= target','rolled < target')
                    proof = proposal('core-check-update', {'sources': {'check-core.lua': source}})
                    value = p1.action('check', {'attribute':'str','mode':'normal'})
                    assert value['passed'] == (value['rolled'] < value['target'])
                    return proof
                case('core-check-update', 'supported', core_rule)

                sid = result(ai(kp, 'ai.session.create', {'title':'重启保留会话'}))['sessionId']
                def fixture_plan(text):
                    submitted=result(ai(kp,'ai.session.submit',{'sessionId':sid,'text':text}))
                    if not submitted.get('taskId'):result(ai(kp,'ai.request.dispatch',{'requestId':submitted['requestId']}))
                    deadline=time.monotonic()+90
                    while time.monotonic()<deadline:
                        item=kp.request('/api/v1/ai/sessions/'+sid)['items'][-1]
                        if item['status'] not in {'received','queued','generating','validating'}:
                            assert item['status']=='review_ready' and 'OFFLINE_REPLY' in str(item.get('response')),item
                            return item
                        time.sleep(.3)
                    raise TimeoutError('loopback fixed plan did not settle')
                if args.batch=='restart':
                    result(ai(kp,'ai.settings.update',{'enabled':True,'profileId':'offline','externalSources':{'public':True,'kp':True,'private':True},'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}))
                    for number in range(2):fixture_plan('配置发布和消费已完成，隔离固定计划第'+str(number+1)+'轮')
                else:result(ai(kp,'ai.session.submit',{'sessionId':sid,'text':'隔离待处理请求，不调用模型'}))
                before_restart = current()
                write_json(output/'before-restart-bundle.json',before_restart)
            with running('ai-config-restart', data=output/'game', ai_config=config, no_browser=True) as (runtime, _):
                kp = Account(runtime.origin, 'kp', password, 'restart')
                def restart():
                    after_restart=kp.request('/package/bundle')
                    write_json(output/'after-restart-bundle.json',after_restart)
                    # Configuration mapping order is not part of the public catalog contract.
                    def comparable(value):
                        return {**value,'configurations':{c['configurationId']:c for c in value['configurations']}}
                    before,after=comparable(before_restart),comparable(after_restart)
                    assert after==before,{'changedBundleFields':[k for k in set(before)|set(after) if before.get(k)!=after.get(k)]}
                    sessions = kp.request('/api/v1/ai/sessions?archived=false')['items']
                    assert any(s['sessionId'] == sid for s in sessions), sessions
                    previous = kp.request('/api/v1/ai/sessions/'+sid)
                    assert previous['items']
                    if args.batch=='restart':
                        assert len(previous['items'])==2 and all('OFFLINE_REPLY' in str(i.get('response')) and not i.get('error') for i in previous['items']),previous
                        submitted=fixture_plan('立即重启后第三轮固定计划；不重新执行历史动作')
                    else:submitted = result(ai(kp,'ai.session.submit',{'sessionId':sid,'text':'重启后继续，不调用模型'}))
                    assert submitted.get('requestId')
                    return {'sessionId':sid,'requestId':submitted['requestId'],
                            'configurationOrderChanged':before_restart['configurations']!=after_restart['configurations']}
                case('same-save-restart-session', 'supported', restart)
            report['fixtureProviderCalls']=len(calls)
            assert len(calls)==(3 if args.batch=='restart' else 0),'unexpected loopback provider call count'
    except Exception as error:
        report.update(errorType=type(error).__name__, error=str(error)[:3500])
    finally:
        report['rates'] = {}
        for kind in ('supported','expected-rejection'):
            rows = [r for r in report['cases'] if r['expectation']==kind]
            report['rates'][kind] = {'passed':sum(r['passed'] for r in rows),'total':len(rows)}
        report['passed'] = bool(report['cases']) and all(r['passed'] for r in report['cases']) and 'errorType' not in report
        write_json(output/'report.json',report); write_json(prior,report)
        print(json.dumps({k:report.get(k) for k in ('passed','rates','errorType','evidenceDirectory')},ensure_ascii=False),flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__': raise SystemExit(main())
