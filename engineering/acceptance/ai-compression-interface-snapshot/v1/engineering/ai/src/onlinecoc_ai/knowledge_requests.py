"""Voluntary player requests; disclosure is a real, separately reviewed host command."""
import copy
import uuid
from jsonschema import Draft202012Validator
from onlinecoc.contracts import OPERATIONS
from onlinecoc.model import member
from .access import policy
from .contracts import digest
from .errors import require


class KnowledgeRequests:
    def __init__(self, app):
        self.app, self.host, self.repository = app, app.host, app.repository

    def create(self, account, args):
        require(policy(self.repository)['allowKnowledgeRequests'], 'KNOWLEDGE_REQUESTS_DISABLED')
        session=self.app.sessions._record(account,args['sessionId'])
        require(session['owner']==account and session['accessLevel']=='player' and not session['archived'], 'PERMISSION_DENIED')
        state=self.repository.state()
        require(args['requestId'] in session['requestIds'], 'NOT_VISIBLE')
        request=state['requests'][args['requestId']]
        require(request['status']!='cancelled', 'REQUEST_CANCELLED')
        existing=next((r for r in state['settings'].get('knowledgeRequests',{}).values() if r['requestId']==args['requestId']),None)
        if existing:return self.public(existing)
        record={'rulingId':'knowledge:'+uuid.uuid4().hex,'kind':'knowledge_request','sessionId':session['sessionId'],
            'requestId':args['requestId'],'initiator':account,'summary':request['text'],'createdAt':self.host.clock(),
            'status':'pending','authorityEpoch':self.host.epoch,'receipts':[]}
        record['digest']=digest(record)
        self.repository.update(lambda s:s['settings'].setdefault('knowledgeRequests',{}).update({record['rulingId']:record}))
        return self.public(record)

    @staticmethod
    def public(record):
        return {k:copy.deepcopy(record[k]) for k in ('rulingId','sessionId','requestId','status','createdAt','digest')}

    def list(self, account):
        self.host.kp(account)
        state=self.repository.state();items=[]
        for record in state['settings'].get('knowledgeRequests',{}).values():
            item=copy.deepcopy(record);item.pop('authorityEpoch',None)
            session=state['settings'].get('sessions',{}).get(record['sessionId'],{})
            active=bool(session) and not session.get('deleted',False) and state['requests'].get(record['requestId'],{}).get('status')!='cancelled'
            item.update(canDecide=active and policy(self.repository)['allowKnowledgeRequests'],risks=[])
            if not active and item['status']=='pending':item['status']='cancelled'
            items.append(item)
        return items

    def _save(self, record):
        self.repository.update(lambda s:s['settings']['knowledgeRequests'].update({record['rulingId']:copy.deepcopy(record)}))

    def decide(self, account, args):
        self.host.kp(account)
        record=self.repository.state()['settings'].get('knowledgeRequests',{}).get(args['rulingId'])
        require(record and record['digest']==args['digest'], 'RULING_STALE')
        if record['status'] in ('completed','rejected'):return self.public(record)
        require(record['status']=='pending', 'RULING_NOT_READY')
        item=next(i for i in self.list(account) if i['rulingId']==record['rulingId'])
        require(item['canDecide'], 'PERMISSION_DENIED')
        if args['decision']=='reject':
            record.update(status='rejected',decidedBy=account);self._save(record);return self.public(record)
        require(record['authorityEpoch']==self.host.epoch, 'STALE_AUTHORITY')
        actions=args.get('disclosures',[])
        require(actions, 'DISCLOSURE_REQUIRED')
        subject=member(self.host.state(),record['initiator'])['memberId']
        for action in actions:
            require(action['op']=='knowledge.observe' and Draft202012Validator(OPERATIONS['knowledge.observe']).is_valid(action['args']), 'DISCLOSURE_INVALID')
            require(action['args']['subjectMemberId']==subject, 'DISCLOSURE_SUBJECT_MISMATCH')
        record.update(status='executing',decidedBy=account,disclosures=copy.deepcopy(actions));self._save(record)
        for index, action in enumerate(actions):
            cid='ai-knowledge:'+record['rulingId'].split(':')[1]+':'+str(index)
            entry={'id':cid,'account':account,'receipt':{'status':'pending'}};record['receipts'].append(entry);self._save(record)
            try:entry['receipt']=self.app.rulings.host_command(account,cid,action['op'],action['args'])
            except Exception as exc:entry['receipt']={'status':'unknown','code':getattr(exc,'code','RESULT_UNKNOWN')}
            if entry['receipt']['status']!='committed':
                record['status']='unknown' if entry['receipt']['status'] in ('unknown','pending') else 'partial'
                self._save(record);return self.public(record)
            self._save(record)
        record['status']='completed';self._save(record);return self.public(record)

    def reconcile(self, account, args):
        self.host.kp(account)
        record=self.repository.state()['settings'].get('knowledgeRequests',{}).get(args['rulingId'])
        require(record and record['digest']==args['digest'], 'RULING_STALE')
        require(record['status'] in ('unknown','executing'), 'RULING_NOT_READY')
        for entry in record['receipts']:
            if entry['receipt']['status'] in ('pending','unknown'):entry['receipt']=self.host.receipt(entry['account'],entry['id'])
        statuses=[r['receipt']['status'] for r in record['receipts']]
        record['status']='unknown' if any(s in ('pending','unknown') for s in statuses) else 'completed' if len(statuses)==len(record['disclosures']) and all(s=='committed' for s in statuses) else 'partial'
        self._save(record);return self.public(record)
