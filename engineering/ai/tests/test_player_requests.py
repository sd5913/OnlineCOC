"""PL intent workflow and known-index retrieval without public-room fallback."""
import asyncio
import copy
import json
import pytest
from onlinecoc_ai.context import Context
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.repository import Repository
from onlinecoc_ai import knowledge
from test_entrypoints import application, command, committed
from test_coordinator import setup, Fake, completion, wait_task
from test_access_batches import access, session, submit, tool_call
from test_known_runtime import install, observe
from test_context import enable


def create(app, text='我想用火把给针剑附魔', **extra):
    access(app);s=session(app,'player1')
    r=committed(command(app,'ai.player.request',{'sessionId':s['sessionId'],'text':text,**extra},'player1'))
    return s,r


def decide(app,request,decision='approve',who='kp'):
    return command(app,'ai.ruling.decide',{'rulingId':request['rulingId'],'digest':request['digest'],'decision':decision},who)


def test_direct_intent_requires_no_provider_knowledge_or_egress_and_is_deduplicated(application):
    app=application;s,r=create(app)
    assert not app.repository.state()['tasks'] and not app.repository.state()['settings'].get('knowledgeRequests')
    assert r['status']=='pending' and set(r)=={'rulingId','sessionId','requestId','status','createdAt','digest'}
    assert app.sessions.get('player1',s['sessionId'])['items'][0]['playerRequest']==r
    assert committed(command(app,'ai.player.request',{'sessionId':s['sessionId'],'requestId':r['requestId']},'player1'))==r
    assert len(app.rulings.list('kp')['items'])==1
    assert app.sessions.access('player1')['allowPlayerRequests'] is True
    assert 'allowPlayerRequests' not in app.repository.state()['settings']['accessPolicy'] or app.repository.state()['settings']['accessPolicy']['allowPlayerRequests'] is True


def test_intent_owner_level_policy_and_input_cannot_be_forged(application):
    app=application;s,r=create(app)
    assert command(app,'ai.player.request',{'sessionId':s['sessionId'],'requestId':r['requestId']},'player2')['code']=='NOT_VISIBLE'
    assert command(app,'ai.player.request',{'sessionId':s['sessionId'],'text':'冒充'},'kp')['code']=='PERMISSION_DENIED'
    assert command(app,'ai.player.request',{'sessionId':session(app)['sessionId'],'text':'错误等级'})['code']=='PERMISSION_DENIED'
    assert decide(app,r,who='player1')['code']=='PERMISSION_DENIED'
    with pytest.raises(AiError,match='INPUT_INVALID'):command(app,'ai.player.request',{'sessionId':s['sessionId'],'text':'x','requestId':r['requestId']},'player1')
    p=app.sessions.access('kp');committed(command(app,'ai.access.update',{'revision':p['revision'],'allowPlayerChat':True,'autoApproveBatches':False,'allowPlayerRequests':False}))
    assert command(app,'ai.player.request',{'sessionId':s['sessionId'],'text':'新申请'},'player1')['code']=='PLAYER_REQUESTS_DISABLED'
    assert decide(app,r)['code']=='PERMISSION_DENIED'
    access(app,players=False)
    assert command(app,'ai.player.request',{'sessionId':s['sessionId'],'text':'关闭后'},'player1')['status']=='rejected'


def test_cancelled_and_deleted_intents_cannot_be_accepted(application):
    app=application;s,r=create(app)
    committed(command(app,'ai.request.cancel',{'requestId':r['requestId']},'player1'))
    assert decide(app,r)['code']=='RULING_NOT_READY'
    assert app.sessions.get('player1',s['sessionId'])['items'][0]['playerRequest']['status']=='cancelled'
    s2,r2=create(app)
    fresh=app.sessions.get('player1',s2['sessionId'])['session']
    committed(command(app,'ai.session.delete',{'sessionId':s2['sessionId'],'revision':fresh['revision']},'player1'))
    assert decide(app,r2)['code']=='RULING_NOT_READY'


