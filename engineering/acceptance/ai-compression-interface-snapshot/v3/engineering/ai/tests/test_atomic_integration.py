"""Real isolated Host + AI store: preflight, atomic receipts and bounded repair."""
import asyncio
import copy
import json
import pytest
from onlinecoc.errors import DomainError
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.contracts import digest
from test_entrypoints import application,command,committed
from test_coordinator import setup,Fake,completion,wait_task
from test_access_batches import batch,decide,session,submit
from test_context import enable


def patch(name):return {'target':'host','op':'entity.patch','args':{'id':'actor-one','name':name}}


@pytest.mark.parametrize('failure',[0,1,2])
def test_real_runtime_failure_rolls_back_whole_batch(application,monkeypatch,failure):
    app=application;b=batch(app,[patch('one'),patch('two'),patch('three')]);before=app.host.state()
    original=app.host.manage;execute=app.host.execute_batch;running=[False];position=[0]
    def manage(*args,**kwargs):
        if running[0]:
            i=position[0];position[0]+=1
            if i==failure:raise DomainError('INJECTED_FAILURE')
        return original(*args,**kwargs)
    def run(*args,**kwargs):
        running[0]=True
        try:return execute(*args,**kwargs)
        finally:running[0]=False
    monkeypatch.setattr(app.host,'manage',manage);monkeypatch.setattr(app.host,'execute_batch',run)
    result=committed(decide(app,b));details=result['execution']
    assert result['status']==('rolled_back' if failure else 'failed') and details['committedCount']==0
    assert [r['status'] for r in details['items']]==['rolled_back']*failure+['failed']+['not_executed']*(2-failure)
    after=app.host.state()
    for key in ('entities','relations','progress','chat','outbox','audit'):assert after[key]==before[key]
    assert not result['receipts']
    for row in details['items']:assert app.host.receipt('kp',row['commandId'])['status']=='unknown'
    parent=app.host.receipt('kp',result['executionCommandId']);assert parent['result']==details


def test_unknown_receipt_reconciles_original_id_without_replay(application,monkeypatch):
    app=application;b=batch(app);execute=app.host.execute_batch;receipt=app.host.receipt;hidden=[True];calls=[]
    def run(*a,**kw):calls.append(kw['command_id']);execute(*a,**kw);raise OSError('reply lost')
    def read(account,cid):
        return {'status':'unknown','commandId':cid} if hidden[0] and cid.startswith('ai-atomic:') else receipt(account,cid)
    monkeypatch.setattr(app.host,'execute_batch',run);monkeypatch.setattr(app.host,'receipt',read)
    assert committed(decide(app,b))['status']=='unknown';hidden[0]=False
    result=committed(decide(app,b,'reconcile'));assert result['status']=='completed' and len(calls)==1
    assert result['execution']['committedCount']==1


def test_ai_only_group_commits_and_rolls_back_in_one_store(application,monkeypatch):
    app=application;actions=[{'target':'ai','op':'ai.session.create','args':{'title':str(i)}} for i in range(3)]
    from onlinecoc_ai.api import Application
    b=batch(app,actions);before=app.repository.state();original=Application._execute;count=[0]
    def execute(self,account,cid,op,args,**kwargs):
        if cid.startswith('ai-batch:'):
            count[0]+=1
            if count[0]==2:raise AiError('INJECTED_FAILURE')
        return original(self,account,cid,op,args,**kwargs)
    monkeypatch.setattr(Application,'_execute',execute)
    result=committed(decide(app,b));assert result['status']=='rolled_back'
    assert app.repository.state()['settings']['sessions']==before['settings']['sessions']
    assert not any('ai-batch:'+b['batchId'] in key for key in app.repository.state()['commands'])
    monkeypatch.setattr(Application,'_execute',original)
    good=batch(app,actions);result=committed(decide(app,good));assert result['status']=='completed'
    assert len(result['receipts'])==3 and result['execution']['scope']=='ai.store.atomic.v1'


def test_cross_store_and_unsupported_host_commands_block_before_execution(application):
    app=application;before=app.host.state()
    for actions in ([patch('x'),{'target':'ai','op':'ai.session.create','args':{'title':'x'}}],
                    [{'target':'host','op':'member.add','args':{'accountId':'new-player','role':'player'}}]):
        b=batch(app,actions);assert b['status']=='blocked' and b['preflight']['status']=='unsupported'
        assert decide(app,b)['code']=='BATCH_NOT_PENDING'
    assert app.host.state()==before


