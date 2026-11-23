import pytest
from onlinecoc_ai.references import References
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.context import Context
from test_entrypoints import application, command, committed
from test_coordinator import setup
from test_context import enable

def test_search_resolve_privacy_and_revision(application):
    app=application;refs=References(app.host)
    token=refs.search('kp','config')['items'][0]['token']
    assert refs.resolve('kp',[token])['items'][0]['value']
    state=app.host.state();key=next(iter(state['entities']))
    state['entities'][key]['visibility']='kp';state['entities'][key]['owner']='player2';state['entities'][key]['metadata']['secret']='must-not-leak';app.host.commit(state)
    for kind in ('entity','data','config'):
        with pytest.raises(AiError,match='REFERENCE_NOT_VISIBLE'):refs.search('player1',kind)
    with pytest.raises(AiError):refs.resolve('player1',[f'[[entity:{key}@1]]'])
    with pytest.raises(AiError,match='REFERENCE_STALE'):refs.resolve('kp',[token.rsplit('@',1)[0]+'@wrong]]'])
    with pytest.raises(AiError,match='REFERENCE_LIMIT'):refs.resolve('kp',[token]*13)

def test_context_references_are_bound_and_obey_external_policy(application):
    app=application;refs=References(app.host);token=refs.search('kp','config')['items'][0]['token']
    req=committed(command(app,'ai.request.create',{'sourceKind':'manual','text':'参考 '+token}))
    request=app.repository.state()['requests'][req['requestId']]
    with pytest.raises(AiError,match='EXTERNAL_SCOPE_DISABLED'):Context(app.proposals).capture('kp',request)
    enable(app.host,public=True)
    snapshot,payload=Context(app.proposals).capture('kp',request)
    assert len(payload['selectedReferences'])==1
    assert any(r['kind']=='configuration' for r in snapshot[0]['sourceRefs'])
    state=app.host.state();key=payload['selectedReferences'][0]['id'];state['configurations'][key]['revision']='2';app.host.commit(state)
    with pytest.raises(AiError,match='REFERENCE_STALE'):Context(app.proposals).capture('kp',request)

def test_session_mutation_and_receipt_use_one_durable_commit(application,monkeypatch):
    app=application;start=app.repository.store.generation
    envelope={'requestId':'atomic-create','authorityEpoch':app.host.epoch,'op':'ai.session.create','args':{'title':'原子会话'}}
    first=app.command('kp',envelope);committed(first)
    assert app.repository.store.generation==start+1
    assert app.command('kp',envelope)==first and app.repository.store.generation==start+1
    state=app.repository.state()
    def fail(*args):raise OSError('test disk failure')
    monkeypatch.setattr(app.repository.store,'commit',fail)
    with pytest.raises(OSError):command(app,'ai.session.create',{'title':'不能残留'})
    assert app.repository.state()==state and app.repository.pending is None

def test_detail_does_not_scan_other_session_tasks(application,monkeypatch):
    app=application;sid=committed(command(app,'ai.session.create',{'title':'范围'}))['sessionId']
    committed(command(app,'ai.session.submit',{'sessionId':sid,'text':'我的需求'}))
    original=app.tasks;seen=[]
    def tasks(*args,**kwargs):seen.append(kwargs.get('request_ids'));return original(*args,**kwargs)
    monkeypatch.setattr(app,'tasks',tasks)
    assert len(app.sessions.get('kp',sid)['items'])==1
    assert len(seen)==1 and len(seen[0])==1


def test_runtime_data_cannot_be_requested_on_behalf_of_player(application):
    refs=References(application.host)
    token=refs.search('kp','data')['items'][0]['token']
    assert refs.resolve('kp',[token])['items'][0]['value'] is not None
    with pytest.raises(AiError,match='REFERENCE_NOT_VISIBLE'):
        refs.resolve('kp',[token],initiator='player1')
    with pytest.raises(AiError,match='EXTERNAL_SCOPE_DISABLED'):
        refs.resolve('kp',[token],external_policy={'public':True,'private':False,'kp':False})
    with pytest.raises(AiError,match='REFERENCE_INVALID'):
        refs.from_text('kp','[[data:../../secret@1]]')


def test_reference_http_boundary(application):
    from test_known_runtime import install,observe
    install(application);observe(application)
    from fastapi.testclient import TestClient
    from onlinecoc.server import create_app
    from types import SimpleNamespace
    async def idle():pass
    app=create_app(application.host,ai_runtime=SimpleNamespace(application=application,start=idle,close=idle))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        assert client.get('/api/v1/ai/references').status_code==401
        client.headers['Origin']='http://127.0.0.1:8765'
        csrf=client.post('/api/v1/login',json={'loginName':'player1','password':'test-password'}).json()['csrf']
        token=client.get('/api/v1/ai/references?kind=knowledge').json()['items'][0]['token']
        assert 'items' not in client.get('/api/v1/ai/references?kind=data').json()
        assert client.post('/api/v1/ai/references/resolve',json={'tokens':[token]}).status_code==403
        client.headers['X-CSRF-Token']=csrf
        result=client.post('/api/v1/ai/references/resolve',json={'tokens':[token]})
        assert result.status_code==200 and result.json()['items'][0]['value']
        assert client.post('/api/v1/ai/references/resolve',json={'tokens':[token],'account':'kp'}).status_code==409
