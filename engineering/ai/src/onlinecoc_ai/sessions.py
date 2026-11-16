"""User-owned room conversations; provenance stays with each original request."""
import copy
import uuid

from onlinecoc.model import member
from .errors import require

DEFAULTS = {'pinned': False, 'historyTurns': 4, 'renderMode': 'formatted', 'showDiagnostics': True}

def public(record):
    return {**DEFAULTS, **{k:v for k,v in record.items() if k != 'requestIds'}}


class Sessions:
    def __init__(self, application):
        self.app = application
        self.repository = application.repository
        self.host = application.host

    def _record(self, account, identifier, state=None):
        if state is None:
            with self.host.lock:member(self.host.state(), account)
        state = state or self.repository.state()
        record = state['settings'].get('sessions', {}).get(identifier)
        require(record and record['owner'] == account, 'NOT_VISIBLE')
        return copy.deepcopy(record)

    def list(self, account, archived=False):
        with self.host.lock:member(self.host.state(), account)
        records = self.repository.state()['settings'].get('sessions', {}).values()
        return {'items': sorted([public(r) | {'requestCount': len(r['requestIds'])}
            for r in records if r['owner'] == account and r['archived'] == archived], key=lambda x: (x['pinned'], x['updatedAt']), reverse=True)}

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
        with self.host.lock:member(self.host.state(), account)
        if op == 'ai.session.create':
            record = {'sessionId': uuid.uuid4().hex, 'owner': account, 'title': args['title'].strip(), 'revision': 1,
                'archived': False, 'createdAt': self.host.clock(), 'updatedAt': self.host.clock(), 'requestIds': []}
            require(record['title'], 'INPUT_INVALID')
            def create(state):
                sessions = state['settings'].setdefault('sessions', {})
                require(len(sessions) < 200, 'LIMIT_EXCEEDED')
                sessions[record['sessionId']] = record
                return public(record)
            return self.repository.update(create)
        if op == 'ai.session.update':
            def update(state):
                record = self._record(account, args['sessionId'], state)
                require(record['revision'] == args['revision'], 'SESSION_VERSION_CONFLICT')
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
        return self.app._execute(account, 'session:' + identifier, 'ai.request.create',
            {'sourceKind': 'manual', 'text': args['text']}, session_id=args['sessionId'])
