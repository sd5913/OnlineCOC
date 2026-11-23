"""Publication is the gate; a model plan never becomes user approval."""
import asyncio
import copy
import pytest
from test_coordinator import setup, Fake, completion, wait_task
from test_entrypoints import application, command, committed, delta
from test_access_batches import session, submit
from test_batch_notifications import actions, inbox
from test_context import enable
from onlinecoc_ai.errors import AiError


def prepare(app, instruction='改名并通知玩家', change=None):
    s=session(app)
    # Keep this first request un-dispatched so the scheduling test is deterministic.
    r=app._execute('kp','staged-source','ai.request.create',{'sourceKind':'manual','text':'调整配置，发布后改名并通知玩家'},session_id=s['sessionId'],dispatch=False)
    request=app.repository.state()['requests'][r['requestId']]
    snapshot,_=app.coordinator.context.capture('kp',request)
    p=app.proposals.create('kp',request['text'],change or delta(),snapshot=snapshot,request=request)
    app.continuations.register('kp',p,{'text':instruction})
    app.proposals.validate('kp',p['proposalId'],1)
    return p,s


def approve(app,p):
    item=app.rulings.detail('kp','proposal:'+p['proposalId'])
    args={'rulingId':item['rulingId'],'digest':item['digest'],'decision':'approve',
        'explicitHighRiskDigest':item['digest'],'riskDecisions':{r['id']:'测试确认该项风险' for r in item['risks']}}
    if item.get('cAssessment',{}).get('requiresAcceptance'):
        args['cReview']={k:item['cAssessment'][k] for k in ('basisRevision','basisDigest','reportDigest')}
    return committed(command(app,'ai.ruling.decide',args))


def test_publication_gates_fresh_runtime_batch_and_notification_once(application):
    app=application;enable(app.host,public=True,private=True,kp=True)
    p,s=prepare(app)
    assert app.continuations.reconcile() is True
    assert not app.repository.state()['tasks'] and not inbox(app,'player1')
    assert app.continuations.public(p['proposalId'],'kp')['status']=='waiting_publication'
    result=approve(app,p)
    assert result['status']=='completed',result
    assert result['continuation']['status']=='queued',result
    record=app.repository.state()['settings']['publicationContinuations'][p['proposalId']]
    assert record['nextTaskId']
    source=app.repository.state()['requests'][record['sourceRequestId']]
    follow=app.repository.state()['requests'][record['nextRequestId']]
    assert follow['text']==source['text']  # Never launder the model's text into user authority.
    snapshot,payload=app.coordinator.context.capture('kp',follow)
    assert payload['publicationContinuation']['completedProposalId']==p['proposalId']
    assert snapshot[0]['baseRuleset']==app.host.state()['activeRuleset']
    assert app.tasks('kp')['items'][0]['continuationOrigin']['proposalId']==p['proposalId']
    async def callback(*args):return completion({'kind':'batch','text':'已发布，准备改名并通知','actions':actions()})
    async def run():
        provider=Fake(callback);app.coordinator.provider_factory=lambda p:provider
        await app.coordinator.start()
        try:
            task=await wait_task(app.coordinator,record['nextTaskId'],60)
            assert task['status']=='review_ready',task
            assert not inbox(app,'player1')
            app.continuations.reconcile()
            assert app.continuations.public(p['proposalId'],'kp')['status']=='awaiting_runtime_approval'
            b=app.repository.state()['settings']['batches'][task['batchId']]
            result=committed(command(app,'ai.batch.approve',{'batchId':b['batchId'],'digest':b['digest']}))
            assert result['status']=='completed',result
            app.continuations.reconcile();app.continuations.reconcile()
            assert app.continuations.public(p['proposalId'],'kp')['status']=='completed'
            assert app.continuations.reconcile() is False
            assert len(inbox(app,'player1'))==1 and not inbox(app,'player2') and provider.calls==1
            assert len(app.repository.state()['tasks'])==1
        finally:await app.coordinator.close()
    asyncio.run(run())


@pytest.mark.parametrize('reason',['archive','revoke','cancel','revision'])
def test_continuation_stops_for_current_authority_or_revision(application,reason):
    app=application;p,s=prepare(app)
    if reason=='archive':
        app.repository.update(lambda state:state['settings']['sessions'][s['sessionId']].update(archived=True))
    elif reason=='revoke':
        room=app.host.state();room['members']['kp']['authorizationEpoch']+=1;app.host.commit(room)
    elif reason=='cancel':
        app.repository.update(lambda state:state['requests'][p['requestId']].update(status='cancelled'))
    else:app.proposals.revise('kp',p['proposalId'],1,delta())
    app.continuations.reconcile()
    row=app.repository.state()['settings']['publicationContinuations'][p['proposalId']]
    assert row['status'] in ('blocked','cancelled','superseded') and not row.get('nextRequestId')


