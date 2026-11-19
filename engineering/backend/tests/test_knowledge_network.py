import json
import hashlib
import pytest
from fastapi.testclient import TestClient
from onlinecoc.server import create_app
from onlinecoc.assets import Assets, restore_host
from onlinecoc.room_migration import convert_file
from onlinecoc.room_validation import check_file
from onlinecoc.host import Host
from onlinecoc_data import canonical
from test_knowledge import host, install, observe, command, descriptor, provider


def login(client,account):
    client.headers['origin']='http://127.0.0.1:8765'
    r=client.post('/api/v1/login',json={'loginName':account,'password':'test-password'})
    assert r.status_code==200,r.text
    client.headers['x-csrf-token']=r.json()['csrf']

def test_http_authority_and_all_five_routes(host):
    install(host);grant=observe(host)
    with TestClient(create_app(host),base_url='http://127.0.0.1:8765') as c:
        login(c,'player1')
        assert c.get('/api/v1/knowledge/capabilities').json()['status']=='ready'
        page=c.post('/api/v1/knowledge/search',json={}).json();ref=page['items'][0]['ref']
        assert c.post('/api/v1/knowledge/read',json={'refs':[ref]}).json()['items'][0]['data']
        assert c.post('/api/v1/knowledge/grants/query',json={}).status_code==403
        del c.headers['x-csrf-token']
        assert c.post('/api/v1/knowledge/read',json={'refs':[ref]}).status_code==403
        login(c,'player2')
        assert c.post('/api/v1/knowledge/read',json={'refs':[ref]}).status_code==404
        login(c,'kp')
        assert c.post('/api/v1/knowledge/grants/query',json={}).json()['items'][0]['grantId']==grant['grantId']
        before=host.store.generation
        preview=c.post('/api/v1/knowledge/preview',json={'policyId':'case-files','resource':{'namespace':'case','kind':'witness','id':'actor-player1'},'facetIds':['identity']})
        assert preview.json()['sourceRevision']=='1'
        assert before==host.store.generation

def test_k17_ws_revocation_before_end_resets(host):
    install(host);grant=observe(host);fired=[]
    def fault(stage):
        if stage=='before_snapshot_end' and not fired:
            fired.append(stage)
            command(host,'knowledge.revoke',{'grantId':grant['grantId'],'expectedRevision':1,'reason':'撤权屏障'})
    host.fault=fault
    with TestClient(create_app(host),base_url='http://127.0.0.1:8765') as c:
        login(c,'player1')
        with c.websocket_connect('ws://127.0.0.1:8765/api/v1/connect',headers={'origin':'http://127.0.0.1:8765'}) as ws:
            frames=[]
            for _ in range(10):
                frame=ws.receive_json();frames.append(frame)
                if frame['type']=='reset':break
            assert frames[-1]['type']=='reset'
            assert not any(f['type']=='snapshot.end' for f in frames)
    assert fired

@pytest.mark.parametrize('kind',['room','snapshot','backup'])
def test_k23_explicit_conversion_original_bytes_unchanged(host,tmp_path,kind):
    # Generate an isolated v3 source without querying or auto-converting it.
    bundle=tmp_path/'v3-backup';Assets(host).backup('kp',bundle,True)
    state=host.state();state['schemaVersion']=3;state.pop('knowledge')
    room=tmp_path/'v3.json';room.write_bytes(canonical(state))
    env=json.loads((bundle/'room.json').read_bytes());env['payload']=state;env['digest']=hashlib.sha256(canonical(state)).hexdigest()
    raw=canonical(env);(bundle/'room.json').write_bytes(raw)
    manifest=json.loads((bundle/'manifest.json').read_bytes());manifest['roomDigest']=hashlib.sha256(raw).hexdigest();(bundle/'manifest.json').write_bytes(canonical(manifest))
    source={'room':room,'snapshot':bundle/'room.json','backup':bundle}[kind]
    original={str(p):p.read_bytes() for p in bundle.rglob('*') if p.is_file()};original[str(room)]=room.read_bytes()
    target=tmp_path/('converted' if kind=='backup' else 'converted.json')
    result=convert_file(source,target,kind);check_file(target,kind)
    assert result['historicalKnowledgeImported'] is False
    for name,data in original.items():
        from pathlib import Path
        assert Path(name).read_bytes()==data
    if kind=='backup':
        restore_host(target,tmp_path/'restored')
        h=Host(tmp_path/'restored')
        try:assert h.state()['schemaVersion']==4 and not h.state()['knowledge']['grants']
        finally:h.close()

def test_k22_backup_restore_forks_knowledge_scope(host,tmp_path):
    install(host);observe(host);old=host.knowledge.search('player1',{})['items'][0]['ref']
    Assets(host).backup('kp',tmp_path/'bundle',True)
    restore_host(tmp_path/'bundle',tmp_path/'copy')
    h=Host(tmp_path/'copy')
    try:
        h.register_knowledge_provider(descriptor(),provider())
        new=h.knowledge.search('player1',{})['items'][0]['ref']
        assert new['scopeId']!=old['scopeId'] and new['id']!=old['id'] and new['digest']==old['digest']
    finally:h.close()
