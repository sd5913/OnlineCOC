"""Observed provider mistakes and self-staging provenance regressions."""
import asyncio
import json
import copy
import pytest
from test_entrypoints import application,command,committed,delta
from test_coordinator import setup,Fake,completion,wait_task
from test_access_batches import session,submit,tool_call
from test_context import enable
from onlinecoc_ai.data_queries import DataQueryService


@pytest.mark.parametrize('external_change',[False,True])
def test_approval_does_not_invalidate_its_own_stable_room_query(application,external_change):
    app=application;enable(app.host,public=True,private=True,kp=True)
    snapshot=app.proposals.snapshot('kp');snapshot[0]['facts']['aiReadScope']='kp-room'
    query=DataQueryService(app.host).attach('kp','search',{'types':['room'],'query':'artifacts','limit':12},snapshot)
    assert query['items']
    DataQueryService(app.host).attach('kp','search',{'types':['entity'],'query':'','limit':12},snapshot)
    changes=delta();name=next(iter(snapshot[2]['sources']));changes['sources']={name:snapshot[2]['sources'][name]+'\n-- staging regression\n'}
    p=app.proposals.create('kp','只调整活动数据',changes,snapshot=snapshot)
    result=app.proposals.validate('kp',p['proposalId'],1)
    assert result['proposal']['status']=='review_ready',[(r['level'],r['status'],r['findings']) for r in result['reports']]
    item=app.rulings.detail('kp','proposal:'+p['proposalId'])
    args={'rulingId':item['rulingId'],'digest':item['digest'],'decision':'approve','explicitHighRiskDigest':item['digest'],
        'riskDecisions':{r['id']:'测试确认该项风险' for r in item['risks']}}
    if item.get('cAssessment',{}).get('requiresAcceptance'):
        args['cReview']={k:item['cAssessment'][k] for k in ('basisRevision','basisDigest','reportDigest')}
    before=app.host.state()['activeRuleset'];original=app.rulings.host_command
    def host_command(account,identifier,op,params):
        if external_change and op=='publication.apply':
            room=app.host.state();room['entities']['actor-one']['name']='Changed after approval';room['entities']['actor-one']['revision']+=1
            app.host.commit(room)
        return original(account,identifier,op,params)
    app.rulings.host_command=host_command
    result=committed(command(app,'ai.ruling.decide',args))
    if external_change:
        # The host may reject at the earlier whole-world baseline gate before
        # reaching the narrower query-source proof check.
        assert result['status']=='blocked' and result['receipts'][-1]['code'] in ('BASELINE_STALE','SOURCE_STALE')
        assert app.host.state()['activeRuleset']==before
    else:
        assert result['status']=='completed',result['receipts']
        assert app.host.state()['activeRuleset']!=before
    assert result['receipts'][0]['status']=='committed'


def run_model(app,callback,text='按原需求查询并准备候选'):
    enable(app.host,public=True,private=True,kp=True)
    for profile in app.coordinator.profiles.values():profile['limits'].update(maxRepairAttempts=2,maxToolRounds=8)
    async def run():
        provider=Fake(callback);app.coordinator.provider_factory=lambda _:provider
        r=submit(app,session(app),text);task=committed(command(app,'ai.request.dispatch',{'requestId':r['requestId']}))
        await app.coordinator.start()
        try:return await wait_task(app.coordinator,task['taskId'],60),provider
        finally:await app.coordinator.close()
    return asyncio.run(run())


def test_close_during_idle_reconciliation_does_not_lose_wake(application):
    import threading
    entered=threading.Event();release=threading.Event();app=application
    def reconcile():
        entered.set();assert release.wait(5);return False
    app.continuations.reconcile=reconcile
    async def run():
        await app.coordinator.start()
        assert await asyncio.to_thread(entered.wait,5)
        closing=asyncio.create_task(app.coordinator.close())
        await asyncio.sleep(0)
        release.set()
        await asyncio.wait_for(closing,2)
        assert app.coordinator.runner is None
    asyncio.run(run())


def test_miswrapped_clarification_is_delivered_once_without_executing_tool(application):
    choices={'prompt':'给哪位玩家？','options':[{'id':'a','label':'甲','text':'给甲'}, {'id':'b','label':'乙','text':'给乙'}]}
    async def callback(*_):return tool_call('clarification',{'text':'要给哪位玩家添路费？','choices':choices})
    task,provider=run_model(application,callback,'想给一个玩家添路费，先确认对象')
    assert task['status']=='needs_input' and task['choices']==choices and provider.calls==1
    assert not application.repository.state()['proposals'] and not application.repository.state()['settings'].get('batches')


