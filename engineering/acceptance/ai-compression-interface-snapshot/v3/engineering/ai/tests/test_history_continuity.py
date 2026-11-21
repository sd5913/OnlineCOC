"""Expired facts are readable history only; grants and execution stay current."""
import asyncio
import copy
import pytest
from onlinecoc_ai.context import Context
from onlinecoc_ai.contracts import digest
from onlinecoc_ai.errors import AiError
from test_entrypoints import application, command, committed
from test_coordinator import setup, Fake, completion, wait_task
from test_access_batches import tool_call
from test_context import enable
from test_sessions import submit


def history_case(app,query=None,demand=False):
    enable(app.host,public=True,kp=True,private=True)
    sid=committed(command(app,'ai.session.create',{'title':'Historical intent'}))['sessionId']
    if demand:
        app.coordinator.context=Context(app.proposals,demand=True)
        if query is None:query=query_for('search')
    async def callback(count,*_):
        if query and count==1:return tool_call(*query(app))
        return completion({'kind':'plan','text':'已确定：给 player1 的角色加1点护甲，保留其他状态；等待另行审批。'})
    async def generate():
        app.coordinator.provider_factory=lambda _:Fake(callback);await app.coordinator.start()
        try:
            req=submit(app,sid,'请先准备给 player1 加护甲的方案')
            dispatched=committed(command(app,'ai.request.dispatch',{'requestId':req['requestId']}))
            task=await wait_task(app.coordinator,dispatched['taskId']);assert task['status']=='review_ready',task
            return task
        finally:await app.coordinator.close()
    task=asyncio.run(generate())
    state=app.host.state();state['entities']['actor-one']['name']='资料更新后的名称';state['entities']['actor-one']['revision']+=1;app.host.commit(state)
    return sid,task


def test_stale_authorized_response_stays_visible_with_readonly_notice(application):
    app=application;sid,task=history_case(app)
    row=app.sessions.get('kp',sid)['items'][0]
    assert row.get('response')==task['text'],row
    assert row['initiator']=='kp' and row['sourceState']=='stale' and row['historicalReadOnly']
    assert row['sourceError'] in ('SOURCE_STALE','BASELINE_STALE') and '重新' in row['sourceNotice']


def test_short_confirmation_retains_stale_intent_without_old_execution_proofs(application):
    app=application;sid,task=history_case(app)
    req=submit(app,sid,'是的，按此方案处理')
    snapshot,payload=Context(app.proposals,demand=True).capture('kp',app.repository.state()['requests'][req['requestId']])
    previous=[row for row in payload['conversationHistory'] if row['role']=='assistant']
    assert previous and previous[-1]['content']==task['text'],payload['conversationHistory']
    assert previous[-1]['authority']=='historical-intent-only' and previous[-1]['stale']
    assert not snapshot[0]['facts'].get('historyContexts')
    assert snapshot[0]['facts']['historyIntents'][0]['contextRef']==task['contextRef']
    assert not snapshot[0]['sourceRefs'] and not snapshot[0]['facts'].get('dataQueries')


def query_for(operation):
    def select(app):
        from onlinecoc_ai.data_queries import DataQueryService
        if operation=='search':return 'room_search_data',{'types':['entity'],'query':''}
        result=DataQueryService(app.host).execute('kp','search',{'types':['entity']})
        ref=next(i['ref'] for i in result['items'] if i['ref']['id']==digest(['host','entity','actor-one']))
        return 'room_read_data',{'refs':[ref]}
    return select


def strip_new_witnesses(app,task):
    state=app.repository.state();old=state['contexts'][task['contextRef']];context=copy.deepcopy(old)
    for proof in context['facts'].get('dataQueries',[]):proof.pop('readRefs',None)
    key=digest(context);state['contexts'][key]=context;state['tasks'][task['taskId']]['contextRef']=key
    app.repository.commit(state);task['contextRef']=key


@pytest.mark.parametrize('operation,legacy,readable',[('read',True,True),('search',False,True),('search',True,False)])
def test_query_history_identity_witness_and_legacy_boundary(application,operation,legacy,readable):
    app=application;sid,task=history_case(app,query_for(operation),demand=True)
    if legacy:strip_new_witnesses(app,task)
    row=app.sessions.get('kp',sid)['items'][0]
    assert bool(row.get('response'))==readable,row
    if readable:assert row['historicalReadOnly'] and row['response']==task['text']
    else:assert row['error']=='HISTORY_PROVENANCE_INCOMPLETE'


