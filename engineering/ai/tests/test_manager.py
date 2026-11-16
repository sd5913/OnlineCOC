import asyncio
import copy
import json
import os
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from onlinecoc_ai.contracts import loads
from onlinecoc_ai.manager import Manager, create_manager_app, local_url
from onlinecoc_ai.profiles import credential, load_profiles
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.vault import Vault
from test_entrypoints import application, command, committed
from test_coordinator import setup


@pytest.fixture
def manager(tmp_path):
    config = tmp_path / 'providers.json'
    config.write_bytes((Path(__file__).parents[1] / 'examples/ai-providers.json').read_bytes())
    return Manager(config, tmp_path / 'manager', vault=Vault(tmp_path / 'keys.json'))


def unlock(manager, client):
    client.headers['Origin'] = 'http://127.0.0.1:8776'
    result = client.post('/manager/api/unlock', json={'key': manager.bootstrap})
    assert result.status_code == 200, result.text
    client.headers['X-CSRF-Token'] = result.json()['csrf']


def test_local_boundary_bootstrap_csrf_and_lock(manager):
    with TestClient(create_manager_app(manager), base_url='http://127.0.0.1:8776') as client:
        assert client.get('/manager/api/providers').status_code == 403
        assert client.post('/manager/api/unlock', json={'key': manager.bootstrap}).json()['code'] == 'ORIGIN_REJECTED'
        original = manager.bootstrap;unlock(manager, client)
        assert client.post('/manager/api/unlock', json={'key': original}).status_code == 403
        assert client.get('/manager/api/providers').status_code == 200
        assert client.post('/manager/api/rooms', json={'name': 'x', 'url': 'http://127.0.0.1:8765'}, headers={'X-CSRF-Token': 'bad'}).status_code == 403
        assert client.get('/manager/api/providers', headers={'Host': 'evil.example'}).status_code == 403
        assert client.post('/manager/api/lock', json={}).status_code == 200
        assert client.get('/manager/api/providers').status_code == 403


def test_profile_cas_disable_delete_and_secret_rejected_in_config(manager):
    with TestClient(create_manager_app(manager), base_url='http://127.0.0.1:8776') as client:
        unlock(manager, client)
        profile = load_profiles(manager.config)['deepseek-main']
        profile['enabled'] = True
        payload = {'profile': profile, 'expectedRevision': 1}
        saved = client.post('/manager/api/providers', json=payload)
        assert saved.json()['revision'] == 2
        assert client.post('/manager/api/providers', json=payload).json()['code'] == 'PROFILE_VERSION_CONFLICT'
        assert client.post('/manager/api/providers/deepseek-main/delete', json={'revision': 2}).json()['code'] == 'PROFILE_MUST_BE_DISABLED'
        bad = copy.deepcopy(saved.json());bad['apiKey'] = 'test-secret'
        rejected = client.post('/manager/api/providers', json={'profile': bad, 'expectedRevision': 2})
        assert rejected.status_code == 409 and 'test-secret' not in rejected.text
        disabled = saved.json();disabled['enabled'] = False
        assert client.post('/manager/api/providers', json={'profile': disabled, 'expectedRevision': 2}).json()['revision'] == 3
        assert client.post('/manager/api/providers/deepseek-main/delete', json={'revision': 3}).status_code == 200
        assert load_profiles(manager.config) == {}


