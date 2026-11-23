"""Cross-store recovery and session deletion must not leak tentative effects."""
import asyncio
import copy
import pytest
from test_entrypoints import application,command,committed
from test_coordinator import setup,Fake,wait_task
from test_access_batches import batch,decide,session,submit
from onlinecoc_ai.errors import AiError


@pytest.mark.parametrize('fail',[False,True])
def test_session_delete_cancels_live_task_only_after_commit(application,monkeypatch,fail):
    from onlinecoc_ai.api import Application
    app=application
    async def run():
        entered=asyncio.Event();cancelled=asyncio.Event()
        async def callback(*_):
            entered.set()
            try:await asyncio.Event().wait()
            finally:cancelled.set()
        app.coordinator.provider_factory=lambda _:Fake(callback);await app.coordinator.start()
        try:
            target=session(app);r=submit(app,target);task=committed(command(app,'ai.request.dispatch',{'requestId':r['requestId']}))
            await asyncio.wait_for(entered.wait(),5)
            current=app.sessions.get('kp',target['sessionId'])['session']
            actions=[{'target':'ai','op':'ai.session.delete','args':{'sessionId':target['sessionId'],'revision':current['revision']}},
                {'target':'ai','op':'ai.session.create','args':{'title':'after-delete'}}]
            b=batch(app,actions);assert not cancelled.is_set() and app.repository.state()['tasks'][task['taskId']]['status']=='generating'
            original=Application._execute
            def execute(self,account,cid,op,args,**kwargs):
                if fail and cid.startswith('ai-batch:') and op=='ai.session.create':raise AiError('INJECTED_FAILURE')
                return original(self,account,cid,op,args,**kwargs)
            monkeypatch.setattr(Application,'_execute',execute)
            result=committed(decide(app,b));await asyncio.sleep(.05)
            if fail:
                assert result['status']=='rolled_back' and not cancelled.is_set()
                assert not app.sessions.get('kp',target['sessionId'])['session'].get('deleted')
                assert app.repository.state()['tasks'][task['taskId']]['status']=='generating'
            else:
                await asyncio.wait_for(cancelled.wait(),5)
                assert result['status']=='completed' and app.repository.state()['tasks'][task['taskId']]['status']=='cancelled'
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_delete_own_source_session_keeps_batch_audit_and_parent_response(application):
    app=application;s=session(app);r=submit(app,s);request=app.repository.state()['requests'][r['requestId']]
    revision=app.sessions.get('kp',s['sessionId'])['session']['revision'];snapshot,_=app.coordinator.context.capture('kp',request)
    actions=[{'target':'ai','op':'ai.session.delete','args':{'sessionId':s['sessionId'],'revision':revision}}]
    bid=app.batches.create('kp',request,actions,'删除本会话',snapshot[0]);record=app.repository.state()['settings']['batches'][bid]
    receipt=decide(app,record);result=committed(receipt)
    assert result['status']=='completed' and result['execution']['committedCount']==1
    saved=app.repository.state()['settings']['batches'][bid]
    assert saved['status']=='completed' and len(saved['receipts'])==1 and saved['actions']==actions
    assert app.receipt('kp',receipt['requestId'])==receipt


def test_recover_old_memory_receipt_cannot_resurrect_revoked_fact(application):
    from test_memory import create
    app=application;draft=create(app.memory,app.host)
    confirmed=app.memory.confirm('kp',draft['memoryId'],1,command_id='original-confirm')
    revoked=app.memory.revoke('kp',draft['memoryId'],2,command_id='later-revoke')
    app.repository.update(lambda s:s['memory'].update({draft['memoryId']:copy.deepcopy(draft)}))
    historical=app.memory.confirm('kp',draft['memoryId'],1,command_id='original-confirm')
    assert historical==confirmed and app.repository.state()['memory'][draft['memoryId']]==revoked
    assert not app.memory.search('kp')


def test_revoked_sources_hide_batch_diagnostics_and_receipt_payload(application):
    from test_context import enable
    app=application;enable(app.host,public=True,kp=True)
    s=session(app);r=submit(app,s);request=app.repository.state()['requests'][r['requestId']]
    snapshot,_=app.coordinator.context.capture('kp',request)
    action={'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'SENSITIVE_BATCH_NAME'}}
    bid=app.batches.create('kp',request,[action],'SENSITIVE_SUMMARY',snapshot[0]);record=app.repository.state()['settings']['batches'][bid]
    receipt=decide(app,record);assert receipt['status']=='committed'
    enable(app.host,public=False,kp=False)
    for value in (app.batches.list('kp'),app.rulings.list('kp'),app.receipt('kp',receipt['requestId'])):
        assert 'SENSITIVE_BATCH_NAME' not in str(value) and 'SENSITIVE_SUMMARY' not in str(value)
