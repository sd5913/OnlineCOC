"""Budget opt-in and authorized summaries of confirmed/unknown model calls."""
import asyncio
import copy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from onlinecoc.server import create_app
from onlinecoc_ai.contracts import validate
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.repository import Repository
from test_coordinator import setup, completion, Fake, wait_task
from test_entrypoints import application, command, committed


def task_for(app, owner='kp', title='统计会话'):
    if owner!='kp' and not app.sessions.access(owner)['canChat']:
        committed(command(app,'ai.access.update',{'revision':app.sessions.access('kp')['revision'],'allowPlayerChat':True,'autoApproveBatches':False}))
    sid=committed(command(app,'ai.session.create',{'title':title},owner))['sessionId']
    rid=committed(command(app,'ai.session.submit',{'sessionId':sid,'text':'私密需求文字不进入统计'},owner))['requestId']
    tid=committed(command(app,'ai.request.dispatch',{'requestId':rid}))['taskId']
    app.coordinator._set(tid,'generating')
    return sid,rid,tid


def reserve(app,tid):
    profile=app.coordinator.profiles['deepseek-main']
    return app.coordinator._reserve(tid,profile,[{'role':'user','content':'statistics'}],[])


def test_unlimited_default_still_records_and_opt_in_reuses_ledger(application):
    app=application;profile=app.coordinator.profiles['deepseek-main'];assert profile['limits']['dailyTokenBudget'] is None
    validate('Profile',profile);_,_,tid=task_for(app)
    for _ in range(3):app.coordinator._reserve(tid,profile,[{'role':'user','content':'x'*40000}],[])
    original=copy.deepcopy(app.repository.state()['budgets']);assert next(iter(original.values()))['charged']>100000
    profile['limits']['dailyTokenBudget']=1;validate('Profile',profile)
    with pytest.raises(AiError,match='BUDGET_EXCEEDED'):reserve(app,tid)
    assert app.repository.state()['budgets']==original
    profile['limits']['dailyTokenBudget']=None;reserve(app,tid)
    assert len(next(iter(app.repository.state()['budgets'].values()))['calls'])==4
    profile['limits']['dailyTokenBudget']=False
    with pytest.raises(AiError):validate('Profile',profile)


def test_totals_owner_dispatch_session_filters_and_pagination(application):
    from test_known_runtime import install
    app=application;install(app);s1,r1,t1=task_for(app,'player1');s2,_,t2=task_for(app,'player2')
    app.coordinator._settle(t1,reserve(app,t1),completion({'kind':'plan','text':'private response'}))
    unknown=reserve(app,t1);app.coordinator._uncertain(unknown)
    pending=reserve(app,t2)
    one=app.usage('player1',{'scope':'mine','limit':'1'});total=one['totals']
    assert total['calls']==2 and total['confirmedTokens']==20 and total['promptTokens']==10 and total['completionTokens']==10
    assert total['uncertainCalls']==1 and total['pendingCalls']==0 and total['uncertainReservedTokens']>0
    assert total['accountedTokens']==20+total['uncertainReservedTokens']
    assert one['budgetsToday']==[] and one['nextBefore']
    assert one['items'][0]['requestId']==r1 and one['items'][0]['sessionId']==s1
    next_page=app.usage('player1',{'before':one['nextBefore'],'limit':'1'})
    assert len(next_page['items'])==1 and next_page['items'][0]['callId']!=one['items'][0]['callId'] and next_page['totals']==total
    assert '私密需求' not in str(one) and 'private response' not in str(one) and s2 not in str(one)
    with pytest.raises(AiError,match='PERMISSION_DENIED'):app.usage('player1',{'scope':'room'})
    with pytest.raises(AiError,match='NOT_VISIBLE'):app.usage('player1',{'sessionId':s2})
    assert app.usage('kp')['totals']['calls']==0
    room=app.usage('kp',{'scope':'room'});assert room['totals']['calls']==3 and room['totals']['pendingCalls']==1
    assert room['budgetsToday'][0]['dailyTokenBudget'] is None and room['budgetsToday'][0]['remainingTokens'] is None
    assert app.usage('player1',{'sessionId':s1})['totals']==total
    assert app.usage('player1',{'profileId':'other'})['totals']['calls']==0
    assert room['totals']=={k:v for k,v in room['byDay'][0].items() if k!='date'}


