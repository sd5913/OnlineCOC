"""ISSUE-018: historical delivery is not authority for current evidence."""
import asyncio
import copy
import json
import pytest
from test_entrypoints import application, command, committed
from test_coordinator import setup, Fake, completion, wait_task
from test_access_batches import session, submit, tool_call
from test_known_runtime import install, observe, host_call
from onlinecoc_ai.references import References
from test_access_batches import batch
from test_review_followup import new_batch, row


async def publish(app):
    async def callback(count,messages,tools):
        if count == 1:return tool_call('room_search_knowledge',{})
        page=json.loads(messages[-1]['content'])
        if count == 2:return tool_call('room_read_knowledge',{'refs':[page['items'][0]['ref']]})
        return completion({'kind':'known','evidence':[page['items'][0]['evidenceId']],'next':'none'})
    app.coordinator.provider_factory=lambda _:Fake(callback)
    await app.coordinator.start()
    try:
        s=session(app,'player1');r=submit(app,s,'我想吃掉奶酪回复一些生命',who='player1')
        task=await wait_task(app.coordinator,r['taskId'])
        assert task['status']=='review_ready',task
        return s,r,task
    finally:await app.coordinator.close()


@pytest.mark.parametrize('delivered',[False,True])
def test_published_player_text_survives_revoke_without_restoring_source(application,delivered):
    app=application;install(app);grant=observe(app)
    s,r,task=asyncio.run(publish(app))
    before=app.sessions.get('player1',s['sessionId'],delivered=delivered)['items'][0]
    assert before['responseAt']==task['responseAt'] and before['sentAt']==before['createdAt']
    assert before['referenceLabels']
    host_call(app,'knowledge.revoke',{'grantId':grant['grantId'],'expectedRevision':1,'reason':'撤回详情权限'})
    after=app.sessions.get('player1',s['sessionId'],delivered=True)['items'][0]
    assert after['response']==before['response'] and after['text']=='我想吃掉奶酪回复一些生命'
    assert after['referenceLabels']==before['referenceLabels'] and after['historicalReadOnly']
    assert after['responseAt']==before['responseAt'] and not after.get('error') and not after.get('choices')
    for token in after['referenceLabels']:
        with pytest.raises(Exception):References(app.host).resolve('player1',[token])
    assert app.tasks('player2',delivered=True)['items']==[]
    # Revoked messages must not become fresh model context or execution evidence.
    request=copy.deepcopy(app.repository.state()['requests'][r['requestId']])
    request['requestId']='f'*32
    app.repository.update(lambda state:(state['requests'].update({request['requestId']:request}),state['settings']['sessions'][s['sessionId']]['requestIds'].append(request['requestId'])))
    target=copy.deepcopy(app.repository.state()['contexts'][task['contextRef']])
    history=app.coordinator.context.history('player1',request,app.host.state(),app.host.state()['aiControl']['settings']['externalSources'],target)
    assert not any(x.get('role')=='assistant' for x in history[0])
    app.repository.verify(app.repository.state())


def test_unpublished_or_unproven_legacy_body_is_not_recovered(application):
    app=application;install(app);grant=observe(app);s,r,task=asyncio.run(publish(app))
    def unproven(state):
        value=state['tasks'][task['taskId']];value.pop('messagePublication');value['status']='failed'
    app.repository.update(unproven)
    host_call(app,'knowledge.revoke',{'grantId':grant['grantId'],'expectedRevision':1,'reason':'撤回'})
    item=app.sessions.get('player1',s['sessionId'])['items'][0]
    assert not item.get('response') and item['text']=='我想吃掉奶酪回复一些生命'
    assert not app.repository.state()['settings'].get('messageDeliveries')


def test_public_delivery_remembers_legacy_text_but_never_invents_time(application):
    app=application;install(app);grant=observe(app);s,r,task=asyncio.run(publish(app))
    def legacy(state):
        value=state['tasks'][task['taskId']];value.pop('responseAt');value.pop('messagePublication')
    app.repository.update(legacy)
    before=app.sessions.get('player1',s['sessionId'],delivered=True)['items'][0]
    assert before['responseAt'] is None
    generation=app.repository.store.generation
    app.sessions.get('player1',s['sessionId'],delivered=True)
    assert app.repository.store.generation==generation
    host_call(app,'knowledge.revoke',{'grantId':grant['grantId'],'expectedRevision':1,'reason':'撤回'})
    after=app.sessions.get('player1',s['sessionId'])['items'][0]
    assert after['response']==before['response'] and after['responseAt'] is None


def test_deleted_session_is_not_revived_by_delivery_receipt(application):
    app=application;install(app);observe(app);s,r,task=asyncio.run(publish(app))
    app.sessions.get('player1',s['sessionId'],delivered=True)
    current=app.sessions.get('player1',s['sessionId'])['session']
    committed(command(app,'ai.session.delete',{'sessionId':s['sessionId'],'revision':current['revision']},'player1'))
    assert app.tasks('player1',delivered=True)['items']==[]


