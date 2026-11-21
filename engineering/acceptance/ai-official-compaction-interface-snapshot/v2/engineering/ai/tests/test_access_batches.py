"""Room session ceilings, automatic player dispatch, and reviewed execution batches."""
import asyncio
import copy
import pytest
from onlinecoc_ai.errors import AiError
from onlinecoc.errors import DomainError
from onlinecoc_ai.context import Context
from onlinecoc_ai.data_queries import DataQueryService
from test_entrypoints import application, command, committed
from test_coordinator import setup, Fake, completion, wait_task
from test_context import enable
from onlinecoc_ai.contracts import canonical, digest, loads
from onlinecoc_ai.providers.base import Completion


def tool_call(name,args=None):
    value={'role':'assistant','content':None,'tool_calls':[{'id':'read','type':'function',
        'function':{'name':name,'arguments':canonical(args or {}).decode()}}]}
    return Completion(value,{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20},'tool_calls',digest(value))


def access(app, players=True, auto=False):
    return committed(command(app,'ai.access.update',{'revision':app.sessions.access('kp')['revision'],
        'allowPlayerChat':players,'autoApproveBatches':auto}))


def session(app, who='kp', **extra):
    return committed(command(app,'ai.session.create',{'title':'权限验收',**extra},who))


def submit(app,s,text='请查询已知资料',who='kp'):
    return committed(command(app,'ai.session.submit',{'sessionId':s['sessionId'],'text':text},who))


def test_defaults_binding_and_no_permission_escalation(application):
    app=application
    assert app.sessions.access('player1')['canChat'] is False
    assert command(app,'ai.session.create',{'title':'禁止'},'player1')['code']=='PLAYER_AI_DISABLED'
    assert command(app,'ai.request.create',{'sourceKind':'manual','text':'绕过'},'player1')['code']=='PLAYER_AI_DISABLED'
    admin=session(app);assert admin['accessLevel']=='administrator' and admin['owner']=='kp'
    assert session(app,accessLevel='player')['accessLevel']=='player'
    access(app)
    assert command(app,'ai.session.create',{'title':'提权','accessLevel':'administrator'},'player1')['code']=='PERMISSION_DENIED'
    own=session(app,'player1');other=session(app,'player2')
    assert own['owner']=='player1' and own['accessLevel']=='player'
    assert len(app.sessions.list('kp')['items'])==4
    assert [s['sessionId'] for s in app.sessions.list('player1')['items']]==[own['sessionId']]
    with pytest.raises(AiError,match='NOT_VISIBLE'):app.sessions.get('player1',other['sessionId'])
    assert command(app,'ai.session.submit',{'sessionId':own['sessionId'],'text':'不能冒充'},'kp')['code']=='SESSION_OWNER_REQUIRED'
    saved=committed(command(app,'ai.session.update',{'sessionId':own['sessionId'],'revision':1,'title':'KP 整理'}))
    assert saved['owner']=='player1'
    for extra in ({'owner':'kp'},{'accessLevel':'administrator'}):
        with pytest.raises(AiError,match='INPUT_INVALID'):command(app,'ai.session.update',{'sessionId':own['sessionId'],'revision':2,**extra},'player1')


