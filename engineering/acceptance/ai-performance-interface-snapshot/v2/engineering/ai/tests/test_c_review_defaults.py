"""New-room defaults and mutable C evidence, without any external API."""
import copy
import pytest

from onlinecoc_ai.c_review import DEFAULT, assessment, basis, basis_binding
from onlinecoc_ai.contracts import digest
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.validation.gameplay import assess
from test_coordinator import setup
from test_entrypoints import application, command, committed, delta
from test_session_restart import reopen


def reset_service(app):
    state = app.host.state()
    state['aiControl']['settings'].update(enabled=False, profileId=None)
    app.host.commit(state)
    return {'scopeId': state['aiControl']['scopeId'], 'profileId': None}


def test_new_room_defaults_and_repeat_preserve_user_settings(application):
    app = application
    args = reset_service(app)
    first = committed(command(app, 'ai.room.initialize', args, identifier='new-room'))
    assert first['initialized'] and first['serviceStatus'] == 'ready'
    settings = app.settings('kp')
    assert all(settings['access'][key] for key in settings['access'] if key.startswith('allow'))
    assert not settings['access']['autoApproveBatches'] and not settings['access']['autoApproveConfigurations']
    assert all(settings['settings']['externalSources'].values())
    committed(command(app, 'ai.access.update', {'revision':1, 'allowPlayerChat':False, 'autoApproveBatches':False}))
    changed = {**settings['settings'], 'enabled':False, 'externalSources':{'public':True,'private':False,'kp':False}}
    changed['auto'].pop('principal', None)
    committed(command(app, 'ai.settings.update', changed))
    assert not committed(command(app, 'ai.room.initialize', args))['initialized']
    assert not app.settings('kp')['access']['allowPlayerChat']
    assert not app.settings('kp')['settings']['externalSources']['kp']
    assert committed(command(app, 'ai.room.initialize', args, identifier='new-room')) == first


@pytest.mark.parametrize('count,status', [(0,'profile_unavailable'),(2,'profile_selection_required')])
def test_new_room_no_implicit_profile_guess(application, count, status):
    app = application;args = reset_service(app)
    profile = next(iter(app.coordinator.profiles.values()))
    app.coordinator.profiles = {str(i):{**profile,'profileId':str(i)} for i in range(count)}
    result = committed(command(app, 'ai.room.initialize', args))
    assert result['serviceStatus'] == status and not result['settings']['enabled']
    assert app.sessions.access('kp')['allowPlayerChat']
    assert all(result['settings']['externalSources'].values())


def test_initialization_requires_kp_scope_and_untouched_settings(application):
    app = application;args = reset_service(app)
    assert command(app, 'ai.room.initialize', args, 'player1')['code'] == 'PERMISSION_DENIED'
    assert command(app, 'ai.room.initialize', {**args,'scopeId':'other'})['code'] == 'SCOPE_MISMATCH'
    committed(command(app, 'ai.access.update', {'revision':1,'allowPlayerChat':False,'autoApproveBatches':False}))
    assert command(app, 'ai.room.initialize', args)['code'] == 'ROOM_ALREADY_CONFIGURED'
    assert not app.host.state()['aiControl']['settings']['enabled']


def test_dynamic_thresholds_affect_real_measurements_and_reset(validation_case):
    first = assess(*validation_case)
    override = {**DEFAULT, 'revision':2, 'metricOverrides':{'success-rate':{'absoluteDelta':.5,'risk':'medium'}}}
    second = assess(*validation_case, basis=override)
    assert first['risk'] == 'high' and second['risk'] == 'low'
    assert first['evidence']['comparisons'] == second['evidence']['comparisons']
    assert second['evidence']['reviewBasis']['basisDigest'] == digest(override)
    assert assess(*validation_case)['risk'] == 'high'


@pytest.mark.parametrize('code,adoptable', [
    ('EXTENSION_FORBIDDEN',True), ('LIVE_SCENARIO_COVERAGE_MISSING',True),
    ('EXISTING_INSTANCE_COVERAGE_MISSING',True), ('SCENARIO_EXECUTION_FAILED',False),
    ('SANDBOX_UNAVAILABLE',False), ('RULE_TIMEOUT',False), ('EXTENSION_EFFECT_FORBIDDEN',False)])