def test_resume_after_request_saved_dispatch_failure_never_duplicates(application,monkeypatch):
    app=application;p,s=prepare(app);original=app._execute
    def fail(*args,**kwargs):
        if args[2]=='ai.request.dispatch':raise OSError('simulated dispatch outage')
        return original(*args,**kwargs)
    monkeypatch.setattr(app,'_execute',fail);approve(app,p)
    first=copy.deepcopy(app.repository.state()['settings']['publicationContinuations'][p['proposalId']])
    assert first['status']=='blocked' and first['nextRequestId'] and not first.get('nextTaskId')
    monkeypatch.setattr(app,'_execute',original);app.continuations.reconcile();app.continuations.reconcile()
    second=app.repository.state()['settings']['publicationContinuations'][p['proposalId']]
    assert second['nextRequestId']==first['nextRequestId'] and second['nextTaskId']
    assert len(app.repository.state()['settings']['sessions'][s['sessionId']]['requestIds'])==2


def test_model_draft_registers_stage_without_asking_again(application):
    app=application;enable(app.host,public=True,private=True,kp=True)
    async def callback(*args):return completion({'kind':'draft','text':'先准备已要求的配置',
        'changeSet':delta(),'afterPublish':{'text':'发布后改名并通知玩家'}})
    async def run():
        provider=Fake(callback);app.coordinator.provider_factory=lambda p:provider;await app.coordinator.start()
        try:
            s=session(app);r=submit(app,s,'调整配置，随后改名并通知玩家')
            if not r.get('taskId'):r=committed(command(app,'ai.request.dispatch',{'requestId':r['requestId']}))
            task=await wait_task(app.coordinator,r['taskId'],60)
            assert task['status']=='review_ready',task
            record=app.continuations.public(task['proposalId'],'kp')
            assert record=={'status':'waiting_publication'} and provider.calls==1
            item=app.rulings.detail('kp','proposal:'+task['proposalId'])
            compact=app.rulings.page('kp')['items'][0]
            assert compact['changeOverview']==item['changeOverview'] and compact['highRisk']==item['highRisk']
            assert any(i['path'].endswith('/defaults/bonus') for i in item['changeOverview']['items'])
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_new_item_configuration_then_owned_instance_and_notice(application):
    app=application;enable(app.host,public=True,private=True,kp=True)
    config=copy.deepcopy(app.host.state()['configurations']['fixture.token']);config['configurationId']='fixture.ext.gift'
    change={'schemaVersion':1,'configurations':[{'kind':'add','id':config['configurationId'],'expectedRevision':None,'value':config}],
        'sources':{},'data':{},'suggestions':[]}
    p,s=prepare(app,'将新增物品发给 player1 并通知',change)
    # Retain the user's actual request in both stages.
    app.repository.update(lambda state:state['requests'][p['requestId']].update(text='新增礼物物品，发布后发给 player1 并通知'))
    assert config['configurationId'] not in app.host.state()['configurations']
    approve(app,p)
    record=app.repository.state()['settings']['publicationContinuations'][p['proposalId']]
    assert config['configurationId'] in app.host.state()['configurations']
    async def callback(*args):return completion({'kind':'batch','text':'准备发放已发布的礼物并通知',
        'actions':[{'target':'host','op':'entity.create','args':{'configurationId':config['configurationId'],'name':'礼物','owner':'player1','visibility':'owner'}},
            {'target':'host','op':'notification.send','args':{'recipientAccountIds':['player1'],'text':'礼物已发放。','sourceActionIndex':0}}]})
    async def run():
        app.coordinator.provider_factory=lambda p:Fake(callback);await app.coordinator.start()
        try:
            task=await wait_task(app.coordinator,record['nextTaskId'],60)
            assert task['status']=='review_ready',task
            assert not [e for e in app.host.state()['entities'].values() if e['configurationId']==config['configurationId']]
            b=app.repository.state()['settings']['batches'][task['batchId']]
            result=committed(command(app,'ai.batch.approve',{'batchId':b['batchId'],'digest':b['digest']}))
            assert result['status']=='completed',result
            created=[e for e in app.host.state()['entities'].values() if e['configurationId']==config['configurationId']]
            assert len(created)==1 and created[0]['owner']=='player1'
            assert len(inbox(app,'player1'))==1 and not inbox(app,'player2')
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_restart_keeps_interrupted_task_and_does_not_redispatch(application):
    from types import SimpleNamespace
    from onlinecoc_ai.api import Application
    from onlinecoc_ai.proposals import Proposals
    from onlinecoc_ai.coordinator import Coordinator
    app=application;p,s=prepare(app);approve(app,p)
    before=app.repository.state()['settings']['publicationContinuations'][p['proposalId']]
    directory=app.repository.directory;app.proposals.close()
    proposals=Proposals(app.host,app.proposals.pack,directory=directory)
    try:
        restarted=Application(SimpleNamespace(proposals=proposals,coordinator=Coordinator(proposals,app.coordinator.profiles)))
        restarted.continuations.reconcile();restarted.continuations.reconcile()
        row=restarted.repository.state()['settings']['publicationContinuations'][p['proposalId']]
        assert row['status']=='interrupted' and row['error']=='PROCESS_RESTARTED'
        assert row['nextTaskId']==before['nextTaskId'] and row['nextRequestId']==before['nextRequestId']
        assert len(restarted.repository.state()['tasks'])==1 and not inbox(restarted,'player1')
    finally:proposals.close()


