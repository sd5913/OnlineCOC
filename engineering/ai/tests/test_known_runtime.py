"""A1 integration: two-account, immutable evidence and actual provider payloads."""
import asyncio
import copy
import json
import uuid
import pytest
from onlinecoc.knowledge import HostStateProvider
from onlinecoc_ai.context import Context
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.references import References
from onlinecoc_ai.known_answers import reference_token
from test_entrypoints import application, command, committed, host_command
from test_coordinator import setup, Fake, completion, wait_task
from test_access_batches import access, session, submit, tool_call
from test_context import enable


def host_call(app,op,args):return committed(host_command(app,op,args,uuid.uuid4().hex))


def install(app):
    import runpy
    from pathlib import Path
    example=runpy.run_path(str(Path(__file__).parents[1]/'examples/knowledge-investigation.py'))
    d=example['install'](app.host)
    host_call(app,'knowledge.policy.bind',{'policyId':d['policyId'],'descriptorDigest':d['descriptorDigest'],'expectedRevision':0})
    access(app);enable(app.host,public=True,private=True,kp=True)
    return d


def observe(app,owner='player1',entity='actor-one'):
    room=app.host.state()
    return host_call(app,'knowledge.observe',{'policyId':'personal-test','expectedPolicyRevision':1,
        'subjectMemberId':room['members'][owner]['memberId'],
        'resource':{'namespace':'witness','kind':'entity','id':entity},'facetIds':['identity'],
        'reason':'明确向本人揭示','expectedSourceRevision':str(room['entities'][entity]['revision'])})


def test_unconfigured_player_never_falls_back_or_calls_model(application):
    app=application;access(app);enable(app.host,public=True,private=True,kp=True)
    result=submit(app,session(app,'player1'),who='player1')
    assert result['dispatchError']=='KNOWLEDGE_UNAVAILABLE' and not result.get('taskId')
    assert app.sessions.access('player1')['knowledge']['status']=='unavailable'
    direct=committed(command(app,'ai.request.create',{'sourceKind':'manual','text':'无绑定会话'},'player1'))
    assert direct['dispatchError']=='KNOWLEDGE_UNAVAILABLE' and direct.get('sessionId')


def test_initial_context_contains_no_pack_guide_world_or_old_model_history(application):
    app=application;install(app);observe(app)
    result=submit(app,session(app,'player1'),who='player1')
    request=app.repository.state()['requests'][result['requestId']]
    snapshot,payload=Context(app.proposals).capture('kp',request)
    assert set(payload)=={'request','selectedReferences','conversationHistory','sessionAccess','authorityNotice','dataAccess'}
    assert snapshot[0]['reviewPrincipal']=='player1' and snapshot[1:]==({}, {})
    assert snapshot[0]['facts']['strictPlayer']
    room=app.host.state();room['entities']['actor-one']['name']='UNKNOWN_FUTURE_NAME';app.host.commit(room)
    Context(app.proposals).recheck('kp',snapshot)
    assert 'UNKNOWN_FUTURE_NAME' not in str(payload)


def test_snapshot_reference_cannot_cross_account_or_follow_world_update(application):
    app=application;install(app);observe(app)
    port=References(app.host);token=port.search('player1','knowledge')['items'][0]['token']
    original=port.resolve('player1',[token])['items'][0]
    room=app.host.state();room['entities']['actor-one']['name']='AFTER_OBSERVATION';app.host.commit(room)
    assert port.resolve('player1',[token])['items'][0]==original
    with pytest.raises(Exception):port.resolve('player2',[token])
    with pytest.raises(AiError):port.search('player1','entity')


def test_model_secret_prose_is_repaired_and_never_stored_or_replayed(application):
    app=application;install(app);grant=observe(app);captured=[]
    async def callback(count,messages,tools):
        captured.append(copy.deepcopy(messages))
        assert 'pack_read_contract' not in str(tools)
        if count==1:return tool_call('room_search_knowledge',{})
        if count==2:
            page=json.loads(messages[-1]['content'])
            return tool_call('room_read_knowledge',{'refs':[page['items'][0]['ref']]})
        if count==3:return completion({'kind':'known','evidence':[],'next':'none','text':'MODEL_INVENTED_SECRET'})
        evidence=next(json.loads(m['content']) for m in messages if m['role']=='tool' and 'evidenceId' in m['content'])
        return completion({'kind':'known','evidence':[evidence['items'][0]['evidenceId']],'next':'ask_kp'})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);await app.coordinator.start()
        try:
            s=session(app,'player1');r=submit(app,s,who='player1')
            task=await wait_task(app.coordinator,r['taskId']);assert task['status']=='needs_input',task
            item=app.sessions.get('player1',s['sessionId'])['items'][0]
            assert '观察记录' in item['response'] and item['choices']['options'][0]['id']=='ask_kp'
            assert 'MODEL_INVENTED_SECRET' not in str(captured)+str(app.repository.state())
            room=app.host.state();room['entities']['actor-one']['name']='HIDDEN_CHANGE';app.host.commit(room)
            assert app.sessions.get('player1',s['sessionId'])['items'][0]['response']==item['response']
            host_call(app,'knowledge.revoke',{'grantId':grant['grantId'],'expectedRevision':1,'reason':'撤回本次披露'})
            stale=app.sessions.get('player1',s['sessionId'])['items'][0]
            assert stale['status']=='stale' and not stale.get('response')
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_inflight_revoke_suppresses_entire_response(application):
    app=application;install(app);grant=observe(app)
    async def callback(count,messages,tools):
        if count==1:return tool_call('room_search_knowledge',{})
        host_call(app,'knowledge.revoke',{'grantId':grant['grantId'],'expectedRevision':1,'reason':'在途撤回'})
        return completion({'kind':'known','evidence':[],'next':'none'})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);await app.coordinator.start()
        try:
            s=session(app,'player1');r=submit(app,s,who='player1');task=await wait_task(app.coordinator,r['taskId'])
            assert task['status']=='failed' and not task.get('text'),task
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_private_export_block_and_kp_player_session_ceiling(application):
    app=application;install(app);observe(app,'kp')
    result=submit(app,session(app,accessLevel='player'))
    snapshot,payload=Context(app.proposals).capture('kp',app.repository.state()['requests'][result['requestId']])
    assert snapshot[0]['facts']['knowledgeProofs'][0]['player'] is True
    enable(app.host,public=True,private=False,kp=True)
    blocked=submit(app,session(app,'player1'),who='player1')
    assert blocked['dispatchError']=='EXTERNAL_SCOPE_DISABLED'


