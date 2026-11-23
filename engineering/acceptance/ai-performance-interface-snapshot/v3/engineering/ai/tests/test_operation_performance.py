import copy
import pytest
from test_entrypoints import application, command, committed, delta
from test_coordinator import setup
from test_access_batches import batch
from onlinecoc_ai.errors import AiError


def test_compact_page_projects_only_selected_and_detail_checks_current_sources(application,monkeypatch):
    app=application
    records=[batch(app) for _ in range(4)]
    seen=[];original=app.rulings.redact_stale
    def count(*args,**kw):seen.append(args[2]['rulingId']);return original(*args,**kw)
    monkeypatch.setattr(app.rulings,'redact_stale',count)
    first=app.rulings.page('kp',limit=2)
    assert len(seen)==2 and first['activeCount']==4 and first['nextBefore']
    assert all(i['compact'] and not i['canDecide'] and 'actions' not in i for i in first['items'])
    second=app.rulings.page('kp',limit=2,before=first['nextBefore'])
    assert second['nextBefore'] is None
    assert len({i['rulingId'] for i in first['items']+second['items']})==4
    seen.clear();detail=app.rulings.detail('kp',first['items'][0]['rulingId'])
    assert len(seen)==1 and detail['actions'] and detail['canDecide']
    with pytest.raises(Exception):app.rulings.page('player1')
    with pytest.raises(AiError,match='CURSOR_INVALID'):app.rulings.page('kp',before='batch:'+'0'*32)
    room=app.host.state();room['members']['kp']['authorizationEpoch']+=1;app.host.commit(room)
    changed=app.rulings.detail('kp',detail['rulingId'])
    assert not changed['canDecide'] and changed['sourceState']=='denied'


def test_queue_index_invalidates_after_decision_archive_and_transaction(application):
    app=application;b=batch(app);rid='batch:'+b['batchId']
    assert app.rulings.page('kp')['activeCount']==1
    committed(command(app,'ai.ruling.decide',{'rulingId':rid,'digest':b['digest'],'decision':'reject'}))
    assert app.rulings.page('kp')['items']==[]
    archived=app.rulings.page('kp',queue='archived')
    assert archived['activeCount']==0 and archived['items'][0]['rulingId']==rid
    assert app.rulings.detail('kp',rid)['status']=='rejected'


def test_read_cache_is_generation_bound_and_public_state_is_detached(application,monkeypatch):
    repo=application.repository;calls=[];original=repo.store.snapshot
    monkeypatch.setattr(repo.store,'snapshot',lambda:(calls.append(1),original())[1])
    repo._read_cache=None
    for _ in range(3):
        with repo.read_scope():assert repo.read_state()['schemaVersion']==1
    assert len(calls)==1
    detached=repo.state();detached['settings']['uncommitted']='private'
    with repo.read_scope():assert 'uncommitted' not in repo.read_state()['settings']
    repo.update(lambda s:s['settings'].update(perfMarker='new'))
    with repo.read_scope():assert repo.read_state()['settings']['perfMarker']=='new'
    with pytest.raises(RuntimeError):
        with repo.transaction():
            repo.update(lambda s:s['settings'].update(perfMarker='rollback'))
            with repo.read_scope():assert repo.read_state()['settings']['perfMarker']=='rollback'
            raise RuntimeError('rollback')
    with repo.read_scope():assert repo.read_state()['settings']['perfMarker']=='new'


def test_validation_cache_is_content_bound_and_relations_still_checked(application):
    app=application;b=batch(app);repo=app.repository;state=repo.state()
    repo.verify(state);repo.verify(copy.deepcopy(state))
    bad=copy.deepcopy(state);bad['settings']['batches'][b['batchId']]['actions'][0]['args']['name']='changed'
    with pytest.raises(AiError,match='BATCH_STATE_INVALID'):repo.verify(bad)
    bad=copy.deepcopy(state);bad['settings']['sessions'][b['sessionId']]['requestIds']=['0'*32]
    with pytest.raises(AiError,match='REFERENCE_CONFLICT'):repo.verify(bad)


def test_three_checks_share_only_same_validation_base(application,monkeypatch):
    from onlinecoc_ai import proposals
    calls=[];original=proposals.check_base
    def checked(*args,**kw):calls.append(1);return original(*args,**kw)
    monkeypatch.setattr(proposals,'check_base',checked)
    p=committed(command(application,'ai.draft.create',{'text':'性能三检','changeSet':delta()}))
    result=committed(command(application,'ai.proposal.validate',{'proposalId':p['proposalId'],'revision':1}))
    assert len(calls)==1 and [r['status'] for r in result['reports']]==['pass']*3
    assert not application.host.state()['aiControl']['publications']


def test_compact_configuration_keeps_risk_and_queue_metadata(application):
    app=application
    p=committed(command(app,'ai.draft.create',{'text':'高危配置列表','changeSet':delta()}))
    committed(command(app,'ai.proposal.validate',{'proposalId':p['proposalId'],'revision':1}))
    rid='proposal:'+p['proposalId'];detail=app.rulings.detail('kp',rid)
    compact=next(i for i in app.rulings.page('kp')['items'] if i['rulingId']==rid)
    assert detail['highRisk'] and compact['highRisk']==detail['highRisk']
    for key in ('riskTags','queueStatus','queueDigest','supersedes','consultationAssessment'):
        assert compact[key]==detail[key]
    assert 'diff' not in compact and 'changeSet' not in compact and not compact['canDecide']
    assert command(app,'ai.ruling.decide',{'rulingId':rid,'digest':detail['digest'],'decision':'approve'})['status']=='rejected'


def test_terminal_state_and_current_trace_share_commit(application):
    from onlinecoc_ai.diagnostics import TaskTrace
    app=application;t=app.coordinator.enqueue('kp','performance-task','只讨论')
    trace=TaskTrace();trace.event('result_save','保存结果');app.coordinator.traces[t['taskId']]=trace
    app.coordinator._set(t['taskId'],'failed',error='TEST_FAILURE')
    saved=app.repository.state()['tasks'][t['taskId']]
    assert saved['status']=='failed' and saved['events'][0]['seq']==1 and saved['diagnostics']
