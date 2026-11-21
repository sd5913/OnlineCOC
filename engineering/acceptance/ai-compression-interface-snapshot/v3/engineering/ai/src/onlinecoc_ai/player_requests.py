"""Explicit player business intent, reviewed separately from disclosure and writes."""
import copy
import uuid
from .access import policy
from .contracts import digest
from .errors import require

BOUND = ('rulingId','kind','sessionId','requestId','initiator','summary','createdAt','authorityEpoch')

class PlayerRequests:
    def __init__(self, app):
        self.app,self.host,self.repository=app,app.host,app.repository

    def create(self, account, identifier, args):
        require(policy(self.repository)['allowPlayerRequests'],'PLAYER_REQUESTS_DISABLED')
        session=self.app.sessions._record(account,args['sessionId'])
        require(session['owner']==account and session['accessLevel']=='player','PERMISSION_DENIED')
        require(not session['archived'],'SESSION_ARCHIVED')
        rid=args.get('requestId')
        token,prior=self.app.queue.submission(account,session['sessionId'],'player',args)
        if prior:rid=prior['requestId']
        if rid is None:
            require(args['text'].strip(),'INPUT_INVALID')
            rid=self.app._execute(account,'player-intent:'+identifier,'ai.request.create',
                {'sourceKind':'manual','text':args['text']},session_id=session['sessionId'],dispatch=False)['requestId']
        self.app.queue.save_submission(token,rid)
        state=self.repository.state()
        require(rid in state['settings']['sessions'][session['sessionId']]['requestIds'],'NOT_VISIBLE')
        request=state['requests'][rid]
        require(request['status']!='cancelled','REQUEST_CANCELLED')
        existing=next((r for r in state['settings'].get('playerRequests',{}).values() if r['requestId']==rid),None)
        if existing:return self.public(existing)
        record={'rulingId':'player:'+uuid.uuid4().hex,'kind':'player_request','sessionId':session['sessionId'],
            'requestId':rid,'initiator':account,'summary':request['text'],'createdAt':self.host.clock(),
            'authorityEpoch':self.host.epoch,'status':'pending'}
        record['digest']=digest({k:record[k] for k in BOUND})
        self.repository.update(lambda s:s['settings'].setdefault('playerRequests',{}).update({record['rulingId']:record}))
        return self.public(record)

    def public(self, record):
        result={k:copy.deepcopy(record[k]) for k in ('rulingId','sessionId','requestId','status','createdAt','digest')}
        state=self.repository.state();session=state['settings'].get('sessions',{}).get(record['sessionId'],{})
        if result['status']=='pending' and (not session or session.get('deleted') or state['requests'].get(record['requestId'],{}).get('status')=='cancelled'):
            result['status']='cancelled'
        return result

    def list(self, account):
        self.host.kp(account);items=[]
        for record in self.repository.state()['settings'].get('playerRequests',{}).values():
            item=copy.deepcopy(record);item.pop('authorityEpoch',None);item.update(self.public(record))
            item.update(canDecide=item['status']=='pending' and policy(self.repository)['allowPlayerRequests'] and policy(self.repository)['allowPlayerChat'],risks=[],receipts=[])
            items.append(item)
        return items

    def review_required(self, session_id):
        return bool(session_id) and (session_id in self.repository.state()['settings'].get('reviews',{}) or any(r.get('reviewSessionId')==session_id for r in self.repository.state()['settings'].get('playerRequests',{}).values()))

    def _save(self, record):
        self.repository.update(lambda s:s['settings']['playerRequests'].update({record['rulingId']:copy.deepcopy(record)}))

    def decide(self, account, args):
        self.host.kp(account)
        self.app.queue.require_active(args['rulingId'])
        record=self.repository.state()['settings'].get('playerRequests',{}).get(args['rulingId'])
        require(record and record['digest']==args['digest'],'RULING_STALE')
        if record['status'] in ('accepted','rejected'):return self._item(account,record)
        item=self._item(account,record)
        require(item['status']=='pending','RULING_NOT_READY')
        require(item['canDecide'],'PERMISSION_DENIED')
        require(record['authorityEpoch']==self.host.epoch,'STALE_AUTHORITY')
        if args['decision']=='reject':
            record.update(status='rejected',decidedBy=account);self._save(record);return self._item(account,record)
        source=self.app.reviews.material(account,{'kind':'ruling','rulingId':record['rulingId'],'digest':record['digest']})
        with self.repository.transaction():
            review=self.app.reviews.prepare(account,'review:'+record['rulingId'],source)
            record.update(status='accepted',decidedBy=account,reviewSessionId=review['sessionId'],reviewRequestId=review['requestId'])
            self._save(record)
        try:
            result=self.app._execute(account,'review-dispatch:'+record['rulingId'],'ai.request.dispatch',{'requestId':record['reviewRequestId']})
            record['reviewTaskId']=result['taskId']
        except Exception as exc:
            from .diagnostics import error_code
            record['generationError']=error_code(exc)
        self._save(record)
        return self._item(account,record)

    def _item(self, account, record):
        return next(i for i in self.list(account) if i['rulingId']==record['rulingId'])
