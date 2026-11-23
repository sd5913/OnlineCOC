"""File-delta staging preserves complete validation and durable host semantics."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from fastapi.testclient import TestClient
from onlinecoc.errors import DomainError
from onlinecoc.host import Host
from onlinecoc.registry import stage
from test_host import host,message,invoke

SOURCE="return rule('delta.check',{},function() return 17 end)"

def submit(h,args,identifier='delta',account='kp'):
    return h.command(account,message(h,account,'rule.stage.delta',args,identifier))

def base(h):
    s=h.state();return s['artifacts'][s['activeRuleset']]

def test_delta_matches_full_stage_preserves_base_and_json_null(host):
    old=base(host);snapshot=copy.deepcopy(old);entities=host.state()['entities']
    changes={'baseRevision':old['revision'],'sources':{'extra.lua':SOURCE},'data':{'value.json':None}}
    result=submit(host,changes);assert result['status']=='committed',result
    expected=stage({**old['sources'],'extra.lua':SOURCE},{**old['data'],'value.json':None})
    current=host.state()
    assert result['result']==expected['revision'] and current['artifacts'][result['result']]==expected
    assert current['artifacts'][old['revision']]==snapshot and current['activeRuleset']==old['revision']
    assert current['entities']==entities
    assert host.command('kp',message(host,'kp','rule.activate',{'revision':result['result']},'activate'))['status']=='committed'
    removed=submit(host,{'baseRevision':result['result'],'removeSources':['extra.lua'],'removeData':['value.json']},'delete')
    assert removed['result']==old['revision']

@pytest.mark.parametrize('change,code',[
    ({},'INPUT_INVALID'),({'sources':{}},'INPUT_INVALID'),
    ({'removeSources':['missing.lua']},'RULE_FILE_NOT_FOUND'),
    ({'removeData':['missing.json']},'RULE_FILE_NOT_FOUND'),
    ({'sources':{'extra.lua':SOURCE},'removeSources':['extra.lua']},'INPUT_INVALID'),
    ({'data':{'environment.json':None},'removeData':['environment.json']},'INPUT_INVALID'),
    ({'sources':{'../evil.lua':SOURCE}},'INPUT_INVALID'),
    ({'sources':{'evil.txt':SOURCE}},'INPUT_INVALID'),
    ({'sources':{'broken.lua':'not Lua'}},'RULE_FAILED'),
    ({'sources':{'duplicate.lua':"return rule('demo.attack',{},function() end)"}},'DUPLICATE_RULE'),
    ({'sources':{'dependency.lua':"return rule('dep',{},function() end,{dependencies={'missing'}})"}},'RULE_CYCLE_OR_MISSING'),
    ({'data':{'huge.json':'x'*(1024*1024)}},'LIMIT_EXCEEDED'),
    ({'sources':{'huge.lua':'--'+('x'*(1024*1024))+'\n'+SOURCE}},'LIMIT_EXCEEDED'),
])
def test_bad_delta_preserves_artifacts_and_active_revision(host,change,code):
    before=host.state();args={'baseRevision':before['activeRuleset'],**change}
    result=submit(host,args)
    assert result['status']=='rejected' and result['code']==code,result
    after=host.state()
    for key in ('artifacts','activeRuleset','entities','configurations','relations'):assert after[key]==before[key]
    assert submit(host,args)==result

@pytest.mark.parametrize('change',[
    {'baseRevision':'bad','sources':{'a.lua':SOURCE}},
    {'removeSources':['x.lua','x.lua']}, {'sources':{'x.lua':None}},
    {'data':[]}, {'extra':True}, {'removeData':[None]},
])
def test_delta_schema_rejects_invalid_envelopes(host,change):
    with pytest.raises(DomainError,match='INPUT_INVALID'):
        submit(host,{'baseRevision':base(host)['revision'],**change})

def test_maximum_rule_count_checked_after_merge(host):
    old=base(host)
    sources={str(i)+'.lua':f"return rule('extra.{i}',{{}},function() end)" for i in range(65-len(old['sources']))}
    result=submit(host,{'baseRevision':old['revision'],'sources':sources})
    assert result['status']=='rejected'
    assert host.state()['artifacts']=={old['revision']:old}

def test_deleting_dependency_revalidates_unchanged_rules(host):
    old=base(host)
    artifact=stage({**old['sources'],'dependent.lua':"return rule('dependent',{},function() end,{dependencies={'demo.lib.check'}})"},old['data'])
    state=host.state();state['artifacts'][artifact['revision']]=artifact;state['activeRuleset']=artifact['revision'];host.commit(state)
    result=submit(host,{'baseRevision':artifact['revision'],'removeSources':['check-library.lua']})
    assert result['code']=='RULE_CYCLE_OR_MISSING'
    assert host.state()['artifacts'][artifact['revision']]==artifact

def test_removing_all_sources_rejected(host):
    old=base(host)
    assert submit(host,{'baseRevision':old['revision'],'removeSources':list(old['sources'])})['status']=='rejected'

def test_stale_base_inactive_base_and_permissions(host):
    old=base(host);args={'baseRevision':old['revision'],'sources':{'extra.lua':SOURCE}}
    assert submit(host,args,account='player1')['code']=='PERMISSION_DENIED'
    accepted=message(host,'kp','rule.stage.delta',args,'accepted')
    result=host.command('kp',accepted);new=result['result']
    assert submit(host,{'baseRevision':new,'data':{'x':1}},'inactive')['code']=='VERSION_CONFLICT'
    host.command('kp',message(host,'kp','rule.activate',{'revision':new},'activate'))
    assert submit(host,args,'stale')['code']=='VERSION_CONFLICT'
    assert host.command('kp',accepted)==result

def test_delta_receipt_restart_conflict_and_revocation(host):
    args={'baseRevision':base(host)['revision'],'sources':{'extra.lua':SOURCE}}
    envelope=message(host,'kp','rule.stage.delta',args,'durable')
    result=host.command('kp',envelope);generation=host.store.generation
    host.close();host.__init__(host.path)
    assert host.command('kp',envelope)==result and host.store.generation==generation
    changed=copy.deepcopy(envelope);changed['payload']['args']['sources']['extra.lua']=SOURCE+'\n--changed'
    with pytest.raises(DomainError,match='COMMAND_ID_CONFLICT'):host.command('kp',changed)
    state=host.state();state['members']['kp']['active']=False;host.commit(state)
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):host.command('kp',envelope)

@pytest.mark.parametrize('point',['before_publish','after_publish'])
def test_delta_store_fault_atomicity_and_reply_recovery(host,point):
    before=host.state();args={'baseRevision':before['activeRuleset'],'sources':{'extra.lua':SOURCE}}
    envelope=message(host,'kp','rule.stage.delta',args,'fault');armed=True
    def fault(stage):
        nonlocal armed
        if stage==point and armed:armed=False;raise OSError('injected publication failure')
    host.store.fault=fault
    if point=='before_publish':
        with pytest.raises(OSError):host.command('kp',envelope)
        assert host.state()==before
    else:assert host.command('kp',envelope)['status']=='committed'
    host.store.fault=None;host.close();host.__init__(host.path)
    envelope['payload']['authorityEpoch']=host.epoch if point=='before_publish' else envelope['payload']['authorityEpoch']
    result=host.command('kp',envelope);assert result['status']=='committed'
    assert host.command('kp',envelope)==result
    assert host.state()['activeRuleset']==before['activeRuleset']

def test_active_precondition_and_commit_share_lock(host,monkeypatch):
    from onlinecoc import registry
    old=base(host);other=stage({**old['sources'],'other.lua':SOURCE},old['data'])
    state=host.state();state['artifacts'][other['revision']]=other;host.commit(state)
    first=message(host,'kp','rule.stage.delta',{'baseRevision':old['revision'],'data':{'x':1}},'first')
    second=message(host,'kp','rule.activate',{'revision':other['revision']},'second')
    entered=threading.Event();resume=threading.Event();changed=threading.Event();original=registry.stage_delta
    def blocked(*args):entered.set();assert resume.wait(5);return original(*args)
    def activate():r=host.command('kp',second);changed.set();return r
    monkeypatch.setattr(registry,'stage_delta',blocked)
    with ThreadPoolExecutor(max_workers=2) as pool:
        one=pool.submit(host.command,'kp',first);assert entered.wait(5)
        two=pool.submit(activate);assert not changed.wait(.05);resume.set()
        assert one.result()['status']==two.result()['status']=='committed'
    assert host.state()['activeRuleset']==other['revision']

def test_old_flow_keeps_old_rule_data_after_delta_activation(host):
    # Existing flow locks its artifact; the added source/data cannot overwrite it.
    old=base(host);r=invoke(host,'player1','demo.timed',{'actor':'actor-player1','amount':3},'flow')
    assert r['status']=='committed',r
    flow_id=r['result']['flowId'];locked=host.state()['flows'][flow_id]['ruleset']
    staged=submit(host,{'baseRevision':old['revision'],'data':{'environment.json':{'attackBonus':100}}})
    host.command('kp',message(host,'kp','rule.activate',{'revision':staged['result']},'activate'))
    assert host.state()['flows'][flow_id]['ruleset']==locked
    assert host.state()['artifacts'][locked]==old

def test_http_large_full_artifact_small_delta_and_unchanged_body_cap(host):
    from onlinecoc.server import create_app
    old=base(host);sources=copy.deepcopy(old['sources']);sources['padding.lua']='--'+('x'*70000)+'\n'+SOURCE
    large=stage(sources,{**old['data'],'padding.json':'y'*70000})
    state=host.state();state['artifacts'][large['revision']]=large;state['activeRuleset']=large['revision'];host.commit(state)
    with TestClient(create_app(host,8765),base_url='http://127.0.0.1:8765') as client:
        client.headers['origin']='http://127.0.0.1:8765'
        login=client.post('/api/v1/login',json={'loginName':'kp','password':'test-password'}).json();client.headers['x-csrf-token']=login['csrf']
        full=message(host,'kp','rule.stage',{'sources':sources,'data':large['data']},'full')
        assert client.post('/api/v1/commands',json=full).status_code==413
        assert host.receipt('kp','full')['status']=='unknown'
        delta=message(host,'kp','rule.stage.delta',{'baseRevision':large['revision'],'data':{'small.json':None}},'small')
        result=client.post('/api/v1/commands',json=delta)
        assert result.status_code==200 and result.json()['status']=='committed',result.text
        new=host.state()['artifacts'][result.json()['result']]
        assert new['sources']==large['sources'] and new['data']['padding.json']==large['data']['padding.json']
        assert client.get('/api/v1/capabilities').json()['maxCommandBytes']==65536
        assert 'rule.stage.delta' in client.get('/api/v1/contracts').json()['operations']
        delta['payload']['commandId']='still-too-large';delta['payload']['args']['data']={'x':'a'*66000}
        assert client.post('/api/v1/commands',json=delta).status_code==413
        # Legacy full staging remains supported when the request itself fits.
        full['payload']['commandId']='legacy';full['payload']['args']={'sources':old['sources'],'data':old['data']}
        assert client.post('/api/v1/commands',json=full).json()['result']==old['revision']
