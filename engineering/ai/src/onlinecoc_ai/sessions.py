"""User-owned room conversations; provenance stays with each original request."""
import copy
import uuid

from onlinecoc.model import member
from .errors import require
from .access import can_use, policy

DEFAULTS = {'pinned': False, 'historyTurns': 4, 'renderMode': 'formatted', 'showDiagnostics': True}

def public(record):
    return {**DEFAULTS, **{k:v for k,v in record.items() if k != 'requestIds'}}


class Sessions:
    def __init__(self, application):
        self.app = application
        self.repository = application.repository
        self.host = application.host

    def _record(self, account, identifier, state=None):
        with self.host.lock:role = can_use(self.host, self.repository, account)
        state = state or self.repository.state()
        record = state['settings'].get('sessions', {}).get(identifier)
        require(record and not record.get('deleted') and (record['owner'] == account or role == 'kp'), 'NOT_VISIBLE')
        require(role == 'kp' or record.get('accessLevel', 'player') == 'player', 'NOT_VISIBLE')
        return copy.deepcopy(record)

    def list(self, account, archived=False):
        with self.host.lock:role = can_use(self.host, self.repository, account)
        records = self.repository.state()['settings'].get('sessions', {}).values()
        return {'items': sorted([public(r) | {'requestCount': len(r['requestIds'])}
            for r in records if not r.get('deleted') and (role == 'kp' or r['owner'] == account and r.get('accessLevel', 'player') == 'player') and r['archived'] == archived], key=lambda x: (x['pinned'], x['updatedAt']), reverse=True), 'access': self.access(account)}

    def access(self, account):
        with self.host.lock:role = member(self.host.state(), account)['role']
        p = policy(self.repository)
        try:
            from .knowledge import service
            port=service(self.host,account)
            knowledge=port.capabilities(account,player=True)
        except Exception:knowledge={'status':'unavailable'}
        return {'role': role, 'canChat': role == 'kp' or p['allowPlayerChat'],
            'knowledge':{'mode':'strict-known','status':knowledge['status'],
                'notice':'玩家会话只使用本人已知记录；观察记录不代表当前场景，未知内容可请 KP 揭示。' if knowledge['status']=='ready' else '知识服务尚未就绪，玩家 AI 暂不读取游戏资料。'},
            'defaultLevel': 'administrator' if role == 'kp' else 'player',
            **{k: v for k, v in p.items() if k != 'principal'}}

    def get(self, account, identifier):
        record = self._record(account, identifier)
        # Reuse the existing read policy; old model output is not a bypass.
        items = [];before = None
        while True:
            page = self.app.tasks(account, before, 100, request_ids=set(record['requestIds']))
            items.extend(x for x in page['items'] if x['requestId'] in record['requestIds'])
            before = page['nextBefore']
            if not before:break
        state = self.repository.state()
        for item in items:
            request = state['requests'][item['requestId']]
            if request['initiator'] == account and request['sourceKind'] == 'manual':item['text'] = request['text']
        return {'session': public(record), 'items': sorted(items, key=lambda x: x['createdAt'])}

    def execute(self, account, identifier, op, args):
        with self.host.lock:role = can_use(self.host, self.repository, account)
        if op == 'ai.session.create':
            level = args.get('accessLevel', 'administrator' if role == 'kp' else 'player')
            require(level == 'player' or role == 'kp', 'PERMISSION_DENIED')
            record = {'sessionId': uuid.uuid4().hex, 'owner': account, 'title': args['title'].strip(), 'revision': 1,
                'accessLevel': level, 'archived': False, 'createdAt': self.host.clock(), 'updatedAt': self.host.clock(), 'requestIds': []}
            require(record['title'], 'INPUT_INVALID')
            def create(state):
                sessions = state['settings'].setdefault('sessions', {})
                require(sum(not s.get('deleted') for s in sessions.values()) < 200 and len(sessions) < 5000, 'LIMIT_EXCEEDED')
                sessions[record['sessionId']] = record
                return public(record)
            return self.repository.update(create)
        if op in ('ai.session.update', 'ai.session.delete'):
            def update(state):
                record = self._record(account, args['sessionId'], state)
                require(record['revision'] == args['revision'], 'SESSION_VERSION_CONFLICT')
                if op == 'ai.session.delete':
                    record.update(deleted=True, archived=True)
                    for rid in record['requestIds']:
                        state['requests'][rid]['status'] = 'cancelled'
                        tid = state['settings'].get('dispatch', {}).get(rid)
                        if tid in state['tasks']:
                            state['tasks'][tid].update(status='cancelled', error='SESSION_DELETED', lease=None)
                            state['requests'][tid]['status'] = 'cancelled'
                if 'title' in args:
                    require(args['title'].strip(), 'INPUT_INVALID');record['title'] = args['title'].strip()
                if 'archived' in args:record['archived'] = args['archived']
                for key in DEFAULTS:
                    if key in args:record[key] = args[key]
                record.update(revision=record['revision'] + 1, updatedAt=self.host.clock())
                state['settings']['sessions'][record['sessionId']] = record
                return public(record)
            return self.repository.update(update)
        require(op == 'ai.session.submit', 'INPUT_INVALID')
        record = self._record(account, args['sessionId'])
        require(record['owner'] == account, 'SESSION_OWNER_REQUIRED')
        if self.app.rulings.is_confirmation(args['text']) and role=='kp' and record['accessLevel']=='administrator':
            confirmation=self.app.rulings.confirm_session(account,record)
            if confirmation is not None:return confirmation
        return self.app._execute(account, 'session:' + identifier, 'ai.request.create',
            {'sourceKind': 'manual', 'text': args['text']}, session_id=args['sessionId'])