@pytest.mark.skipif(os.name != 'nt', reason='Real DPAPI acceptance requires Windows')
def test_real_dpapi_key_roundtrip_no_plaintext_and_legacy_fallback(manager, monkeypatch):
    profile = load_profiles(manager.config)['deepseek-main']
    monkeypatch.setenv(profile['credentialRef'][4:], 'environment-test-value')
    with TestClient(create_manager_app(manager), base_url='http://127.0.0.1:8776') as client:
        unlock(manager, client)
        result = client.post('/manager/api/providers/deepseek-main/credential', json={'secret': 'test-credential-for-manager'})
        assert result.json() == {'saved': True}
        assert b'test-credential-for-manager' not in manager.vault.path.read_bytes()
        assert credential(profile, vault=Vault(manager.vault.path)) == 'test-credential-for-manager'
        assert 'test-credential-for-manager' not in client.get('/manager/api/providers').text
        assert 'test-credential-for-manager' not in manager.config.read_text()
        assert client.post('/manager/api/providers/deepseek-main/credential', json={'secret': None}).json() == {'saved': False}
        assert credential(profile, vault=manager.vault) == 'environment-test-value'


@pytest.mark.parametrize('url', ['https://127.0.0.1:8765','http://192.168.1.2:8765','http://example.com:8765','http://user:pass@127.0.0.1:8765','http://127.0.0.1:8765/api','http://127.0.0.1:8765?x=1','http://127.0.0.1:99999'])
def test_room_endpoint_is_bounded(url):
    with pytest.raises(AiError):local_url(url)


def test_room_profiles_persist_but_login_does_not(manager):
    room = manager.save_room('测试房间', 'http://localhost:8765')
    restored = Manager(manager.config, manager.directory, vault=manager.vault)
    assert restored.rooms[room['id']]['url'] == 'http://127.0.0.1:8765'
    assert not restored.clients
    with pytest.raises(AiError):manager.save_room('duplicate', 'http://127.0.0.1:8765')


def test_room_bridge_never_exposes_host_control_or_shares_sessions(manager):
    async def run():
        seen=[]
        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={'ok':True})
        client=httpx.AsyncClient(base_url='http://127.0.0.1:8765', transport=httpx.MockTransport(handler))
        manager.clients[('one','room')]={'client':client,'csrf':'room-csrf'}
        try:
            with pytest.raises(AiError,match='ROOM_ROUTE_FORBIDDEN'):await manager.room_request('one','room',{'path':'host-control/accounts'})
            with pytest.raises(AiError,match='ROOM_LOGIN_REQUIRED'):await manager.room_request('two','room',{'path':'view'})
            assert await manager.room_request('one','room',{'path':'ai/commands','method':'POST','body':{'op':'test'}})=={'ok':True}
            assert seen[0].headers['x-csrf-token']=='room-csrf'
            assert 'onlinecoc-ai-manager' not in str(seen[0].headers)
        finally:await client.aclose();manager.clients.clear()
    asyncio.run(run())


def test_session_ownership_archive_idempotence_and_reopen(application):
    app=application
    s=committed(command(app,'ai.session.create',{'title':'我的会话'},'player1'))
    assert app.sessions.list('player2')['items']==[] and app.sessions.list('kp')['items']==[]
    with pytest.raises(AiError,match='NOT_VISIBLE'):app.sessions.get('player2',s['sessionId'])
    args={'sessionId':s['sessionId'],'text':'希望增加一个有限次数物品'}
    first=command(app,'ai.session.submit',args,'player1','stable-submit')
    assert command(app,'ai.session.submit',args,'player1','stable-submit')==first
    committed(first)
    detail=app.sessions.get('player1',s['sessionId'])
    assert len(detail['items'])==1 and detail['items'][0]['text']==args['text']
    current=detail['session']
    renamed=committed(command(app,'ai.session.update',{'sessionId':s['sessionId'],'revision':current['revision'],'title':'道具设计','archived':True},'player1'))
    assert not app.sessions.list('player1')['items']
    assert app.sessions.list('player1',True)['items'][0]['title']=='道具设计'
    before=len(app.repository.state()['requests'])
    assert command(app,'ai.session.submit',args,'player1')['code']=='SESSION_ARCHIVED'
    assert len(app.repository.state()['requests'])==before
    assert command(app,'ai.session.update',{'sessionId':s['sessionId'],'revision':1,'title':'stale'},'player1')['code']=='SESSION_VERSION_CONFLICT'
    committed(command(app,'ai.session.update',{'sessionId':s['sessionId'],'revision':renamed['revision'],'archived':False},'player1'))
    assert app.sessions.get('player1',s['sessionId'])['items'][0]['requestId']==first['result']['requestId']