@pytest.mark.parametrize('name',['publication.apply','unknown_read','batch'])
def test_non_answer_tools_are_not_treated_as_authority(application,name):
    async def callback(*_):return tool_call(name,{'text':'伪装回答'})
    task,provider=run_model(application,callback)
    assert task['status']=='failed' and task['error']=='TOOL_FORBIDDEN' and provider.calls==1
    assert not application.host.state()['aiControl']['publications']


def test_invalid_fields_and_opaque_entity_ref_recover_same_intent(application):
    app=application;refs=[]
    async def callback(n,messages,tools):
        if n==1:return tool_call('room_search_data',{'types':['entity'],'query':'','limit':20})
        if n==2:
            result=json.loads(messages[-1]['content']);refs.extend(i['ref'] for i in result['items'] if i['citation']['token'].startswith('[[entity:actor-one@'))
            assert len(refs)==1
            return tool_call('room_read_data',{'refs':refs,'fields':['pips','numbers','label']})
        detail=json.loads(messages[-1]['content'])
        assert detail['technicalCorrection']['code']=='QUERY_FIELDS_REPAIRED'
        assert detail['items'][0]['data']['instanceId']=='actor-one'
        return completion({'kind':'batch','text':'按已确认方案改名并通知', 'actions':[
            {'target':'host','op':'entity.patch','args':{'id':refs[0]['id'],'name':'已确认的名字'}},
            {'target':'host','op':'notification.send','args':{'recipientAccountIds':['player1'],'text':'名称已更新。','sourceActionIndex':0}}]})
    before=app.host.state()['entities']['actor-one']['name'];task,provider=run_model(app,callback,'将第一个角色改为已确认的名字并通知持有人')
    assert task['status']=='review_ready' and provider.calls==3,task
    batch=app.repository.state()['settings']['batches'][task['batchId']]
    assert batch['actions'][0]['args']['id']=='actor-one' and batch['status']=='pending'
    assert app.host.state()['entities']['actor-one']['name']==before and not app.host.notifications('player1')['items']
    context=app.repository.state()['contexts'][task['contextRef']]
    proof=context['facts']['dataQueries'][-1]
    assert proof['operation']=='read' and 'fields' not in proof['args']
    result=committed(command(app,'ai.batch.approve',{'batchId':batch['batchId'],'digest':batch['digest']}))
    assert result['status']=='completed' and len(app.host.notifications('player1')['items'])==1
    assert app.host.state()['entities']['actor-one']['name']=='已确认的名字'


def test_identity_resolution_requires_exact_authorized_details_and_typed_position():
    from onlinecoc_ai.reliability import remember_targets,resolve_targets
    pool={};artifact={'metadata':{'act':{'inputs':{'actor':'actor','amount':'number'}}}}
    entity={'authority':'host-state','ref':{'sourceId':'host','kind':'entity','id':'opaque'},'data':{'instanceId':'real','typeRef':'actor'}}
    remember_targets({'items':[entity]},pool)
    source=[{'target':'host','op':'action.invoke','args':{'actionId':'act','input':{'actor':'opaque','amount':'opaque'}}},
        {'target':'host','op':'entity.patch','args':{'id':'guessed','name':'opaque'}}]
    fixed,paths=resolve_targets(source,pool,artifact)
    assert fixed[0]['args']['input']=={'actor':'real','amount':'opaque'} and fixed[1]==source[1]
    assert source[0]['args']['input']['actor']=='opaque' and len(paths)==1
    for bad in (None,{},[3],[{'args':3}],[{'target':'host','op':'action.invoke','args':{'actionId':[]}}]):
        assert resolve_targets(bad,pool,artifact)[0]==bad
    fake={**entity,'authority':'package-record'};untrusted={};remember_targets({'items':[fake]},untrusted);assert not untrusted
    remember_targets({'items':[{**entity,'data':{'instanceId':'different','typeRef':'actor'}}]},pool)
    assert not resolve_targets(source,pool,artifact)[1]


