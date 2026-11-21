"""Durable recipient inbox, reviewed source binding, and crash-safe acknowledgement."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from onlinecoc.errors import DomainError
from onlinecoc.gateway import InProcessTransport
from onlinecoc.model import validate
from onlinecoc.notifications import SCHEMAS, records
from onlinecoc.server import create_app
from test_host import host, message, invoke


def call(h, op, args, identifier, account='kp'):
    return h.command(account, message(h, account, op, args, identifier))


def action(h, identifier='change'):
    result = call(h, 'entity.update', {'id': 'actor-player1', 'numbers': {'hp': 8}}, identifier)
    assert result['status'] == 'committed'
    return result


def args(source='change', recipients=None, text='生命值已调整为 8'):
    return {'sourceCommandId': source, 'sourceOp': 'entity.update',
            'recipientAccountIds': recipients or ['player1'], 'text': text}


def send(h, source='change', identifier='notify', recipients=None):
    result = call(h, 'notification.send', args(source, recipients), identifier)
    assert result['status'] == 'committed', result
    return result['result']


def test_offline_delivery_restart_ack_and_durable_deduplication(host):
    action(host)
    notice = send(host)
    generation = host.store.generation
    page = host.notifications('player1')
    assert Draft202012Validator(SCHEMAS['page']).is_valid(page)
    assert page['items'][0]['notificationId'] == notice['notificationId']
    assert page['items'][0]['source'] == {'commandId': 'change', 'op': 'entity.update', 'status': 'committed'}
    assert host.notifications('player2')['items'] == host.notifications('kp')['items'] == []
    assert host.store.generation == generation
    assert 'numbers' not in json.dumps(page) and 'recipientAccountIds' not in json.dumps(page)
    host.close(); host.__init__(host.path)
    assert host.notifications('player1') == page
    assert send(host, identifier='retry-new-id') == notice
    ack = call(host, 'notification.ack', {'notificationId': notice['notificationId']}, 'ack', 'player1')
    assert ack['status'] == 'committed' and host.notifications('player1')['items'] == []
    assert host.receipt('player1', 'ack') == ack
    duplicate = call(host, 'notification.ack', {'notificationId': notice['notificationId']}, 'ack-again', 'player1')
    assert duplicate['result'] == ack['result']
    host.close(); host.__init__(host.path)
    assert host.notifications('player1')['items'] == []
    assert send(host, identifier='after-ack') == notice
    assert host.notifications('player1')['items'] == [] and len(records(host.state())) == 1


def test_recipient_isolation_conflict_and_independent_ack(host):
    action(host); notice = send(host, recipients=['player1', 'player2'])
    assert send(host, identifier='reordered', recipients=['player2', 'player1']) == notice
    changed = call(host, 'notification.send', args(text='Different'), 'different')
    assert changed['code'] == 'NOTIFICATION_CONFLICT'
    assert call(host, 'notification.send', args(recipients=['player1']), 'other-audience')['code'] == 'NOTIFICATION_CONFLICT'
    assert call(host, 'notification.ack', {'notificationId': notice['notificationId']}, 'kp-ack')['code'] == 'NOT_VISIBLE'
    assert call(host, 'notification.ack', {'notificationId': notice['notificationId']}, 'pl-ack', 'player1')['status'] == 'committed'
    assert host.notifications('player1')['items'] == [] and len(host.notifications('player2')['items']) == 1


@pytest.mark.parametrize('status', ['missing', 'pending', 'rejected', 'unknown'])
def test_unsuccessful_or_unknown_source_never_reports_success(host, status):
    if status != 'missing':
        state = host.state()
        state['commands']['kp:change'] = {'id': 'change', 'account': 'kp', 'op': 'entity.update',
            'status': status, 'receipt': {'commandId': 'change', 'status': status}}
        host.commit(state)
    result = call(host, 'notification.send', args(), 'notify')
    assert result['status'] == 'rejected' and result['code'] == 'NOTIFICATION_SOURCE_NOT_COMMITTED'
    assert not records(host.state()) and host.notifications('player1')['items'] == []


def test_source_operation_sender_and_recipient_permissions(host):
    action(host)
    assert call(host, 'notification.send', {**args(), 'sourceOp': 'entity.patch'}, 'wrong-op')['code'] == 'NOTIFICATION_SOURCE_INVALID'
    assert call(host, 'notification.send', args(), 'player-send', 'player1')['code'] == 'PERMISSION_DENIED'
    call(host, 'member.update', {'accountId': 'player2', 'role': 'kp'}, 'promote')
    assert call(host, 'notification.send', args(), 'other-kp', 'player2')['code'] == 'NOTIFICATION_SOURCE_NOT_COMMITTED'
    call(host, 'member.update', {'accountId': 'player1', 'active': False}, 'revoke')
    assert call(host, 'notification.send', args(), 'inactive-target')['code'] == 'PERMISSION_DENIED'
    assert not records(host.state())


def test_revocation_and_rejoin_do_not_resurrect_old_notifications(host):
    action(host); notice = send(host)
    call(host, 'member.update', {'accountId': 'player1', 'active': False}, 'leave')
    with pytest.raises(DomainError, match='PERMISSION_DENIED'):host.notifications('player1')
    call(host, 'member.update', {'accountId': 'player1', 'active': True}, 'rejoin')
    assert host.notifications('player1')['items'] == []
    assert call(host, 'notification.ack', {'notificationId': notice['notificationId']}, 'late-ack', 'player1')['code'] == 'NOT_VISIBLE'
    assert send(host, identifier='resend-old-source') == notice
    assert host.notifications('player1')['items'] == []


def test_flow_admission_cannot_be_announced_as_completed(host):
    state = host.state(); state['entities']['skill-player1']['numbers']['value'] = 0; host.commit(state)
    receipt = invoke(host, 'kp', 'demo.ruling', {'actor': 'actor-player1', 'skill': 'skill-player1', 'amount': 1}, 'flow')
    assert receipt['status'] == 'committed' and 'flowId' in receipt['result']
    result = call(host, 'notification.send', {**args('flow'), 'sourceOp': 'action.invoke'}, 'notify-flow')
    assert result['code'] == 'NOTIFICATION_SOURCE_INCOMPLETE' and not records(host.state())


def test_pagination_and_partial_batch_source_location(host):
    for i in range(3):action(host, str(i)); send(host, str(i), 'notify-' + str(i))
    first = host.notifications('player1', limit=2)
    second = host.notifications('player1', after=first['nextAfter'], limit=2)
    assert first['hasMore'] and not second['hasMore']
    assert [r['source']['commandId'] for r in first['items'] + second['items']] == ['0', '1', '2']
    assert host.notifications('player2', after=0) == {'items': [], 'nextAfter': 0, 'hasMore': False}
    failed = call(host, 'entity.archive', {'id': 'actor-player1'}, 'failed-after-partial')
    assert failed['status'] == 'rejected'
    rejected = call(host, 'notification.send', {**args('failed-after-partial'), 'sourceOp': 'entity.archive'}, 'failed-notice')
    assert rejected['code'] == 'NOTIFICATION_SOURCE_NOT_COMMITTED'
    assert len(host.notifications('player1')['items']) == 3


@pytest.mark.parametrize('stage', ['before_notification_commit', 'after_notification_commit'])
@pytest.mark.parametrize('acknowledge', [False, True])
def test_process_crash_at_commit_and_retry(host, stage, acknowledge):
    action(host)
    notice = send(host) if acknowledge else None
    directory = host.path
    envelope_file = directory.parent / 'notification-envelope.json'
    host.close()
    code = '''
import json,os,sys
from pathlib import Path
from onlinecoc.host import Host
path,stage,ack,nid,output=sys.argv[1:]
h=Host(path); account='player1' if ack=='yes' else 'kp';v=h.project(account)
args={'notificationId':nid} if ack=='yes' else {'sourceCommandId':'change','sourceOp':'entity.update','recipientAccountIds':['player1'],'text':'Crash delivery'}
envelope={'protocolVersion':1,'type':'command','requestId':'crash','roomId':v['roomId'],'payload':{'commandId':'crash-op','authorityEpoch':v['authorityEpoch'],'runId':v['runId'],'catalogRevision':v['catalog']['revision'],'rulesetRevision':v['catalog']['rulesetRevision'],'op':'notification.ack' if ack=='yes' else 'notification.send','args':args}}
Path(output).write_text(json.dumps(envelope),encoding='utf-8')
h.fault=lambda value: os._exit(17) if value==stage else None
h.command(account,envelope)
os._exit(99)
'''
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join(sys.path), 'PYTHONDONTWRITEBYTECODE': '1'}
    result = subprocess.run([sys.executable, '-B', '-c', code, str(directory), stage,
        'yes' if acknowledge else 'no', notice['notificationId'] if notice else '', str(envelope_file)],
        env=env, capture_output=True, timeout=30)
    host.__init__(directory)
    assert result.returncode == 17, result.stderr.decode(errors='replace')
    envelope = json.loads(envelope_file.read_text(encoding='utf-8'))
    account = 'player1' if acknowledge else 'kp'
    assert len(host.notifications('player1')['items']) == (int(stage.startswith('before')) if acknowledge else int(stage.startswith('after')))
    if stage.startswith('before'):
        envelope = message(host, account, envelope['payload']['op'], envelope['payload']['args'], 'crash-op')
    receipt = host.command(account, envelope)
    assert receipt['status'] == 'committed' and host.command(account, envelope) == receipt
    assert len(records(host.state())) == 1
    assert len(host.notifications('player1')['items']) == (0 if acknowledge else 1)


@pytest.mark.parametrize('mutation', [
    lambda r: r.update(sourceSignature='0'*64),
    lambda r: r['source'].update(commandId='missing'),
    lambda r: r.update(id='0'*64),
    lambda r: r['acknowledgedAt'].update(player2=123),
    lambda r: r.update(text=7),
])
def test_corrupt_notification_rejected_by_room_validation(host, mutation):
    action(host); send(host)
    state = host.state(); mutation(records(state)[0])
    with pytest.raises(DomainError, match='NOTIFICATION_STATE_INVALID'):validate(state)


def test_http_read_ack_auth_origin_and_csrf(host):
    action(host); notice = send(host)
    with TestClient(create_app(host), base_url='http://127.0.0.1:8765') as client:
        assert client.get('/api/v1/notifications').status_code == 401
        client.headers['origin'] = 'http://127.0.0.1:8765'
        login = client.post('/api/v1/login', json={'loginName': 'player1', 'password': 'test-password'})
        assert login.status_code == 200
        response = client.get('/api/v1/notifications?limit=1')
        assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
        assert response.json()['items'][0]['notificationId'] == notice['notificationId']
        for query in ['limit=0', 'limit=101', 'after=-1', 'after=nan', 'accountId=player2']:
            assert client.get('/api/v1/notifications?' + query).status_code == 409
        envelope = message(host, 'player1', 'notification.ack', {'notificationId': notice['notificationId']}, 'http-ack')
        assert client.post('/api/v1/commands', json=envelope).status_code == 403
        client.headers['x-csrf-token'] = login.json()['csrf']
        client.headers['origin'] = 'http://evil.example'
        assert client.post('/api/v1/commands', json=envelope).status_code == 403
        client.headers['origin'] = 'http://127.0.0.1:8765'
        assert client.post('/api/v1/commands', json=envelope).json()['status'] == 'committed'
        assert client.get('/api/v1/notifications').json()['items'] == []


def test_transport_read_and_backup_preserve_ack_state(host, tmp_path):
    from onlinecoc.assets import Assets, restore_host
    from onlinecoc.host import Host
    from onlinecoc.room_lifecycle import fork_scope
    action(host); notice=send(host)
    call(host,'notification.ack',{'notificationId':notice['notificationId']},'before-backup','player1')
    action(host,'pending-source'); send(host,'pending-source','pending-notice')
    transport = InProcessTransport(host, 'player1')
    page = transport.notifications(limit=1)
    assert page == host.notifications('player1', limit=1)
    # Restore forks authority scope but keeps immutable action receipts and inbox facts.
    restored = fork_scope(host.state())
    from onlinecoc.notifications import page as read_page
    assert read_page(restored, 'player1') == page
    assert restored['schemaVersion'] == 4
    validate(restored)
    bundle=tmp_path/'backup';target=tmp_path/'restored'
    Assets(host).backup('kp',bundle,True)
    restore_host(bundle,target)
    with_host=Host(target)
    try:
        assert with_host.notifications('player1',limit=1)==page
        assert with_host.receipt('player1','before-backup')['status']=='committed'
        assert len(records(with_host.state()))==2
    finally:with_host.close()


@pytest.mark.parametrize('change', [
    {'recipientAccountIds': ['player1', 'player1']},
    {'recipientAccountIds': []},
    {'text': 'x'*2001},
    {'sourceStatus': 'committed'},
    {'sourceOp': 'notification.send'},
])
def test_untrusted_send_fields_rejected_before_write(host, change):
    action(host); generation = host.store.generation
    with pytest.raises(DomainError, match='INPUT_INVALID'):
        call(host, 'notification.send', {**args(), **change}, 'bad-input')
    assert host.store.generation == generation and not records(host.state())
