"""Recoverable, fail-closed local administration across identity and room stores."""
import copy
import time
from uuid import UUID, uuid4
from .errors import DomainError, require


def usable(account):
    return bool(account and not account.get('disabled') and not account.get('deleted')
                and not account.get('hostAdminPending'))


def viable_kp(room, identities, excluding=None):
    return any(key != excluding and value['active'] and value['role'] == 'kp'
               and usable(identities.get(key)) for key, value in room['members'].items())


def receipt(host, request_id):
    with host.lock:
        return copy.deepcopy(host.identity.store.snapshot()[1].get('hostAdminReceipts', {}).get(
            request_id, {'requestId': request_id, 'status': 'unknown'}))


def recover(host):
    for request_id, intent in list(host.identity.store.snapshot()[1].get('hostAdminRequests', {}).items()):
        if intent['status'] == 'pending':
            _finish(host, request_id)


def _finish(host, request_id):
    intent = host.identity.store.snapshot()[1]['hostAdminRequests'][request_id]
    if intent['status'] != 'pending':
        return receipt(host, request_id)
    account, operation = intent['accountId'], intent['operation']
    room = host.state()
    target = room['members'].get(account)
    if not target or target['metadata'].get('hostAccountRequestId') != request_id:
        if operation == 'create':
            require(target is None, 'MEMBER_EXISTS')
            target = {'memberId': intent['memberId'], 'accountId': account, 'role': intent['roomRole'],
                      'active': True, 'authorizationEpoch': 1, 'metadata': {}}
            room['members'][account] = target
        elif target:
            target['active'] = False
            target['authorizationEpoch'] += 1
        if target:
            target['metadata']['hostAccountRequestId'] = request_id
            host.commit(room)
    host.hit('after_host_account_room')
    generation, identities = host.identity.store.snapshot()
    target = identities['accounts'][account]
    target.pop('hostAdminPending', None)
    if operation == 'create':
        target['disabled'] = False
    result = identities['hostAdminReceipts'][request_id]
    member = host.state()['members'].get(account, {})
    result.update(status='committed', roomRole=member.get('role'), roomActive=member.get('active', False),
                  disabled=target['disabled'], deleted=bool(target.get('deleted')))
    identities['hostAdminRequests'][request_id]['status'] = 'committed'
    host.identity.store.commit(generation, identities)
    host.hit('after_host_account_final')
    return copy.deepcopy(result)


def change(host, data):
    require(isinstance(data, dict))
    operation = data.get('operation')
    required = {'requestId', 'operation', 'accountId'}
    if operation in ('create', 'password'):
        required.add('password')
    allowed = required | ({'role'} if operation == 'create' else set())
    require(operation in ('create', 'password', 'delete') and required <= set(data) <= allowed)
    try:
        UUID(data['requestId'])
    except (ValueError, TypeError, AttributeError):
        raise DomainError('INPUT_INVALID')
    account, request_id = data['accountId'], data['requestId']
    require(isinstance(account, str) and 1 <= len(account) <= 80 and account == account.strip()
            and not any(ord(char) < 32 for char in account))
    role = data.get('role', 'player')
    require(role in ('player', 'kp'))
    if operation in ('create', 'password'):
        require(isinstance(data['password'], str) and 8 <= len(data['password']) <= 1024)
    with host.lock:
        recover(host)
        generation, identities = host.identity.store.snapshot()
        receipts = identities.setdefault('hostAdminReceipts', {})
        previous = receipts.get(request_id)
        if previous:
            require(previous['operation'] == operation and previous['accountId'] == account, 'COMMAND_ID_CONFLICT')
            if operation == 'create' and 'requestedRole' in previous:
                require(previous['requestedRole'] == role, 'COMMAND_ID_CONFLICT')
            # A retry never compares or resets its password. No extra password
            # verifier or plaintext credential is retained in the journal.
            return copy.deepcopy(previous)
        require(len(receipts) < 10000, 'LIMIT_EXCEEDED')
        result = {'requestId': request_id, 'operation': operation, 'accountId': account,
                  'status': 'pending', 'actor': 'local-host-user', 'time': time.time()}
        if operation == 'create':
            result['requestedRole'] = role
        room = host.state()
        target = identities['accounts'].get(account)
        try:
            if operation == 'create':
                require(target is None, 'ACCOUNT_EXISTS')
                require(account not in room['members'], 'MEMBER_EXISTS')
            else:
                require(target is not None, 'NOT_VISIBLE')
                require(not target.get('deleted'), 'ACCOUNT_DELETED')
                if operation == 'delete':
                    require(viable_kp(room, identities['accounts'], excluding=account), 'LAST_KP_REQUIRED')
        except DomainError as exc:
            result.update(status='rejected', code=exc.code)
            receipts[request_id] = result
            host.identity.store.commit(generation, identities)
            return copy.deepcopy(result)
        result['revokedSessions'] = sum(session['accountId'] == account for session in identities['sessions'].values())
        if operation == 'create':
            identities['accounts'][account] = {'accountId': account, 'loginName': account, 'nickname': account,
                'passwordHash': host.identity.hasher.hash(data['password']), 'disabled': True, 'hostAdminPending': request_id}
        else:
            identities['sessions'] = {key: session for key, session in identities['sessions'].items()
                                      if session['accountId'] != account}
            if operation == 'password':
                target['passwordHash'] = host.identity.hasher.hash(data['password'])
                member = room['members'].get(account, {})
                result.update(status='committed', roomRole=member.get('role'), roomActive=member.get('active', False),
                              disabled=target['disabled'], deleted=False)
            else:
                target.update(disabled=True, deleted=True, deletedAt=result['time'], hostAdminPending=request_id)
        receipts[request_id] = result
        if operation != 'password':
            identities.setdefault('hostAdminRequests', {})[request_id] = {
                'requestId': request_id, 'accountId': account, 'operation': operation, 'status': 'pending',
                'roomRole': role if operation == 'create' else room['members'].get(account, {}).get('role'),
                'memberId': uuid4().hex if operation == 'create' else None}
        host.identity.store.commit(generation, identities)
        host.hit('after_host_account_intent')
        return copy.deepcopy(result) if operation == 'password' else _finish(host, request_id)