def test_player_auto_dispatch_context_output_and_revoke(application):
    from test_known_runtime import install
    install(application)
    app=application;access(app);enable(app.host,public=True,private=True,kp=True)
    room=app.host.state();room['entities']['actor-one']['metadata']['secret']='NEVER_PLAYER_SECRET';app.host.commit(room)
    async def callback(count,messages,tools):
        assert 'NEVER_PLAYER_SECRET' not in str(messages)
        assert 'room_manage_catalog' not in str(tools)
        return completion({'kind':'known','evidence':[],'next':'none'})
    async def run():
        app.coordinator.provider_factory=lambda p:Fake(callback);await app.coordinator.start()
        try:
            s=session(app,'player1');r=submit(app,s,who='player1');assert r.get('taskId'),r
            task=await wait_task(app.coordinator,r['taskId']);assert task['status']=='review_ready',task
            result=app.sessions.get('player1',s['sessionId'])['items'][0]
            assert '暂未获得与问题匹配的本人已知资料' in result['response'] and 'diagnostics' not in result
            assert app.sessions.get('kp',s['sessionId'])['items'][0]['response']==result['response']
            context=app.repository.state()['contexts'][task['contextRef']]
            assert context['facts']['sessionAccess']['owner']=='player1'
            access(app,False)
            with pytest.raises(AiError,match='PLAYER_AI_DISABLED'):app.sessions.get('player1',s['sessionId'])
            assert command(app,'ai.session.submit',{'sessionId':s['sessionId'],'text':'停止后提交'},'player1')['code']=='PLAYER_AI_DISABLED'
            assert app.sessions.get('kp',s['sessionId'])['items'][0]['status']=='stale'
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_kp_player_session_has_player_ceiling_and_data_proof(application):
    from test_known_runtime import install
    from onlinecoc_ai.knowledge import attach
    install(application)
    app=application;enable(app.host,public=True,private=True,kp=True)
    s=session(app,accessLevel='player');r=submit(app,s)
    assert r.get('taskId'),r
    request=app.repository.state()['requests'][r['requestId']]
    snapshot,payload=Context(app.proposals).capture('kp',request)
    assert 'rules' not in payload and 'roomFacts' not in payload
    query=attach(app.host,snapshot[0],'room_search_knowledge',{'limit':50},{})
    assert all(item['visibility']!='kp' for item in query['items'])
    assert snapshot[0]['facts']['knowledgeProofs'][0]['accountId']=='kp'
    app.host.validate_ai_sources(app.host.state(),'kp',snapshot[0])


