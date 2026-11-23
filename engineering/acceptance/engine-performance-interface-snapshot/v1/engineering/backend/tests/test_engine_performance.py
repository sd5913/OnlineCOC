"""Optimization boundaries: fresh interpreters, exact cache keys and durable snapshots."""
import copy
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

import pytest
from jsonschema import Draft202012Validator
from onlinecoc import contracts, registry, chat
from onlinecoc.assets import Assets, verify_bundle
from onlinecoc.errors import DomainError
from onlinecoc.lua_runtime import execute
from onlinecoc.model import demo_state
from onlinecoc.worker_process import _POOL, execute_request
from onlinecoc.knowledge import HostStateProvider
from test_host import host
from test_knowledge import install, observe, command, descriptor


def job():
    return {'kind':'run','rule':'isolated','input':{},'mode':'action',
            'account':'player1','state':demo_state([('kp','kp'),('player1','player')])}


def test_pool_fresh_vm_random_and_source_version():
    sources={'isolated.lua':"local n=0; return rule('isolated',{},function(r) n=n+1; return {count=n,roll=r.roll(6)} end)"}
    for roll in (1,6,2):
        result=execute(sources,job(),lambda sides:roll)
        assert result['result']=={'count':1,'roll':roll}
        assert result['workerTimings']['loadMs']>=0
    sources['isolated.lua']="return rule('isolated',{},function() return 42 end)"
    assert execute(sources,job())['result']==42
    sources['isolated.lua']="assert(python==nil and io==nil and os==nil and debug==nil); return rule('isolated',{},function() return 7 end)"
    assert execute(sources,job())['result']==7


def test_pool_destroys_timeout_error_and_dead_process():
    _POOL.close()
    good={'safe.lua':"return rule('isolated',{},function() return 1 end)"}
    execute(good,job())
    previous=_POOL.idle[-1].process
    with pytest.raises(DomainError,match='RULE_TIMEOUT'):
        execute({'loop.lua':'while true do end'},{'kind':'inspect'},timeout=.2)
    assert previous.poll() is not None
    assert execute(good,job())['result']==1
    previous=_POOL.idle[-1].process
    with pytest.raises(DomainError):execute({'bad.lua':"error('BAD_RULE')"},{'kind':'inspect'})
    assert previous.poll() is not None
    execute(good,job());_POOL.idle[-1].process.kill();_POOL.idle[-1].process.wait(timeout=3)
    assert execute(good,job())['result']==1


def test_pool_memory_fault_replaces_worker():
    with pytest.raises(DomainError):
        execute({'memory.lua':"local t={}; while true do table.insert(t,string.format('%01000d',1)) end"},{'kind':'inspect'},timeout=3)
    assert execute({'ok.lua':"return rule('isolated',{},function() return 1 end)"},job())['result']==1


def test_pool_concurrent_requests_keep_channels_separate():
    source={'random.lua':"return rule('isolated',{},function(r) return r.roll(100) end)"}
    def run(value):return execute(source,job(),lambda sides:value)['result']
    with ThreadPoolExecutor(max_workers=8) as pool:assert list(pool.map(run,range(1,17)))==list(range(1,17))
    assert len(_POOL.idle)<=2


def test_stage_content_and_policy_cache_never_aliases(monkeypatch):
    calls=[];original=registry.execute
    monkeypatch.setattr(registry,'execute',lambda *a,**kw:(calls.append(1),original(*a,**kw))[1])
    sources={'unique-cache.lua':"return rule('cache-unique',{},function() return 17 end)"}
    a=registry.stage(sources,{'v':1});a['metadata'].clear();a['sources'].clear()
    b=registry.stage({'unique-cache.lua':"return rule('cache-unique',{},function() return 17 end)"},{'v':1})
    assert b['metadata'] and b['sources'] and len(calls)==1
    registry.stage(b['sources'],{'v':2});assert len(calls)==2
    monkeypatch.setattr(registry,'STATIC_VALIDATION_VERSION','another-policy')
    registry.stage(b['sources'],{'v':2});assert len(calls)==3


def test_projection_cache_revoke_role_registration_and_copy(host,monkeypatch):
    install(host);grant=observe(host)
    calls=[];original=host.knowledge.projection
    monkeypatch.setattr(host.knowledge,'projection',lambda *a:(calls.append(1),original(*a))[1])
    a=host.project('player1');a['knowledge']['items'].clear()
    assert host.project('player1')['knowledge']['items'] and len(calls)==1
    assert not host.project('player2')['knowledge']['items']
    assert command(host,'knowledge.revoke',{'grantId':grant['grantId'],'expectedRevision':1,'reason':'测试撤权'})['status']=='committed'
    assert not host.project('player1')['knowledge']['items']
    s=host.state();s['members']['player1']['role']='kp';s['members']['player1']['authorizationEpoch']+=1;host.commit(s)
    assert host.project('player1')['role']=='kp'
    before=len(calls);host.register_knowledge_provider(descriptor(),HostStateProvider({'identity':{'name':'name'}},live_facets=['health']))
    host.project('player1');assert len(calls)>before


