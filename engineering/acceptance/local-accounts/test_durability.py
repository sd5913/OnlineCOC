import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
import pytest
from onlinecoc.host import Host
from onlinecoc.errors import DomainError

HERE=Path(__file__).resolve().parent
PASSWORD='synthetic-account-password'

@pytest.mark.parametrize('operation',['create','delete'])
@pytest.mark.parametrize('stage',['after_host_account_intent','after_host_account_room','after_host_account_final'])
def test_hard_process_exit_recovery(tmp_path,operation,stage):
    data={'requestId':str(uuid4()),'operation':operation,'accountId':'new' if operation=='create' else 'player1'}
    if operation=='create':data['password']=PASSWORD
    proc=subprocess.run([sys.executable,'-B',str(HERE/'crash_worker.py'),str(tmp_path/'host'),stage],input=json.dumps(data),text=True,capture_output=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    assert proc.returncode==77 and proc.stdout=='' and proc.stderr==''
    h=Host(tmp_path/'host')
    try:
        result=h.local_account_change(data)
        assert result['status']=='committed'
        assert h.state()['members'][data['accountId']]['active']==(operation=='create')
        assert h.state()['members'][data['accountId']]['authorizationEpoch']==(1 if operation=='create' else 2)
    finally:h.close()

@pytest.mark.parametrize('store_name',['identity','room'])
@pytest.mark.parametrize('stage',['before_publish','after_publish'])
def test_store_publish_failure_reconciles_without_duplicating(tmp_path,store_name,stage):
    h=Host(tmp_path/'host',bootstrap=PASSWORD)
    store=h.identity.store if store_name=='identity' else h.store
    def fault(at):
        if at==stage:raise OSError('simulated storage acknowledgement failure')
    store.fault=fault
    data={'requestId':str(uuid4()),'operation':'create','accountId':'durable','password':PASSWORD}
    with pytest.raises(Exception):h.local_account_change(data)
    store.fault=None;h.close()
    h=Host(tmp_path/'host')
    try:
        result=h.local_account_change(data)
        assert result['status']=='committed'
        assert h.state()['members']['durable']['authorizationEpoch']==1
        assert h.local_account_change(data)==result
    finally:h.close()
