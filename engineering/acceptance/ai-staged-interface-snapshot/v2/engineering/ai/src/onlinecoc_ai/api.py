"""Framework-free application commands; all actors come from host authentication."""
import copy
import threading
import uuid
from contextlib import nullcontext

from jsonschema import Draft202012Validator
from onlinecoc import chat
from onlinecoc.model import member
from .contracts import ENGINEERING, SCHEMAS, canonical, digest, loads, validate
from .errors import require
from .memory import Memory
from .reviews import request_text

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
        from .access import validate_context
        from types import SimpleNamespace
        validation_repository=SimpleNamespace(state=self.repository.validation_state,read_state=self.repository.validation_state)
        self.host.ai_access_validator = lambda room, context: validate_context(self.host, validation_repository, room, context)
        self.coordinator.application = self
        def migrate(state):
            for session in state['settings'].get('sessions', {}).values():
                session.setdefault('accessLevel', 'administrator' if self.host.state()['members'].get(session['owner'], {}).get('role') == 'kp' else 'player')
        with self.host.lock:self.repository.update(migrate)
        from .batches import Batches
        self.batches = Batches(self)
        from .rulings import Rulings
        self.rulings = Rulings(self)
        from .knowledge_requests import KnowledgeRequests
        self.knowledge_requests = KnowledgeRequests(self)
        from .player_requests import PlayerRequests
        self.player_requests = PlayerRequests(self)
        from .reviews import Reviews
        self.reviews = Reviews(self)
        from .review_queue import ReviewQueue
        self.queue = ReviewQueue(self)
        self.proposals.queue = self.queue
        from .continuations import Continuations
        self.continuations = Continuations(self)
        from .access import policy
        # room_read.authorize checks both principals against its current room.
        # This callback supplies only the AI policy; copying Host again for each
        # ancestor in a history graph makes every page hold the room lock longer.
        self.host.ai_room_read_authorizer = lambda account: policy(validation_repository)['allowAdminRoomRead']
        self.queue.reconcile_completed()
        from .room_defaults import recover
        recover(self)

    def command(self, account, envelope):
        if type(envelope) is dict and envelope.get('op')=='ai.session.submit' and self.rulings.is_confirmation(str(envelope.get('args',{}).get('text',''))):
            return self._command(account,envelope)
        if type(envelope) is dict and envelope.get('op') in ('ai.session.create', 'ai.session.update', 'ai.session.submit', 'ai.session.delete', 'ai.request.create', 'ai.access.update', 'ai.c_basis.update', 'ai.knowledge.request', 'ai.player.request'):
            # One durable commit for mutation + idempotency receipt. Lock order
            # stays host -> application -> repository, shared with context reads.
            with self.host.lock, self.lock, self.repository.transaction():
                result = self._command(account, envelope)
            if envelope['op']=='ai.session.delete' and result['status']=='committed' and self.coordinator.active:
                task = self.repository.state()['tasks'].get(self.coordinator.active_id,{})
                if task.get('status')=='cancelled':self.coordinator.loop.call_soon_threadsafe(self.coordinator.active.cancel)
            return result
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
                # Only mirror an already committed authoritative memory fact.
                # Reusing an uncertain request never issues another host change.
                recover_memory=op in ('ai.memory.confirm','ai.memory.revoke') and prior['receipt']['status'] in ('pending','unknown') and self.host.receipt(account,'ai-memory:'+digest([account,identifier]))['status']=='committed'
                if not recover_memory:return self.receipt(account, identifier)
            else:
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
        if value and role != 'kp' and value.get('op') not in ('ai.request.create', 'ai.request.cancel', 'ai.session.create', 'ai.session.update', 'ai.session.submit', 'ai.session.delete', 'ai.knowledge.request', 'ai.player.request'):receipt.pop('result', None)
        result = receipt.get('result')
        if isinstance(result, dict):
            try:
                if result.get('batchId') and result.get('context'):
                    receipt['result']=result=self.batches.public(account,result)
                if result.get('sessionId') and not result.get('deleted') and not result.get('batchId'):self.sessions._record(account, result['sessionId'])
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

    def _execute(self, account, identifier, op, args, *, session_id=None, dispatch=True):
        if op == 'ai.room.initialize':
            from .room_defaults import initialize
            return initialize(self, account, args)
        if op == 'ai.c_basis.update':
            from .c_review import update
            return update(self, account, args)
        if op=='ai.queue.archive':return self.queue.archive(account,args)
        if op=='ai.review.create':return self.reviews.create(account,identifier,args)
        if op=='ai.player.request':return self.player_requests.create(account,identifier,args)
        if op=='ai.knowledge.request':return self.knowledge_requests.create(account,args)
        if op=='ai.knowledge.reconcile':
            with self.host.lock,self.rulings.lock:return self.knowledge_requests.reconcile(account,args)
        if op=='ai.ruling.decide':return self.rulings.decide(account,args)
        if op.startswith('ai.batch.'):
            return self.batches.execute(account, identifier, op, args)
        if op == 'ai.access.update':
            from .access import policy
            with self.host.lock:self.host.kp(account)
            def save_policy(data):
                prior = policy(self.repository)
                require(args['revision'] == prior['revision'], 'POLICY_VERSION_CONFLICT')
                value = {**prior, **args, 'revision': prior['revision'] + 1, 'principal': account}
                data['settings']['accessPolicy'] = value
                return {k:v for k,v in value.items() if k != 'principal'}
            return self.repository.update(save_policy)
        if op.startswith('ai.session.'):
            return self.sessions.execute(account, identifier, op, args)
        if op == 'ai.request.create':
            from .access import can_use, policy
            role = can_use(self.host, self.repository, account)
            if role != 'kp' and not session_id:
                require(args['sourceKind'] == 'manual', 'PERMISSION_DENIED')
                session = self.sessions.execute(account, identifier, 'ai.session.create', {'title': args['text'][:36].strip() or '新会话'})
                session_id = session['sessionId']
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
                    require(session and not session.get('deleted') and session['owner'] == account, 'NOT_VISIBLE')
                    require(not session['archived'], 'SESSION_ARCHIVED')
                    require(session.get('accessLevel') != 'administrator' or role == 'kp', 'PERMISSION_DENIED')
                existing = next((r for r in data['requests'].values() if r['dedupKey'] == request['dedupKey']), None)
                if existing:return {'requestId': existing['requestId'], **({'sessionId': session_id} if session else {})}
                require(sum(r['status'] == 'received' for r in data['requests'].values()) < 64, 'QUEUE_FULL')
                if session:
                    require(len(session['requestIds']) < 100, 'LIMIT_EXCEEDED')
                    session['requestIds'].append(rid);session['revision'] += 1;session['updatedAt'] = self.host.clock()
                data['requests'][rid] = request
                return {'requestId': rid, **({'sessionId': session_id} if session else {})}
            result = self.repository.update(save)
            if not dispatch:return result
            player_session = session_id and self.repository.state()['settings']['sessions'][session_id].get('accessLevel') == 'player'
            if player_session and args['text'].strip()=='请 KP 说明本次问题中允许我获知的信息。':
                ids=self.repository.state()['settings']['sessions'][session_id]['requestIds']
                target=ids[-2] if len(ids)>1 else result['requestId']
                self.knowledge_requests.create(account,{'sessionId':session_id,'requestId':target})
                return {**result,'awaitingKnowledge':True}
            if role != 'kp' or player_session:
                principal = account if role == 'kp' else policy(self.repository)['principal']
                require(principal, 'AI_ADMIN_REQUIRED')
                try:
                    dispatched = self._execute(principal, 'player-dispatch:' + rid, 'ai.request.dispatch', {'requestId': result['requestId']})
                    result['taskId'] = dispatched['taskId']
                except Exception as exc:
                    from .diagnostics import error_code
                    result['dispatchError'] = error_code(exc)
                    self.repository.update(lambda data:data['settings'].setdefault('requestErrors',{}).update({rid:result['dispatchError']}))
            return result
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
            with self.host.lock,self.lock,self.repository.lock:
                # Player submission already owns the outer atomic transaction.
                transaction=nullcontext() if self.repository.pending is not None else self.repository.transaction()
                with transaction:
                    from .review_queue import canonical_request
                    self.queue.require_active('request:'+canonical_request(self.repository.state(),args['requestId']))
                    state = self.repository.state();request = state['requests'].get(args['requestId'])
                    require(request and request['status'] in ('received', 'queued'), 'REQUEST_NOT_READY')
                    task = self.coordinator.enqueue(account, 'dispatch:' + request['requestId'], request['text'],
                        source_kind=request['sourceKind'], source_id=request['sourceId'], source_revision=request['sourceRevision'], initiator=request['initiator'],generation_request=request)
                    def save(data):
                        data['requests'][request['requestId']]['status'] = 'queued'
                        data['settings'].setdefault('dispatch', {})[request['requestId']] = task['taskId']
                        data['settings'].get('requestErrors',{}).pop(request['requestId'],None)
                    self.repository.update(save)
                    return {'requestId': request['requestId'], 'taskId': task['taskId']}
        if op == 'ai.draft.create':return self.proposals.create(account, args['text'], args['changeSet'])
        if op == 'ai.proposal.revise':return self.proposals.revise(account, args['proposalId'], args['revision'], args['changeSet'], summary=args.get('summary', 'KP 修订草稿'))
        if op == 'ai.proposal.validate':
            result=self.proposals.validate(account,args['proposalId'],args['revision'])
            self.rulings.auto_configuration(account,args['proposalId'])
            return result
        if op == 'ai.memory.create':return self.memory.create(account, args['content'], args['sourceRefs'], kind=args.get('kind', 'summary'), visibility=args.get('visibility', 'kp'))
        if op == 'ai.memory.confirm':return self.memory.confirm(account, args['memoryId'], args['revision'],command_id='ai-memory:'+digest([account,identifier]))
        if op == 'ai.memory.revoke':return self.memory.revoke(account, args['memoryId'], args['revision'],command_id='ai-memory:'+digest([account,identifier]))
        if op == 'ai.settings.update':
            from .room_defaults import recover
            recover(self)
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

    def tasks(self, account, before=None, limit=30, *, request_ids=None, delivered=False):
        from .messages import project
        with self.host.lock, self.lock, self.repository.read_scope():
            page = self._tasks(account, before, limit, request_ids=request_ids)
            return project(self, account, page, delivered=delivered)

    def _tasks(self, account, before=None, limit=30, *, request_ids=None):
        require(type(limit) is int and 1 <= limit <= 100, 'INPUT_INVALID')
        with self.host.lock:
            room = self.host.state();kp = member(room, account)['role'] == 'kp'
        state = self.repository.read_state();results = []
        from .access import can_use
        can_use(self.host, self.repository, account)
        sessions = {rid:s for s in state['settings'].get('sessions', {}).values() for rid in s['requestIds']}
        dispatched = set(state['settings'].get('dispatch', {}).values())
        proposals = {r['revisions'][str(r['currentRevision'])]['requestId']:r['revisions'][str(r['currentRevision'])]
                     for r in state['proposals'].values()}
        requests = (state['requests'][rid] for rid in request_ids if rid in state['requests']) if request_ids is not None else state['requests'].values()
        messages={m['messageId']:(cid,m) for cid,values in room['chat']['messages'].items() for m in values}
        def visible_request(request):
            session=sessions.get(request['requestId'])
            if session and (session.get('deleted') or not kp and session.get('accessLevel')!='player'):return False
            if request['requestId'] in dispatched or not kp and request['initiator']!=account:return False
            if request['sourceKind']=='chat':
                found=messages.get(request['sourceId'])
                if not found:return False
                cid,message=found
                if not chat.can_read(room,account,room['chat']['channels'][cid]) or message['deleted'] or str(message['revision'])!=str(request['sourceRevision']):return False
            return True
        requests=sorted((r for r in requests if visible_request(r)),key=lambda r:(r['createdAt'],r['requestId']),reverse=True)
        if before:
            index=next((i for i,r in enumerate(requests) if r['requestId']==before),None)
            require(index is not None,'CURSOR_INVALID');requests=requests[index+1:]
        next_before=requests[limit-1]['requestId'] if len(requests)>limit else None
        requests=requests[:limit];recipients={};history_memo={};history_shared={}
        def history_state(context):
            from .history import assess
            key=digest(context)
            if key not in history_memo:
                try:history_memo[key]=(assess(self.host,self.repository,room,context,shared=history_shared),None)
                except Exception as exc:history_memo[key]=(None,exc)
            value,error=history_memo[key]
            if error:raise error
            return value
        for request in requests:
            session = sessions.get(request['requestId'])
            if session and (session.get('deleted') or not kp and session.get('accessLevel') != 'player'):continue
            if request_ids is not None and request['requestId'] not in request_ids:continue
            if request['requestId'] in dispatched:continue
            if not kp and request['initiator'] != account:continue
            task = state['tasks'].get(state['settings'].get('dispatch', {}).get(request['requestId'], request['requestId']))
            proposal = proposals.get(task['requestId'] if task else request['requestId'])
            item = {'requestId': request['requestId'], 'sessionId':session['sessionId'] if session else None,
                    'status': state['requests'][task['requestId']]['status'] if task else request['status'], 'createdAt': request['createdAt']}
            if kp and session:
                sid=session['sessionId']
                if sid not in recipients:recipients[sid]=self.reviews.recipient(sid,state,room)
                recipient=recipients[sid]
                if recipient:item['recipientAccountId']=recipient
            if request['sourceKind']=='manual':
                item.update(text=request_text(self.repository,request,state),initiator=request['initiator'])
            continuation=self.continuations.for_request(request,state)
            if continuation and continuation[1]['owner']==account:
                item['continuationOrigin']={'proposalId':continuation[0],'requestId':continuation[1]['sourceRequestId']}
            dispatch_error=state['settings'].get('requestErrors',{}).get(request['requestId']) if request['status']!='cancelled' else None
            if dispatch_error:item.update(error=dispatch_error,status='blocked')
            disclosure=next((r for r in state['settings'].get('knowledgeRequests',{}).values() if r['requestId']==request['requestId']),None)
            if disclosure:item['knowledgeRequest']=self.knowledge_requests.public(disclosure)
            creative=next((r for r in state['settings'].get('playerRequests',{}).values() if r['requestId']==request['requestId']),None)
            if creative:
                item['playerRequest']=self.player_requests.public(creative)
                if not task:item['status']='request_'+item['playerRequest']['status']
            batch=state['settings'].get('batches',{}).get(task.get('batchId')) if task else None
            if batch:
                item['ruling']={k:batch[k] for k in ('batchId','status','digest')}
                if batch['status']!='pending':item['status']=batch['status']
            if proposal and any(a['proposalId'] == proposal['proposalId'] and a['status'] == 'consumed' for a in room['aiControl']['approvals'].values()):item['status'] = 'published'
            player_reply = not kp and session and session['owner'] == account and session.get('accessLevel') == 'player'
            if kp or player_reply:
                if task:
                    trace=self.coordinator.traces.get(task['taskId'])
                    item['events']=trace.events() if trace else copy.deepcopy(task.get('events',[]))
                    if task.get('dependencyCheck'):item['dependencyCheck']=copy.deepcopy(task['dependencyCheck'])
                    if batch and kp and batch.get('execution'):
                        for row in batch['execution'].get('items',[]):
                            item['events'].append({'seq':len(item['events'])+1,'at':batch.get('decidedAt',batch['createdAt']),
                                'stage':'command_execute','status':'completed' if row['status']=='committed' else 'running' if row['status']=='unknown' else 'failed',
                                'summary':{'committed':'指令已提交','failed':'指令失败','rolled_back':'暂存修改已撤销','not_executed':'未执行','unknown':'结果待核对'}.get(row['status'],row['status']),
                                'operation':row['op'],'receiptStatus':row['status'],**({'code':row['code']} if row.get('code') else {})})
                    elif batch and kp:
                        for index,entry in enumerate(batch['receipts']):
                            receipt=entry['receipt']
                            event={'seq':len(item['events'])+1,'at':entry.get('startedAt',batch['createdAt']),'stage':'command_execute',
                                'status':'completed' if receipt['status']=='committed' else 'running' if receipt['status']=='pending' else 'failed',
                                'summary':'执行已批准动作','operation':batch['actions'][index]['op'],'receiptStatus':receipt['status']}
                            if entry.get('finishedAt') is not None:event['durationMs']=round(max(0,entry['finishedAt']-event['at'])*1000,2)
                            if receipt.get('code'):event['code']=receipt['code']
                            item['events'].append(event)
                if player_reply and task and not task.get('contextRef'):
                    if task.get('error'):item['error']=task['error']
                    results.append(item);continue
                if task and task.get('contextRef'):
                    context = state['contexts'].get(task['contextRef'])
                    try:
                        principal = context['reviewPrincipal'] if context else account
                        strict=bool(context and context['facts'].get('strictPlayer'))
                        require(context and context['scopeId'] == room['aiControl']['scopeId'] and
                            (strict or member(room, principal)['role'] == 'kp') and context['authorizationEpoch'] == room['members'][principal]['authorizationEpoch'], 'PERMISSION_DENIED')
                        if player_reply:require(strict and context['facts'].get('sessionAccess', {}).get('owner') == account and context['facts']['sessionAccess']['level'] == 'player', 'PERMISSION_DENIED')
                        from .history import assess,NOTICE
                        stale=history_state(context)
                        item['sourceState']='stale' if stale else 'fresh'
                        if stale:
                            item.update(sourceState='stale',sourceError=stale)
                            if task and task.get('text') or not task and proposal and proposal.get('summary'):
                                item.update(sourceNotice=NOTICE,historicalReadOnly=True)
                                if item['status'] in ('review_ready','needs_input','approved'):item['status']='stale'
                    except Exception as exc:
                        from .diagnostics import error_code
                        results.append({**{k:v for k,v in item.items() if k not in ('sourceState','sourceError','sourceNotice','historicalReadOnly')},'sourceState':'denied','error':error_code(exc), 'status': 'stale' if item['status'] in ('review_ready','needs_input','approved') else item['status']})
                        continue
                if request['sourceKind'] == 'chat':
                    matches = [(cid, m) for cid, messages in room['chat']['messages'].items() for m in messages if m['messageId'] == request['sourceId']]
                    if len(matches) != 1:continue
                    cid, message = matches[0]
                    if not chat.can_read(room, account, room['chat']['channels'][cid]) or message['deleted'] or str(message['revision']) != str(request['sourceRevision']):continue
                if proposal and kp:
                    try:
                        from .history import assess,NOTICE
                        stale=history_state(state['contexts'].get(proposal['contextRef']))
                        item['sourceState']='stale' if stale else item.get('sourceState','fresh')
                        if stale:
                            item.update(sourceState='stale',sourceError=stale)
                            if task and task.get('text') or not task and proposal and proposal.get('summary'):
                                item.update(sourceNotice=NOTICE,historicalReadOnly=True)
                                if item['status'] in ('review_ready','needs_input','approved'):item['status']='stale'
                        else:self.proposals.get(task['account'] if task else account, proposal['proposalId'])
                    except Exception as exc:
                        from .diagnostics import error_code
                        results.append({**{k:v for k,v in item.items() if k not in ('sourceState','sourceError','sourceNotice','historicalReadOnly')},'sourceState':'denied','error':error_code(exc), 'status': 'stale' if item['status'] in ('review_ready','needs_input','approved') else item['status']})
                        continue
                item.update(text=request_text(self.repository,request,state), initiator=request['initiator'], taskId=task['taskId'] if task else None,
                    proposalId=proposal['proposalId'] if proposal and kp else None, error=task['error'] if task else dispatch_error,
                    response=task.get('text') if task else proposal['summary'] if proposal and kp else None)
                if task and task.get('contextRef') and context and context['facts'].get('strictPlayer'):
                    from .known_answers import format_legacy
                    item['response'] = format_legacy(item.get('response'))
                if kp and session:
                    source=self.reviews.source(session['sessionId'],state)
                    if source:item['reviewSource']=source
                if task and task.get('calls'):item['modelCalls']=[{k:c[k] for k in ('requestedModel','returnedModel','systemFingerprint','usage','profileRevision') if k in c} for c in task['calls']]
                if kp and task and task.get('diagnostics'):item['diagnostics'] = copy.deepcopy(task['diagnostics'])
                if kp and task and task.get('batchId'):item['batchId'] = task['batchId']
                if task and task.get('choices') and item['status'] in ('review_ready','needs_input'):
                    item['choices']=copy.deepcopy(task['choices'])
            results.append(item)
        if kp:
            for item in results:self.queue.decorate(item,target='request:'+item['requestId'],state=state,room=room)
        results.sort(key=lambda r: (r['createdAt'], r['requestId']), reverse=True)
        return {'items': results, 'nextBefore': next_before}

    def proposal(self, account, key):
        data = self.repository.state()
        with self.host.lock:self.host.kp(account)
        record = data['proposals'].get(key)
        require(record is not None, 'NOT_VISIBLE')
        current = record['revisions'][str(record['currentRevision'])]
        # Room administrators may inspect each other's drafts. Mutation and
        # publication still require the engine's original review principal.
        principal = data['contexts'][current['contextRef']]['reviewPrincipal']
        proposal = self.proposals.get(principal, key)
        return {'proposal': proposal, 'reports': [data['reports'][r] for r in proposal['reportRefs']]}

    def settings(self, account):
        from .c_review import settings as c_settings
        if hasattr(self.runtime, 'refresh_profiles'):self.runtime.refresh_profiles()
        with self.host.lock:
            self.host.kp(account);value = copy.deepcopy(self.host.state()['aiControl']['settings'])
        return {'settings': value, 'scopeId': self.host.state()['aiControl']['scopeId'], 'cReviewBasis': c_settings(self), 'access': self.sessions.access(account), 'profiles': [{k: p[k] for k in ('profileId', 'revision', 'model', 'enabled')} for p in self.coordinator.profiles.values()],
            'budgets': self.repository.state()['budgets'], 'maxContextBytes': 96 * 1024,
            'memory': self.memory.search(account), 'autoError': getattr(self.runtime, 'auto_error', None)}

    def debug(self, account, options=None):
        from .debug import export
        return export(self,account,options or {})

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
