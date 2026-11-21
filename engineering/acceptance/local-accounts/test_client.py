import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4

import httpx
import pytest
from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed
from onlinecoc.host_control import protect
from onlinecoc.host_control_client import request

HERE=Path(__file__).resolve().parent
ROOT=HERE/'work/engine/engineering'
PASSWORD='synthetic-account-password'

@pytest.fixture
def running(tmp_path,request):
    discovery=tmp_path/'discovery';data=tmp_path/'host'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    log=(tmp_path/'server.log').open('w')
    proc=subprocess.Popen([sys.executable,'-B',str(HERE/'serve_fixture.py'),str(data),str(port),str(discovery)]+([request.param] if hasattr(request,'param') else []),stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    url=f'http://127.0.0.1:{port}'
    try:
        with httpx.Client(trust_env=False) as client:
            for _ in range(150):
                assert proc.poll() is None
                try:
                    if client.get(url+'/api/v1/capabilities',timeout=.2).status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.1)
            else:pytest.fail('isolated host startup timeout')
        yield data,discovery,url,proc
    finally:
        proc.terminate();proc.wait(timeout=10);log.close()

def cli(running,data,**env):
    directory,discovery,_,_=running
    result=subprocess.run([sys.executable,'-B',str(ROOT/'backend/scripts/run.py'),'--data-dir',str(directory),'host-account-request','--host-control-dir',str(discovery)],
        input=json.dumps(data),text=True,capture_output=True,timeout=15,env={**os.environ,**env},creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    assert result.stderr==''
    assert PASSWORD not in result.stdout
    return result.returncode,json.loads(result.stdout)

def test_real_cli_create_list_receipt_delete(running):
    code,listing=cli(running,{'operation':'list'},HTTP_PROXY='http://127.0.0.1:1',HTTPS_PROXY='http://127.0.0.1:1')
    assert code==0 and len(listing['items'])==3
    data={'operation':'create','requestId':str(uuid4()),'accountId':'cli-player','password':PASSWORD,'role':'player'}
    code,result=cli(running,data)
    assert code==0 and result['status']=='committed'
    assert cli(running,{'operation':'receipt','requestId':data['requestId']})==(0,result)
    with httpx.Client(base_url=running[2],trust_env=False,headers={'Origin':running[2]}) as client:
        assert client.post('/api/v1/login',json={'loginName':'cli-player','password':PASSWORD}).status_code==200
        assert client.get('/api/v1/view').json()['role']=='player'
        code,deleted=cli(running,{'operation':'delete','requestId':str(uuid4()),'accountId':'cli-player'})
        assert code==0 and deleted['deleted']
        assert client.get('/api/v1/me').status_code==401

def test_real_cli_last_kp_and_idempotent_errors(running):
    data={'operation':'delete','requestId':str(uuid4()),'accountId':'kp'}
    code,result=cli(running,data)
    assert code==2 and result['code']=='LAST_KP_REQUIRED' and result['status']=='rejected'
    assert cli(running,{'operation':'receipt','requestId':data['requestId']})==(2,result)

def test_live_websocket_revoked_after_delete(running):
    with httpx.Client(base_url=running[2],trust_env=False,headers={'Origin':running[2]}) as client:
        assert client.post('/api/v1/login',json={'loginName':'player1','password':PASSWORD}).status_code==200
        cookie='onlinecoc='+client.cookies['onlinecoc']
        with connect(running[2].replace('http:','ws:')+'/api/v1/connect',origin=running[2],additional_headers={'Cookie':cookie},proxy=None) as ws:
            while json.loads(ws.recv(timeout=4))['type']!='snapshot.end':pass
            assert cli(running,{'operation':'delete','requestId':str(uuid4()),'accountId':'player1'})[0]==0
            assert json.loads(ws.recv(timeout=4))['type']=='reset'
            with pytest.raises(ConnectionClosed):ws.recv(timeout=4)

def test_authority_rejects_browser_and_wrong_instance(running):
    record=json.loads(next(running[1].glob('*.json')).read_text())
    headers={'X-OnlineCOC-Instance':record['instanceId'],'X-OnlineCOC-Host-Key':protect(base64.b64decode(record['protectedKey']),decrypt=True).decode()}
    with httpx.Client(base_url=running[2],trust_env=False) as client:
        assert client.get('/api/v1/host-control/accounts').status_code==403
        assert client.get('/api/v1/host-control/accounts',headers={**headers,'Origin':running[2]}).status_code==403
        assert client.get('/api/v1/host-control/accounts',headers={**headers,'X-OnlineCOC-Instance':'wrong'}).status_code==403

def test_stale_foreign_and_stopped_discovery(running,tmp_path):
    record=json.loads(next(running[1].glob('*.json')).read_text())
    (running[1]/'stale.json').write_text(json.dumps({**record,'url':'http://127.0.0.1:1'}))
    (running[1]/'foreign.json').write_text(json.dumps({**record,'dataDirectory':str(tmp_path/'different')}))
    assert cli(running,{'operation':'list'})[0]==0
    running[3].terminate();running[3].wait(timeout=10)
    code,result=cli(running,{'operation':'list'})
    assert code==2 and result['code']=='HOST_NOT_RUNNING'

@pytest.mark.parametrize('running',['after_host_account_final'],indirect=True)
def test_committed_post_loses_reply_then_recovers_original_id(running,tmp_path):
    data={'operation':'create','requestId':str(uuid4()),'accountId':'lost-reply','password':PASSWORD}
    code,result=cli(running,data)
    assert code==2 and result['code']=='HOST_CONTROL_OUTCOME_UNKNOWN'
    assert running[3].wait(timeout=5)==77
    port=running[2].rsplit(':',1)[1]
    with (tmp_path/'restart.log').open('w') as log:
        proc=subprocess.Popen([sys.executable,'-B',str(HERE/'serve_fixture.py'),str(running[0]),port,str(running[1])],stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            with httpx.Client(trust_env=False) as client:
                for _ in range(100):
                    try:
                        if client.get(running[2]+'/api/v1/capabilities',timeout=.2).status_code==200:break
                    except httpx.HTTPError:pass
                    time.sleep(.1)
                else:pytest.fail('restart timeout')
            code,receipt=cli(running,{'operation':'receipt','requestId':data['requestId']})
            assert code==0 and receipt['status']=='committed'
            assert cli(running,{**data,'password':'changed-retry-value'})==(0,receipt)
            assert len([a for a in cli(running,{'operation':'list'})[1]['items'] if a['accountId']=='lost-reply'])==1
        finally:proc.terminate();proc.wait(timeout=10)