def batch(app,actions=None):
    s=session(app);r=submit(app,s,'修改名称')
    request=app.repository.state()['requests'][r['requestId']]
    snapshot,_=app.coordinator.context.capture('kp',request)
    bid=app.batches.create('kp',request,actions or [{'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'审核后的名称'}}],'改名',snapshot[0])
    return next(b for b in app.batches.list('kp')['items'] if b['batchId']==bid)


def decide(app,b,op='approve',who='kp'):
    return command(app,'ai.batch.'+op,{'batchId':b['batchId'],'digest':b['digest']},who)


def test_batch_human_approval_idempotence_and_player_denial(application):
    app=application;b=batch(app);before=app.host.state()['entities']['actor-one']['name']
    assert before!='审核后的名称' and b['status']=='pending'
    assert decide(app,b,who='player1')['code']=='PERMISSION_DENIED'
    result=committed(decide(app,b));assert result['status']=='completed'
    assert result['receipts'][0]['receipt']['status']=='committed'
    assert app.host.state()['entities']['actor-one']['name']=='审核后的名称'
    assert decide(app,b)['code']=='BATCH_NOT_PENDING'
    assert len([r for r in app.host.state()['commands'].values() if r['id'].startswith('batch-')])==1


def test_batch_stale_reject_auto_and_bypass_forbidden(application):
    app=application;b=batch(app)
    room=app.host.state();room['entities']['actor-one']['name']='外部修改';app.host.commit(room)
    assert decide(app,b)['code']=='BATCH_STALE'
    assert committed(decide(app,b,'reject'))['status']=='rejected'
    access(app,auto=True);b=batch(app);assert b['status']=='completed'
    for op in ('configuration.put','rule.activate','publication.apply'):
        with pytest.raises(AiError,match='BATCH_OPERATION_FORBIDDEN'):
            app.batches.validate_actions('kp',[{'target':'host','op':op,'args':{}}])
    with pytest.raises(AiError,match='BATCH_OPERATION_FORBIDDEN'):
        app.batches.validate_actions('kp',[{'target':'ai','op':'ai.access.update','args':{}}])


def test_batch_unknown_reconciles_without_reexecuting(application):
    app=application;b=batch(app);original=app.host.execute_batch;count=[]
    def lost(*args,**kwargs):
        result=original(*args,**kwargs);count.append(result);raise OSError('simulated response loss')
    app.host.execute_batch=lost
    try:assert committed(decide(app,b))['status']=='completed'
    finally:app.host.execute_batch=original
    assert decide(app,b,'reconcile')['code']=='BATCH_NOT_UNCERTAIN'
    assert len(count)==1


def test_preflight_blocks_bad_middle_step_without_any_business_writes(application,tmp_path):
    from onlinecoc_ai.repository import Repository
    app=application;before=app.host.state();b=batch(app,[
        {'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'第一步已完成'}},
        {'target':'host','op':'entity.patch','args':{'id':'missing-entity','name':'失败项'}},
        {'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'不可执行的第三步'}}])
    assert b['status']=='blocked' and b['preflight']['items'][1]['status']=='blocked'
    assert decide(app,b)['code']=='BATCH_NOT_PENDING'
    assert app.host.state()==before and not b['receipts']
    assert decide(app,b,'reconcile')['code']=='BATCH_NOT_UNCERTAIN'
    state=app.repository.state()
    path=tmp_path/'batch-restart';repo=Repository(path,state['scopeId']);repo.commit(state);repo.close()
    reopened=Repository(path,state['scopeId'])
    try:
        recovered=reopened.state()['settings']['batches'][b['batchId']]
        assert recovered['status']=='blocked' and recovered['receipts']==[] and recovered['digest']==b['digest']
    finally:reopened.close()


def test_delete_cancels_queue_hides_session_and_keeps_usage_audit(application):
    app=application;s=session(app);r=submit(app,s)
    task=committed(command(app,'ai.request.dispatch',{'requestId':r['requestId']}))
    revision=app.sessions.get('kp',s['sessionId'])['session']['revision']
    deleted=committed(command(app,'ai.session.delete',{'sessionId':s['sessionId'],'revision':revision},identifier='delete-once'))
    assert deleted['deleted'] and not app.sessions.list('kp')['items'] and not app.sessions.list('kp',True)['items']
    assert app.repository.state()['tasks'][task['taskId']]['status']=='cancelled'
    assert r['requestId'] in app.repository.state()['requests']
    assert app.receipt('kp','delete-once')['result']['deleted']
    with pytest.raises(AiError,match='NOT_VISIBLE'):app.sessions.get('kp',s['sessionId'])
    assert not app.tasks('kp')['items']


def test_administrator_tools_respect_external_scope(application):
    app=application
    async def callback(*unused):return tool_call('room_read_sessions')
    async def run():
        app.coordinator.provider_factory=lambda p:Fake(callback);await app.coordinator.start()
        try:
            r=submit(app,session(app));task=committed(command(app,'ai.request.dispatch',{'requestId':r['requestId']}))
            result=await wait_task(app.coordinator,task['taskId'])
            assert result['status']=='failed' and result['error']=='EXTERNAL_SCOPE_DISABLED',result
            assert not app.batches.list('kp')['items']
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_player_contract_tool_and_batch_output_cannot_escalate(application):
    from test_known_runtime import install
    install(application)
    app=application;access(app);enable(app.host,public=True,private=True,kp=True)
    async def callback(count,messages,tools):
        if count==1:return tool_call('pack_read_contract')
        if count==2:
            contract=loads(messages[-1]['content'].encode())
            assert all(s['visibility']=='public' for s in contract['sources'])
        return completion({'kind':'batch','text':'尝试提权','actions':[{'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'不应生效'}}]})
    async def run():
        app.coordinator.provider_factory=lambda p:Fake(callback);await app.coordinator.start()
        try:
            task=submit(app,session(app,'player1'),who='player1')
            result=await wait_task(app.coordinator,task['taskId'])
            assert result['status']=='failed' and result['error']=='TOOL_FORBIDDEN',result
            assert app.host.state()['entities']['actor-one']['name']!='不应生效'
            assert not app.batches.list('kp')['items']
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_delete_interrupts_active_generation(application):
    app=application
    async def run():
        entered=asyncio.Event();cancelled=asyncio.Event()
        async def callback(*unused):
            entered.set()
            try:await asyncio.Event().wait()
            finally:cancelled.set()
        app.coordinator.provider_factory=lambda p:Fake(callback);await app.coordinator.start()
        try:
            s=session(app);r=submit(app,s);t=committed(command(app,'ai.request.dispatch',{'requestId':r['requestId']}))
            await asyncio.wait_for(entered.wait(),5)
            current=app.sessions.get('kp',s['sessionId'])['session']
            committed(command(app,'ai.session.delete',{'sessionId':s['sessionId'],'revision':current['revision']}))
            await asyncio.wait_for(cancelled.wait(),5)
            assert (await wait_task(app.coordinator,t['taskId']))['status']=='cancelled'
            assert not app.sessions.list('kp')['items']
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_management_catalog_is_bounded_and_schema_complete(application):
    app=application;catalog=app.batches.catalog('kp')
    assert len(canonical(catalog))<64*1024
    app.batches.validate_actions('kp',[{'target':'ai','op':'ai.session.create','args':{'title':'批次创建','accessLevel':'player'}}])
    first=app.batches.read('kp','members',limit=1)
    second=app.batches.read('kp','members',offset=first['nextOffset'],limit=1)
    assert first['snapshot']==second['snapshot'] and first['items'][0]['id']!=second['items'][0]['id']


def test_other_administrator_can_inspect_draft_without_taking_review_identity(application):
    from test_entrypoints import delta
    app=application
    state=app.host.state();state['members']['player2']['role']='kp';app.host.commit(state)
    p=committed(command(app,'ai.draft.create',{'text':'人工草稿','changeSet':delta()}))
    assert app.proposal('player2',p['proposalId'])['proposal']==p
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):app.proposal('player1',p['proposalId'])
    assert command(app,'ai.proposal.validate',{'proposalId':p['proposalId'],'revision':1},'player2')['code']=='PERMISSION_DENIED'


def test_player_history_rechecks_package_evidence_during_generation(application):
    from test_known_runtime import install,observe,host_call
    install(application);grant=observe(application)
    app=application;access(app);enable(app.host,public=True,private=True,kp=True)
    class Evidence:
        kinds=('event',)
        value='已知事件'
        def read(self,room,account):
            return [{'sourceId':'fixture','kind':'event','id':'event-one','revision':digest(self.value),
                'label':'事件','data':{'text':self.value},'visibility':'private'}]
    adapter=Evidence();app.host.ai_data_adapter=adapter
    async def callback(count,messages,tools):
        payload=loads(messages[1]['content'].encode())
        if any(turn['role']=='assistant' for turn in payload['conversationHistory']):
            host_call(app,'knowledge.revoke',{'grantId':grant['grantId'],'expectedRevision':1,'reason':'历史来源撤回'})
            return completion({'kind':'known','evidence':[],'next':'none'})
        if count==1:return tool_call('room_search_knowledge',{})
        return completion({'kind':'known','evidence':[],'next':'none'})
    async def run():
        app.coordinator.provider_factory=lambda p:Fake(callback);await app.coordinator.start()
        try:
            s=session(app,'player1');one=submit(app,s,who='player1')
            assert (await wait_task(app.coordinator,one['taskId']))['status']=='review_ready'
            two=submit(app,s,'继续解释经历',who='player1');result=await wait_task(app.coordinator,two['taskId'])
            assert result['status']=='failed' and result['error']=='NOT_VISIBLE',result
            assert '不应返回' not in str(app.sessions.get('player1',s['sessionId']))
        finally:await app.coordinator.close()
    asyncio.run(run())
