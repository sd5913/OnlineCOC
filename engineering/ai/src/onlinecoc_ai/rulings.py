"""One KP queue for immutable runtime batches and checked configuration publications."""
import copy
import threading
from .errors import require, AiError
from onlinecoc.errors import DomainError
from .access import policy, request_session


class Rulings:
    def __init__(self, app):
        self.app, self.host, self.repository = app, app.host, app.repository
        self.lock = threading.RLock()

    @staticmethod
    def is_confirmation(text):
        return text.strip().rstrip('。.!！') in ('批准','批准执行','确认执行','同意执行','approve')

    def redact_stale(self, account, room, item, context):
        try:self.host.validate_ai_sources(room,account,context)
        except (AiError,DomainError):
            item.update(summary='来源权限或资料已变化，请重新生成。',canDecide=False,risks=[],receipts=[])
            for key in ('actions','changeSet','reports','publications'):
                if key in item:item[key]=[]
        return item

    def list(self, account, session_id=None):
        with self.host.lock:
            self.host.kp(account)
            room=self.host.state();state=self.repository.state();items=[]
            for batch in state['settings'].get('batches',{}).values():
                item={k:copy.deepcopy(batch[k]) for k in ('sessionId','requestId','summary','status','createdAt','digest','actions','receipts')}
                item.update(rulingId='batch:'+batch['batchId'],kind='runtime',canDecide=True,risks=[])
                request=state['requests'][batch['requestId']]
                if request['status']=='cancelled' and item['status']=='pending':item['status']='cancelled'
                items.append(self.redact_stale(account,room,item,batch['context']))
            for record in state['proposals'].values():
                proposal=record['revisions'][str(record['currentRevision'])];request=state['requests'][proposal['requestId']]
                session=request_session(self.repository,request);context=state['contexts'][proposal['contextRef']]
                reports=[state['reports'][r] for r in proposal['reportRefs']]
                rid='proposal:'+proposal['proposalId'];decision=state['settings'].get('rulingDecisions',{}).get(rid,{})
                status='pending' if proposal['status']=='review_ready' else proposal['status']
                if decision.get('digest')==proposal['candidateDigest']:status=decision['status']
                if request['status']=='cancelled':status='rejected'
                publications=[p for p in room['aiControl']['publications'].values() if p['candidateDigest']==proposal['candidateDigest'] and room['aiControl']['approvals'][p['approvalId']]['proposalId']==proposal['proposalId']]
                if publications:status='completed'
                consultation_only=context['facts'].get('consultationOnly',False)
                if consultation_only and status=='pending':status='blocked'
                risks=[copy.deepcopy(r) for r in self.app.proposals.pack.contract['reviewPolicy']['items'] if r['required']]
                if any(r['risk'] in ('medium','high','unknown') for r in reports):risks.append({'id':'gameplay-risk','question':'接受已报告的游戏性影响与未覆盖范围','required':True})
                item={'rulingId':rid,'kind':'configuration','sessionId':session['sessionId'] if session else None,
                    'requestId':proposal['requestId'],'summary':proposal['summary'],'status':status,'createdAt':proposal['createdAt'],
                    'digest':proposal['candidateDigest'],'revision':proposal['revision'],'canDecide':context['reviewPrincipal']==account and not consultation_only,
                    'changeSet':copy.deepcopy(proposal['changeSet']),'reports':copy.deepcopy(reports),'risks':risks,
                    'receipts':copy.deepcopy(decision.get('receipts',[])), 'publications':copy.deepcopy(publications)}
                if consultation_only:item['blockingReason']='CONSULTATION_ONLY'
                items.append(self.redact_stale(account,room,item,context))
            return {'items':sorted([i for i in items if session_id is None or i['sessionId']==session_id],key=lambda i:i['createdAt'],reverse=True)}

    def host_command(self, account, identifier, op, args):
        existing=self.host.receipt(account,identifier)
        if existing['status']!='unknown':return existing
        room=self.host.state();cat=self.host.catalog(account)
        return self.host.command(account,{'protocolVersion':1,'type':'command','requestId':identifier,'roomId':room['roomId'],
            'payload':{'commandId':identifier,'authorityEpoch':self.host.epoch,'runId':room['runId'],
                'catalogRevision':cat['revision'],'rulesetRevision':cat['rulesetRevision'],'op':op,'args':args}})

    def decide(self, account, args):
        with self.host.lock,self.lock:
            self.host.kp(account)
            item=next((i for i in self.list(account)['items'] if i['rulingId']==args['rulingId']),None)
            require(item and item['digest']==args['digest'],'RULING_STALE')
            if item['status'] in ('completed','rejected'):return item
            require(item['canDecide'],'PERMISSION_DENIED')
            require(item['status']=='pending','RULING_NOT_READY')
            if item['kind']=='runtime':
                self.app.batches.execute(account,'ruling:'+item['rulingId'],'ai.batch.'+('approve' if args['decision']=='approve' else 'reject'),
                    {'batchId':item['rulingId'].split(':',1)[1],'digest':item['digest']})
            else:
                pid=item['rulingId'].split(':',1)[1]
                if args['decision']=='reject':
                    proposal=self.app.proposals.get(account,pid)
                    self.host.ai_proposal_head(account,pid,proposal['revision']+1)
                    self.repository.update(lambda s:s['requests'][proposal['requestId']].update(status='cancelled'))
                else:
                    proposal=self.app.proposals.get(account,pid)
                    decisions=args.get('riskDecisions',{})
                    require({r['id'] for r in item['risks']}<=set(decisions),'RISK_REVIEW_REQUIRED')
                    # Durable intent: restart/retry never starts a second publication.
                    record={'digest':item['digest'],'status':'executing','decidedBy':account,'receipts':[]}
                    def save():self.repository.update(lambda s:s['settings'].setdefault('rulingDecisions',{}).update({item['rulingId']:copy.deepcopy(record)}))
                    save()
                    for stage,op in (('approve','ai.proposal.approve'),('apply','publication.apply')):
                        params={'proposalId':pid,'proposalRevision':item['revision'],'riskDecisions':decisions} if stage=='approve' else {'approvalId':receipt['result']['approvalId']}
                        try:receipt=self.host_command(account,'ai-ruling:'+pid+':'+str(item['revision'])+':'+stage,op,params)
                        except Exception:record['status']='unknown';save();raise
                        record['receipts'].append(receipt)
                        if receipt['status']!='committed':
                            record['status']='unknown' if receipt['status'] in ('pending','unknown') else 'blocked';save()
                            return next(i for i in self.list(account)['items'] if i['rulingId']==item['rulingId'])
                        save()
                    record['status']='completed';save();self.app.proposals.reconcile()
            return next(i for i in self.list(account)['items'] if i['rulingId']==item['rulingId'])

    def confirm_session(self, account, session):
        require(session['accessLevel']=='administrator','PERMISSION_DENIED')
        items=self.list(account,session['sessionId'])['items'];pending=[i for i in items if i['status']=='pending']
        require(len(pending)<=1,'RULING_AMBIGUOUS')
        item=pending[0] if pending else items[0] if items else None
        if not item:return None
        state=self.repository.state();latest=session['requestIds'][-1] if session['requestIds'] else None
        if item['requestId'] not in (latest,state['settings'].get('dispatch',{}).get(latest)):
            return {'sessionId':session['sessionId'],'ruling':item,'reviewRequired':True}
        # Explicit risk decisions remain on the review card; never invent acceptance text.
        if item['status'] not in ('pending','completed','rejected') or (item['status']=='pending' and item['risks']):
            return {'sessionId':session['sessionId'],'ruling':item,'reviewRequired':True}
        result=self.decide(account,{'rulingId':item['rulingId'],'digest':item['digest'],'decision':'approve'})
        return {'sessionId':session['sessionId'],'ruling':result}

    def auto_configuration(self, account, proposal_id):
        p=policy(self.repository)
        if not p.get('autoApproveConfigurations') or p['principal']!=account:return
        item=next(i for i in self.list(account)['items'] if i['rulingId']=='proposal:'+proposal_id)
        if item['status']!='pending':return
        self.decide(account,{'rulingId':item['rulingId'],'digest':item['digest'],'decision':'approve',
            'riskDecisions':{r['id']:'KP 已开启通过三检后的配置自动批准' for r in item['risks']}})
