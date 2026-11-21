"""Live NPC failures replayed without a provider or mutable package sources."""
import asyncio
import json
import pytest
from onlinecoc.errors import DomainError
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.data_queries import model_result
from test_entrypoints import application, command, committed, delta
from test_coordinator import setup, Fake, completion, wait_task
from test_access_batches import tool_call
from test_context import enable
from test_sessions import submit


@pytest.mark.parametrize('name,args',[
    ('room_manage_catalog',{'operations':['config.create','configuration.create']}),
    ('room_manage_catalog',{'operations':['config.list','configuration.update']}),
    ('room_read_management',{'section':'invented'}),
    ('room_read_management',{'section':'configurations','limit':0}),
    ('room_read_sessions',{'limit':100}),
])
def test_bad_management_query_can_recover_into_checked_unpublished_draft(application,name,args):
    app=application;enable(app.host,public=True,kp=True,private=True)
    async def callback(count,messages,tools):
        if count==1:return tool_call(name,args)
        result=json.loads(messages[-1]['content'])
        if count==2:
            assert result['error']['code']=='INPUT_INVALID'
            assert 'No data was returned' in result['notice']
            return tool_call('room_read_management',{'section':'configurations'})
        assert any(row['id']=='fixture.token' and row['value']['defaults']['bonus']==0 for row in result['items'])
        return completion({'kind':'draft','text':'Checked configuration candidate','changeSet':delta()})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);await app.coordinator.start()
        try:
            sid=committed(command(app,'ai.session.create',{'title':'Management recovery'}))['sessionId']
            req=submit(app,sid,'Prepare a configuration draft')
            dispatched=committed(command(app,'ai.request.dispatch',{'requestId':req['requestId']}))
            task=await wait_task(app.coordinator,dispatched['taskId'])
            assert task['status']=='review_ready',task
            assert next(row for row in task['diagnostics']['toolCalls'] if not row.get('automatic'))['status']=='rejected'
            context=app.repository.state()['contexts'][task['contextRef']]
            assert 'configurations' in context['facts']['managementReads']
            assert not context['facts'].get('consultationOnly')
            row=next(r for r in app.rulings.list('kp')['items'] if r['rulingId']=='proposal:'+task['proposalId'])
            assert row['status']=='pending' and row['canDecide']
            assert app.host.state()['configurations']['fixture.token']['defaults']['bonus']==0
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_authoritative_templates_are_paginated_kp_only_and_changes_invalidate_proof(application):
    app=application;enable(app.host,public=True,kp=True)
    first=app.batches.read('kp','configurations',limit=1)
    assert len(first['items'])==1 and first['nextOffset']==1
    second=app.batches.read('kp','configurations',offset=1,limit=1)
    assert first['snapshot']==second['snapshot'] and first['items'][0]['id']!=second['items'][0]['id']
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):app.batches.read('player1','configurations')
    sid=committed(command(app,'ai.session.create',{'title':'Template proof'}))['sessionId']
    req=submit(app,sid,'Read current templates');request=app.repository.state()['requests'][req['requestId']]
    snapshot,_=app.coordinator.context.capture('kp',request)
    snapshot[0]['facts']['managementReads']={'configurations':first['snapshot']}
    app.host.validate_ai_sources(app.host.state(),'kp',snapshot[0])
    state=app.host.state();state['configurations']['fixture.token']['defaults']['bonus']=5;app.host.commit(state)
    with pytest.raises(AiError,match='SOURCE_STALE'):app.host.validate_ai_sources(app.host.state(),'kp',snapshot[0])


def test_configuration_read_cannot_recover_from_disabled_external_scope(application):
    app=application;enable(app.host,public=True,kp=False)
    async def callback(count,*_):
        assert count==1
        return tool_call('room_read_management',{'section':'configurations'})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);await app.coordinator.start()
        try:
            sid=committed(command(app,'ai.session.create',{'title':'Scope protection'}))['sessionId']
            req=submit(app,sid,'Read current templates');task=committed(command(app,'ai.request.dispatch',{'requestId':req['requestId']}))
            result=await wait_task(app.coordinator,task['taskId'])
            assert result['status']=='failed' and result['error']=='EXTERNAL_SCOPE_DISABLED'
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_mixed_search_warns_model_without_relabeling_or_removing_evidence():
    rows=[{'ref':{'sourceId':'host','kind':'config'}},{'ref':{'sourceId':'stumpsville','kind':'config'}}]
    page={'items':rows,'page':{'nextCursor':None}}
    result=model_result(page,{'types':['config']})
    assert result['sourcePolicy']['publication']=='requires-kp-source-review'
    assert result['items']==rows and page['items']==rows
    assert model_result({'items':rows[:1],'page':{'nextCursor':None}},{})['sourcePolicy']['publication']=='host-evidence'
