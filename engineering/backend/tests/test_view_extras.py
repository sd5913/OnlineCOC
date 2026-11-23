import copy
from concurrent.futures import ThreadPoolExecutor
import threading
import pytest
from fastapi.testclient import TestClient
from onlinecoc.errors import DomainError
from onlinecoc.server import create_app
from test_host import host
from test_knowledge import install, observe
from test_notifications import action, send, call


@pytest.mark.parametrize('account,mode,expected',[
    ('kp','auto','keeper'),('player1','auto','player'),('player2','player','player'),
    ('kp','keeper','keeper'),('kp','player','player')])
def test_extras_one_snapshot_and_existing_projections(host,monkeypatch,account,mode,expected):
    action(host);send(host);install(host);observe(host)
    original=host.store.snapshot;calls=[]
    monkeypatch.setattr(host.store,'snapshot',lambda:(calls.append(1),original())[1])
    for cold in (True,False):
        if cold:host._projection_generation=None
        calls.clear();view=host.project(account,extras=mode)
        assert len(calls)==1
        extra=view['viewExtras'];assert extra['mode']==expected and extra['knowledgeStatus']=='ready'
        if expected=='keeper':
            assert extra['knowledgeGrants']==host.knowledge.grants(account,{'limit':50})
            assert extra['members']=={'items':host.chat_members(account)}
            assert set(extra)=={'mode','knowledgeStatus','knowledgeGrants','members'}
        else:
            assert extra['notifications']==host.notifications(account)
            assert set(extra)=={'mode','knowledgeStatus','notifications'}
    assert 'viewExtras' not in host.project(account)


def test_extras_revoke_and_grant_page_limit(host):
    action(host);notice=send(host);install(host);observe(host)
    state=host.state();grant=next(iter(state['knowledge']['grants'].values()))
    for i in range(60):
        value=copy.deepcopy(grant);value['grantId']='extra-'+str(i);state['knowledge']['grants'][value['grantId']]=value
    state['knowledge']['revision']+=1;host.commit(state)
    result=host.project('kp',extras='keeper')['viewExtras']['knowledgeGrants']
    assert len(result['items'])==50 and result['nextCursor']
    assert len(host.knowledge.grants('kp',{'cursor':result['nextCursor'],'limit':50})['items'])==11
    assert host.project('player1',extras='player')['viewExtras']['notifications']['items']
    call(host,'notification.ack',{'notificationId':notice['notificationId']},'ack-extra','player1')
    assert not host.project('player1',extras='player')['viewExtras']['notifications']['items']
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):host.project('player1',extras='keeper')
    state=host.state();state['members']['player1']['active']=False;host.commit(state)
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):host.project('player1',extras='auto')


def test_extras_hold_one_authority_snapshot(host,monkeypatch):
    entered=threading.Event();resume=threading.Event();changed=threading.Event()
    original=host.knowledge.capabilities
    def blocked(*args,**kw):entered.set();assert resume.wait(5);return original(*args,**kw)
    monkeypatch.setattr(host.knowledge,'capabilities',blocked)
    def revoke():
        with host.lock:
            state=host.state();state['members']['player1']['active']=False;host.commit(state);changed.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        reading=pool.submit(host.project,'player1',extras='auto');assert entered.wait(5)
        changing=pool.submit(revoke);assert not changed.wait(.05)
        resume.set();assert reading.result()['viewExtras']['mode']=='player';changing.result()
    with pytest.raises(DomainError):host.project('player1',extras='auto')


def test_extras_http_validation_current_auth_and_compatibility(host):
    with TestClient(create_app(host,8765),base_url='http://127.0.0.1:8765') as client:
        client.headers['origin']='http://127.0.0.1:8765'
        assert client.get('/api/v1/view?extras=keeper').status_code==401
        client.post('/api/v1/login',json={'loginName':'player1','password':'test-password'})
        assert 'viewExtras' not in client.get('/api/v1/view').json()
        assert client.get('/api/v1/view?extras=auto').json()['viewExtras']['mode']=='player'
        assert client.get('/api/v1/view?extras=keeper').status_code==403
        for query in ('extras=','extras=invalid','extras=player&extras=keeper','extras=player&accountId=kp'):
            assert client.get('/api/v1/view?'+query).json()=={'code':'INPUT_INVALID'}
