"""Authorization, provenance, budgets and real HTTP/model-tool composition."""
import asyncio
import copy
import json
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from onlinecoc import chat
from onlinecoc.errors import DomainError
from onlinecoc.server import create_app
from onlinecoc_ai.context import Context
from onlinecoc_ai.data_queries import DataQueryService
from onlinecoc_ai.contracts import canonical, digest
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.providers.base import Completion
from onlinecoc_ai.coordinator import Coordinator
from onlinecoc_ai.references import References
from test_coordinator import setup, Fake, completion, wait_task
from test_context import enable, add_message, request
from test_entrypoints import application


def test_search_detail_and_external_policy(setup):
    host,service,_=setup;q=DataQueryService(host)
    assert q.execute('kp','search',{'types':['config']})['items']
    assert q.execute('kp','search',{'types':['config']},external=True)['items']==[]
    enable(host,public=True)
    ref=q.execute('kp','search',{'types':['config']},external=True)['items'][0]['ref']
    assert q.execute('kp','read',{'refs':[ref]},external=True)['items'][0]['data']
    ref['scopeId']='other-room'
    with pytest.raises(DomainError,match='SOURCE_STALE'):q.execute('kp','read',{'refs':[ref]})


@pytest.mark.parametrize('args',[{'account':'kp'},{'limit':True},{'limit':51},{'types':['commands']},{'query':'x'*121},{'cursor':'bogus'},{'sql':'select *'}])
def test_query_rejects_unbounded_or_identity_input(setup,args):
    with pytest.raises((AiError,DomainError)):DataQueryService(setup[0]).execute('player1','search',args)


def test_chat_intersection_window_cursor_and_edit(setup):
    host,_,_=setup;q=DataQueryService(host);enable(host,public=True,private=True)
    for text in ('first','second','third'):add_message(host,'player1',text)
    state=host.state();state['chat']['channels']['secret']=chat.channel('secret','direct','secret',['player1','player2']);state['chat']['messages']['secret']=[];host.commit(state)
    add_message(host,'player1','hidden','secret')
    with pytest.raises(DomainError,match='NOT_VISIBLE'):q.execute('kp','chat',{'channelId':'secret'},initiator='player1')
    page=q.execute('player1','chat',{'channelId':'general','limit':1})
    assert page['items'][0]['data']['text']=='first'
    cursor=page['page']['nextCursor'];assert cursor
    assert q.execute('player1','chat',{'channelId':'general','limit':1,'cursor':cursor})['items'][0]['data']['text']=='second'
    add_message(host,'player1','fourth')
    with pytest.raises(DomainError,match='SOURCE_STALE'):q.execute('player1','chat',{'channelId':'general','limit':1,'cursor':cursor})


def test_dynamic_evidence_and_explicit_reference_recheck(setup):
    host,service,_=setup;enable(host,public=True)
    message=add_message(host,'player1','test evidence')
    token=References(host).search('kp','chat')['items'][0]['token']
    context=Context(service,demand=True)
    snapshot,payload=context.capture('kp',request(token))
    assert not payload['roomFacts']['messages'] and payload['selectedReferences']
    assert snapshot[0]['facts']['dataQueries']
    state=host.state();state['chat']['messages']['general'][0].update(text='edited',revision=2);host.commit(state)
    with pytest.raises(DomainError,match='SOURCE_STALE'):context.recheck('kp',snapshot)


def test_tool_queries_never_read_kp_secret_for_player(setup):
    host,_,_=setup;enable(host,public=True,kp=True)
    state=host.state();state['entities']['actor-one']['metadata']['secret']='hidden';host.commit(state)
    q=DataQueryService(host)
    refs=[r['ref'] for r in q.execute('kp','search',{'types':['entity']},initiator='player1',external=True)['items']]
    assert 'hidden' not in canonical(q.execute('kp','read',{'refs':refs},initiator='player1',external=True)).decode()