def test_continuation_cannot_recreate_published_configuration(application):
    app=application;enable(app.host,public=True,private=True,kp=True);p,s=prepare(app);approve(app,p)
    tid=app.repository.state()['settings']['publicationContinuations'][p['proposalId']]['nextTaskId']
    async def callback(*args):return completion({'kind':'draft','text':'错误地再建配置','changeSet':delta()})
    async def run():
        provider=Fake(callback);app.coordinator.provider_factory=lambda p:provider;await app.coordinator.start()
        try:
            task=await wait_task(app.coordinator,tid,60)
            assert task['status']=='failed' and task['error']=='MODEL_OUTPUT_INVALID',task
            app.continuations.reconcile();app.continuations.reconcile()
            assert app.continuations.public(p['proposalId'],'kp')['status']=='failed'
            assert len(app.repository.state()['proposals'])==1 and len(app.repository.state()['tasks'])==1
            assert len(app.host.state()['aiControl']['publications'])==1 and not inbox(app,'player1')
            assert provider.calls<=3
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_approval_without_publication_does_not_advance(application):
    app=application;p,s=prepare(app)
    item=app.rulings.detail('kp','proposal:'+p['proposalId'])
    receipt=app.rulings.host_command('kp','approval-only','ai.proposal.approve',{'proposalId':p['proposalId'],'proposalRevision':1,
        'riskDecisions':{r['id']:'测试接受该项风险' for r in item['risks']},'explicitHighRiskDigest':item['digest']})
    # If the public operation name/schema changes this must fail, not silently simulate approval.
    assert receipt['status']=='committed',receipt
    app.continuations.reconcile()
    assert app.host.state()['aiControl']['approvals'] and not app.repository.state()['tasks']


def test_continuation_integrity_detects_modified_plan(application):
    app=application;p,s=prepare(app)
    with pytest.raises(AiError,match='CONTINUATION_STATE_INVALID'):
        app.repository.update(lambda state:state['settings']['publicationContinuations'][p['proposalId']].update(text='伪造的新指令'))


def test_two_consecutive_publications_refresh_baseline_keep_external_conflict(application):
    app=application
    for bonus in (15,10):
        change=delta();current=app.host.state()['configurations']['fixture.token']
        change['configurations'][0].update(expectedRevision=current['revision'])
        change['configurations'][0]['value']['revision']=str(int(current['revision'])+1)
        change['configurations'][0]['value']['defaults']['bonus']=bonus
        p=app.proposals.create('kp','连续发布',change)
        checked=app.proposals.validate('kp',p['proposalId'],1)
        assert checked['proposal']['status']=='review_ready',checked
        assert approve(app,p)['status']=='completed'
    assert len(app.host.state()['aiControl']['publications'])==2
    snapshot=app.proposals.snapshot('kp');room=app.host.state();room['entities']['actor-one']['name']='外部改变';app.host.commit(room)
    with pytest.raises(Exception,match='BASELINE_STALE'):app.proposals.create('kp','旧基线',delta(),snapshot=snapshot)


def test_exact_paths_escape_and_bounded_overview():
    from onlinecoc_ai.change_overview import overview
    state={'configurations':{}}
    base={'sources':{},'data':{'a/b.json':{'items':[],'same':1}}}
    change={'sources':{},'data':{'a/b.json':{'items':[{'id':'new','name':'新物品'}],'same':1}},'configurations':[]}
    value=overview(state,base,change)
    assert value=={'total':1,'items':[{'path':'/data/a~1b.json/items/0','operation':'add','summary':'新增 新物品'}],'truncated':False}
    change['data']['a/b.json']['items']*=45
    value=overview(state,base,change)
    assert value['total']==45 and len(value['items'])==40 and value['truncated']


def test_projection_inheritance_only_selector(validation_case):
    from onlinecoc_ai.pack import local_schema
    from onlinecoc_ai.validation.base import check_base
    pack,state,artifact,context,change=validation_case
    name=next(iter(pack.schemas))
    pack.inherited_only[name]=local_schema({})
    assert check_base(pack,state,artifact,context,change)[0]['status']=='pass'
    change['data'][name]['_new']='unpaired'
    result,_=check_base(pack,state,artifact,context,change)
    assert result['findings'][0]['code']=='PACK_PROJECTION_EDIT_FORBIDDEN'