@pytest.mark.parametrize('change',['deleted','hidden','authorization','policy','profile','session_deleted'])
def test_delivered_body_survives_but_changed_sources_do_not_enter_new_context(application,change):
    app=application;sid,task=history_case(app)
    room=app.host.state()
    if change=='deleted':del room['entities']['actor-one']
    elif change=='hidden':room['entities']['actor-one']['visibility']='kp'
    elif change=='authorization':room['members']['kp']['authorizationEpoch']+=1
    elif change=='policy':room['aiControl']['settings']['externalSources']['private']=False
    elif change=='profile':room['aiControl']['settings']['profileId']='other-profile'
    elif change=='session_deleted':
        record=app.sessions.get('kp',sid)['session'];committed(command(app,'ai.session.delete',{'sessionId':sid,'revision':record['revision']}))
        assert not app.tasks('kp')['items'];return
    app.host.commit(room)
    row=app.sessions.get('kp',sid)['items'][0]
    if change=='authorization':assert not row.get('response') and row['sourceState']=='denied'
    else:assert row['response']==task['text'] and row['historicalReadOnly'],row
    req=submit(app,sid,'重新核对最新资料')
    _,payload=Context(app.proposals,demand=True).capture('kp',app.repository.state()['requests'][req['requestId']])
    assert not any(turn['content']==task['text'] for turn in payload['conversationHistory'])


def test_new_query_witness_does_not_restore_deleted_object(application):
    app=application;sid,task=history_case(app,query_for('search'),demand=True)
    room=app.host.state();del room['entities']['actor-one'];app.host.commit(room)
    row=app.sessions.get('kp',sid)['items'][0]
    assert row['response']==task['text'] and row['historicalReadOnly']
    req=submit(app,sid,'重新查询')
    _,payload=Context(app.proposals,demand=True).capture('kp',app.repository.state()['requests'][req['requestId']])
    assert not any(turn['content']==task['text'] for turn in payload['conversationHistory'])


def test_historical_intent_is_rechecked_after_capture_and_has_no_execution_authority(application):
    from onlinecoc.publication import check_context
    app=application;sid,task=history_case(app)
    old=app.repository.state()['contexts'][task['contextRef']]
    with pytest.raises(Exception):check_context(app.host,app.host.state(),'kp',old)
    req=submit(app,sid,'是的，按此方案处理')
    snap,_=Context(app.proposals,demand=True).capture('kp',app.repository.state()['requests'][req['requestId']])
    app.host.validate_ai_sources(app.host.state(),'kp',snap[0])
    room=app.host.state();del room['entities']['actor-one'];app.host.commit(room)
    with pytest.raises(Exception):app.host.validate_ai_sources(room,'kp',snap[0])


def test_history_scope_mismatch_never_falls_back(application):
    from onlinecoc_ai.history import assess
    app=application;sid,task=history_case(app)
    room=app.host.state();room['aiControl']['scopeId']='different-room'
    with pytest.raises(AiError,match='SCOPE_MISMATCH'):assess(app.host,app.repository,room,app.repository.state()['contexts'][task['contextRef']])


