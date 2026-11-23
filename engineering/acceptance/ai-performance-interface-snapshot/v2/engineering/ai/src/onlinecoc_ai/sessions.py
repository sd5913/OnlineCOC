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
        state = state or self.repository.read_state()
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
            from .errors import require
            require(self.host.state()['aiControl']['settings']['externalSources']['private'],'EXTERNAL_SCOPE_DISABLED')
            require(p['allowDataQueries'],'DATA_QUERIES_DISABLED')
        except Exception as exc:
            code=getattr(exc,'code','KNOWLEDGE_UNAVAILABLE')
            knowledge={'status':'unavailable' if code=='KNOWLEDGE_UNAVAILABLE' else 'blocked','code':code}
        notices={'KNOWLEDGE_UNAVAILABLE':'本房间尚未提供可用的个人知识服务，请 KP 检查配置包接入。',
            'KNOWLEDGE_EGRESS_DISABLED':'配置包禁止个人已知资料外发给 AI，请 KP 检查知识策略。',
            'EXTERNAL_SCOPE_DISABLED':'房间未允许向 AI 外发本人已知资料（私密信息），请 KP 检查服务设置。',
            'DATA_QUERIES_DISABLED':'KP 已停用 AI 资料查询；仍可提交创作申请供 KP 处理。'}
        external=self.host.state()['aiControl']['settings']['externalSources']
        return {'role': role, 'canChat': role == 'kp' or p['allowPlayerChat'],
            **({'effectiveAccess':{'roomRead':p['allowAdminRoomRead'],'dataQueries':p['allowDataQueries'],'kpExternal':external['kp'],'privateExternal':external['private'],'notice':'读写权限与资料外发分别控制；关闭 KP 外发时，隐藏资料、包指南和管理正文不会交给模型。'}} if role=='kp' else {}),
            'knowledge':{'mode':'strict-known','status':knowledge['status'],
                **({'code':knowledge['code']} if 'code' in knowledge else {}),
                'notice':notices.get(knowledge.get('code'),'玩家会话只使用本人已知记录；观察记录不代表当前场景，未知内容可请 KP 揭示。' if knowledge['status']=='ready' else '个人资料暂不可用，请 KP 检查当前会话与知识服务。')},
            'defaultLevel': 'administrator' if role == 'kp' else 'player',
            **{k: v for k, v in p.items() if k != 'principal'}}

    def get(self, account, identifier, *, delivered=False):
        with self.host.lock,self.repository.read_scope():
            return self._get(account,identifier,delivered=delivered)

    def _get(self, account, identifier, *, delivered=False):
        record = self._record(account, identifier)
        # Reuse the existing read policy; old model output is not a bypass.
        items = [];before = None
        while True:
            page = self.app.tasks(account, before, 100, request_ids=set(record['requestIds']), delivered=delivered)
            items.extend(x for x in page['items'] if x['requestId'] in record['requestIds'])
            before = page['nextBefore']
            if not before:break
        state = self.repository.read_state()
        for item in items:
            request = state['requests'][item['requestId']]
            if request['initiator'] == account and request['sourceKind'] == 'manual':
                from .reviews import request_text
                item['text'] = request_text(self.repository,request,state)
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
        related=args.get('replyToRequestId')
        if related:
            from .review_queue import canonical_request
            related=canonical_request(self.repository.state(),related)
            require(related in record['requestIds'],'NOT_VISIBLE')
        token,prior=self.app.queue.submission(account,record['sessionId'],'session',args)
        if prior:return prior
        result=self.app._execute(account, 'session:' + identifier, 'ai.request.create',
            {'sourceKind': 'manual', 'text': args['text']}, session_id=args['sessionId'])
        self.app.queue.bind(result['requestId'],related=related)
        self.app.queue.save_submission(token,result['requestId'])
        return result