def test_single_memory_receipt_repairs_mirror_after_commit(application,monkeypatch):
    from test_memory import create
    app=application;memory=create(app.memory,app.host);args={'memoryId':memory['memoryId'],'revision':1}
    original=app.repository.update;fail=[True]
    def update(callback):
        result=original(callback)
        if fail[0] and app.host.state()['aiControl'].get('memoryFacts',{}).get(memory['memoryId']):
            fail[0]=False;raise OSError('mirror reply lost')
        return result
    monkeypatch.setattr(app.repository,'update',update)
    first=command(app,'ai.memory.confirm',args,identifier='recover-memory');assert first['status']=='unknown'
    fact=app.host.state()['aiControl']['memoryFacts'][memory['memoryId']]
    second=committed(command(app,'ai.memory.confirm',args,identifier='recover-memory'))
    assert second==fact and second['revision']==2
    assert app.repository.state()['memory'][memory['memoryId']]==fact
    assert len([r for r in app.host.state()['commands'].values() if r['id'].startswith('ai-memory:')])==1


def test_single_memory_batch_mirrors_exact_authoritative_fact(application):
    from test_memory import create
    app=application;draft=create(app.memory,app.host)
    for op,revision in [('ai.memory.confirm',1),('ai.memory.revoke',2)]:
        b=batch(app,[{'target':'ai','op':op,'args':{'memoryId':draft['memoryId'],'revision':revision}}])
        result=committed(decide(app,b));assert result['status']=='completed',result
        assert app.repository.state()['memory'][draft['memoryId']]==app.host.state()['aiControl']['memoryFacts'][draft['memoryId']]


@pytest.mark.parametrize('repair',[True,False])
def test_semantic_feedback_repairs_or_preserves_blocked_candidate(application,repair):
    app=application;enable(app.host,public=True,kp=True)
    for p in app.coordinator.profiles.values():p['limits'].update(maxRepairAttempts=2,maxToolRounds=4)
    calls=[]
    async def callback(n,messages,tools):
        calls.append(copy.deepcopy(messages))
        if n>1:
            feedback=json.loads(messages[-1]['content']);assert feedback['preflight']['status']=='blocked'
            assert feedback['preflight']['items'][0]['code']=='NOT_VISIBLE'
        action=patch('Resolved name');action['args']['id']='actor-one' if n>1 and repair else 'unknown-actor'
        return completion({'kind':'batch','text':'修改已指明角色的名称','actions':[action]})
    async def run():
        before=app.host.state();app.coordinator.provider_factory=lambda _:Fake(callback)
        r=submit(app,session(app),'修改角色名字');task=committed(command(app,'ai.request.dispatch',{'requestId':r['requestId']}))
        await app.coordinator.start()
        try:
            result=await wait_task(app.coordinator,task['taskId']);assert result['status']==('review_ready' if repair else 'failed'),result
            b=app.repository.state()['settings']['batches'][result['batchId']]
            assert b['status']==('pending' if repair else 'blocked') and len(calls)==(2 if repair else 3)
            assert app.host.state()==before and not result.get('choices')
            assert any(e['stage']=='technical_repair' for e in result['events'])
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_business_failure_is_committed_without_reroll_or_goal_resolution(application,monkeypatch):
    import onlinecoc.atomic_batches as atomic
    app=application;monkeypatch.setattr(atomic.secrets,'randbelow',lambda _:99)
    action={'target':'host','op':'action.invoke','args':{'actionId':'fixture.check','input':{'actor':'actor-one','item':'token-one'}}}
    charges=app.host.state()['entities']['token-one']['numbers']['charges']
    b=batch(app,[action]);assert b['preflight']['status']=='runtime_required'
    result=committed(decide(app,b));assert result['status']=='completed'
    assert result['execution']['items'][0]['result']['passed'] is False
    assert 'resolution' not in app.queue.fields('batch:'+b['batchId'])
    assert app.host.state()['entities']['token-one']['numbers']['charges']==charges-1


def test_more_than_32_actions_have_no_count_cap(application):
    app=application;b=batch(app,[patch(str(i)) for i in range(33)])
    result=committed(decide(app,b));assert result['execution']['committedCount']==33


def test_legacy_pending_batch_cannot_enter_sequential_executor(application):
    app=application;b=batch(app);state=app.repository.state();old=state['settings']['batches'][b['batchId']]
    old['context']['facts'].pop('batchExecutionVersion');old['digest']=digest({k:old[k] for k in ('batchId','sessionId','requestId','creator','actions','context','baseline','authorityEpoch')})
    app.repository.commit(state);before=app.host.state()
    assert decide(app,old)['code']=='BATCH_REGENERATE_REQUIRED' and app.host.state()==before
