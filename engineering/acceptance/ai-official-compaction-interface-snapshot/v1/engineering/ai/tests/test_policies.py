"""Real host approval, player disclosure, policy revocation and unlimited batch counts."""
import copy
import pytest
from onlinecoc_ai.contracts import validate, digest
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.context import Context
from onlinecoc_ai.data_queries import DataQueryService
from onlinecoc_ai.change_policy import describe
from onlinecoc_ai.validation.rules import extension_check
from test_coordinator import setup
from test_entrypoints import application, command, committed, delta
from test_access_batches import batch, decide, access, session, submit
from test_context import enable
from test_known_runtime import install


def test_high_risk_requires_exact_manual_fingerprint_and_retains_diff(application):
    app=application;access(app)
    p=committed(command(app,'ai.draft.create',{'text':'更新物品','changeSet':delta()}))
    committed(command(app,'ai.proposal.validate',{'proposalId':p['proposalId'],'revision':1}))
    item=app.rulings.list('kp')['items'][0]
    assert item['highRisk'] and 'item-configuration' in item['riskTags']
    assert item['diff'][0]['before']['defaults']['bonus']==0
    assert item['diff'][0]['after']['defaults']['bonus']==15
    args={'rulingId':item['rulingId'],'digest':item['digest'],'decision':'approve','riskDecisions':{r['id']:'已核对完整差异并接受风险' for r in item['risks']}}
    assert command(app,'ai.ruling.decide',args)['code']=='HIGH_RISK_REVIEW_REQUIRED'
    assert command(app,'ai.ruling.decide',{**args,'explicitHighRiskDigest':'0'*64})['code']=='HIGH_RISK_REVIEW_REQUIRED'
    args['explicitHighRiskDigest']=item['digest']
    with pytest.raises(AiError,match='HIGH_RISK_REVIEW_REQUIRED'):app.rulings.decide('kp',args,automatic=True)
    assert not app.host.state()['aiControl']['publications']
    assert committed(command(app,'ai.ruling.decide',args))['status']=='completed'
    assert app.host.state()['configurations']['fixture.token']['defaults']['bonus']==15


def test_more_than_eight_actions_execute_without_truncation(application):
    app=application
    actions=[{'target':'host','op':'entity.patch','args':{'id':'actor-one','name':f'name-{i}'}} for i in range(19)]
    b=batch(app,actions);assert len(b['actions'])==19
    result=committed(decide(app,b));assert result['status']=='completed' and len(result['receipts'])==19
    assert app.host.state()['entities']['actor-one']['name']=='name-18'


