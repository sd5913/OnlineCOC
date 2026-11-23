"""Technical repair feedback never invents a business decision or executes data."""
import asyncio
import json
import pytest
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.reliability import tool_arguments
from test_entrypoints import application,command,committed
from test_coordinator import setup,Fake,completion,wait_task
from test_access_batches import session,submit,tool_call
from test_context import enable


def test_negative_search_without_evidence_is_repaired(application):
    app=application;enable(app.host,public=True,kp=True)
    app.coordinator.context.demand=True
    for profile in app.coordinator.profiles.values():profile['limits'].update(maxRepairAttempts=2,maxToolRounds=3)
    async def callback(n,messages,tools):
        if n==1:return completion({'kind':'plan','text':'没有找到任何角色记录。'})
        if n==2:
            assert json.loads(messages[-1]['content'])['error']['code']=='MODEL_EVIDENCE_REQUIRED'
            return tool_call('room_search_data',{'types':['entity'],'query':'','limit':10})
        assert json.loads(messages[-1]['content'])['items']
        return completion({'kind':'plan','text':'已经查询到当前角色。'})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback)
        r=submit(app,session(app),'查询角色记录')
        task=committed(command(app,'ai.request.dispatch',{'requestId':r['requestId']}));await app.coordinator.start()
        try:
            result=await wait_task(app.coordinator,task['taskId'])
            assert result['status']=='review_ready' and len(result['calls'])==3,result
            assert not result.get('proposalId') and not result.get('batchId')
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_search_guard_accepts_real_empty_query_and_explicit_failure():
    from onlinecoc_ai.reliability import require_search_evidence
    payload={'dataAccess':{'mode':'demand'}}
    require_search_evidence('查询角色',payload,{'facts':{'dataQueries':[{'count':0}]}},{'kind':'plan','text':'没有找到角色记录'})
    require_search_evidence('查询角色',payload,{'facts':{}},{'kind':'plan','text':'查询没有完成，无法确认记录。'})
    require_search_evidence('我是什么身份',payload,{'facts':{}},{'kind':'plan','text':'你是KP，目前未找到玩家身份。'})
    with pytest.raises(AiError,match='MODEL_EVIDENCE_REQUIRED'):
        require_search_evidence('查询角色',payload,{'facts':{}},{'kind':'plan','text':'未找到角色'})


def test_blocked_draft_cannot_become_ready_by_returning_plan(application):
    app=application;enable(app.host,public=True,kp=True)
    async def callback(n,messages,tools):
        if n==1:return completion({'kind':'draft','text':'Only add a rule','changeSet':{'schemaVersion':1,'configurations':[],'sources':{'extra.lua':'invalid lua'},'data':{},'suggestions':[]}})
        if n==2:assert 'DSL constructor' in messages[-1]['content']
        return completion({'kind':'plan','text':'Unable to repair'})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);s=session(app);request=submit(app,s,'Add one rule')
        task=committed(command(app,'ai.request.dispatch',{'requestId':request['requestId']}));await app.coordinator.start()
        try:
            result=await wait_task(app.coordinator,task['taskId']);assert result['status']=='failed' and result['error']=='MODEL_OUTPUT_INVALID'
            assert app.proposals.get('kp',result['proposalId'])['status']=='blocked'
            assert not app.host.state()['aiControl']['publications']
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_rule_feedback_includes_only_requested_rule_and_transitive_dependencies():
    from onlinecoc_ai.reliability import rule_feedback
    artifact={'revision':'frozen','metadata':{'one':{'dependencies':['helper']},'helper':{'dependencies':[]}},
        'sources':{'one.lua':'return rule("one", {}, function(r) end)','helper.lua':"return rule('helper', {}, function(r) end)",'secret.lua':'return rule("unrelated", {}, function(r) end)'}}
    value=rule_feedback(artifact,{'one'})
    assert set(value['sources'])=={'one.lua','helper.lua'} and value['rulesetRevision']=='frozen'


