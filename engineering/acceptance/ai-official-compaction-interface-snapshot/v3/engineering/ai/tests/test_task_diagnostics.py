"""Offline failures and provider-wire replay; no credential or live endpoint."""
import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from onlinecoc_ai.api import Application
from onlinecoc_ai.context import Context
from onlinecoc_ai.coordinator import Coordinator, SYSTEM
from onlinecoc_ai.data_queries import DataQueryService
from onlinecoc_ai.diagnostics import TaskTrace
from onlinecoc_ai.providers import create_provider
from onlinecoc_ai.providers.base import ProviderError
from test_coordinator import setup, Fake, completion, wait_task
from test_context import enable


def test_failure_diagnostics_redact_messages_and_preserve_primary(setup, caplog):
    _, service, profile = setup
    class Broken(Fake):
        async def close(self):raise RuntimeError('cleanup-secret')
    async def callback(*_):raise KeyError('key-secret and private-chat')
    async def run():
        c=Coordinator(service,{profile['profileId']:profile},provider_factory=lambda _:Broken(callback))
        await c.start()
        try:
            task=c.enqueue('kp','unexpected','private-request')
            saved=await wait_task(c,task['taskId'])
            assert saved['error']=='AI_TASK_FAILED'
            errors=saved['diagnostics']['errors']
            assert [(e['stage'],e['exceptionType']) for e in errors]==[('provider_complete','KeyError'),('provider_close','RuntimeError')]
            assert any(f['function']=='_generate' for f in errors[0]['frames'])
            encoded=json.dumps(saved['diagnostics'])+caplog.text
            assert not any(word in encoded for word in ('key-secret','private-chat','private-request','cleanup-secret',str(service.repository.store.path)))
        finally:await c.close()
    asyncio.run(run())


@pytest.mark.parametrize('cancel', [False,True])
def test_cleanup_error_does_not_replace_result_or_cancellation(setup, cancel):
    _,service,profile=setup
    class BrokenClose(Fake):
        async def close(self):raise RuntimeError('hidden cleanup error')
    async def run():
        entered=asyncio.Event()
        async def callback(*_):
            entered.set()
            if cancel:await asyncio.Event().wait()
            return completion({'kind':'plan','text':'valid answer'})
        c=Coordinator(service,{profile['profileId']:profile},provider_factory=lambda _:BrokenClose(callback));await c.start()
        try:
            task=c.enqueue('kp','close','test');await entered.wait()
            if cancel:c.cancel('kp',task['taskId'])
            await wait_task(c,task['taskId'])
        finally:await c.close()
        saved=service.repository.state()['tasks'][task['taskId']]
        assert saved['status']==('cancelled' if cancel else 'review_ready')
        assert saved['text']==(None if cancel else 'valid answer')
        assert saved['diagnostics']['errors'][0]['stage']=='provider_close'
    asyncio.run(run())


def test_tool_metadata_is_bounded_and_contains_no_argument_values():
    trace=TaskTrace();trace.tool('room_search_data',{'types':['entity'],'query':'SECRET_NAME','limit':12,'otherSecret':'SECRET_VALUE'})
    info=trace.snapshot()['toolCalls'][0]
    assert info['types']==['entity'] and info['hasQuery'] and info['unknownKeys']
    assert 'SECRET' not in json.dumps(info) and 'otherSecret' not in json.dumps(info)


