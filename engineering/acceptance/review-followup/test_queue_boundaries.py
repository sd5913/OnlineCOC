"""Extra concurrency-state and persistence checks, independent of package work."""
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'ai/tests'),str(ROOT/'ai/src'),str(ROOT/'backend/src'),str(ROOT/'data-management')]
from test_entrypoints import application,command,committed,delta
from test_coordinator import setup
from test_access_batches import batch,session,submit
from test_review_followup import archive,row


@pytest.mark.parametrize('status',['queued','generating','validating'])
def test_candidate_with_running_generation_cannot_be_archived(application,status):
    app=application;s=session(app);r=submit(app,s,'配置生成中')
    dispatched=committed(command(app,'ai.request.dispatch',{'requestId':r['requestId']}));tid=dispatched['taskId']
    app.repository.update(lambda state:state['tasks'][tid].update(status=status))
    request=app.repository.state()['requests'][tid]
    p=app.proposals.create('kp','配置生成中',delta(),request=request)
    candidate=row(app,'proposal:'+p['proposalId'])
    assert not candidate['canArchive']
    assert archive(app,candidate)['code']=='QUEUE_ITEM_PROTECTED'


@pytest.mark.parametrize('kind',['batch','proposal'])
def test_cancelled_request_is_not_still_an_active_queue_candidate(application,kind):
    app=application
    if kind=='batch':
        b=batch(app);target='batch:'+b['batchId'];rid=b['requestId']
    else:
        p=app.proposals.create('kp','取消配置',delta());target='proposal:'+p['proposalId'];rid=p['requestId']
    committed(command(app,'ai.request.cancel',{'requestId':rid}))
    candidate=row(app,target)
    assert candidate['status'] in ('cancelled','rejected') and candidate['queueStatus']=='history'


def test_archive_metadata_and_business_status_survive_repository_reopen(application):
    from onlinecoc_ai.repository import Repository
    app=application;b=batch(app);target='batch:'+b['batchId'];before=app.repository.state()['settings']['batches'][b['batchId']]
    committed(archive(app,row(app,target)))
    state=app.repository.state();directory=app.repository.store.path
    app.repository.close();reopened=Repository(directory,state['scopeId'])
    try:
        stored=reopened.state()
        assert stored['settings']['batches'][b['batchId']]==before
        assert stored['settings']['reviewQueue'][target]['archived']
    finally:reopened.close()


def test_dispatch_and_archive_are_serialized_without_archived_running_task(application):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    app=application;s=session(app);request=submit(app,s,'并发派发')
    item=app.sessions.get('kp',s['sessionId'])['items'][0]
    entered=Event();release=Event();archiving=Event();capture=app.coordinator.context.capture
    def blocked(*args,**kwargs):
        entered.set();assert release.wait(10)
        return capture(*args,**kwargs)
    def organize():
        archiving.set();return archive(app,item)
    app.coordinator.context.capture=blocked
    with ThreadPoolExecutor(max_workers=2) as workers:
        dispatch=workers.submit(command,app,'ai.request.dispatch',{'requestId':request['requestId']})
        try:
            assert entered.wait(10);archived=workers.submit(organize);assert archiving.wait(10)
            assert not archived.done()
        finally:release.set()
        assert dispatch.result(timeout=10)['status']=='committed'
        assert archived.result(timeout=10)['code']=='QUEUE_VERSION_CONFLICT'
    assert not app.queue.fields('request:'+request['requestId'])['archived']