def test_kp_accept_creates_private_review_once_without_state_changes(application):
    app=application;s,r=create(app);before=copy.deepcopy(app.host.state()['entities'])
    item=committed(decide(app,r));assert item['status']=='accepted' and item['reviewSessionId']!=s['sessionId']
    assert committed(decide(app,r))['reviewSessionId']==item['reviewSessionId']
    assert app.host.state()['entities']==before
    review=app.sessions.get('kp',item['reviewSessionId']);assert review['session']['owner']=='kp' and review['session']['accessLevel']=='administrator'
    with pytest.raises(AiError,match='NOT_VISIBLE'):app.sessions.get('player1',item['reviewSessionId'])
    shown=app.sessions.get('player1',s['sessionId'])['items'][0]['playerRequest']
    assert shown['status']=='accepted' and not any(k in shown for k in ('summary','reviewSessionId','reviewRequestId','reviewTaskId','generationError'))
    state=app.repository.state();app.repository.verify(state)
    bad=copy.deepcopy(state);bad['settings']['playerRequests'][r['rulingId']]['summary']='伪造'
    with pytest.raises(AiError,match='PLAYER_REQUEST_STATE_INVALID'):app.repository.verify(bad)


def test_kp_reject_and_archive_do_not_create_review(application):
    app=application;s,r=create(app)
    assert committed(decide(app,r,'reject'))['status']=='rejected'
    assert committed(decide(app,r))['status']=='rejected'
    fresh=app.sessions.get('player1',s['sessionId'])['session']
    committed(command(app,'ai.session.update',{'sessionId':s['sessionId'],'revision':fresh['revision'],'archived':True},'player1'))
    assert command(app,'ai.player.request',{'sessionId':s['sessionId'],'text':'新申请'},'player1')['code']=='SESSION_ARCHIVED'
    assert len(app.repository.state()['settings']['sessions'])==1