def test_action_schema_errors_identify_exact_step_and_field(application):
    app=application
    with pytest.raises(AiError) as caught:
        app.batches.validate_actions('kp',[{'target':'host','op':'entity.patch','args':{'id':'actor-one'}}])
    assert caught.value.code=='BATCH_ARGUMENTS_INVALID' and caught.value.path=='/actions/0/args'
    with pytest.raises(AiError) as caught:
        app.batches.validate_actions('kp',[{'target':'host','op':'action.invoke','args':{'actionId':'fixture.check','input':{'actor':'actor-one','item':3}}}])
    assert caught.value.code=='RULE_INPUT_INVALID' and caught.value.path=='/actions/0/args/input/item'


def test_catalog_keeps_whitelist_and_declares_atomic_scope_before_generation(application):
    app=application
    for catalog in (app.batches.catalog('kp'),app.batches.catalog_query('kp'),app.batches.catalog_query('kp',['flow.respond','ai.memory.confirm'])):
        scopes=catalog['executionScopes']
        assert len(scopes['host.room.atomic.v1']['operations'])==21
        assert len(scopes['ai.store.atomic.v1']['operations'])==4
        assert scopes['host.memory.single.v1']['singleActionOnly']
        assert set(scopes['unsupportedHostOperations'])=={'flow.respond','flow.retry','flow.cancel','member.add'}
    full=app.batches.catalog('kp');assert len(full['host'])==25 and len(full['ai'])==6


@pytest.mark.parametrize('bad',['{','[]','{"limit":0}','{"unexpected":true}'])
def test_tool_json_and_schema_are_feedback_not_execution(bad):
    schema={'type':'object','properties':{'limit':{'type':'integer','minimum':1}},'additionalProperties':False}
    with pytest.raises(AiError,match='TOOL_ARGUMENTS_INVALID|INPUT_INVALID'):tool_arguments(bad,schema)


@pytest.mark.parametrize('raw',['{','{"section":"invalid"}'])
def test_bad_tool_arguments_repair_with_declared_schema_without_user_question(application,raw):
    app=application;enable(app.host,public=True,kp=True)
    for profile in app.coordinator.profiles.values():profile['limits'].update(maxRepairAttempts=2,maxToolRounds=4)
    async def callback(n,messages,tools):
        if n==1:
            value=tool_call('room_read_management',{});value.message['tool_calls'][0]['function']['arguments']=raw;return value
        if n==2:
            feedback=json.loads(messages[-1]['content']);assert feedback['error']['code']==('TOOL_ARGUMENTS_INVALID' if raw=='{' else 'INPUT_INVALID')
            assert feedback['schema']['properties']['section']['enum']
            return tool_call('room_read_management',{'section':'configurations'})
        assert 'items' in json.loads(messages[-1]['content'])
        return completion({'kind':'plan','text':'查询已完成，无需用户修正技术参数。'})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);s=session(app);request=submit(app,s,'查询配置目录')
        dispatched=committed(command(app,'ai.request.dispatch',{'requestId':request['requestId']}));await app.coordinator.start()
        try:
            result=await wait_task(app.coordinator,dispatched['taskId']);assert result['status']=='review_ready',result
            assert len(result['calls'])==3 and not result.get('choices')
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_billable_malformed_tool_arguments_reach_coordinator():
    import httpx
    from test_providers import call,response
    def handler(_):
        value=response(None);value['choices'][0].update(finish_reason='tool_calls',message={'role':'assistant','content':None,
            'tool_calls':[{'id':'invalid','type':'function','function':{'name':'room_read_management','arguments':'{'}}]})
        return httpx.Response(200,json=value)
    result=call(handler)
    assert result.usage['total_tokens']==20 and result.message['tool_calls'][0]['function']['arguments']=='{'


def test_tool_repairs_stop_at_two_and_do_not_ask_business_question(application):
    app=application;enable(app.host,public=True,kp=True)
    for profile in app.coordinator.profiles.values():profile['limits'].update(maxRepairAttempts=2,maxToolRounds=8)
    async def callback(*_):return tool_call('room_read_management',{'section':'invalid'})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);s=session(app);request=submit(app,s,'查询配置目录')
        dispatched=committed(command(app,'ai.request.dispatch',{'requestId':request['requestId']}));await app.coordinator.start()
        try:
            result=await wait_task(app.coordinator,dispatched['taskId']);assert result['status']=='failed',result
            assert result['error']=='MODEL_TOOL_REPAIR_LIMIT' and len(result['calls'])==3
            assert not result.get('choices') and not result.get('batchId')
        finally:await app.coordinator.close()
    asyncio.run(run())
