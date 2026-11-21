"""ISSUE-022: ordinary chat is not an AI dependency; delivered summaries survive age."""
import asyncio
import copy
import json
import pytest
from onlinecoc_ai.context import Context
from test_entrypoints import application,command,committed
from test_coordinator import setup,Fake,completion,wait_task
from test_access_batches import session,submit,tool_call
from test_context import enable,add_message,request


def generated(app,query=''):
    enable(app.host,public=True,private=True,kp=True)
    app.coordinator.context=Context(app.proposals,demand=True)
    async def callback(n,messages,tools):
        if n==1:return tool_call('room_search_data',{'types':['room'],'query':query,'limit':1})
        return completion({'kind':'batch','text':'原始裁决正文：将角色改名为测试名称。','actions':[{'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'测试名称'}}]})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);s=session(app)
        r=submit(app,s,'准备角色改名');task=committed(command(app,'ai.request.dispatch',{'requestId':r['requestId']}))
        await app.coordinator.start()
        try:return s,await wait_task(app.coordinator,task['taskId'])
        finally:await app.coordinator.close()
    s,t=asyncio.run(run());assert t['status']=='review_ready',t
    return s,t


def ruling(app,task,**kwargs):
    return next(i for i in app.rulings.list('kp',**kwargs)['items'] if i['rulingId']=='batch:'+task['batchId'])


def test_context_never_auto_collects_ordinary_chat(application):
    app=application;enable(app.host,public=True,private=True,kp=True)
    add_message(app.host,'player1','普通聊天室内容不得进入AI默认上下文')
    for demand in (False,True):
        snapshot,payload=Context(app.proposals,demand=demand).capture('kp',request())
        assert not payload['roomFacts']['messages']
        assert not any(r['kind']=='message' for r in snapshot[0]['sourceRefs'])


def test_broad_room_query_batch_survives_ordinary_chat(application):
    app=application;s,t=generated(app)
    before=ruling(app,t);assert before['canDecide']
    for account in ('kp','player1'):add_message(app.host,account,'并发普通聊天')
    after=ruling(app,t)
    assert after['summary']==before['summary'] and after['canDecide'],after
    result=committed(command(app,'ai.batch.approve',{'batchId':t['batchId'],'digest':after['digest']}))
    assert result['status']=='completed' and app.host.state()['entities']['actor-one']['name']=='测试名称'


@pytest.mark.parametrize('change',['value','removed','revoked','unproven'])
def test_ruling_keeps_only_proven_delivered_summary(application,change):
    app=application;s,t=generated(app,'/entities/actor-one')
    assert ruling(app,t)['summary']==t['text']
    state=app.host.state()
    if change=='removed':del state['entities']['actor-one']
    elif change=='revoked':state['members']['kp']['authorizationEpoch']+=1
    else:state['entities']['actor-one']['name']='Updated';state['entities']['actor-one']['revision']+=1
    app.host.commit(state)
    if change=='unproven':
        def strip(store):
            value=store['tasks'][t['taskId']];value.pop('messagePublication',None);value['status']='failed'
        app.repository.update(strip)
    result=ruling(app,t)
    if change in ('value','removed'):
        assert result['summary']==t['text'] and result['sourceState']=='stale' and result['historicalReadOnly'],result
        assert not result['canDecide']
    else:assert result['summary']!=t['text'] and result['sourceState']=='denied'


@pytest.mark.parametrize('change',['edit','retract'])
def test_selected_message_depends_only_on_that_message(application,change):
    app=application;enable(app.host,public=True,private=True,kp=True)
    selected=add_message(app.host,'kp','明确引用的需求')
    req={'sourceKind':'chat','sourceId':selected['messageId'],'sourceRevision':str(selected['revision']),'text':selected['text']}
    context=Context(app.proposals,demand=True);snapshot,_=context.capture('kp',req)
    add_message(app.host,'player1','不相关新增')
    context.recheck('kp',snapshot)
    room=app.host.state();message=room['chat']['messages']['general'][0];message['revision']+=1
    if change=='edit':message['text']='引用已修改'
    else:message.update(deleted=True,text='')
    app.host.commit(room)
    with pytest.raises(Exception):context.recheck('kp',snapshot)


def test_default_tools_exclude_chat_but_explicit_reference_allows_it():
    from onlinecoc_ai.data_queries import TOOLS,generation_tools
    default=generation_tools(TOOLS,{'sourceKind':'manual'},{})
    assert 'room_read_chat' not in [t['function']['name'] for t in default]
    search=next(t['function']['parameters'] for t in default if t['function']['name']=='room_search_data')
    assert search['required']==['types'] and not {'channel','chat'} & set(search['properties']['types']['items']['enum'])
    assert 'roomMode' not in search['properties']
    assert generation_tools(TOOLS,{'sourceKind':'chat'},{})==TOOLS
    assert generation_tools(TOOLS,{'sourceKind':'manual'},{'selectedReferences':[{'kind':'chat'}]})==TOOLS


def test_legacy_chat_context_is_not_inherited_by_next_default_request(application):
    from onlinecoc_ai.context import source
    app=application;enable(app.host,public=True,private=True,kp=True)
    message=add_message(app.host,'kp','旧版默认收集的普通聊天')
    original=Context(app.proposals,demand=True);capture=original.capture
    def legacy(account,request):
        snapshot,payload=capture(account,request)
        snapshot[0]['sourceRefs'].append(source('message',message['messageId'],message,'public',channelId='general'))
        payload['roomFacts']['messages'].append(message)
        return snapshot,payload
    original.capture=legacy;app.coordinator.context=original
    async def run():
        s=session(app);r=submit(app,s,'旧版任务')
        async def callback(*_):return completion({'kind':'plan','text':'旧版读过普通聊天的回答'})
        app.coordinator.provider_factory=lambda _:Fake(callback);await app.coordinator.start()
        try:
            task=committed(command(app,'ai.request.dispatch',{'requestId':r['requestId']}));result=await wait_task(app.coordinator,task['taskId']);assert result['status']=='review_ready'
            current=submit(app,s,'新任务只讨论设计，不引用聊天室')
            context=Context(app.proposals,demand=True);snapshot,payload=context.capture('kp',app.repository.state()['requests'][current['requestId']])
            assert not snapshot[0]['facts'].get('historyContexts') and not snapshot[0]['sourceRefs']
            assert not any(row['role']=='assistant' for row in payload['conversationHistory'])
            state=app.host.state();state['chat']['messages']['general'][0].update(text='已编辑',revision=2);app.host.commit(state)
            context.recheck('kp',snapshot)
        finally:await app.coordinator.close()
    asyncio.run(run())


@pytest.mark.parametrize('changed',['value','removed','revoked'])
def test_task_original_request_and_delivered_reply_are_separate_from_source_access(application,changed):
    app=application;s,t=generated(app,'/entities/actor-one')
    before=app.sessions.get('kp',s['sessionId'],delivered=True)['items'][0]
    assert before['sourceState']=='fresh'
    room=app.host.state()
    if changed=='removed':del room['entities']['actor-one']
    elif changed=='revoked':room['members']['kp']['authorizationEpoch']+=1
    else:room['entities']['actor-one']['name']='Changed';room['entities']['actor-one']['revision']+=1
    app.host.commit(room)
    item=app.sessions.get('kp',s['sessionId'],delivered=True)['items'][0]
    assert item['text']==before['text'] and item['initiator']=='kp'
    if changed=='revoked':assert not item.get('response') and item['sourceState']=='denied'
    else:assert item['response']==before['response'] and item['sourceState']=='stale'


def test_public_ruling_delivery_preserves_manual_summary_without_inventing_task(application):
    from onlinecoc_ai.data_queries import DataQueryService
    app=application;enable(app.host,public=True,private=True,kp=True)
    s=session(app);r=submit(app,s,'人工待审方案')
    request=app.repository.state()['requests'][r['requestId']]
    snapshot,_=Context(app.proposals,demand=True).capture('kp',request)
    DataQueryService(app.host).attach('kp','search',{'types':['room'],'query':'/entities/actor-one','limit':1},snapshot,'kp')
    bid=app.batches.create('kp',request,[{'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'人工变更'}}],'人工原始裁决正文',snapshot[0])
    rid='batch:'+bid
    before=next(i for i in app.rulings.list('kp',delivered=True)['items'] if i['rulingId']==rid)
    generation=app.repository.store.generation;app.rulings.list('kp',delivered=True)
    assert app.repository.store.generation==generation
    room=app.host.state();del room['entities']['actor-one'];app.host.commit(room)
    after=next(i for i in app.rulings.list('kp')['items'] if i['rulingId']==rid)
    assert after['summary']==before['summary'] and after['sourceState']=='stale' and not after['canDecide']
    assert not after['actions'] and not app.repository.state()['tasks']