def test_short_confirmation_requires_current_target_read_before_batch(application):
    from onlinecoc_ai.data_queries import DataQueryService
    from onlinecoc_ai.history import require_current_evidence
    app=application;sid,task=history_case(app)
    req=submit(app,sid,'是的，按此方案处理');request=app.repository.state()['requests'][req['requestId']]
    snapshot,_=Context(app.proposals,demand=True).capture('kp',request)
    actions=[{'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'最新方案'}}]
    with pytest.raises(AiError,match='HISTORY_REQUERY_REQUIRED'):app.batches.create('kp',request,actions,'审核候选',snapshot[0])
    q=DataQueryService(app.host)
    refs=q.execute('kp','search',{'types':['entity']})['items']
    other=next(i['ref'] for i in refs if i['ref']['id']!=digest(['host','entity','actor-one']))
    q.attach('kp','read',{'refs':[other]},snapshot,'kp')
    with pytest.raises(AiError,match='HISTORY_REQUERY_REQUIRED'):require_current_evidence(snapshot[0],{'kind':'batch','actions':actions})
    ref=next(i['ref'] for i in refs if i['ref']['id']==digest(['host','entity','actor-one']))
    q.attach('kp','read',{'refs':[ref]},snapshot,'kp')
    bid=app.batches.create('kp',request,actions,'审核候选',snapshot[0])
    assert app.repository.state()['settings']['batches'][bid]['status']=='pending'
    assert app.host.state()['entities']['actor-one']['name']!='最新方案'


def test_model_repairs_stale_intent_by_reading_target_without_reasking(application):
    import json
    from onlinecoc_ai.data_queries import DataQueryService
    from test_batch_notifications import actions
    from test_access_batches import decide
    app=application;sid,old=history_case(app,demand=True)
    from onlinecoc_ai.coordinator import Coordinator
    app.coordinator=Coordinator(app.proposals,app.coordinator.profiles,context=Context(app.proposals,demand=True))
    app.runtime.coordinator=app.coordinator;app.coordinator.application=app
    ref=next(i['ref'] for i in DataQueryService(app.host).execute('kp','search',{'types':['entity']})['items'] if i['ref']['id']==digest(['host','entity','actor-one']))
    seen=[]
    async def callback(count,messages,tools):
        seen.append(count)
        if count==1:
            payload=json.loads(messages[1]['content'])
            assert payload['currentActor']['accountId']=='kp'
            assert payload['conversationHistory'][-1]['authority']=='historical-intent-only'
            return completion({'kind':'batch','text':'保留原方案，待审核后修改并通知','actions':actions()})
        if count==2:
            feedback=json.loads(messages[-1]['content'])
            assert feedback['error']['code']=='HISTORY_REQUERY_REQUIRED'
            assert 'do not ask' in feedback['instruction']
            return tool_call('room_read_data',{'refs':[ref]})
        return completion({'kind':'batch','text':'已核对当前目标，修改和通知均等待审核','actions':actions()})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);await app.coordinator.start()
        try:
            request=submit(app,sid,'是的，按此方案处理')
            task=committed(command(app,'ai.request.dispatch',{'requestId':request['requestId']}))
            result=await wait_task(app.coordinator,task['taskId']);assert result['status']=='review_ready',result
            return result
        finally:await app.coordinator.close()
    result=asyncio.run(run());assert seen==[1,2,3]
    row=next(i for i in app.sessions.get('kp',sid)['items'] if i.get('taskId')==result['taskId'])
    assert row['status']=='review_ready' and not row.get('historicalReadOnly'),row
    record=app.repository.state()['settings']['batches'][result['batchId']]
    assert record['status']=='pending' and not app.host.notifications('player1')['items']
    assert committed(decide(app,record))['status']=='completed'
    assert len(app.host.notifications('player1')['items'])==1 and not app.host.notifications('player2')['items']


@pytest.mark.parametrize('change_during_generation',[False,True])
def test_new_generation_public_status_is_not_expired_historical_intent(application,change_during_generation):
    from onlinecoc_ai.coordinator import Coordinator
    app=application;sid,old=history_case(app,demand=True)
    app.coordinator=Coordinator(app.proposals,app.coordinator.profiles,context=Context(app.proposals,demand=True))
    app.runtime.coordinator=app.coordinator;app.coordinator.application=app
    async def run():
        entered=asyncio.Event();release=asyncio.Event()
        async def callback(*_):
            entered.set();await release.wait()
            return completion({'kind':'plan','text':'已保留原意图，继续准备当前方案'})
        app.coordinator.provider_factory=lambda _:Fake(callback);await app.coordinator.start()
        try:
            req=submit(app,sid,'是的，按此方案处理')
            dispatched=committed(command(app,'ai.request.dispatch',{'requestId':req['requestId']}))
            await asyncio.wait_for(entered.wait(),5)
            if change_during_generation:
                room=app.host.state();room['entities']['actor-one']['name']='生成期间再次变化';room['entities']['actor-one']['revision']+=1;app.host.commit(room)
            row=next(i for i in app.sessions.get('kp',sid)['items'] if i['requestId']==req['requestId'])
            assert row['status']=='generating' and not row.get('historicalReadOnly'),row
            release.set();task=await wait_task(app.coordinator,dispatched['taskId'])
            row=next(i for i in app.sessions.get('kp',sid)['items'] if i['requestId']==req['requestId'])
            if change_during_generation:
                assert task['status']=='review_ready' and row['response']==task['text'],row
                assert not row.get('error')
            else:
                assert task['status']=='review_ready' and row['status']=='review_ready',row
                assert not row.get('historicalReadOnly') and row.get('sourceState') in (None,'fresh')
            old_row=next(i for i in app.sessions.get('kp',sid)['items'] if i.get('taskId')==old['taskId'])
            assert old_row['historicalReadOnly'] and old_row['response']==old['text']
        finally:release.set();await app.coordinator.close()
    asyncio.run(run())
