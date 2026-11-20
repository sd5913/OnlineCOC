"""Durable, explicitly addressed receipts of successful host actions."""
import copy
import hashlib
import json

from jsonschema import Draft202012Validator
from onlinecoc_data import canonical
from .contracts import ROOT
from .errors import require
from .model import member

SCHEMAS = json.loads((ROOT / 'contracts/notifications.json').read_text(encoding='utf-8'))
SOURCE_OPS = frozenset(('entity.create', 'entity.update', 'entity.patch', 'entity.archive',
    'relation.set', 'relation.remove', 'progress.set', 'asset.attach', 'asset.remove',
    'action.invoke', 'behavior.invoke', 'publication.apply'))


def identifier(account, command_id):
    return hashlib.sha256(canonical([account, command_id])).hexdigest()


def records(state):
    return [row for row in state['outbox'] if isinstance(row, dict) and row.get('kind') == 'notification']


def validate(state):
    ids, sequences = set(), set()
    for row in records(state):
        require(Draft202012Validator(SCHEMAS['record']).is_valid(row), 'NOTIFICATION_STATE_INVALID')
        source = state['commands'].get(row['senderAccountId'] + ':' + row['source']['commandId'])
        require(source and source.get('status') == 'committed' and source.get('receipt', {}).get('status') == 'committed'
            and source.get('op') == row['source']['op'] in SOURCE_OPS
            and source.get('signature') == row['sourceSignature'], 'NOTIFICATION_STATE_INVALID')
        require(row['id'] == identifier(row['senderAccountId'], row['source']['commandId'])
            and row['id'] not in ids and row['sequence'] not in sequences, 'NOTIFICATION_STATE_INVALID')
        require(set(row['recipientAuthorization']) == set(row['recipientAccountIds'])
            and set(row['acknowledgedAt']) <= set(row['recipientAccountIds'])
            and row['senderAccountId'] in state['members']
            and all(a in state['members'] for a in row['recipientAccountIds']), 'NOTIFICATION_STATE_INVALID')
        ids.add(row['id']); sequences.add(row['sequence'])


def entitled(state, account, row):
    current = member(state, account)
    return row['recipientAuthorization'].get(account) == {
        'memberId': current['memberId'], 'authorizationEpoch': current['authorizationEpoch']}


def page(state, account, after=0, limit=50):
    member(state, account)
    require(type(after) is int and 0 <= after <= 2**53-1 and type(limit) is int and 1 <= limit <= 100, 'INPUT_INVALID')
    pending = sorted((r for r in records(state) if r['sequence'] > after
        and entitled(state, account, r) and account not in r['acknowledgedAt']), key=lambda r: r['sequence'])
    items = [{'notificationId': r['id'], 'sequence': r['sequence'], 'senderAccountId': r['senderAccountId'],
        'text': r['text'], 'createdAt': r['createdAt'], 'source': copy.deepcopy(r['source'])} for r in pending[:limit]]
    return {'items': items, 'nextAfter': items[-1]['sequence'] if items else after, 'hasMore': len(pending) > limit}


def apply(state, account, op, args, now):
    actor = member(state, account)
    if op == 'notification.ack':
        row = next((r for r in records(state) if r['id'] == args['notificationId']), None)
        require(row and entitled(state, account, row), 'NOT_VISIBLE')
        row['acknowledgedAt'].setdefault(account, now)
        return {'notificationId': row['id'], 'acknowledgedAt': row['acknowledgedAt'][account]}
    require(op == 'notification.send' and actor['role'] == 'kp', 'PERMISSION_DENIED')
    source = state['commands'].get(account + ':' + args['sourceCommandId'])
    require(source and source.get('status') == 'committed' and source.get('receipt', {}).get('status') == 'committed',
        'NOTIFICATION_SOURCE_NOT_COMMITTED')
    require(source.get('op') == args['sourceOp'] in SOURCE_OPS, 'NOTIFICATION_SOURCE_INVALID')
    # A flow-start receipt confirms admission, not completion of its later steps.
    result = source['receipt'].get('result')
    require(not source.get('flowId') and not (isinstance(result, dict) and 'flowId' in result), 'NOTIFICATION_SOURCE_INCOMPLETE')
    require(args['text'].strip(), 'INPUT_INVALID')
    recipients = sorted(args['recipientAccountIds'])
    nid = identifier(account, args['sourceCommandId'])
    existing = next((r for r in records(state) if r['id'] == nid), None)
    if existing:
        require(existing['recipientAccountIds'] == recipients and existing['text'] == args['text']
            and existing['source']['op'] == args['sourceOp'], 'NOTIFICATION_CONFLICT')
        return {'notificationId': nid, 'sequence': existing['sequence']}
    require(len(records(state)) < 10000, 'LIMIT_EXCEEDED')
    authorizations = {}
    for recipient in recipients:
        target = member(state, recipient)
        authorizations[recipient] = {k: target[k] for k in ('memberId', 'authorizationEpoch')}
    sequence = max((r['sequence'] for r in records(state)), default=0) + 1
    state['outbox'].append({'kind': 'notification', 'schemaVersion': 1, 'id': nid, 'sequence': sequence,
        'senderAccountId': account, 'recipientAccountIds': recipients, 'recipientAuthorization': authorizations,
        'text': args['text'], 'createdAt': now, 'sourceSignature': source['signature'],
        'source': {'commandId': args['sourceCommandId'], 'op': args['sourceOp'], 'status': 'committed'}, 'acknowledgedAt': {}})
    return {'notificationId': nid, 'sequence': sequence}
