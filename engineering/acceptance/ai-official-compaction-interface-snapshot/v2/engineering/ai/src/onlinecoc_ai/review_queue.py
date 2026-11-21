"""Organization metadata, separate from business status and execution receipts."""
import re
from .contracts import digest
from .errors import require

TARGET = r'(request|batch|proposal|player|knowledge):[a-f0-9]{32}'
PROTECTED = frozenset({'queued','generating','validating','executing','unknown','partial','completed','published','approved','accepted'})


def canonical_request(state, request_id):
    return next((key for key,value in state['settings'].get('dispatch',{}).items() if value==request_id),request_id)


def correlation(state, request_id):
    rid=canonical_request(state,request_id)
    return state['settings'].get('requestLinks',{}).get(rid,{}).get('correlationId',digest({'scopeId':state['scopeId'],'requestId':rid}))


def verify(state):
    settings=state['settings'];links=settings.get('requestLinks',{});queue=settings.get('reviewQueue',{});submissions=settings.get('submissions',{})
    require(all(type(v) is dict for v in (links,queue,submissions)),'QUEUE_STATE_INVALID')
    for rid,link in links.items():
        require(rid in state['requests'] and type(link) is dict and set(link)<={'correlationId','replyToRequestId'} and
            re.fullmatch('[a-f0-9]{64}',link.get('correlationId','')) and
            ('replyToRequestId' not in link or link['replyToRequestId'] in state['requests']),'QUEUE_STATE_INVALID')
    for key,value in queue.items():
        require(re.fullmatch(TARGET,key) and type(value) is dict and set(value)<={'archived','archiveReason','archivedBy','updatedAt','supersededBy','resolution'} and
            type(value.get('archived',False)) is bool and
            ('supersededBy' not in value or value['supersededBy']!=key and re.fullmatch(TARGET,value['supersededBy'])) and
            (not value.get('archived') or type(value.get('archiveReason')) is str and 1<=len(value['archiveReason'])<=500),'QUEUE_STATE_INVALID')
        proof=value.get('resolution')
        if proof:
            require(type(proof) is dict and set(proof)=={'targetId','correlationId','goalDigest','receiptRefs','completedAt'} and
                re.fullmatch('batch:[a-f0-9]{32}',proof.get('targetId','')) and
                all(re.fullmatch('[a-f0-9]{64}',proof.get(k,'')) for k in ('correlationId','goalDigest')) and
                isinstance(proof.get('receiptRefs'),list) and bool(proof['receiptRefs']),'QUEUE_STATE_INVALID')
    for key,value in submissions.items():
        require(re.fullmatch('[a-f0-9]{64}',key) and type(value) is dict and set(value)=={'requestId','fingerprint'} and
            value['requestId'] in state['requests'] and re.fullmatch('[a-f0-9]{64}',value['fingerprint']),'QUEUE_STATE_INVALID')