def test_projection_unknown_provider_is_uncached(host,monkeypatch):
    class Unknown(HostStateProvider):pass
    install(host,Unknown({'identity':{'name':'name'}},live_facets=['health']));observe(host)
    calls=[];original=host.knowledge.projection
    monkeypatch.setattr(host.knowledge,'projection',lambda *a:(calls.append(1),original(*a))[1])
    host.project('player1');host.project('player1');assert len(calls)==2


def test_external_revision_replace_delete_corrupt_and_guard(host,tmp_path):
    path=tmp_path/'source.json';path.write_text('{"ok":true}')
    class External(HostStateProvider):
        def projection_revision(self):
            value=json.loads(path.read_bytes());st=path.stat()
            return repr((st.st_dev,st.st_ino,st.st_mtime_ns,st.st_size,value))
        def check_guard(self,guard,context):
            return json.loads(path.read_bytes())['ok'] and super().check_guard(guard,context)
    p=External({'identity':{'name':'name'}},live_facets=['health']);install(host,p);observe(host)
    assert host.project('player1')['knowledge']['items']
    replacement=tmp_path/'new.json';replacement.write_text('{"ok":false}')
    os.replace(replacement,path)
    assert not host.project('player1')['knowledge']['items']
    path.write_text('{"ok":true}');assert host.project('player1')['knowledge']['items']
    path.write_text('broken json');assert not host.project('player1')['knowledge']['items']
    path.unlink();assert not host.project('player1')['knowledge']['items']
    path.write_text('{"ok":true}');assert host.project('player1')['knowledge']['items']


def test_message_cache_full_validator_differential_same_id():
    state=demo_state([('kp','kp')]);chat.apply(state,'kp','chat.message.send',{'channelId':'general','text':'first'},1.)
    original=state['chat'];full=Draft202012Validator(contracts.MODELS['ChatState'])
    mutations=[{}, {'text':17},{'sequence':True},{'revision':0},{'senderAccountId':None},
               {'assetIds':('asset',)}, {'unexpected':'field'}, {'card':{'invalid':True}},
               {'text':'changed same ID'},{'createdAt':float('inf')},{'sequence':-1}]
    for mutation in mutations:
        value=copy.deepcopy(original);value['messages']['general'][0].update(mutation)
        expected=not any(full.iter_errors(value))
        try:contracts.validate_model('ChatState',value);actual=True
        except DomainError:actual=False
        assert actual==expected,mutation
    # Valid cached bytes may not authorize a cross-record permission mutation.
    value=copy.deepcopy(original);contracts.validate_model('ChatState',value)
    value['messages']['general'][0]['senderAccountId']='absent'
    state['chat']=value
    with pytest.raises(DomainError):chat.validate(state)


def test_backup_uses_captured_generation_and_does_not_hold_room_lock(host,tmp_path,monkeypatch):
    assets=Assets(host);aid=assets.upload('kp','a',b'asset-content')
    snapshot=assets.prepare_backup('kp',include_identity=True)
    old_generation=snapshot['generation'];old_name=snapshot['state']['name']
    entered=threading.Event();resume=threading.Event()
    from onlinecoc import assets as module
    original=module.durable_write
    def delayed(path,data):
        if Path(path).name=='room.json':entered.set();assert resume.wait(5)
        original(path,data)
    monkeypatch.setattr(module,'durable_write',delayed)
    with ThreadPoolExecutor(max_workers=1) as pool:
        writing=pool.submit(assets.write_backup,snapshot,tmp_path/'bundle')
        assert entered.wait(5)
        with host.lock:
            state=host.state();state['name']='new name';state['assets'].pop(aid);host.commit(state)
        assert assets.collect_orphans('kp',older_than=-1)==[]
        assert not (tmp_path/'bundle/manifest.json').exists()
        resume.set();writing.result(timeout=5)
    manifest,payload=verify_bundle(tmp_path/'bundle')
    assert payload['name']==old_name and aid in manifest['assets']
    assert json.loads((tmp_path/'bundle/room.json').read_bytes())['sourceGeneration']==old_generation
    assert len(assets.collect_orphans('kp',older_than=-1))==1 and not assets._backup_pins
    assert host.metrics['backups'][-1]['complete'] is True


def test_backup_fault_releases_pins_and_never_completes(host,tmp_path,monkeypatch):
    assets=Assets(host);assets.upload('kp','a',b'asset')
    def fail(*args):raise OSError('injected disk failure')
    monkeypatch.setattr('onlinecoc.assets.durable_write',fail)
    with pytest.raises(OSError):assets.backup('kp',tmp_path/'failed')
    assert not assets._backup_pins and not (tmp_path/'failed/manifest.json').exists()
    assert not host.metrics['backups'][-1]['complete']