def test_c_risk_classification_never_relaxes_execution(code, adoptable):
    reports = [{'level':k,'status':'pass','findings':[],'risk':'low'} for k in ('A','B','C')]
    reports[-1].update(status='unknown',risk='unknown',findings=[{'severity':'error','code':code}])
    value = assessment(reports, DEFAULT)
    assert value['adoptable'] is adoptable and value['requiresAcceptance']
    reports[1].update(status='fail',findings=[{'severity':'error','code':'EXTENSION_FORBIDDEN'}])
    assert not assessment(reports, DEFAULT)['adoptable']


def test_basis_update_authorization_revision_and_restart(application):
    app = application
    args = {**copy.deepcopy(DEFAULT), 'notes':'KP 增补依据'}
    assert command(app,'ai.c_basis.update',args,'player1')['code'] == 'PERMISSION_DENIED'
    first = committed(command(app,'ai.c_basis.update',args,identifier='basis'))
    assert first['revision'] == 2
    assert committed(command(app,'ai.c_basis.update',args,identifier='basis')) == first
    assert command(app,'ai.c_basis.update',args)['code'] == 'C_BASIS_VERSION_CONFLICT'
    bad = {**args,'revision':2,'metricOverrides':{'missing':{'absoluteDelta':1,'risk':'low'}}}
    assert command(app,'ai.c_basis.update',bad)['code'] == 'C_METRIC_NOT_FOUND'
    current = reopen(app)
    try:
        assert basis(current.repository)['notes'] == args['notes']
        assert current.settings('kp')['cReviewBasis']['revision'] == 2
        assert len(current.repository.state()['settings']['cReviewBasisHistory']) == 1
    finally:current.proposals.close();current.host.close()


def test_changing_basis_invalidates_prepared_and_recheck_binds_new_version(application):
    app = application
    p = committed(command(app,'ai.draft.create',{'text':'配置修改','changeSet':delta()}))
    checked = committed(command(app,'ai.proposal.validate',{'proposalId':p['proposalId'],'revision':1}))
    old = app.proposals.prepared('kp',p['proposalId'],1)['cAssessment']
    committed(command(app,'ai.c_basis.update',{**copy.deepcopy(DEFAULT),'notes':'新依据'}))
    with pytest.raises(AiError,match='C_BASIS_STALE'):app.proposals.prepared('kp',p['proposalId'],1)
    assert app.rulings.list('kp')['items'][0]['cAssessment']['stale']
    committed(command(app,'ai.proposal.validate',{'proposalId':p['proposalId'],'revision':1}))
    new = app.proposals.prepared('kp',p['proposalId'],1)['cAssessment']
    assert new['basisRevision'] == 2 and old['reportDigest'] != new['reportDigest']
    assert not app.rulings.list('kp')['items'][0]['cAssessment']['stale']


def uncovered_draft(app):
    state = app.host.state()
    extra = copy.deepcopy(state['entities']['actor-one'])
    extra['instanceId'] = 'actor-extra'
    state['entities']['actor-extra'] = extra
    app.host.commit(state)
    changes = delta()
    changes['sources']['check.lua'] = app.proposals.pack.sources['check.lua'] + '\n-- harmless new version\n'
    p = committed(command(app,'ai.draft.create',{'text':'保留规则行为；评估实况覆盖','changeSet':changes}))
    return p


def test_actual_coverage_gap_is_reviewable_and_rejectable(application):
    app=application;p=uncovered_draft(app)
    result=committed(command(app,'ai.proposal.validate',{'proposalId':p['proposalId'],'revision':1}))
    assert result['proposal']['status']=='review_ready'
    assert [r['status'] for r in result['reports']]==['pass','pass','unknown']
    c=result['reports'][2]
    assert any(f['code']=='EXISTING_INSTANCE_COVERAGE_MISSING' and 'actor-extra' in f['evidence']['ids'] for f in c['findings'])
    item=app.rulings.list('kp')['items'][0]
    args={'rulingId':item['rulingId'],'digest':item['digest'],'decision':'approve','riskDecisions':{r['id']:'Test acceptance' for r in item['risks']},'explicitHighRiskDigest':item['digest']}
    assert command(app,'ai.ruling.decide',args)['code']=='C_REVIEW_REQUIRED'
    rejected=committed(command(app,'ai.ruling.decide',{**args,'decision':'reject'}))
    assert rejected['status']=='rejected' and not app.host.state()['aiControl']['publications']