def test_accepted_request_batch_remains_manual_with_auto_approval_enabled(application):
    app=application;s,r=create(app);access(app,auto=True)
    item=committed(decide(app,r));request=app.repository.state()['requests'][item['reviewRequestId']]
    snapshot,_=Context(app.proposals).capture('kp',request)
    before=app.host.state()['entities']['actor-one']['name']
    bid=app.batches.create('kp',request,[{'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'手动批准后'}}],'修改名称',snapshot[0])
    batch=app.repository.state()['settings']['batches'][bid]
    assert batch['status']=='pending' and app.host.state()['entities']['actor-one']['name']==before
    result=committed(command(app,'ai.ruling.decide',{'rulingId':'batch:'+bid,'digest':batch['digest'],'decision':'approve'}))
    assert result['status']=='completed' and app.host.state()['entities']['actor-one']['name']=='手动批准后'


@pytest.mark.parametrize('block,code',[('unconfigured','KNOWLEDGE_UNAVAILABLE'),('private','EXTERNAL_SCOPE_DISABLED'),('queries','DATA_QUERIES_DISABLED'),('egress','KNOWLEDGE_EGRESS_DISABLED')])
def test_query_blockers_have_distinct_safe_errors_without_model_calls(application,monkeypatch,block,code):
    app=application
    if block=='unconfigured':access(app);enable(app.host,public=True,private=True,kp=True)
    else:install(app)
    if block=='private':enable(app.host,public=True,private=False,kp=True)
    if block=='queries':
        p=app.sessions.access('kp');committed(command(app,'ai.access.update',{'revision':p['revision'],'allowPlayerChat':True,'autoApproveBatches':False,'allowDataQueries':False}))
    if block=='egress':
        from onlinecoc.errors import DomainError
        def denied(*a,**kw):raise DomainError('PERMISSION_DENIED')
        monkeypatch.setattr(app.host.knowledge,'require_egress',denied)
    s=session(app,'player1');r=submit(app,s,who='player1');assert r['dispatchError']==code and not r.get('taskId')
    item=app.sessions.get('player1',s['sessionId'])['items'][0];assert item['error']==code and 'diagnostics' not in item
    assert app.sessions.access('player1')['knowledge']['code']==code
    # Business intent is independent, including while query service is unavailable.
    assert committed(command(app,'ai.player.request',{'sessionId':s['sessionId'],'text':'创作需求'},'player1'))['status']=='pending'


def test_keyword_miss_returns_explicit_personal_index_and_never_other_players(application):
    app=application;install(app);observe(app)
    r=submit(app,session(app,'player1'),who='player1');snap,_=Context(app.proposals).capture('kp',app.repository.state()['requests'][r['requestId']])
    page=knowledge.attach(app.host,snap[0],'room_search_knowledge',{'query':'组合火把与针剑'}, {})
    assert page['fallback']=='personal-index' and page['queryMatch']=='none' and page['items']
    assert all('data' not in item for item in page['items'])
    app.coordinator.context.recheck('kp',snap)
    r2=submit(app,session(app,'player2'),who='player2');snap2,_=Context(app.proposals).capture('kp',app.repository.state()['requests'][r2['requestId']])
    assert not knowledge.attach(app.host,snap2[0],'room_search_knowledge',{'query':'组合火把与针剑'}, {})['items']


def test_preloaded_known_index_can_be_read_and_creative_choice_is_not_auto_submitted(application):
    app=application;install(app);observe(app)
    async def callback(count,messages,tools):
        if count==1:
            payload=json.loads(messages[1]['content']);assert payload['knownIndex']['items'] and 'configurations' not in payload
            return tool_call('room_read_knowledge',{'refs':[payload['knownIndex']['items'][0]['ref']]})
        value=json.loads(messages[-1]['content']);return completion({'kind':'known','evidence':[value['items'][0]['evidenceId']],'next':'ask_kp_change'})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);await app.coordinator.start()
        try:
            s=session(app,'player1');r=submit(app,s,'我想组合火把与针剑',who='player1');task=await wait_task(app.coordinator,r['taskId'])
            assert task['status']=='needs_input',task
            assert task['choices']['options'][0]['id']=='ask_kp_change'
            assert '观察记录' in task['text']
            assert not app.repository.state()['settings'].get('playerRequests')
            assert task['diagnostics']['toolCalls'][0]['hasQuery'] is False
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_recoverable_invalid_knowledge_query_can_retry_then_read_index(application):
    app=application;install(app);observe(app)
    async def callback(count,messages,tools):
        if count==1:return tool_call('room_read_knowledge',{'refs':[]})
        if count==2:
            assert json.loads(messages[-1]['content'])['error']['code']=='INPUT_INVALID'
            payload=json.loads(messages[1]['content'])
            return tool_call('room_read_knowledge',{'refs':[payload['knownIndex']['items'][0]['ref']]})
        value=json.loads(messages[-1]['content']);return completion({'kind':'known','evidence':[value['items'][0]['evidenceId']],'next':'none'})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);await app.coordinator.start()
        try:
            r=submit(app,session(app,'player1'),who='player1');task=await wait_task(app.coordinator,r['taskId'])
            assert task['status']=='review_ready',task
            assert task['diagnostics']['toolCalls'][1]['status']=='rejected'
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_player_request_reference_is_label_only_in_kp_review(application):
    from onlinecoc_ai.references import References
    app=application;install(app);observe(app)
    token=References(app.host).search('player1','knowledge')['items'][0]['token']
    s,r=create(app,text='我想改造 '+token);result=committed(decide(app,r))
    review=app.sessions.get('kp',result['reviewSessionId'])['items'][0]
    assert '玩家引用' in review['text'] and '[[knowledge:' not in review['text']
    assert app.sessions.get('player1',s['sessionId'])['items'][0]['text'].endswith(token)


def test_ordinary_configuration_from_player_review_cannot_auto_publish(application):
    from onlinecoc_ai.validation.common import validator_digest
    app=application;pack=app.proposals.pack
    pack.contract['extensionPoints'].append({'namespace':'ordinary.','typeRefs':['actor'],'allowedPaths':['/defaults'],'allowExistingIds':[],'rulePrefixes':[]})
    app.host.register_ai(app.proposals.prepared,{'contract':pack.contract,'digest':pack.digest,'validatorSetDigest':validator_digest()})
    s,r=create(app);p=app.sessions.access('kp')
    committed(command(app,'ai.access.update',{'revision':p['revision'],'allowPlayerChat':True,'autoApproveBatches':True,'autoApproveConfigurations':True}))
    accepted=committed(decide(app,r));request=app.repository.state()['requests'][accepted['reviewRequestId']]
    snapshot,_=Context(app.proposals).capture('kp',request)
    original=next(c for c in app.host.state()['configurations'].values() if c['typeRef']=='actor')
    value={**copy.deepcopy(original),'configurationId':'ordinary.actor','revision':'1'}
    change={'schemaVersion':1,'configurations':[{'kind':'add','id':value['configurationId'],'expectedRevision':None,'value':value}],'sources':{},'data':{},'suggestions':[]}
    proposal=app.proposals.create('kp',request['text'],change,snapshot=snapshot,request=request)
    committed(command(app,'ai.proposal.validate',{'proposalId':proposal['proposalId'],'revision':1}))
    item=next(i for i in app.rulings.list('kp')['items'] if i['kind']=='configuration')
    assert not item['highRisk'] and item['status']=='pending'
    assert not app.host.state()['aiControl']['publications']


def test_restart_preserves_accepted_review_without_duplicate_dispatch(application,tmp_path):
    app=application;s,r=create(app);accepted=committed(decide(app,r));state=app.repository.state()
    with_repository=Repository(tmp_path/'copy-ai',state['scopeId'])
    try:with_repository.commit(state)
    finally:with_repository.close()
    reopened=Repository(tmp_path/'copy-ai',state['scopeId'])
    try:
        record=reopened.state()['settings']['playerRequests'][r['rulingId']]
        assert record['status']=='accepted' and record['reviewSessionId']==accepted['reviewSessionId']
        assert len(reopened.state()['settings']['playerRequests'])==1
    finally:reopened.close()


def test_cancelled_query_failure_keeps_cancelled_status(application):
    app=application;access(app);s=session(app,'player1');r=submit(app,s,who='player1')
    assert r['dispatchError']=='KNOWLEDGE_UNAVAILABLE'
    committed(command(app,'ai.request.cancel',{'requestId':r['requestId']},'player1'))
    assert app.sessions.get('player1',s['sessionId'])['items'][0]['status']=='cancelled'


def test_review_context_identifies_original_player_for_my_character_intent(application):
    app=application;s,r=create(app,text='请为我的角色设计一件新道具')
    captured=[]
    async def callback(count,messages,tools):
        payload=json.loads(messages[1]['content']);captured.append(payload)
        assert payload['playerRequestReview']['requestedBy']=='player1'
        assert payload['sessionAccess']['level']=='administrator'
        return completion({'kind':'plan','text':'为申请人的角色准备道具方案。'})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);await app.coordinator.start()
        try:
            result=committed(decide(app,r));task=await wait_task(app.coordinator,result['reviewTaskId'])
            assert task['status']=='review_ready',task
            assert captured and not app.sessions.get('player1',s['sessionId'])['items'][0].get('response')
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_reference_label_cannot_bypass_disabled_private_egress_during_kp_accept(application):
    from onlinecoc_ai.references import References
    app=application;install(app);observe(app)
    ref=References(app.host).search('player1','knowledge')['items'][0]
    s,r=create(app,text='请帮我改造 '+ref['token'])
    enable(app.host,public=True,private=False,kp=True)
    result=committed(decide(app,r));text=app.sessions.get('kp',result['reviewSessionId'])['items'][0]['text']
    assert '当前不可核验' in text and ref['label'] not in text and '[[knowledge:' not in text