@pytest.mark.parametrize('followup,replay',[('就按刚才说好的做法继续，查当前数据，把未完成的部分提交裁决。',True),('再额外增加一份新的奖励',False)])
def test_actual_completed_intent_is_not_replayed_by_bare_continuation(application,followup,replay):
    app=application;enable(app.host,public=True,private=True,kp=True);captured=[]
    before=app.host.state()['entities']['actor-one']['numbers']['target']
    def output(value):return completion({'kind':'batch','text':'准备调整并通知','actions':[
        {'target':'host','op':'entity.update','args':{'id':'actor-one','numbers':{'target':value}}},
        {'target':'host','op':'notification.send','args':{'recipientAccountIds':['player1'],'text':'调整已完成','sourceActionIndex':0}}]})
    async def callback(n,messages,tools):
        payload=json.loads(messages[1]['content']);captured.append(payload)
        if payload['request']=='增加一份奖励并通知':return output(before+1)
        if n==1:
            row=payload['executionLedger'][0]
            assert row['status']=='completed' and row['confirmedExecution'] and row['latestIntent']
            assert row['runtimeBefore'][0]['numbers']=={'target':before}
            assert len(row['actions'])==2 and row['request']=='增加一份奖励并通知'
            return output(before+2)
        assert json.loads(messages[-1]['content'])['error']['code']=='INTENT_EXECUTION_REPLAY'
        return completion({'kind':'plan','text':'此前调整和通知均已实际完成，没有新增执行。'})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);await app.coordinator.start()
        try:
            s=session(app);first=submit(app,s,'增加一份奖励并通知')
            tid=committed(command(app,'ai.request.dispatch',{'requestId':first['requestId']}))['taskId']
            task=await wait_task(app.coordinator,tid);assert task['status']=='review_ready',task
            batch=app.repository.state()['settings']['batches'][task['batchId']]
            assert committed(command(app,'ai.batch.approve',{'batchId':batch['batchId'],'digest':batch['digest']}))['status']=='completed'
            second=submit(app,s,followup);tid=committed(command(app,'ai.request.dispatch',{'requestId':second['requestId']}))['taskId']
            task=await wait_task(app.coordinator,tid);assert task['status']=='review_ready',task
            assert bool(task.get('batchId')) is not replay
            assert len(task['calls'])==(2 if replay else 1)
            assert len(app.repository.state()['settings']['batches'])==(1 if replay else 2)
            assert app.host.state()['entities']['actor-one']['numbers']['target']==before+1
            assert len(app.host.notifications('player1')['items'])==1
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_increment_refusal_is_repaired_without_reasking(application):
    async def callback(n,messages,tools):
        if n==1:return completion({'kind':'plan','text':'角色已经有一捆绳索，所以不需要再发一捆。'})
        assert json.loads(messages[-1]['content'])['error']['code']=='REQUESTED_INCREMENT_OMITTED'
        return completion({'kind':'batch','text':'准备新的增量','actions':[{'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'新增赠予候选'}}]})
    task,provider=run_model(application,callback,'给角色发一捆现成的绳索，放哪你安排')
    assert task['status']=='review_ready' and task['batchId'] and provider.calls==2


def test_replay_and_increment_guards_do_not_infer_new_authority():
    from onlinecoc_ai.execution_ledger import require_no_replay,continue_only
    from onlinecoc_ai.reliability import require_increment_intent
    from onlinecoc_ai.errors import AiError
    action={'target':'host','op':'entity.update','args':{'id':'a','numbers':{'coins':2}}}
    row={'latestIntent':True,'status':'completed','actions':[action]}
    for status in ('completed','pending','unknown','partial','executing'):
        with pytest.raises(AiError,match='INTENT_EXECUTION_REPLAY'):
            require_no_replay({'request':'继续','executionLedger':[{**row,'status':status}]},{'kind':'batch','actions':[action]})
    for text in ('再给一枚','继续给乙两枚','扣除上一笔错误奖励并补偿一枚'):
        assert not continue_only(text)
        require_no_replay({'request':text,'executionLedger':[row]},{'kind':'batch','actions':[action]})
    require_no_replay({'request':'继续','executionLedger':[{**row,'latestIntent':False}]},{'kind':'batch','actions':[action]})
    require_no_replay({'request':'继续','executionLedger':[{**row,'status':'failed'}]},{'kind':'batch','actions':[action]})
    require_increment_intent({'request':'确保角色有一捆绳索','aiPermissions':{'allowRuntimeChanges':True}}, {'kind':'plan','text':'已经有绳索，不需要再发一捆。'})