def test_added_live_scenarios_run_and_close_coverage_gap(application):
    app=application;p=uncovered_draft(app)
    before=app.host.state()['entities']
    declaration={'configurationId':'fixture.actor','rule':'fixture.check','actorInput':'actor','input':{'item':'token-one'},'coversData':[],'coversRules':['fixture.check'],'randomSides':100}
    committed(command(app,'ai.c_basis.update',{**copy.deepcopy(DEFAULT),'liveScenarios':[declaration],'notes':'验证所有当前角色'}))
    result=committed(command(app,'ai.proposal.validate',{'proposalId':p['proposalId'],'revision':1}))
    c=result['reports'][2]
    assert c['status']=='pass',c['findings']
    live=next(s['liveValidation'] for s in c['evidence']['scenarios'] if 'liveValidation' in s)
    assert live['scenarios'][0]['matched']==2
    assert {t['entityId'] for t in live['scenarios'][0]['trials']}=={'actor-one','actor-extra'}
    assert app.host.state()['entities']==before


def test_initialization_recovers_interrupted_host_commit(application,monkeypatch):
    app=application;args=reset_service(app);commit=app.host.commit
    def fail(value):raise OSError('injected store uncertainty')
    monkeypatch.setattr(app.host,'commit',fail)
    receipt=command(app,'ai.room.initialize',args)
    assert receipt['status']=='unknown'
    assert app.repository.state()['settings']['roomDefaults']['pendingSettings']
    monkeypatch.setattr(app.host,'commit',commit)
    result=committed(command(app,'ai.room.initialize',args))
    assert result['settings']['enabled'] and all(result['settings']['externalSources'].values())
    assert 'pendingSettings' not in app.repository.state()['settings']['roomDefaults']


@pytest.mark.parametrize('changed',[False,True])
def test_approved_publication_after_ai_close_rechecks_persisted_basis(application,changed):
    from onlinecoc_ai.repository import Repository
    app=application
    p=committed(command(app,'ai.draft.create',{'text':'保存后发布','changeSet':delta()}))
    committed(command(app,'ai.proposal.validate',{'proposalId':p['proposalId'],'revision':1}))
    item=app.rulings.list('kp')['items'][0]
    approved=committed(app.rulings.host_command('kp','approve-before-close','ai.proposal.approve',{'proposalId':p['proposalId'],'proposalRevision':1,
        'explicitHighRiskDigest':item['digest'],'riskDecisions':{r['id']:'Test acceptance' for r in item['risks']}}))
    path=app.repository.store.path;scope=app.host.state()['aiControl']['scopeId'];app.proposals.close()
    if changed:
        other=Repository(path,scope)
        try:other.update(lambda s:s['settings'].update(cReviewBasis={**copy.deepcopy(DEFAULT),'revision':2,'notes':'Changed while AI closed'}))
        finally:other.close()
    result=app.rulings.host_command('kp','apply-after-close','publication.apply',{'approvalId':approved['approvalId']})
    if changed:assert result['status']=='rejected' and result['code']=='C_BASIS_STALE',result
    else:assert result['status']=='committed',result


def test_closed_basis_resolver_reports_locked_storage(application):
    from onlinecoc_ai.repository import Repository
    from onlinecoc.errors import DomainError
    app=application;path=app.repository.store.path;scope=app.host.state()['aiControl']['scopeId'];app.proposals.close()
    other=Repository(path,scope)
    try:
        with pytest.raises(DomainError,match='C_BASIS_UNAVAILABLE'):app.host.ai_c_basis_resolver()
    finally:other.close()