def test_manager_static_modules_have_correct_mime_and_headers(manager):
    with TestClient(create_manager_app(manager),base_url='http://127.0.0.1:8776') as client:
        assert '房间文件夹' in client.get('/').text
        assert client.get('/components/client.js').headers['content-type'].startswith('text/javascript')
        assert client.get('/manager.js').headers['cache-control']=='no-store'
        assert 'frame-ancestors' in client.get('/').headers['content-security-policy']


def test_late_room_login_cannot_restore_locked_session(manager, monkeypatch):
    import time
    async def run():
        started, finish = asyncio.Event(), asyncio.Event()
        async def handler(request):
            started.set();await finish.wait()
            return httpx.Response(200, json={'csrf': 'room-csrf'})
        factory = httpx.AsyncClient
        monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: factory(**kw, transport=httpx.MockTransport(handler)))
        room = manager.save_room('测试', 'http://127.0.0.1:8765')
        manager.sessions['one'] = {'expires': time.monotonic() + 60, 'csrf': 'test'}
        task = asyncio.create_task(manager.login_room('one', room['id'], {'loginName': 'kp', 'password': 'fake'}))
        await started.wait();await manager.close_session('one');finish.set()
        with pytest.raises(AiError, match='MANAGER_AUTH_REQUIRED'):await task
        assert manager.clients == {}
    asyncio.run(run())


def test_concurrent_profile_edits_have_exactly_one_winner(manager):
    from concurrent.futures import ThreadPoolExecutor
    from onlinecoc_ai.profiles import save_profile
    profile = load_profiles(manager.config)['deepseek-main']
    def save():
        try:return save_profile(profile, manager.config, expected_revision=1)['revision']
        except AiError as exc:return exc.code
    with ThreadPoolExecutor(max_workers=2) as executor:results = list(executor.map(lambda _: save(), range(2)))
    assert sorted(map(str, results)) == ['2', 'PROFILE_VERSION_CONFLICT']
    assert load_profiles(manager.config)['deepseek-main']['revision'] == 2


def test_advisory_lock_is_bounded(tmp_path):
    from onlinecoc_ai.local_lock import file_lock
    with file_lock(tmp_path / 'config.json'):
        with pytest.raises(AiError, match='LOCAL_CONFIGURATION_BUSY'):
            with file_lock(tmp_path / 'config.json', timeout=.03):pass


def test_running_room_refreshes_profile_and_fails_closed(manager, tmp_path):
    from onlinecoc.host import Host
    from onlinecoc_ai.runtime import Runtime
    from onlinecoc_ai.profiles import save_profile
    host = Host(tmp_path / 'host', bootstrap='test-password')
    runtime = Runtime(host, manager.config, Path(__file__).resolve().parents[2] / 'rulepacks/demo')
    try:
        state = host.state();state['aiControl']['settings'].update(enabled=True, profileId='deepseek-main');host.commit(state)
        with pytest.raises(AiError, match='PROFILE_DISABLED'):runtime.coordinator._profile('kp')
        profile = load_profiles(manager.config)['deepseek-main'];profile['enabled'] = True
        saved = save_profile(profile, manager.config, expected_revision=1)
        assert runtime.coordinator._profile('kp')['revision'] == 2
        saved['enabled'] = False;save_profile(saved, manager.config, expected_revision=2)
        with pytest.raises(AiError, match='PROFILE_DISABLED'):runtime.coordinator._profile('kp')
        manager.config.write_text('{"profiles":[]}', encoding='utf-8')
        with pytest.raises(AiError):runtime.coordinator._profile('kp')
    finally:asyncio.run(runtime.close());host.close()