def test_old_records_restart_and_utc_date_filters(application):
    app=application;sid,_,tid=task_for(app)
    first=reserve(app,tid);app.coordinator._settle(tid,first,completion({'kind':'plan','text':'x'}));second=reserve(app,tid)
    state=app.repository.state();key=first[0]
    # Old ledgers retain total charges even when detailed usage/timestamps are absent.
    for call in state['budgets'][key]['calls'].values():
        for field in ('outcome','createdAt','finishedAt'):call.pop(field,None)
    for call in state['tasks'][tid]['calls']:call.pop('usage',None)
    state['budgets']['deepseek-main:2020-01-01']=state['budgets'].pop(key);app.repository.commit(state)
    before=app.repository.state();old=app.usage('kp',{'from':'2020-01-01','to':'2020-01-01','sessionId':sid})
    assert old['totals']['confirmedTokens']==20 and old['totals']['missingBreakdownCalls']==1 and old['totals']['uncertainCalls']==1
    assert old['totals']['pendingCalls']==0 and app.usage('kp')['totals']['calls']==0
    assert app.repository.state()==before
    path=app.repository.store.path;scope=before['scopeId'];app.repository.close();repo=Repository(path,scope)
    try:assert repo.state()['budgets']==before['budgets']
    finally:repo.close()


@pytest.mark.parametrize('options',[{'from':'bad'},{'from':'2020-01-02','to':'2020-01-01'},{'from':'2020-01-01','to':'2021-01-01'},{'limit':'101'},{'limit':'0'},{'scope':'admin'},{'accountId':'kp'},{'profileId':''}])
def test_invalid_usage_queries(application,options):
    with pytest.raises(AiError,match='INPUT_INVALID'):application.usage('kp',options)


def test_http_auth_parameter_injection_and_duplicate_filters(application):
    async def idle():pass
    runtime=SimpleNamespace(application=application,start=idle,close=idle)
    with TestClient(create_app(application.host,ai_runtime=runtime),base_url='http://127.0.0.1:8765') as client:
        assert client.get('/api/v1/ai/usage').status_code==401
        client.headers['origin']='http://127.0.0.1:8765';client.post('/api/v1/login',json={'loginName':'player1','password':'test-password'})
        assert client.get('/api/v1/ai/usage').json()['scope']=='mine'
        assert client.get('/api/v1/ai/usage?scope=room').status_code==403
        for suffix in ('?accountId=kp','?scope=mine&scope=room','?limit=500'):
            assert client.get('/api/v1/ai/usage'+suffix).status_code==409


def test_retry_and_cancel_classification(application):
    from onlinecoc_ai.providers.base import ProviderError
    app=application
    async def run():
        entered=asyncio.Event();stop=asyncio.Event()
        async def callback(number,*args):
            if number==1:raise ProviderError('PROVIDER_UNAVAILABLE',retryable=True)
            entered.set();await stop.wait()
        app.coordinator.provider_factory=lambda profile:Fake(callback)
        await app.coordinator.start()
        try:
            task=app.coordinator.enqueue('kp','cancel-usage','request');await asyncio.wait_for(entered.wait(),5)
            current=app.usage('kp')['totals'];assert current['uncertainCalls']==1 and current['pendingCalls']==1
            app.coordinator.cancel('kp',task['taskId'])
            for _ in range(100):
                if app.usage('kp')['totals']['pendingCalls']==0:break
                await asyncio.sleep(.02)
            current=app.usage('kp')['totals'];assert current['uncertainCalls']==2 and current['confirmedTokens']==0
        finally:await app.coordinator.close()
    asyncio.run(run())