def test_explicit_completed_followup_archives_predecessors_with_proof(application):
    app=application;first=batch(app);other=new_batch(app,first['sessionId'],name='独立请求')
    second=new_batch(app,first['sessionId'],related=first['requestId'])
    committed(command(app,'ai.batch.approve',{'batchId':second['batchId'],'digest':second['digest']}))
    old=row(app,'batch:'+first['batchId']);done=row(app,'batch:'+second['batchId'])
    assert old['queueStatus']=='archived' and not old['canRestore'] and not old['canDecide']
    assert old['resolution']==done['resolution'] and old['resolution']['goalDigest']
    assert old['resolution']['receiptRefs'][0]['commandId']==app.repository.state()['settings']['batches'][second['batchId']]['execution']['items'][0]['commandId']
    assert row(app,'batch:'+other['batchId'])['queueStatus']=='active'
    generation=app.repository.store.generation;app.queue.reconcile_completed()
    assert app.repository.store.generation==generation
    app.repository.verify(app.repository.state())


@pytest.mark.parametrize('status',['partial','unknown','executing'])
def test_uncertain_predecessor_is_never_closed(application,status):
    app=application;first=batch(app)
    app.repository.update(lambda state:state['settings']['batches'][first['batchId']].update(status=status))
    second=new_batch(app,first['sessionId'],related=first['requestId'])
    committed(command(app,'ai.batch.approve',{'batchId':second['batchId'],'digest':second['digest']}))
    item=row(app,'batch:'+first['batchId'])
    assert item['status']==status and item['queueStatus']=='active' and 'resolution' not in item


def test_completion_without_matching_host_receipts_cannot_close_group(application):
    app=application;first=batch(app);second=new_batch(app,first['sessionId'],related=first['requestId'])
    app.repository.update(lambda state:state['settings']['batches'][second['batchId']].update(status='completed',receipts=[
        {'id':'ai-batch:'+second['batchId']+':0','account':'kp','target':'host','receipt':{'status':'committed','result':{}}}]))
    app.queue.reconcile_completed()
    assert row(app,'batch:'+first['batchId'])['queueStatus']=='superseded'


def test_legacy_final_reply_migrates_after_revoke_and_survives_restart(application):
    from onlinecoc_ai.repository import Repository
    app=application;install(app);grant=observe(app);s,r,task=asyncio.run(publish(app))
    def old(state):
        value=state['tasks'][task['taskId']];value.pop('messagePublication');value.pop('responseAt')
    app.repository.update(old)
    host_call(app,'knowledge.revoke',{'grantId':grant['grantId'],'expectedRevision':1,'reason':'旧会话撤权'})
    item=app.sessions.get('player1',s['sessionId'])['items'][0]
    assert item['response']==task['text'] and item['responseAt'] is None and not item.get('referenceLabels')
    assert app.repository.state()['tasks'][task['taskId']]['messagePublication']['origin']=='legacy-final-task'
    app.repository.close()
    repo=Repository(app.host.path/'ai',app.host.state()['aiControl']['scopeId'])
    try:
        assert repo.state()['tasks'][task['taskId']]['messagePublication']['responseAt'] is None
        app.repository=repo;app.sessions.repository=repo
        assert app.sessions.get('player1',s['sessionId'])['items'][0]['response']==item['response']
    finally:repo.close()


def test_nested_review_recipient_remains_original_player(application):
    from test_player_requests import create
    app=application;s,r=create(app)
    first=committed(command(app,'ai.review.create',{'source':{'kind':'request','requestId':r['requestId']}}))
    second=committed(command(app,'ai.review.create',{'source':{'kind':'request','requestId':first['requestId']}}))
    for result in (first,second):
        item=app.sessions.get('kp',result['sessionId'])['items'][0]
        assert item['initiator']=='kp' and item['recipientAccountId']=='player1'
    ordinary=session(app);request=submit(app,ordinary)
    assert 'recipientAccountId' not in app.sessions.get('kp',ordinary['sessionId'])['items'][0]


@pytest.mark.parametrize('route',['tasks','session'])
def test_public_http_routes_record_only_authorized_deliveries(application,route):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from onlinecoc.server import create_app
    app=application;install(app);observe(app);s,r,task=asyncio.run(publish(app))
    async def idle():pass
    runtime=SimpleNamespace(application=app,start=idle,close=idle)
    with TestClient(create_app(app.host,ai_runtime=runtime),base_url='http://127.0.0.1:8765') as client:
        client.headers['origin']='http://127.0.0.1:8765'
        path='/api/v1/ai/tasks' if route=='tasks' else '/api/v1/ai/sessions/'+s['sessionId']
        assert client.get(path).status_code==401
        assert not app.repository.state()['settings'].get('messageDeliveries')
        assert client.post('/api/v1/login',json={'loginName':'player1','password':'test-password'}).status_code==200
        result=client.get(path);assert result.status_code==200
        assert result.json()['items'][0]['response']==task['text']
        deliveries=app.repository.state()['settings']['messageDeliveries']
        assert len(deliveries)==1 and next(iter(deliveries.values()))['account']=='player1'