@pytest.mark.parametrize('bad', [None, {'limit':None}, {'types':['unknown']}, {'fields':['no-such-field']}])
def test_deepseek_wire_query_replay_and_parameter_repair(setup, bad):
    host,service,profile=setup;enable(host,public=True,kp=True,private=True)
    seen=[]
    def handler(request):
        body=json.loads(request.content);seen.append(body)
        assert body['thinking']=={'type':'disabled'}
        assert 'NOT LOADED' in body['messages'][0]['content']
        tools=[m for m in body['messages'] if m['role']=='tool']
        if bad is not None and not tools:
            name='room_read_data' if 'fields' in bad else 'room_search_data'
            arguments={**bad}
            if name=='room_read_data':
                arguments['refs']=[DataQueryService(host).execute('kp','search',{'types':['entity'],'limit':1},external=True)['items'][0]['ref']]
        elif not tools or (json.loads(tools[-1]['content']).get('error') and len(tools)==1):
            if tools:assert json.loads(tools[-1]['content'])['error']['code']=='INPUT_INVALID'
            name,arguments='room_search_data',{'types':['entity'],'query':'','limit':12}
        elif not any(m['role']=='assistant' and any(c['function']['name']=='room_read_data' and 'fields' not in json.loads(c['function']['arguments']) for c in m.get('tool_calls',[])) for m in body['messages']):
            found=json.loads(tools[-1]['content']);assert found['items']
            name,arguments='room_read_data',{'refs':[found['items'][0]['ref']]}
        else:
            data=json.loads(tools[-1]['content']);assert data['items'][0]['data']['name']
            message={'role':'assistant','content':json.dumps({'kind':'plan','text':'已读取角色 '+data['items'][0]['data']['name']})}
            return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':message}],'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}})
        message={'role':'assistant','content':None,'tool_calls':[{'id':'call'+str(len(seen)),'type':'function',
            'function':{'name':name,'arguments':json.dumps(arguments)}}]}
        return httpx.Response(200,json={'choices':[{'finish_reason':'tool_calls','message':message}],'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}})
    async def run():
        c=Coordinator(service,{profile['profileId']:profile},context=Context(service,demand=True),
            provider_factory=lambda p:create_provider(p,transport=httpx.MockTransport(handler),credential_loader=lambda _:'offline-key'))
        await c.start()
        try:
            task=c.enqueue('kp','wire','查看所有房间信息并梳理')
            saved=await wait_task(c,task['taskId'])
            assert saved['status']=='review_ready',saved
            assert '已读取角色' in saved['text']
            diagnostics=saved['diagnostics']
            assert not diagnostics['errors'] and diagnostics['stage']=='completed'
            assert len(diagnostics['toolCalls'])==(3 if bad is not None else 2)
            assert diagnostics['toolCalls'][0]['status']==('rejected' if bad is not None else 'completed')
            app=Application(SimpleNamespace(proposals=service,coordinator=c))
            assert app.tasks('kp')['items'][0]['diagnostics']==diagnostics
            app.repository.update(lambda state:state['settings'].update(accessPolicy={'revision':1,'allowPlayerChat':True,'autoApproveBatches':False,'principal':'kp'}))
            assert app.tasks('player1')['items']==[]
            assert not host.state()['aiControl']['approvals']
        finally:await c.close()
    asyncio.run(run())


def test_provider_error_and_cleanup_keep_stable_code(setup):
    _,service,profile=setup;profile['limits']['maxTransportRetries']=0
    class BrokenClose(Fake):
        async def close(self):raise RuntimeError('do not replace auth error')
    async def callback(*_):raise ProviderError('PROVIDER_AUTH_FAILED')
    async def run():
        c=Coordinator(service,{profile['profileId']:profile},provider_factory=lambda _:BrokenClose(callback));await c.start()
        try:
            saved=await wait_task(c,c.enqueue('kp','auth','test')['taskId'])
            assert saved['error']=='PROVIDER_AUTH_FAILED'
            assert saved['diagnostics']['errors'][0]['code']=='PROVIDER_AUTH_FAILED'
        finally:await c.close()
    asyncio.run(run())


def test_model_page_counts_do_not_change_proofs_or_reveal_hidden_totals(setup):
    from onlinecoc_ai.data_queries import model_result
    from onlinecoc_ai.contracts import canonical
    host, service, _ = setup;enable(host,public=True,kp=True,private=True)
    context=Context(service,demand=True)
    snapshot,_=context.capture('kp',{'sourceKind':'manual','text':'page counts'})
    query=DataQueryService(host);args={'types':['entity'],'limit':1}
    raw=query.attach('kp','search',args,snapshot);before=canonical(raw)
    shown=model_result(raw,args)
    assert shown['pageSummary']=={'returnedItems':1,'countsByType':{'entity':1},'hasMore':True,'isFirstPage':True}
    assert canonical(raw)==before and 'pageSummary' not in raw
    context.recheck('kp',snapshot)
    next_args={**args,'cursor':raw['page']['nextCursor']}
    assert model_result(query.execute('kp','search',next_args,external=True),next_args)['pageSummary']['isFirstPage'] is False
    args={'types':['memory'],'limit':50}
    empty=model_result(query.execute('kp','search',args,external=True),args)
    assert empty['pageSummary']['returnedItems']==0 and empty['pageSummary']['countsByType']=={'memory':0}
    # Counts describe this principal's authorized result, not a hidden/global count.
    args={'types':['entity'],'limit':50}
    with pytest.raises(Exception,match='KNOWLEDGE_UNAVAILABLE'):
        query.execute('player1','search',args,external=True)


def test_channel_reference_resolves_actual_id_before_chat(setup):
    host,service,profile=setup;enable(host,public=True,kp=True,private=True)
    from test_context import add_message
    selected=add_message(host,'kp','check chat after this selected message')
    profile['limits']['maxToolRounds']=4
    seen=[]
    def handler(request):
        body=json.loads(request.content);seen.append(body)
        assert 'ref.id is an opaque' in body['messages'][0]['content']
        tools=[m for m in body['messages'] if m['role']=='tool']
        if not tools:name,args='room_search_data',{'types':['channel'],'limit':50}
        else:
            found=json.loads(tools[-1]['content'])
            assert found['pageSummary']['returnedItems']==len(found['items'])
            if len(tools)==1:
                assert found['items'][0]['ref']['id']!='general'
                name,args='room_read_data',{'refs':[found['items'][0]['ref']]}
            elif len(tools)==2:
                cid=found['items'][0]['data']['channelId'];assert cid=='general'
                name,args='room_read_chat',{'channelId':cid,'after':selected['sequence'],'limit':50}
            else:
                assert found['items']==[]
                return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps({'kind':'plan','text':'One channel; no messages in the authorized window.'})}}],'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}})
        message={'role':'assistant','content':None,'tool_calls':[{'id':'c'+str(len(seen)),'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}
        return httpx.Response(200,json={'choices':[{'finish_reason':'tool_calls','message':message}],'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}})
    async def run():
        c=Coordinator(service,{profile['profileId']:profile},context=Context(service,demand=True),provider_factory=lambda p:create_provider(p,transport=httpx.MockTransport(handler),credential_loader=lambda _:'offline-key'))
        await c.start()
        try:
            saved=await wait_task(c,c.enqueue('kp','channel-id',selected['text'],source_kind='chat',source_id=selected['messageId'],source_revision=str(selected['revision']))['taskId'])
            assert saved['status']=='review_ready',saved
            assert all(x['status']=='completed' for x in saved['diagnostics']['toolCalls'])
        finally:await c.close()
    asyncio.run(run())


def test_last_round_closes_tools_and_returns_bounded_partial_answer(setup):
    from onlinecoc_ai.providers.base import Completion
    host,service,profile=setup;enable(host,public=True)
    profile['limits']['maxToolRounds']=1
    seen=[]
    async def callback(count,messages,tools):
        seen.append(tools)
        if count==1:
            assert tools
            return Completion({'role':'assistant','content':None,'tool_calls':[{'id':'one','type':'function','function':{'name':'room_search_data','arguments':json.dumps({'types':['entity'],'limit':1})}}]}, {'prompt_tokens':10,'completion_tokens':10,'total_tokens':20},'tool_calls','f'*64)
        assert tools==[] and len(seen)==2
        assert messages[-1]['role']=='system' and 'final response-only turn' in messages[-1]['content']
        result=json.loads(next(m['content'] for m in reversed(messages) if m['role']=='tool'))
        assert result['pageSummary']['hasMore']
        return completion({'kind':'plan','text':'One entity on this page; further pages and details were not read.'})
    async def run():
        c=Coordinator(service,{profile['profileId']:profile},context=Context(service,demand=True),provider_factory=lambda _:Fake(callback))
        await c.start()
        try:
            saved=await wait_task(c,c.enqueue('kp','bounded','overview')['taskId'])
            assert saved['status']=='review_ready' and len(saved['calls'])==2,saved
            assert len(saved['diagnostics']['toolCalls'])==1
        finally:await c.close()
    asyncio.run(run())


@pytest.mark.parametrize('status',[400,422,None,'private error',True,99,600])
def test_http_diagnostics_keep_only_valid_status_without_remote_text(status,caplog):
    error=ProviderError('PROVIDER_REQUEST_INVALID',status=status)
    error.detail='SECRET_REMOTE_BODY';error.args=('SECRET_REMOTE_BODY',)
    trace=TaskTrace();trace.at('provider_complete');trace.error(error);trace.log('test-task')
    item=trace.snapshot()['errors'][0]
    if status in (400,422):assert item['httpStatus']==status
    else:assert 'httpStatus' not in item
    assert 'SECRET_REMOTE_BODY' not in json.dumps(trace.snapshot())+caplog.text