def test_model_search_read_then_result_keeps_evidence(setup):
    host,service,profile=setup;enable(host,public=True)
    async def callback(number,messages,tools):
        if number==1:name,args='room_search_data',{'types':['config'],'limit':1}
        elif number==2:
            found=json.loads(messages[-1]['content']);name,args='room_read_data',{'refs':[found['items'][0]['ref']]}
        else:return completion({'kind':'plan','text':'已读取所选配置，尚未修改游戏。'})
        data={'role':'assistant','content':None,'tool_calls':[{'id':str(number),'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}
        return Completion(data,{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20},'tool_calls',digest(data))
    async def run():
        c=Coordinator(service,{profile['profileId']:profile},context=Context(service,demand=True),provider_factory=lambda _:Fake(callback));await c.start()
        try:
            task=c.enqueue('kp','query','查询配置');result=await wait_task(c,task['taskId'])
            assert result['status']=='review_ready',result
            evidence=service.repository.state()['contexts'][result['contextRef']]
            assert len(evidence['facts']['dataQueries'])==2
            assert not host.state()['aiControl']['approvals']
        finally:await c.close()
    asyncio.run(run())


def test_http_query_auth_csrf_and_contract(application):
    app=application
    async def noop():pass
    runtime=SimpleNamespace(application=app,start=noop,close=noop)
    with TestClient(create_app(app.host,8765,ai_runtime=runtime),base_url='http://127.0.0.1:8765') as client:
        assert client.post('/api/v1/ai/data/search',json={}).status_code!=200
        login=client.post('/api/v1/login',json={'loginName':'kp','password':'test-password'},headers={'Origin':'http://127.0.0.1:8765'})
        headers={'Origin':'http://127.0.0.1:8765','X-CSRF-Token':login.json()['csrf']}
        assert client.post('/api/v1/ai/data/search',json={},headers={'Origin':'http://127.0.0.1:8765'}).status_code!=200
        result=client.post('/api/v1/ai/data/search',json={'types':['config']},headers=headers)
        assert result.status_code==200 and result.json()['items']
        assert len(client.get('/api/v1/ai/contracts').json()['dataTools'])==4


def test_result_limit_and_missing_adapter_are_fail_closed(setup):
    host,_,_=setup
    for _ in range(6):add_message(host,'player1','x'*3900)
    with pytest.raises(DomainError,match='QUERY_RESULT_LIMIT'):DataQueryService(host).execute('kp','chat',{'channelId':'general'})
    class Broken:
        def read(self,*args):raise OSError('secret path')
    host.ai_data_adapter=Broken()
    with pytest.raises(DomainError,match='DATA_SOURCE_UNAVAILABLE'):DataQueryService(host).execute('kp','search',{})


def test_query_evidence_prevents_publish_after_source_edit(setup):
    from onlinecoc.publication import check_context
    host,service,_=setup;enable(host,public=True)
    add_message(host,'player1','published evidence')
    context=Context(service,demand=True);snapshot,_=context.capture('kp',request())
    DataQueryService(host).attach('kp','chat',{'channelId':'general'},snapshot)
    # This is the host-owned check shared by approval and publication, without the AI repository.
    service.repository.close()
    check_context(host,host.state(),'kp',snapshot[0])
    state=host.state();state['chat']['messages']['general'][0].update(text='',deleted=True,revision=2);host.commit(state)
    with pytest.raises(DomainError,match='SOURCE_STALE'):check_context(host,host.state(),'kp',snapshot[0])


def test_per_round_multi_call_budget(setup):
    host,service,profile=setup;enable(host,public=True)
    async def callback(*unused):
        calls=[{'id':str(i),'type':'function','function':{'name':'room_search_data','arguments':'{"types":["config"]}'}} for i in range(25)]
        data={'role':'assistant','content':None,'tool_calls':calls}
        return Completion(data,{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20},'tool_calls',digest(data))
    async def run():
        c=Coordinator(service,{profile['profileId']:profile},context=Context(service,demand=True),provider_factory=lambda _:Fake(callback));await c.start()
        try:
            task=c.enqueue('kp','budget','query');result=await wait_task(c,task['taskId'])
            assert result['status']=='failed' and result['error']=='QUERY_LIMIT',result
        finally:await c.close()
    asyncio.run(run())
