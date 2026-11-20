"""Opt-in bounded DeepSeek configuration batches with per-attempt consumption evidence."""
import argparse
import copy
from datetime import datetime
import json
from pathlib import Path
import secrets
import time

from harness import PACK, running, provision
from integrations import ROOT, write_json
from verify_integrations import ai, result
from verify_ai_rulings_live import observed_provider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--batch', choices=['npc','items','map-rules'], required=True)
    parser.add_argument('--call-limit', type=int, default=24)
    parser.add_argument('--output-root',type=Path,default=PACK/'tests/output')
    args = parser.parse_args()
    if not args.live: parser.error('--live is required for billable calls')
    if not 1 <= args.call_limit <= 40: parser.error('call-limit must be 1..40')
    config_path = ROOT/'engineering/ai/config/ai-providers.json'
    original_config = config_path.read_bytes()
    profile = next(p for p in json.loads(original_config)['profiles'] if p['profileId']=='deepseek-main')
    assert profile['enabled']
    output = args.output_root.resolve()/('ai-config-live-'+args.batch+'-'+secrets.token_hex(4)); output.mkdir(parents=True)
    prior = PACK/'tests'/('ai-config-live-'+args.batch+'-results.json')
    report = {'checkedAt':datetime.now().astimezone().isoformat(),'batch':args.batch,'requestedModel':profile['model'],
              'realSaveChanged':False,'callLimit':args.call_limit,'cases':[],'calls':[],
              'evidenceDirectory':output.relative_to(PACK).as_posix()}
    if prior.exists():
        old=json.loads(prior.read_text(encoding='utf-8'))
        report['previousRuns']=[*old.get('previousRuns',[]),{k:old.get(k) for k in ('checkedAt','passed','rates','realCalls','confirmedTokens','evidenceDirectory')}]
    outputs=[]; tools=[]
    try:
        with observed_provider(profile,report['calls'],outputs,inject_fault=False,call_limit=args.call_limit,tool_evidence=tools) as selected:
            selected['request']=copy.deepcopy(profile['request'])
            selected['request']['maxOutputTokens']=min(selected['request']['maxOutputTokens'],8192)
            config=output/'ai-providers.json';write_json(config,{'schemaVersion':1,'profiles':[selected]})
            with running('ai-config-live',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
                kp,p1,p2=provision(runtime,password)
                result(ai(kp,'ai.settings.update',{'enabled':True,'profileId':selected['profileId'],
                    'externalSources':{'public':True,'kp':True,'private':True},'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}))
                access=kp.request('/api/v1/ai/access')
                result(ai(kp,'ai.access.update',{'revision':access['revision'],'allowPlayerChat':True,'allowAdminRoomRead':True,'allowRuntimeChanges':True,
                    'allowConfigurationChanges':True,'autoApproveConfigurations':False,'autoApproveBatches':False}))
                def bundle():return kp.request('/package/bundle')
                def game():return copy.deepcopy(bundle()['data']['game.json'])
                def configurations():return kp.request('/api/v1/admin')['configurations']
                def ask(sid,prompt):
                    submitted=result(ai(kp,'ai.session.submit',{'sessionId':sid,'text':prompt}))
                    if not submitted.get('taskId'):result(ai(kp,'ai.request.dispatch',{'requestId':submitted['requestId']}))
                    deadline=time.monotonic()+320
                    task=None
                    while time.monotonic()<deadline:
                        task=kp.request('/api/v1/ai/sessions/'+sid)['items'][-1]
                        if task['status'] not in {'received','queued','generating','validating'}:return task
                        time.sleep(1)
                    raise TimeoutError('task did not settle')
                def decide(row):
                    decision={'rulingId':row['rulingId'],'digest':row['digest'],'decision':'approve',
                              'riskDecisions':{r['id']:'仅隔离验收：核对完整候选、编号、引用和存量影响' for r in row.get('risks',[])}}
                    if row.get('highRisk'):decision['explicitHighRiskDigest']=row['digest']
                    value=result(ai(kp,'ai.ruling.decide',decision));assert value['status']=='completed',value
                    kp.state();return value
                def run_case(key,prompt,consume,expectation='supported'):
                    row={'id':key,'expectation':expectation,'prompt':prompt,'attempts':[],'passed':False};report['cases'].append(row)
                    sid=result(ai(kp,'ai.session.create',{'title':'隔离矩阵 '+key}))['sessionId']
                    for attempt in range(2):
                        item={'attempt':attempt+1,'passed':False,'callsBefore':len(report['calls'])};row['attempts'].append(item)
                        try:
                            task=ask(sid,prompt if attempt==0 else '上次未完成，反馈：'+row['attempts'][-2].get('error','未满足验收')[:900]+'。请重新读取当前活动数据，修正方案；仍只提交候选，不执行。原需求：'+prompt)
                            item['task']=task
                            rulings=kp.request('/api/v1/ai/rulings')['items']
                            proposal=next((r for r in reversed(rulings) if r.get('sessionId')==sid and r['kind']=='configuration' and r.get('proposalId',r['rulingId'].removeprefix('proposal:'))==task.get('proposalId')),None)
                            if expectation=='expected-rejection':
                                assert not proposal or proposal['status']!='pending','unsafe candidate reached approval'
                                assert task['status'] in {'needs_input','review_ready','blocked'},task
                                item['consumption']=consume(None)
                                item['feedback']=task.get('response') or task.get('error')
                                assert item['feedback'],'rejection has no feedback'
                            else:
                                feedback={'taskStatus':task['status'],'error':task.get('error'),'rulingStatus':proposal.get('status') if proposal else None,'blockingReason':proposal.get('blockingReason') if proposal else None,'findings':[{ 'level':r['level'],'status':r['status'],'findings':r['findings']} for r in (proposal or {}).get('reports',[])]}
                                item['validationFeedback']=feedback
                                assert proposal and proposal['status']=='pending',feedback
                                item['proposal']=proposal
                                item['decision']=decide(proposal)
                                item['consumption']=consume(proposal)
                            item['passed']=True;row['passed']=True
                        except Exception as error:
                            item.update(errorType=type(error).__name__,error=str(error)[:2500])
                        item['callsAfter']=len(report['calls']);write_json(output/'progress.json',report)
                        print(json.dumps({'case':key,'attempt':attempt+1,'passed':item['passed'],'calls':len(report['calls'])},ensure_ascii=False),flush=True)
                        # Do not repeat a publication after a successful decision but failed consumption.
                        if item['passed'] or item.get('decision') or len(report['calls'])>=args.call_limit:break
                    return row

                if args.batch=='npc':
                    key='sv.ext.npc.live_matrix'; created={}
                    def consume_add(_):
                        value=configurations()[key];assert value['defaults']['hp']==6 and value['defaults']['isNpc']==1
                        created['id']=result(kp.command('entity.create',{'configurationId':key,'name':'真实矩阵向导','owner':'kp','visibility':'kp'}))
                        actor=kp.request('/api/v1/view')['entities'][created['id']];assert actor['numbers']['hp']==6
                        return {'configurationId':key,'instanceId':created['id'],'hp':6}
                    run_case('npc-add','新增独立 NPC 模板 '+key+'，完整复制当前 sv.npc 默认值，仅将 hp/maxHp 设为6，并增加 isNpc=1。不要创建实例，不改核心规则；请提交完整配置候选供KP审核。',consume_add)
                    def consume_update(_):
                        assert configurations()[key]['defaults']['armor']==1
                        assert kp.request('/api/v1/view')['entities'][created['id']]['numbers']['armor']==0
                        new_id=result(kp.command('entity.create',{'configurationId':key,'name':'更新后默认值验收','owner':'kp','visibility':'kp'}))
                        current=kp.request('/api/v1/view')['entities']
                        assert current[new_id]['numbers']['armor']==1 and current[created['id']]['numbers']['armor']==0
                        return {'newDefaultArmor':1,'existingInstanceArmor':0,'newInstanceArmor':1,'newInstanceId':new_id}
                    if created.get('id'):
                        run_case('npc-update','修改刚建立的 '+key+' 模板，只将默认 armor 改为1，保留其余字段，使用当前修订。不要修改已存在实例，提交候选。',consume_update)
                    else:
                        report['cases'].append({'id':'npc-update','expectation':'supported','passed':False,'attempts':[],'notRun':'npc-add did not create the prerequisite template/instance'})
                    preserved_ids=set(kp.request('/api/v1/view')['entities'])
                    # Unused template fixture; creation is not credited to the model's deletion case.
                    disposable=copy.deepcopy(configurations()['sv.npc']);disposable.update(configurationId='sv.ext.npc.live_unused',revision='1');disposable['defaults']['isNpc']=1
                    result(kp.command('configuration.put',disposable))
                    def consume_delete(_):
                        assert 'sv.ext.npc.live_unused' not in configurations()
                        assert preserved_ids <= set(kp.request('/api/v1/view')['entities'])
                        return {'unusedTemplateRemoved':True,'existingGuideKept':True}
                    run_case('npc-delete-unused','删除未使用模板 sv.ext.npc.live_unused。请先查当前修订和引用，提交高危删除候选；不删其他模板或实例。',consume_delete)
                elif args.batch=='items':
                    for kind,name,slots,slot in [('item','矩阵提灯',1,11),('weapon','矩阵短矛',1,12),('container','矩阵布袋',2,13)]:
                        key='live-matrix-'+kind;before=game()
                        def consume_item(_,key=key,before=before,slot=slot):
                            after=game();assert after['items'][:len(before['items'])]==before['items']
                            index=next(i+1 for i,v in enumerate(after['items']) if v['id']==key)
                            definition=after['items'][index-1];actor=p1.state()['character']['instanceId']
                            result(kp.command('action.invoke',{'actionId':'sv.grant','input':{'actor':actor,'item':index,'slot':slot,'uses':definition['uses']}}))
                            state=p1.state();assert state['character']['numbers']['item'+str(slot)]==index
                            assert state['items'][str(index)]['name']==definition['name']
                            return {'itemIndex':index,'slot':slot,'heldName':definition['name']}
                        details='kind=weapon，damage=d8，useDie=true' if kind=='weapon' else 'kind=item，不增加新机制'
                        run_case(kind+'-add','在当前 game.json.items 末尾追加 '+name+'，id='+key+'，'+details+'，slots='+str(slots)+'，uses=3，description说明为隔离测试物品。布袋只是普通占槽物品，没有嵌套容量或减重。保留所有旧字段和编号，仅提交高危候选，不发放。',consume_item)
                else:
                    before=game();index=len(before['locations'])+1
                    def consume_map(_):
                        after=game();place=after['locations'][index-1];assert place['index']==index and 1 in place['exits']
                        state=kp.state();assert str(index) not in state['published'] and state['doors']['1-'+str(index)]=='closed'
                        actor=p1.state()['character']['instanceId']
                        result(kp.command('action.invoke',{'actionId':'sv.travel','input':{'actor':actor,'location':index}}))
                        assert p1.state()['character']['numbers']['location']==index
                        return {'location':index,'private':True,'door':'closed','actualTravel':True}
                    run_case('map-add','在 game.json 追加地点，编号为'+str(index)+'，名为矩阵侧门，普通描述为隔离测试侧门，主持真相为测试地点，features/stock/clues为空，exits=[1]；同时给1号地点exits追加该编号。其余配置完整保留。只提交高危候选，不公开、不移动角色。',consume_map)
                    def consume_rule(_):
                        actor=p1.state()['character'];expected=actor['numbers']['str']+actor['numbers']['wil']
                        actual=kp.request('/api/v1/preview',{'rule':'sv.ext.live_matrix_score','input':{'actor':actor['instanceId']}})['result']
                        assert actual==expected
                        return {'actual':actual,'expected':expected}
                    run_case('rule-add','新增独立计算规则 sv.ext.live_matrix_score，文件 live-matrix-score.lua，输入 actor，返回 r.number(actor, str) 与 r.number(actor, wil) 之和；Lua字段使用字符串，mode=calculation、kp=true。不要改核心规则或任何实例，仅提交配置候选。',consume_rule)
                    before_delete=game()
                    def rejected(_):
                        assert game()==before_delete
                        return {'activeGameUnchanged':True}
                    run_case('item-delete-stable-id','从 game.json.items 删除第1项针剑，并把后面的物品编号前移。我知道编号会变化，请处理这个请求。',rejected,'expected-rejection')
                report['usage']=kp.request('/api/v1/ai/usage?scope=room')
    except Exception as error:
        report.update(errorType=type(error).__name__,error=str(error)[:2500])
    finally:
        report['persistentProviderConfigUnchanged']=config_path.read_bytes()==original_config
        report['realCalls']=sum(not c.get('injected') for c in report['calls'])
        report['experimentCallLimitReached']=report['realCalls']>=args.call_limit
        report['confirmedTokens']=sum(c.get('usage',{}).get('total_tokens',0) for c in report['calls'])
        report['rates']={}
        for kind in ('supported','expected-rejection'):
            rows=[r for r in report['cases'] if r['expectation']==kind]
            report['rates'][kind]={'firstPassed':sum(bool(r['attempts']) and r['attempts'][0]['passed'] for r in rows),
                                 'finalPassed':sum(r['passed'] for r in rows),'total':len(rows)}
        report['passed']=bool(report['cases']) and all(r['passed'] for r in report['cases']) and 'errorType' not in report and report['persistentProviderConfigUnchanged']
        write_json(output/'fixture-model-tools.json',tools);write_json(output/'fixture-model-outputs.json',outputs)
        write_json(output/'report.json',report);write_json(prior,report)
        print(json.dumps({k:report.get(k) for k in ('passed','rates','realCalls','confirmedTokens','errorType','evidenceDirectory')},ensure_ascii=False),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
