import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
from onlinecoc.host import Host
from onlinecoc.errors import DomainError
from onlinecoc.host_control import HostControl

PASSWORD='synthetic-account-password'

def change(h,operation,account,**extra):
    data={'requestId':str(uuid4()),'operation':operation,'accountId':account,**extra}
    if operation in ('create','password'):data.setdefault('password',PASSWORD)
    return h.local_account_change(data),data

@pytest.fixture
def host(tmp_path):
    h=Host(tmp_path/'host',bootstrap=PASSWORD)
    yield h
    h.close()

@pytest.mark.parametrize('role',['player','kp'])
def test_create_login_membership_and_retry(host,role):
    result,data=change(host,'create','new-account',role=role)
    assert result['status']=='committed' and result['roomRole']==role and result['roomActive']
    token,_=host.identity.login('new-account',PASSWORD)
    assert host.auth(token)['accountId']=='new-account'
    assert host.project('new-account')['role']==role
    generation=host.store.generation
    assert host.local_account_change({**data,'password':'different-password'})==result
    assert host.store.generation==generation
    with pytest.raises(DomainError,match='AUTH_FAILED'):host.identity.login('new-account','different-password')
    with pytest.raises(DomainError,match='COMMAND_ID_CONFLICT'):host.local_account_change({**data,'role':'kp' if role=='player' else 'player'})

def test_legacy_create_default_role(host):
    result,_=change(host,'create','legacy-client')
    assert result['roomRole']=='player' and host.project('legacy-client')['role']=='player'

def test_delete_revokes_all_sessions_preserves_attribution(host,tmp_path):
    tokens=[host.identity.login('player1',PASSWORD)[0] for _ in range(2)]
    before=host.state()
    member=copy.deepcopy(before['members']['player1'])
    result,data=change(host,'delete','player1')
    assert result['status']=='committed' and result['revokedSessions']==2 and result['deleted']
    after=host.state()
    assert after['members']['player1']['memberId']==member['memberId']
    assert after['members']['player1']['authorizationEpoch']==member['authorizationEpoch']+1
    for field in ('entities','chat','commands','progress'):assert after[field]==before[field]
    for token in tokens:
        with pytest.raises(DomainError,match='AUTH_REQUIRED'):host.auth(token)
    with pytest.raises(DomainError,match='AUTH_FAILED'):host.identity.login('player1',PASSWORD)
    assert host.local_account_change(data)==result
    assert change(host,'create','player1')[0]['code']=='ACCOUNT_EXISTS'
    assert change(host,'password','player1')[0]['code']=='ACCOUNT_DELETED'
    assert 'player1' not in [x['accountId'] for x in HostControl(host,1,tmp_path/'discovery').accounts()['items']]

def test_last_viable_kp_and_stable_rejected_receipt(host):
    result,data=change(host,'delete','kp')
    assert result['code']=='LAST_KP_REQUIRED'
    change(host,'create','kp2',role='kp')
    assert host.local_account_change(data)==result
    assert change(host,'delete','kp')[0]['status']=='committed'
    assert change(host,'delete','kp2')[0]['code']=='LAST_KP_REQUIRED'

def test_inactive_kp_does_not_count(host):
    change(host,'create','kp2',role='kp')
    room=host.state();host.manage(room,'kp','member.update',{'accountId':'kp2','active':False});host.commit(room)
    assert change(host,'delete','kp')[0]['code']=='LAST_KP_REQUIRED'

def test_deleted_member_cannot_be_reactivated(host):
    change(host,'delete','player1')
    with pytest.raises(DomainError,match='ACCOUNT_UNAVAILABLE'):
        host.manage(host.state(),'kp','member.update',{'accountId':'player1','active':True,'role':'kp'})

def test_member_update_last_kp_guard(host):
    with pytest.raises(DomainError,match='LAST_KP_REQUIRED'):
        host.manage(host.state(),'kp','member.update',{'accountId':'kp','role':'player'})

def test_password_legacy_retry_and_session_revocation(host):
    token,_=host.identity.login('player2',PASSWORD)
    result,data=change(host,'password','player2',password='replacement-password')
    assert result['revokedSessions']==1 and result['status']=='committed'
    with pytest.raises(DomainError,match='AUTH_REQUIRED'):host.auth(token)
    assert host.local_account_change({**data,'password':'ignored-retry-password'})==result
    assert host.identity.login('player2','replacement-password')
    serialized=json.dumps(host.identity.store.snapshot()[1])
    assert 'replacement-password' not in serialized and 'ignored-retry-password' not in serialized

@pytest.mark.parametrize('operation',['create','delete'])
@pytest.mark.parametrize('stage',['after_host_account_intent','after_host_account_room','after_host_account_final'])
def test_restart_recovers_each_boundary(tmp_path,operation,stage):
    h=Host(tmp_path/'host',bootstrap=PASSWORD)
    data={'requestId':str(uuid4()),'operation':operation,'accountId':'new' if operation=='create' else 'player1'}
    if operation=='create':data.update(password=PASSWORD,role='player')
    def fail(at):
        if at==stage:raise RuntimeError('simulated interruption')
    h.fault=fail
    with pytest.raises(RuntimeError):h.local_account_change(data)
    receipt=h.local_account_receipt(data['requestId'])
    assert receipt['status']==('committed' if stage.endswith('final') else 'pending')
    if not stage.endswith('final'):
        with pytest.raises(DomainError,match='AUTH_FAILED'):h.identity.login(data['accountId'],PASSWORD)
    h.close()
    h=Host(tmp_path/'host')
    try:
        result=h.local_account_change(data)
        assert result['status']=='committed'
        member=h.state()['members'][data['accountId']]
        assert member['active']==(operation=='create')
        assert member['authorizationEpoch']==(1 if operation=='create' else 2)
        assert h.local_account_receipt(data['requestId'])==result
    finally:h.close()

@pytest.mark.parametrize('data',[{}, {'operation':'delete','requestId':'bad','accountId':'kp'},
    {'operation':'delete','requestId':str(uuid4()),'accountId':'kp','password':'forbidden'},
    {'operation':'create','requestId':str(uuid4()),'accountId':' x','password':PASSWORD},
    {'operation':'create','requestId':str(uuid4()),'accountId':'x','password':PASSWORD,'role':'admin'}])
def test_invalid_input_has_no_effect(host,data):
    before=(host.store.generation,host.identity.store.generation)
    with pytest.raises(DomainError):host.local_account_change(data)
    assert before==(host.store.generation,host.identity.store.generation)

def test_identity_only_legacy_account_can_be_deleted(host):
    host.identity.create('unbound',PASSWORD)
    result,_=change(host,'delete','unbound')
    assert result['status']=='committed' and not result['roomActive'] and result['roomRole'] is None