class ReviewQueue:
    def __init__(self, app):
        self.app,self.host,self.repository=app,app.host,app.repository

    def bind(self, request_id, *, related=None, correlation_id=None):
        def save(state):
            rid=canonical_request(state,request_id)
            state['settings'].setdefault('requestLinks',{})[rid]={'correlationId':correlation_id or correlation(state,related or rid),
                **({'replyToRequestId':canonical_request(state,related)} if related else {})}
        self.repository.update(save)

    def submission(self, account, session_id, mode, args):
        if not args.get('submissionKey'):return None,None
        state=self.repository.state();key=digest({'scopeId':state['scopeId'],'account':account,'sessionId':session_id,'mode':mode,'key':args['submissionKey']})
        fingerprint=digest({k:v for k,v in args.items() if k!='submissionKey'})
        prior=state['settings'].get('submissions',{}).get(key)
        require(not prior or prior['fingerprint']==fingerprint,'SUBMISSION_KEY_CONFLICT')
        if prior:
            rid=prior['requestId'];result={'requestId':rid,'sessionId':session_id}
            tid=state['settings'].get('dispatch',{}).get(rid)
            if tid:result['taskId']=tid
            return (key,fingerprint),result
        return (key,fingerprint),None

    def save_submission(self, token, request_id):
        if token:self.repository.update(lambda state:state['settings'].setdefault('submissions',{}).update({token[0]:{'requestId':request_id,'fingerprint':token[1]}}))

    def entry(self, target, state=None, room=None):
        state=state or self.repository.state();room=room or self.host.state();kind,key=target.split(':',1)
        settings=state['settings'];protected=False
        if kind=='request':
            rid=canonical_request(state,key);record=state['requests'].get(rid)
            if not record:return None
            task=state['tasks'].get(settings.get('dispatch',{}).get(rid,rid),{})
            status=task.get('status',record['status']);signature=digest({'request':record,'task':task})
            # A request with a candidate is represented by its candidate card.
            protected=bool(task.get('proposalId') or task.get('batchId') or any(canonical_request(state,b['requestId'])==rid for b in settings.get('batches',{}).values()) or
                any(canonical_request(state,p['revisions'][str(p['currentRevision'])]['requestId'])==rid for p in state['proposals'].values()))
        elif kind=='proposal':
            revisions=state['proposals'].get(key)
            if not revisions:return None
            record=revisions['revisions'][str(revisions['currentRevision'])];rid=record['requestId'];status=record['status'];signature=record['candidateDigest']
            decision=self.app.rulings.decision_for_revision(settings.get('rulingDecisions',{}).get(target,{}),record)
            if decision:status=decision['status']
            protected=bool(any(a['proposalId']==key and a['proposalRevision']==record['revision'] for a in room['aiControl']['approvals'].values()) or decision.get('receipts'))
            if any(p['candidateDigest']==record['candidateDigest'] and room['aiControl']['approvals'][p['approvalId']]['proposalId']==key for p in room['aiControl']['publications'].values()):
                status='completed';protected=True
        else:
            group={'batch':'batches','player':'playerRequests','knowledge':'knowledgeRequests'}[kind]
            record=settings.get(group,{}).get(key if kind=='batch' else target)
            if not record:return None
            rid=record['requestId'];status=record['status'];signature=record['digest'];protected=bool(record.get('receipts'))
        original=canonical_request(state,rid)
        task=state['tasks'].get(settings.get('dispatch',{}).get(original,original),{})
        protected=protected or task.get('status') in ('queued','generating','validating')
        if not protected and status not in PROTECTED and any(state['requests'].get(r,{}).get('status')=='cancelled' for r in (rid,original)):
            status='cancelled'
        return {'requestId':original,'correlationId':correlation(state,rid),'status':status,'signature':signature,
            'protected':protected or status in PROTECTED}

    def targets(self, state):
        dispatched=set(state['settings'].get('dispatch',{}).values())
        return (['request:'+r for r in state['requests'] if r not in dispatched]+['proposal:'+p for p in state['proposals']]+
            ['batch:'+b for b in state['settings'].get('batches',{})]+list(state['settings'].get('playerRequests',{}))+list(state['settings'].get('knowledgeRequests',{})))

    def fields(self, target, state=None, room=None):
        state=state or self.repository.state();room=room or self.host.state();entry=self.entry(target,state,room)
        require(entry is not None,'NOT_VISIBLE')
        meta=state['settings'].get('reviewQueue',{}).get(target,{})
        archived=meta.get('archived',False);successor=meta.get('supersededBy')
        active=entry['status'] not in ('completed','published','accepted','rejected','cancelled')
        if target.startswith('request:') and entry['protected'] and entry['status'] not in PROTECTED:active=False
        status='archived' if archived else 'superseded' if successor else 'active' if active else 'history'
        return {'queueTargetId':target,'queueDigest':digest({'target':target,'entry':entry,'metadata':meta}),
            'correlationId':entry['correlationId'],'queueStatus':status,'archived':archived,
            'canArchive':not archived and not entry['protected'],'canRestore':archived and not entry['protected'] and not meta.get('resolution'),
            **({'resolution':meta['resolution']} if meta.get('resolution') else {}),
            **({'archiveReason':meta['archiveReason']} if meta.get('archiveReason') else {}),
            **({'supersededBy':successor} if successor else {}),
            'supersedes':[key for key,value in state['settings'].get('reviewQueue',{}).items() if value.get('supersededBy')==target]}

    def decorate(self, item, *, target=None, state=None, room=None):
        item.update(self.fields(target or item['rulingId'],state,room))
        if item.get('resolution'):
            # Completion metadata must not re-expose receipt identifiers stripped
            # by the ruling projection, including predecessors without a context.
            try:
                from .history import assess
                state=state or self.repository.state();room=room or self.host.state()
                batch=state['settings']['batches'][item['resolution']['targetId'].split(':',1)[1]]
                require(not item.get('sourceUnavailable'),'NOT_VISIBLE')
                assess(self.host,self.repository,room,batch['context'])
            except Exception:item.pop('resolution',None)
        if item['queueStatus'] in ('archived','superseded'):item['canDecide']=False
        return item

    def require_active(self, target):
        meta=self.repository.state()['settings'].get('reviewQueue',{}).get(target,{})
        require(not meta.get('archived') and not meta.get('supersededBy'),'QUEUE_ITEM_INACTIVE')

    def reconcile_completed(self):
        """Close explicit predecessor chains only after every command is committed."""
        with self.host.lock,self.app.lock:
            room=self.host.state();state=self.repository.state();updates={}
            for batch in state['settings'].get('batches',{}).values():
                if batch['status']!='completed' or len(batch['receipts'])!=len(batch['actions']):continue
                target='batch:'+batch['batchId'];refs=[]
                for index,receipt in enumerate(batch['receipts']):
                    expected='ai-batch:'+batch['batchId']+':'+str(index);expected_target=batch['actions'][index]['target']
                    if batch['context']['facts'].get('batchExecutionVersion')==2:
                        rows=batch.get('execution',{}).get('items',[])
                        if index>=len(rows) or rows[index]['status']!='committed':break
                        expected=rows[index].get('commandId')
                        if batch['execution']['scope']=='host.memory.single.v1':expected_target='host'
                    if receipt['id']!=expected or receipt['target']!=expected_target or receipt['receipt'].get('status')!='committed':break
                    try:
                        live=(self.app.receipt if receipt['target']=='ai' else self.host.receipt)(receipt['account'],receipt['id'])
                    except Exception:break
                    if live.get('status')!='committed' or live!=receipt['receipt']:break
                    from .reliability import business_unsuccessful
                    if business_unsuccessful(live.get('result')):break
                    refs.append({'target':receipt['target'],'account':receipt['account'],'commandId':receipt['id']})
                if len(refs)!=len(batch['actions']):continue
                relation=correlation(state,batch['requestId'])
                proof={'targetId':target,'correlationId':relation,'goalDigest':digest(batch['actions']),
                    'receiptRefs':refs,'completedAt':batch.get('completedAt')}
                meta=state['settings'].get('reviewQueue',{})
                if meta.get(target,{}).get('resolution')==proof:continue
                updates[target]={**meta.get(target,{}),'resolution':proof}
                for old in self.targets(state):
                    if old==target:continue
                    entry=self.entry(old,state,room)
                    if not entry or entry['correlationId']!=relation or entry['protected']:continue
                    seen=set();cursor=old
                    while cursor not in seen and cursor!=target:
                        seen.add(cursor);cursor=meta.get(cursor,{}).get('supersededBy')
                        if not cursor:break
                    if cursor!=target:continue
                    updates[old]={**meta.get(old,{}),'archived':True,'archiveReason':'明确关联的后续方案已全部执行成功',
                        'archivedBy':batch.get('decidedBy',batch['creator']),'updatedAt':self.host.clock(),'resolution':proof}
            if updates:self.repository.update(lambda s:s['settings'].setdefault('reviewQueue',{}).update(updates))

    def ready(self, target):
        """A checked candidate replaces only explicit, unexecuted predecessors."""
        with self.host.lock,self.app.lock:
            room=self.host.state()
            def save(state):
                new=self.entry(target,state,room);meta=state['settings'].setdefault('reviewQueue',{})
                if not new or meta.get(target,{}).get('archived') or meta.get(target,{}).get('supersededBy'):return
                for old in self.targets(state):
                    if old==target:continue
                    previous=self.entry(old,state,room)
                    if not previous or previous['correlationId']!=new['correlationId'] or previous['protected']:continue
                    if previous['status'] in ('rejected','cancelled') or meta.get(old,{}).get('supersededBy'):continue
                    meta.setdefault(old,{})['supersededBy']=target
            self.repository.update(save)

    def archive(self, account, args):
        with self.host.lock,self.app.lock,self.repository.transaction():
            self.host.kp(account);target=args['targetId'];fields=self.fields(target)
            require(fields['queueDigest']==args['digest'],'QUEUE_VERSION_CONFLICT')
            require(fields['canArchive'] if args['archived'] else fields['canRestore'],'QUEUE_ITEM_PROTECTED')
            reason=args.get('reason','').strip()
            require(not args['archived'] or reason,'ARCHIVE_REASON_REQUIRED')
            def save(state):
                meta=state['settings'].setdefault('reviewQueue',{}).setdefault(target,{})
                meta.update(archived=args['archived'],archivedBy=account,updatedAt=self.host.clock())
                if args['archived']:meta['archiveReason']=reason
            self.repository.update(save)
            return self.fields(target)