def test_batch_storage_has_no_business_count_limit(application):
    app=application
    template=batch(app);original=app.repository.state()['settings']['batches'][template['batchId']]
    import uuid
    def populate(state):
        for _ in range(1001):
            value=copy.deepcopy(original);value['batchId']=uuid.uuid4().hex;value['status']='rejected'
            value['digest']=digest({k:value[k] for k in ('batchId','sessionId','requestId','creator','actions','context','baseline','authorityEpoch')})
            state['settings']['batches'][value['batchId']]=value
    app.repository.update(populate)
    s=session(app);r=submit(app,s);request=app.repository.state()['requests'][r['requestId']]
    snapshot,_=Context(app.proposals).capture('kp',request)
    bid=app.batches.create('kp',request,[{'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'new'}}],'追加',snapshot[0])
    assert bid in app.repository.state()['settings']['batches'] and len(app.repository.state()['settings']['batches'])==1003


def test_policy_switches_are_enforced_for_new_and_pending_writes(application):
    app=application;b=batch(app)
    committed(command(app,'ai.access.update',{'revision':1,'allowPlayerChat':False,'autoApproveBatches':False,'allowRuntimeChanges':False,'allowConfigurationChanges':False}))
    # A pending batch cannot use the earlier policy snapshot to execute.
    assert decide(app,b)['status']=='rejected'
    assert command(app,'ai.draft.create',{'text':'禁止','changeSet':delta()})['code']=='CONFIGURATION_CHANGES_DISABLED'
    assert app.host.state()['entities']['actor-one']['name']!='审核后的名称'


def test_ordinary_actor_configuration_still_supports_explicit_auto_policy(application):
    app=application
    # Extend this isolated fixture's author-declared namespace before rebinding.
    pack=app.proposals.pack
    pack.contract['extensionPoints'].append({'namespace':'ordinary.','typeRefs':['actor'],'allowedPaths':['/defaults'], 'allowExistingIds':[], 'rulePrefixes':[]})
    from onlinecoc_ai.validation.common import validator_digest
    app.host.register_ai(app.proposals.prepared,{'contract':pack.contract,'digest':pack.digest,'validatorSetDigest':validator_digest()})
    committed(command(app,'ai.access.update',{'revision':1,'allowPlayerChat':False,'autoApproveBatches':False,'autoApproveConfigurations':True}))
    original=next(c for c in app.host.state()['configurations'].values() if c['typeRef']=='actor')
    value={**copy.deepcopy(original),'configurationId':'ordinary.actor','revision':'1'}
    change={'schemaVersion':1,'configurations':[{'kind':'add','id':value['configurationId'],'expectedRevision':None,'value':value}],'sources':{},'data':{},'suggestions':[]}
    p=committed(command(app,'ai.draft.create',{'text':'普通角色模板','changeSet':change}))
    committed(command(app,'ai.proposal.validate',{'proposalId':p['proposalId'],'revision':1}))
    item=app.rulings.list('kp')['items'][0]
    assert item['highRisk'] is False and item['status']=='completed'


def test_admin_room_scope_is_default_and_revocable_without_player_escalation(application):
    app=application;install(app)
    r=submit(app,session(app));request=app.repository.state()['requests'][r['requestId']]
    snapshot,_=Context(app.proposals,demand=True).capture('kp',request)
    assert snapshot[0]['facts']['aiReadScope']=='kp-room'
    page=DataQueryService(app.host).attach('kp','search',{'types':['room'],'limit':2},snapshot,'kp')
    assert page['items'] and all(i['ref']['sourceId']=='host-room-state' for i in page['items'])
    assert snapshot[0]['facts']['dataQueries'][-1]['args']['roomMode']=='state'
    assert not snapshot[0]['facts'].get('consultationOnly')
    pl=submit(app,session(app,'player1'),who='player1')
    player_snapshot,_=Context(app.proposals).capture('kp',app.repository.state()['requests'][pl['requestId']])
    assert 'aiReadScope' not in player_snapshot[0]['facts']
    p=app.sessions.access('kp')
    committed(command(app,'ai.access.update',{'revision':p['revision'],'allowPlayerChat':True,'autoApproveBatches':False,'allowAdminRoomRead':False}))
    with pytest.raises(Exception):Context(app.proposals).recheck('kp',snapshot)
    with pytest.raises(Exception):DataQueryService(app.host).execute('kp','search',{'types':['room']},initiator='kp',read_scope='kp-room')


def request_disclosure(app):
    install(app);s=session(app,'player1');r=submit(app,s,'我可以知道此人的身份吗',who='player1')
    args={'sessionId':s['sessionId'],'requestId':r['requestId']}
    return s,r,args,committed(command(app,'ai.knowledge.request',args,'player1'))


def disclosure_args(app,owner='player1'):
    room=app.host.state()
    return {'op':'knowledge.observe','args':{'policyId':'personal-test','expectedPolicyRevision':1,
        'subjectMemberId':room['members'][owner]['memberId'],'resource':{'namespace':'witness','kind':'entity','id':'actor-one'},
        'facetIds':['identity'],'reason':'按玩家申请明确披露','expectedSourceRevision':str(room['entities']['actor-one']['revision'])}}


def test_player_request_is_explicit_private_and_real_observation_is_required(application):
    app=application;s,r,args,req=request_disclosure(app)
    assert committed(command(app,'ai.knowledge.request',args,'player1'))==req
    assert command(app,'ai.knowledge.request',args,'player2')['status']=='rejected'
    assert len(app.rulings.list('kp')['items'])==1
    decision={'rulingId':req['rulingId'],'digest':req['digest'],'decision':'approve'}
    assert command(app,'ai.ruling.decide',decision,'player1')['code']=='PERMISSION_DENIED'
    assert command(app,'ai.ruling.decide',decision)['code']=='DISCLOSURE_REQUIRED'
    assert command(app,'ai.ruling.decide',{**decision,'disclosures':[disclosure_args(app,'player2')]})['code']=='DISCLOSURE_SUBJECT_MISMATCH'
    assert committed(command(app,'ai.ruling.decide',{**decision,'disclosures':[disclosure_args(app)]}))['status']=='completed'
    from onlinecoc_ai.references import References
    assert References(app.host).search('player1','knowledge')['items']
    assert not References(app.host).search('player2','knowledge')['items']
    item=app.tasks('player1')['items'][0];assert item['knowledgeRequest']['status']=='completed'
    assert set(item['knowledgeRequest'])=={'rulingId','sessionId','requestId','status','createdAt','digest'}


def test_rejected_request_has_no_disclosure_and_disabled_policy_blocks_new_request(application):
    app=application;s,r,args,req=request_disclosure(app)
    rejected=committed(command(app,'ai.ruling.decide',{'rulingId':req['rulingId'],'digest':req['digest'],'decision':'reject'}))
    assert rejected['status']=='rejected'
    from onlinecoc_ai.references import References
    assert not References(app.host).search('player1','knowledge')['items']
    p=app.sessions.access('kp')
    committed(command(app,'ai.access.update',{'revision':p['revision'],'allowPlayerChat':True,'autoApproveBatches':False,'allowKnowledgeRequests':False}))
    assert command(app,'ai.knowledge.request',args,'player1')['code']=='KNOWLEDGE_REQUESTS_DISABLED'


def test_remove_schema_and_no_configuration_count_limit():
    changes={'schemaVersion':1,'configurations':[{'kind':'remove','id':f'unused-{i}','expectedRevision':'1','value':None} for i in range(150)],'sources':{},'data':{},'suggestions':[]}
    validate('ChangeSet',changes)
    changes['configurations'][0]['expectedRevision']=None
    with pytest.raises(AiError):validate('ChangeSet',changes)


def test_stable_array_uses_current_baseline_and_candidate_references():
    from types import SimpleNamespace
    from onlinecoc_ai.validation.rules import extension_check
    declarations={'stable':[{'dataRef':'game.json','pointer':'/items','idKey':'id','appendOnly':True}],
        'refs':[{'dataRef':'game.json','pointer':'/locations','idKey':'index','referencesKey':'exits'}]}
    pack=SimpleNamespace(contract={'extensionPoints':[],'contextMapping':{'stableArrays':'stable','dataReferences':'refs'}},json=lambda p:declarations[p])
    baseline={'metadata':{},'sources':{},'data':{'game.json':{'items':[{'id':'initial'},{'id':'later-published'}],'locations':[{'index':1,'exits':[]}]}}}
    changes={'configurations':[],'sources':{},'data':copy.deepcopy(baseline['data'])}
    changes['data']['game.json']['items'].append({'id':'new'})
    extension_check(pack,{'configurations':{}},baseline,baseline,changes)
    changes['data']['game.json']['items'][1]['id']='renumbered'
    with pytest.raises(AiError,match='STABLE_ARRAY_ID_CONFLICT'):extension_check(pack,{'configurations':{}},baseline,baseline,changes)
    changes['data']['game.json']=copy.deepcopy(baseline['data']['game.json']);changes['data']['game.json']['locations'][0]['exits']=[2]
    with pytest.raises(AiError,match='DATA_REFERENCE_CONFLICT'):extension_check(pack,{'configurations':{}},baseline,baseline,changes)


@pytest.mark.parametrize('outcome,expected',[('success',True),('declared-block',True),('changed-error',False),('unlisted-error',False)])
def test_live_probes_bind_real_ids_and_do_not_hide_changed_or_unlisted_failures(monkeypatch,outcome,expected):
    from types import SimpleNamespace
    from onlinecoc_ai.validation import live
    declarations=[{'configurationId':'character','rule':'layout','actorInput':'actor','input':{},'coversData':['game.json'],'coversRules':[], 'expectedErrors':['NOT_READY']}]
    pack=SimpleNamespace(contract={'contextMapping':{'liveScenarios':'live.json'}},json=lambda _:declarations)
    state={'configurations':{},'entities':{k:{'configurationId':'character','lifecycle':'active'} for k in ['random-a','random-b']}}
    baseline={'metadata':{'layout':{'public':True}},'sources':{},'data':{'game.json':{'x':1}}}
    candidate={**baseline,'data':{'game.json':{'x':2}}}
    changes={'configurations':[],'sources':{},'data':candidate['data']}
    calls=[]
    def run(rules,world,scenario,rolls,**kwargs):
        calls.append(scenario['steps'][0]['input']['actor'])
        step={'ok':True}
        if outcome!='success':step={'ok':False,'code':'UNKNOWN_FAILURE' if outcome=='unlisted-error' else 'NOT_READY'}
        if outcome=='changed-error' and rules is candidate:step={'ok':False,'code':'DIFFERENT_FAILURE'}
        return [{'steps':[step]} for _ in rolls]
    monkeypatch.setattr(live,'run_scenario',run)
    if expected:
        result=live.assess_live(pack,state,baseline,candidate,changes,'kp')
        assert result['scenarios'][0]['matched']==2 and calls==['random-a','random-a','random-b','random-b']
        if outcome=='declared-block':assert any(t.get('status')=='blocked-compatible' for t in result['scenarios'][0]['trials'])
    else:
        with pytest.raises(AiError,match='LIVE_SCENARIO_FAILED'):live.assess_live(pack,state,baseline,candidate,changes,'kp')
import asyncio
from onlinecoc_ai.contracts import canonical
from test_coordinator import Fake, completion, wait_task
from test_access_batches import tool_call

@pytest.mark.parametrize('size,expected', [(110*1024,'review_ready'),(270*1024,'review_ready'),(790*1024,'failed')])
def test_cumulative_tool_budget_uses_transport_limit_and_reports_sizes(application,monkeypatch,size,expected):
    app=application;enable(app.host,public=True,private=True,kp=True)
    original=app.batches.catalog_query
    monkeypatch.setattr(app.batches,'catalog_query',lambda *args,**kwargs: {**original(*args,**kwargs),'notice':'x'*size})
    import onlinecoc_ai.preparation
    monkeypatch.setattr(onlinecoc_ai.preparation,'prepare',lambda *args:0)
    async def callback(count,messages,tools):
        return tool_call('room_manage_catalog') if count==1 else completion({'kind':'plan','text':'已读取目录，等待具体需求。'})
    provider=Fake(callback)
    async def run():
        app.coordinator.provider_factory=lambda _:provider;await app.coordinator.start()
        try:
            request=submit(app,session(app),'读取管理目录')
            dispatched=committed(command(app,'ai.request.dispatch',{'requestId':request['requestId']}))
            result=await wait_task(app.coordinator,dispatched['taskId'])
            assert result['status']==expected,result
            budget=result['diagnostics']['contextBudget']
            assert budget['limitBytes']==768*1024-2048 and budget['toolMessageBytes']>=size
            assert 'x'*100 not in str(result['diagnostics'])
            if expected=='failed':assert result['error']=='CONTEXT_LIMIT_EXCEEDED' and provider.calls==1
            else:assert provider.calls==2 and 96*1024<budget['bytes']<budget['limitBytes']
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_management_catalog_indexes_before_returning_selected_schemas(application):
    app=application;full=app.batches.catalog('kp');index=app.batches.catalog_query('kp')
    assert index['mode']=='index' and 'entity.patch' in index['host']
    assert len(canonical(index))<len(canonical(full))//2
    selected=app.batches.catalog_query('kp',['entity.patch'])
    assert selected['host']=={'entity.patch':full['host']['entity.patch']} and selected['ai']=={}
    with pytest.raises(AiError,match='INPUT_INVALID'):app.batches.catalog_query('kp',['arbitrary.run'])


@pytest.mark.parametrize('allowed', [True,False])
def test_unused_extension_remove_requires_policy_without_making_actor_edits_high_risk(allowed):
    from types import SimpleNamespace
    contract={'extensionPoints':[{'namespace':'npc.','typeRefs':['actor'],'allowExistingIds':[], 'allowedPaths':['/defaults'],'rulePrefixes':[]}], 'contextMapping':{},'highRisk':{'allowRemove':allowed}}
    pack=SimpleNamespace(contract=contract)
    state={'configurations':{'npc.extra':{'typeRef':'actor','revision':'1','defaults':{'hp':4}}}}
    artifact={'sources':{},'data':{},'metadata':{}}
    change={'configurations':[{'kind':'remove','id':'npc.extra','value':None}],'sources':{},'data':{}}
    if allowed:extension_check(pack,state,artifact,artifact,change)
    else:
        with pytest.raises(AiError,match='EXTENSION_FORBIDDEN'):extension_check(pack,state,artifact,artifact,change)
    assert describe(contract,state,artifact,change)['highRisk']
    change['configurations'][0].update(kind='replace',value={'typeRef':'actor','revision':'2','defaults':{'hp':5}})
    assert not describe(contract,state,artifact,change)['highRisk']

@pytest.mark.parametrize('repair', ['correct-after-plan','clarification','exhausted'])
def test_malformed_batch_gets_exact_schema_and_cannot_escape_to_plan(application,repair):
    import json
    app=application;enable(app.host,public=True,private=True,kp=True)
    for profile in app.coordinator.profiles.values():profile['limits']['maxRepairAttempts']=5
    original=app.host.state()['entities']['actor-one']['name']
    bad={'kind':'batch','text':'变更待审核','changeSet':{'schemaVersion':1,'configurations':[],'sources':{},'data':{},'suggestions':[{'rule':'action.invoke','input':{},'reason':'proposed'}]}}
    action={'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'修正后等待审核'}}
    async def callback(count,messages,tools):
        if count==1:return tool_call('room_manage_catalog',{'operations':['entity.patch']})
        if count==2:return completion(bad)
        feedback=json.loads(messages[-1]['content'])
        assert not app.batches.list('kp')['items']
        assert feedback['expectedKind']=='batch' and feedback['outputSchema']['required']==['kind','text','actions']
        assert feedback['completedTools']==['room_manage_catalog']
        if count==3:
            assert feedback['missingFields']==['actions'] and feedback['unexpectedFields']==['changeSet']
            if repair=='clarification':return completion({'kind':'clarification','text':'希望恢复到最低生命值，还是满生命值？'})
            return completion({'kind':'plan','text':'管理接口没有开放。'})
        assert feedback['error']['code']=='MODEL_REPAIR_KIND_CHANGED'
        if repair=='exhausted':return completion({'kind':'plan','text':'无法提交。'})
        return completion({'kind':'batch','text':'已按目录编写，等待审核。','actions':[action]})
    provider=Fake(callback)
    async def run():
        app.coordinator.provider_factory=lambda _:provider;await app.coordinator.start()
        try:
            request=submit(app,session(app),'请修改角色名称')
            dispatched=committed(command(app,'ai.request.dispatch',{'requestId':request['requestId']}))
            result=await wait_task(app.coordinator,dispatched['taskId'])
            if repair=='correct-after-plan':
                assert result['status']=='review_ready' and provider.calls==4,result
                saved=app.batches.list('kp')['items'];assert len(saved)==1 and saved[0]['actions']==[action] and saved[0]['status']=='pending'
                assert [v['code'] for v in result['diagnostics']['outputFailures']]==['MODEL_FIELDS_INVALID','MODEL_REPAIR_KIND_CHANGED']
            elif repair=='clarification':assert result['status']=='needs_input' and provider.calls==3 and not app.batches.list('kp')['items']
            else:assert result['error']=='MODEL_OUTPUT_INVALID' and provider.calls==4 and not app.batches.list('kp')['items']
            assert app.host.state()['entities']['actor-one']['name']==original
        finally:await app.coordinator.close()
    asyncio.run(run())

@pytest.mark.parametrize('outcome',['completed','partial','pending'])
def test_batch_self_mutation_preserves_safe_execution_status_after_source_change_and_revocation(application,outcome):
    app=application;enable(app.host,public=True,private=True,kp=True)
    s=session(app);r=submit(app,s,'修改已读取的角色')
    request=app.repository.state()['requests'][r['requestId']]
    snapshot,_=Context(app.proposals,demand=True).capture('kp',request)
    queries=DataQueryService(app.host)
    page=queries.attach('kp','search',{'types':['entity'],'query':'','limit':50},snapshot,'kp')
    name=app.host.state()['entities']['actor-one']['name']
    ref=next(i['ref'] for i in page['items'] if i['label']==name)
    queries.attach('kp','read',{'refs':[ref]},snapshot,'kp')
    actions=[{'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'批次已修改'}}]
    bid=app.batches.create('kp',request,actions,'SECRET_ORIGINAL_SUMMARY',snapshot[0])
    item=next(i for i in app.rulings.list('kp')['items'] if i['rulingId']=='batch:'+bid)
    assert item['status']=='pending' and item['canDecide']
    args={'rulingId':item['rulingId'],'digest':item['digest'],'decision':'approve'}
    if outcome=='pending':
        receipt=app.rulings.host_command('kp','external-change','entity.patch',{'id':'actor-one','name':'其他修改'})
        assert receipt['status']=='committed'
    else:
        result=committed(command(app,'ai.ruling.decide',args))
        assert result['status']=='completed',result
        if outcome=='partial':
            # Seed a legacy sequential audit: one real committed mutation and a
            # historical rejection. New atomic batches cannot produce partial.
            def legacy(state):
                record=state['settings']['batches'][bid]
                record['context']['facts'].pop('batchExecutionVersion')
                record['actions'].append({'target':'host','op':'entity.patch','args':{'id':'missing-actor','name':'不应成功'}})
                record['receipts'].append({'id':'legacy-failed','account':'kp','target':'host','receipt':{'status':'rejected','code':'NOT_VISIBLE'}})
                record['status']='partial'
                for key in ('execution','preflight','executionCommandId','batchReceipt'):record.pop(key,None)
                record['digest']=digest({k:record[k] for k in ('batchId','sessionId','requestId','creator','actions','context','baseline','authorityEpoch')})
            app.repository.update(legacy)
    expected={'completed':[{'receipt':{'status':'committed'}}],
        'partial':[{'receipt':{'status':'committed'}},{'receipt':{'status':'rejected'}}],'pending':[]}[outcome]
    for revoked in (False,True):
        if revoked:enable(app.host,public=False,private=False,kp=False)
        view=next(i for i in app.rulings.list('kp')['items'] if i['rulingId']=='batch:'+bid)
        assert view['status']==outcome and view['canDecide'] is False
        if revoked:
            assert view['actions']==[] and view['receipts']==expected
            assert 'SECRET_ORIGINAL_SUMMARY' not in str(view) and 'actor-one' not in str(view) and '批次已修改' not in str(view)
            if outcome=='completed':assert '已执行完成' in view['summary'] and '重新' not in view['summary']
            if outcome=='partial':assert '部分操作已执行' in view['summary'] and '重新' not in view['summary']
            if outcome=='pending':assert '不能执行' in view['summary']
        else:
            assert view['actions'][0]==actions[0] and view.get('sourceNotice')
            assert view['summary']=='SECRET_ORIGINAL_SUMMARY'
        if outcome=='pending':assert command(app,'ai.ruling.decide',args)['status']=='rejected'
    revision=app.host.state()['entities']['actor-one']['revision']
    if outcome=='completed':assert committed(command(app,'ai.ruling.decide',args))['status']=='completed'
    assert app.host.state()['entities']['actor-one']['revision']==revision
    with pytest.raises(Exception,match='PERMISSION_DENIED'):app.rulings.list('player1')
