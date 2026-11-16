"""Framework-free application commands; all actors come from host authentication."""
import copy
import threading
import uuid

from jsonschema import Draft202012Validator
from onlinecoc import chat
from onlinecoc.model import member
from .contracts import ENGINEERING, SCHEMAS, canonical, digest, loads, validate
from .errors import require
from .memory import Memory

OPERATIONS = loads((ENGINEERING / 'contracts/ai-operations.json').read_bytes())


class Application:
    def __init__(self, runtime):
        self.runtime, self.proposals = runtime, runtime.proposals
        self.coordinator = runtime.coordinator
        self.host, self.repository = self.proposals.host, self.proposals.repository
        self.memory = Memory(self.proposals)
        from .sessions import Sessions
        self.sessions = Sessions(self)
        self.lock = threading.RLock()

    def command(self, account, envelope):
        if type(envelope) is dict and envelope.get('op') in ('ai.session.create', 'ai.session.update', 'ai.session.submit'):
            # One durable commit for mutation + idempotency receipt. Lock order
            # stays host -> application -> repository, shared with context reads.
            with self.host.lock, self.lock, self.repository.transaction():
                return self._command(account, envelope)
        return self._command(account, envelope)

    def _command(self, account, envelope):
        require(type(envelope) is dict and set(envelope) == {'requestId', 'authorityEpoch', 'op', 'args'}, 'INPUT_INVALID')
        identifier, op, args = envelope['requestId'], envelope['op'], envelope['args']
        require(isinstance(identifier, str) and 1 <= len(identifier) <= 200 and isinstance(op, str) and op in OPERATIONS and type(envelope['authorityEpoch']) is str, 'INPUT_INVALID')
        schema = {**OPERATIONS[op], '$defs': SCHEMAS['$defs']}
        require(Draft202012Validator(schema).is_valid(args), 'INPUT_INVALID')
        signature, key = digest(envelope), 'api:' + account + ':' + identifier
        with self.host.lock, self.lock:
            member(self.host.state(), account)
            prior = self.repository.state()['commands'].get(key)
            if prior:
                require(prior['signature'] == signature, 'COMMAND_ID_CONFLICT')
                return self.receipt(account, identifier)
            require(envelope['authorityEpoch'] == self.host.epoch, 'STALE_AUTHORITY')
            self.repository.update(lambda s: s['commands'].update({key: {'signature': signature,
                'op': op, 'receipt': {'requestId': identifier, 'status': 'pending'}}}))
        try:
            result = self._execute(account, identifier, op, args)
            receipt = {'requestId': identifier, 'status': 'committed', 'result': result}
        except Exception as exc:
            # Cross-store operations may have committed. Do not manufacture a
            # rejection for storage/transport uncertainty; preserve queryability.
            code = getattr(exc, 'code', 'RESULT_UNKNOWN')
            receipt = {'requestId': identifier, 'status': 'unknown' if code == 'RESULT_UNKNOWN' else 'rejected', 'code': code}
        self.repository.update(lambda s: s['commands'][key].update(receipt=receipt))
        return self.receipt(account, identifier)

    def receipt(self, account, identifier):
        with self.host.lock:role = member(self.host.state(), account)['role']
        value = self.repository.state()['commands'].get('api:' + account + ':' + identifier)
        receipt = copy.deepcopy(value['receipt']) if value else {'requestId': identifier, 'status': 'unknown'}
        if value and role != 'kp' and value.get('op') not in ('ai.request.create', 'ai.request.cancel', 'ai.session.create', 'ai.session.update', 'ai.session.submit'):receipt.pop('result', None)
        result = receipt.get('result')
        if isinstance(result, dict):
            try:
                if 'sessionId' in result:self.sessions._record(account, result['sessionId'])
                proposal = result.get('proposal', result)
                if 'proposalId' in proposal and 'changeSet' in proposal:
                    self.proposals.get(account, proposal['proposalId'], proposal['revision'])
                if 'memoryId' in result and 'sourceRefs' in result:
                    from onlinecoc.ai_sources import check_sources
                    with self.host.lock:check_sources(self.host, self.host.state(), account, result['sourceRefs'])
            except Exception:
                receipt.pop('result', None)
                receipt['resultUnavailable'] = True
        return receipt

    def _execute(self, account, identifier, op, args, *, session_id=None):
        if op.startswith('ai.session.'):
            return self.sessions.execute(account, identifier, op, args)
        if op == 'ai.request.create':
            with self.host.lock:
                state = self.host.state();member(state, account)
                if args['sourceKind'] == 'chat':
                    channel = state['chat']['channels'].get(args.get('channelId'))
                    require(chat.can_read(state, account, channel), 'PERMISSION_DENIED')
                    message = next((m for m in state['chat']['messages'][channel['channelId']] if m['messageId'] == args.get('sourceId')), None)
                    require(message and not message['deleted'] and message['kind'] == 'text' and message['text'] == args['text'] and
                        str(message['revision']) == str(args.get('sourceRevision')), 'SOURCE_STALE')
                    initiator = message['senderAccountId']
                else:
                    require(not any(k in args for k in ('channelId', 'sourceId', 'sourceRevision')), 'INPUT_INVALID')
                    initiator = account
                from .references import References
                References(self.host).from_text(account, args['text'], room=state, initiator=initiator)
                rid = uuid.uuid4().hex
                request = validate('Request', {'schemaVersion': 1, 'requestId': rid, 'scopeId': state['aiControl']['scopeId'],
                    'sourceKind': args['sourceKind'], 'sourceId': args.get('sourceId', account + ':' + identifier),
                    'sourceRevision': str(args.get('sourceRevision', '1')), 'initiator': initiator, 'text': args['text'], 'intent': 'configure',
                    'dedupKey': digest({'scope': state['aiControl']['scopeId'], 'sourceKind': args['sourceKind'], 'source': args.get('sourceId', account + ':' + identifier), 'revision': str(args.get('sourceRevision', '1'))}),
                    'status': 'received', 'createdAt': self.host.clock()})
            def save(data):
                session = None
                if session_id:
                    session = data['settings'].get('sessions', {}).get(session_id)
                    require(session and session['owner'] == account, 'NOT_VISIBLE')
                    require(not session['archived'], 'SESSION_ARCHIVED')
                existing = next((r for r in data['requests'].values() if r['dedupKey'] == request['dedupKey']), None)
                if existing:return {'requestId': existing['requestId'], **({'sessionId': session_id} if session else {})}
                require(sum(r['status'] == 'received' for r in data['requests'].values()) < 64, 'QUEUE_FULL')
                if session:
                    require(len(session['requestIds']) < 100, 'LIMIT_EXCEEDED')
                    session['requestIds'].append(rid);session['revision'] += 1;session['updatedAt'] = self.host.clock()
                data['requests'][rid] = request
                return {'requestId': rid, **({'sessionId': session_id} if session else {})}
            return self.repository.update(save)
        if op == 'ai.request.cancel':
            state = self.repository.state();request = state['requests'].get(args['requestId'])
            require(request is not None, 'NOT_VISIBLE')
            with self.host.lock:
                require(request['initiator'] == account or member(self.host.state(), account)['role'] == 'kp', 'PERMISSION_DENIED')
            tid = state['settings'].get('dispatch', {}).get(request['requestId'], request['requestId'])
            if tid not in state['tasks']:tid = None
            if tid:
                task = state['tasks'][tid]
                self.coordinator.cancel(account, tid)
            for record in state['proposals'].values():
                proposal = record['revisions'][str(record['currentRevision'])]
                if proposal['requestId'] in (request['requestId'], tid):
                    principal = state['contexts'][proposal['contextRef']]['reviewPrincipal']
                    with self.host.lock:
                        m = self.host.state()['members'].get(principal, {})
                        if m.get('active') and m.get('role') == 'kp':
                            self.host.ai_proposal_head(principal, proposal['proposalId'], proposal['revision'] + 1)
            self.repository.update(lambda s: s['requests'][request['requestId']].update(status='cancelled'))
            return {'requestId': request['requestId'], 'status': 'cancelled'}
        with self.host.lock:self.host.kp(account)
        if op == 'ai.request.dispatch':
            state = self.repository.state();request = state['requests'].get(args['requestId'])
            require(request and request['status'] in ('received', 'queued'), 'REQUEST_NOT_READY')
            self.coordinator.context.capture(account, request)
            task = self.coordinator.enqueue(account, 'dispatch:' + request['requestId'], request['text'],
                source_kind=request['sourceKind'], source_id=request['sourceId'], source_revision=request['sourceRevision'], initiator=request['initiator'])
            def save(data):
                data['requests'][request['requestId']]['status'] = 'queued'
                data['settings'].setdefault('dispatch', {})[request['requestId']] = task['taskId']
            self.repository.update(save)
            return {'requestId': request['requestId'], 'taskId': task['taskId']}
        if op == 'ai.draft.create':return self.proposals.create(account, args['text'], args['changeSet'])
        if op == 'ai.proposal.revise':return self.proposals.revise(account, args['proposalId'], args['revision'], args['changeSet'], summary=args.get('summary', 'KP 修订草稿'))
        if op == 'ai.proposal.validate':return self.proposals.validate(account, args['proposalId'], args['revision'])
        if op == 'ai.memory.create':return self.memory.create(account, args['content'], args['sourceRefs'], kind=args.get('kind', 'summary'), visibility=args.get('visibility', 'kp'))
        if op == 'ai.memory.confirm':return self.memory.confirm(account, args['memoryId'], args['revision'])
        if op == 'ai.memory.revoke':return self.memory.revoke(account, args['memoryId'], args['revision'])
        if op == 'ai.settings.update':
            if hasattr(self.runtime, 'refresh_profiles'):self.runtime.refresh_profiles()
            require(args['profileId'] is None or args['profileId'] in self.coordinator.profiles, 'PROFILE_NOT_FOUND')
            if args['enabled']:require(args['profileId'] and self.coordinator.profiles[args['profileId']]['enabled'], 'PROFILE_DISABLED')
            with self.host.lock:
                self.host.kp(account);state = self.host.state()
                auto = args['auto']
                require(not auto['enabled'] or args['enabled'], 'AI_DISABLED')
                for cid in auto['channelIds']:
                    require(chat.can_read(state, account, state['chat']['channels'].get(cid)), 'NOT_VISIBLE')
                state['aiControl']['settings'] = {**copy.deepcopy(args), 'auto': {**auto, 'principal': account if auto['enabled'] else None}}
                self.host.commit(state)
                positions = {cid: state['chat']['channels'][cid]['lastSequence'] for cid in auto['channelIds']}
            self.repository.update(lambda s: s['settings'].update(autoPositions=positions, autoSeen={}))
            return state['aiControl']['settings']
        raise ValueError('Unknown AI operation')

    def tasks(self, account, before=None, limit=30, *, request_ids=None):
        require(type(limit) is int and 1 <= limit <= 100, 'INPUT_INVALID')
        with self.host.lock:
            room = self.host.state();kp = member(room, account)['role'] == 'kp'
        state = self.repository.state();results = []
        for request in state['requests'].values():
            if request_ids is not None and request['requestId'] not in request_ids:continue
            if request['requestId'] in state['settings'].get('dispatch', {}).values():continue
            if not kp and request['initiator'] != account:continue
            task = state['tasks'].get(state['settings'].get('dispatch', {}).get(request['requestId'], request['requestId']))
            if task and kp and task['account'] != account:continue
            proposal = next((r['revisions'][str(r['currentRevision'])] for r in state['proposals'].values()
                if r['revisions'][str(r['currentRevision'])]['requestId'] == (task['requestId'] if task else request['requestId'])), None)
            item = {'requestId': request['requestId'], 'status': state['requests'][task['requestId']]['status'] if task else request['status'], 'createdAt': request['createdAt']}
            if proposal and any(a['proposalId'] == proposal['proposalId'] and a['status'] == 'consumed' for a in room['aiControl']['approvals'].values()):item['status'] = 'published'
            if kp:
                if task and task.get('contextRef'):
                    context = state['contexts'].get(task['contextRef'])
                    try:
                        require(context and context['reviewPrincipal'] == account and context['scopeId'] == room['aiControl']['scopeId'] and
                            context['authorizationEpoch'] == room['members'][account]['authorizationEpoch'], 'PERMISSION_DENIED')
                        self.host.validate_ai_sources(room, account, context)
                    except Exception:
                        results.append({**item, 'status': 'published' if item['status'] == 'published' else 'stale'})
                        continue
                if request['sourceKind'] == 'chat':
                    matches = [(cid, m) for cid, messages in room['chat']['messages'].items() for m in messages if m['messageId'] == request['sourceId']]
                    if len(matches) != 1:continue
                    cid, message = matches[0]
                    if not chat.can_read(room, account, room['chat']['channels'][cid]) or message['deleted'] or str(message['revision']) != str(request['sourceRevision']):continue
                if proposal:
                    try:self.proposals.get(account, proposal['proposalId'])
                    except Exception:
                        results.append({**item, 'status': 'published' if item['status'] == 'published' else 'stale'})
                        continue
                item.update(text=request['text'], initiator=request['initiator'], taskId=task['taskId'] if task else None,
                    proposalId=proposal['proposalId'] if proposal else None, error=task['error'] if task else None,
                    response=proposal['summary'] if proposal else task.get('text') if task else None)
                if task and task.get('diagnostics'):item['diagnostics'] = copy.deepcopy(task['diagnostics'])
            results.append(item)
        results.sort(key=lambda r: (r['createdAt'], r['requestId']), reverse=True)
        if before:
            index = next((i for i, r in enumerate(results) if r['requestId'] == before), None)
            require(index is not None, 'CURSOR_INVALID');results = results[index + 1:]
        return {'items': results[:limit], 'nextBefore': results[limit - 1]['requestId'] if len(results) > limit else None}

    def proposal(self, account, key):
        proposal = self.proposals.get(account, key)
        data = self.repository.state()
        return {'proposal': proposal, 'reports': [data['reports'][r] for r in proposal['reportRefs']]}

    def settings(self, account):
        if hasattr(self.runtime, 'refresh_profiles'):self.runtime.refresh_profiles()
        with self.host.lock:
            self.host.kp(account);value = copy.deepcopy(self.host.state()['aiControl']['settings'])
        return {'settings': value, 'profiles': [{k: p[k] for k in ('profileId', 'revision', 'model', 'enabled')} for p in self.coordinator.profiles.values()],
            'budgets': self.repository.state()['budgets'], 'maxContextBytes': 96 * 1024,
            'memory': self.memory.search(account), 'autoError': getattr(self.runtime, 'auto_error', None)}

    def usage(self, account, options=None):
        from .usage import summarize
        return summarize(self, account, options)

    def scan_auto(self):
        with self.host.lock:
            room = self.host.state();settings = room['aiControl']['settings'];auto = settings['auto']
            if not settings['enabled'] or not auto['enabled']:return
            account = auto['principal']
            if not account or not room['members'].get(account, {}).get('active') or room['members'][account]['role'] != 'kp':return
            channels = [cid for cid in auto['channelIds'] if chat.can_read(room, account, room['chat']['channels'].get(cid))]
        data = self.repository.state();positions = data['settings'].get('autoPositions', {});seen = data['settings'].get('autoSeen', {})
        for cid in channels:
            for message in room['chat']['messages'][cid]:
                key = cid + ':' + message['messageId'];revision = message['revision']
                if message['sequence'] <= positions.get(cid, 0) and key not in seen:continue
                previous = seen.get(key)
                if previous and previous['revision'] == revision:continue
                if previous and previous.get('requestId'):
                    self._execute(account, 'auto-cancel', 'ai.request.cancel', {'requestId': previous['requestId']})
                if message['deleted'] or message['kind'] != 'text' or not message['text'].startswith(auto['prefix']):
                    seen[key] = {'revision': revision, 'requestId': None}
                    self.repository.update(lambda s: s['settings'].update(autoSeen=copy.deepcopy(seen)))
                    continue
                result = self._execute(account, 'auto:' + key + ':' + str(revision), 'ai.request.create',
                    {'sourceKind': 'chat', 'channelId': cid, 'sourceId': message['messageId'], 'sourceRevision': revision, 'text': message['text']})
                self._execute(account, 'auto-dispatch', 'ai.request.dispatch', result)
                seen[key] = {'revision': revision, 'requestId': result['requestId']}
                self.repository.update(lambda s: s['settings'].update(autoSeen=copy.deepcopy(seen)))