def test_second_package_witness_testimony_stays_personal_and_fixed(application):
    app=application;install(app)
    room=app.host.state();room['entities']['actor-one']['metadata'].update(testimony='当时看见一盏灯',secret='NEVER_DISCLOSED_SOLUTION');app.host.commit(room)
    observe(app);port=app.host.knowledge
    ref=port.search('player1',{})['items'][0]['ref']
    observed=port.read('player1',{'refs':[ref]})['items'][0]
    assert observed['data']['testimony']=='当时看见一盏灯' and 'NEVER_DISCLOSED' not in str(observed)
    assert port.search('player2',{})['items']==[]
    room=app.host.state();room['entities']['actor-one']['metadata']['testimony']='后来改口';app.host.commit(room)
    assert port.read('player1',{'refs':[ref]})['items'][0]==observed


def test_ask_kp_option_is_queued_for_human_without_model_redispatch(application):
    app=application;install(app)
    s=session(app,'player1')
    r=submit(app,s,'请 KP 说明本次问题中允许我获知的信息。',who='player1')
    assert r['awaitingKnowledge'] and not r.get('taskId')
    assert app.sessions.get('kp',s['sessionId'])['items'][0]['status']=='received'
    assert not app.repository.state()['tasks']


@pytest.mark.parametrize('http_status',[200,400])
def test_player_real_adapter_json_mode_and_http_error_projection(application,http_status):
    import httpx
    from onlinecoc_ai.providers import create_provider
    app=application;install(app);observe(app);seen=[]
    def handler(request):
        body=json.loads(request.content);seen.append(body);messages=body['messages']
        assert 'player' in messages[0]['content'] and 'json' in messages[0]['content'].lower()
        assert {t['function']['name'] for t in body['tools']}=={'room_search_knowledge','room_read_knowledge'}
        assert body['response_format']=={'type':'json_object'} and body['thinking']=={'type':'disabled'}
        if http_status==400:return httpx.Response(400,text='SECRET_REMOTE_BODY')
        result=next((json.loads(m['content']) for m in reversed(messages) if m['role']=='tool'),None)
        if result is None:name,args='room_search_knowledge',{}
        elif 'evidenceId' not in result['items'][0]:name,args='room_read_knowledge',{'refs':[result['items'][0]['ref']]}
        else:
            content={'kind':'known','evidence':[result['items'][0]['evidenceId']],'next':'none'}
            message={'role':'assistant','content':json.dumps(content)}
            return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':message}],'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}})
        message={'role':'assistant','content':None,'tool_calls':[{'id':'c'+str(len(seen)),'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}
        return httpx.Response(200,json={'choices':[{'finish_reason':'tool_calls','message':message}],'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}})
    async def run():
        app.coordinator.provider_factory=lambda p:create_provider(p,transport=httpx.MockTransport(handler),credential_loader=lambda _:'offline-key')
        await app.coordinator.start()
        try:
            s=session(app,'player1');r=submit(app,s,who='player1');task=await wait_task(app.coordinator,r['taskId'])
            pl=app.sessions.get('player1',s['sessionId'])['items'][0]
            kp=app.sessions.get('kp',s['sessionId'])['items'][0]
            assert 'diagnostics' not in pl and 'SECRET_REMOTE_BODY' not in str(app.repository.state())
            if http_status==400:
                assert len(seen)==1 and task['error']=='PROVIDER_REQUEST_INVALID'
                assert kp['diagnostics']['errors'][0]['httpStatus']==400
                assert not task['diagnostics']['outputFailures']
            else:
                assert len(seen)==3 and task['status']=='review_ready',task
                assert '观察记录' in pl['response'] and not task['diagnostics']['errors']
        finally:await app.coordinator.close()
    asyncio.run(run())
