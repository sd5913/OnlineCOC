"""One KP queue for immutable runtime batches and checked configuration publications."""
import copy
import re
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

    def redact_stale(self, account, room, item, context, shared=None):
        original=item['summary']
        try:
            from .history import assess,NOTICE
            stale=assess(self.host,self.repository,room,context,shared=shared)
            item['sourceState']='fresh'
            if stale:item.update(sourceState='stale',sourceError=stale,sourceNotice=NOTICE,historicalReadOnly=True,canDecide=False,canRevalidate=False)
        except (AiError,DomainError) as exc:
            item.update(sourceUnavailable=True,sourceState='denied',sourceError=exc.code)
            # A successful mutation normally changes its own source revision.
            # Preserve durable execution facts, never redisplay revoked source content.
            summaries={
                'completed':'已执行完成；原引用或访问权限已变化，详情已隐藏，请勿重复执行。',
                'partial':'部分操作已执行；原引用或访问权限已变化，详情已隐藏。请核对原回执，不要重做整批。',
                'executing':'执行结果待核对；原引用或访问权限已变化，详情已隐藏，请核对原回执。',
                'unknown':'执行结果待核对；原引用或访问权限已变化，详情已隐藏，请核对原回执。',
                'rejected':'已拒绝；原引用或访问权限已变化，详情已隐藏。',
                'cancelled':'已取消；原引用或访问权限已变化，详情已隐藏。'}
            summaries.update(failed='执行失败，业务修改未提交；原引用或访问权限已变化，详情已隐藏。',
                rolled_back='批次失败，暂存修改已撤销；原引用或访问权限已变化，详情已隐藏。')
            receipts=[]
            for entry in item.get('receipts',[]):
                raw=entry.get('receipt',entry);status=raw.get('status')
                if status in ('committed','rejected','pending','unknown'):
                    receipts.append({'receipt':{'status':status}} if 'receipt' in entry else {'status':status})
            if item['status']=='partial' and not any(r.get('receipt',r).get('status')=='committed' for r in receipts):
                summaries['partial']='旧批次没有成功提交项；原引用或访问权限已变化，详情已隐藏。旧记录不能证明事务回滚。'
            item.update(summary=summaries.get(item['status'],'来源权限或资料已变化，当前内容不能执行；请重新读取并生成方案。'),
                canDecide=False,canRevalidate=False,risks=[],receipts=receipts)
            item.pop('cAssessment',None)
            for key in ('actions','changeSet','reports','publications','diff'):
                if key in item:item[key]=[]
            item.pop('preflight',None)
            for key in ('executionCommandId','executionAccount','batchReceipt'):item.pop(key,None)
            if 'execution' in item:
                item['execution']={k:v for k,v in item['execution'].items() if k in ('status','scope','committedCount','failedCount','notExecutedCount','rolledBackCount')}
            from .ruling_history import restore
            if restore(self.repository,room,account,item,context,original):
                item.update(summary=original,sourceState='stale',historicalReadOnly=True,sourceDetailsUnavailable=True)
                item.pop('sourceUnavailable',None)
        return item

    @staticmethod
    def decision_for_revision(decision, proposal):
        if not decision:return {}
        revision=decision.get('proposalRevision')
        receipts=decision.get('receipts',[])
        if receipts:
            # Legacy records have no revision field. Require all receipt IDs to
            # agree; a prefix match or the first of conflicting receipts is unsafe.
            pattern=re.escape('ai-ruling:'+proposal['proposalId']+':')+r'([1-9][0-9]*):(approve|apply)'
            matches=[re.fullmatch(pattern,r.get('commandId','')) for r in receipts]
            revisions={int(m[1]) for m in matches if m}
            if all(matches) and len(revisions)==1:
                inferred=next(iter(revisions))
                if 'proposalRevision' not in decision:revision=inferred
                elif revision!=inferred:revision=None
            else:revision=None
        same_digest=decision.get('digest')==proposal['candidateDigest']
        if type(revision) is not int or revision<1:
            # An unbound interrupted intent is not evidence of non-execution,
            # even when a later candidate has a different digest.
            return decision if same_digest or decision.get('status') in ('unknown','executing') else {}
        return decision if revision==proposal['revision'] and same_digest else {}

    def list(self, account, session_id=None, *, delivered=False, ruling_ids=None, compact=False):
        with self.host.lock,self.repository.read_scope():
            self.host.kp(account)
            room=self.host.state();state=self.repository.read_state();items=[];history_shared={};contexts={}
            for batch in state['settings'].get('batches',{}).values():
                if ruling_ids is not None and 'batch:'+batch['batchId'] not in ruling_ids:continue
                if session_id is not None and batch['sessionId']!=session_id:continue
                item={k:copy.deepcopy(batch[k]) for k in (('sessionId','requestId','summary','status','createdAt','digest') if compact else ('sessionId','requestId','summary','status','createdAt','digest','actions','receipts'))}
                item.update(rulingId='batch:'+batch['batchId'],kind='runtime',canDecide=batch['status']=='pending' and batch.get('preflight',{}).get('status') in ('passed','runtime_required'),risks=[])
                from .consultation import assessment
                item['consultationAssessment']=assessment(batch['context'])
                if item['consultationAssessment']['requiresAcceptance']:item['risks'].append({'id':'consultation-source','question':item['consultationAssessment']['notice'],'required':True})
                for key in ('preflight','execution'):
                    if not compact and key in batch:item[key]=copy.deepcopy(batch[key])
                request=state['requests'][batch['requestId']]
                item['initiator']=request['initiator']
                if request['status']=='cancelled' and item['status']=='pending':item['status']='cancelled'
                contexts[item['rulingId']]=batch['context']
                items.append(self.redact_stale(account,room,item,batch['context'],history_shared))
            for pid,record in state['proposals'].items():
                if ruling_ids is not None and 'proposal:'+pid not in ruling_ids:continue
                proposal=record['revisions'][str(record['currentRevision'])];request=state['requests'][proposal['requestId']]
                session=request_session(self.repository,request)
                if session_id is not None and (session or {}).get('sessionId')!=session_id:continue
                context=state['contexts'][proposal['contextRef']]
                reports=[state['reports'][r] for r in proposal['reportRefs']]
                rid='proposal:'+proposal['proposalId'];decision=self.decision_for_revision(state['settings'].get('rulingDecisions',{}).get(rid,{}),proposal)
                status='pending' if proposal['status']=='review_ready' else proposal['status']
                if decision:status=decision['status']
                if request['status']=='cancelled':status='rejected'
                publications=[p for p in room['aiControl']['publications'].values() if p['candidateDigest']==proposal['candidateDigest'] and room['aiControl']['approvals'][p['approvalId']]['proposalId']==proposal['proposalId']]
                if publications:status='completed'
                consultation_only=context['facts'].get('consultationOnly',False)
                risks=[copy.deepcopy(r) for r in self.app.proposals.pack.contract['reviewPolicy']['items'] if r['required']]
                if any(r['risk'] in ('medium','high','unknown') for r in reports):risks.append({'id':'gameplay-risk','question':'接受已报告的游戏性影响与未覆盖范围','required':True})
                item={'rulingId':rid,'kind':'configuration','sessionId':session['sessionId'] if session else None,
                    'requestId':proposal['requestId'],'initiator':request['initiator'],'summary':proposal['summary'],'status':status,'createdAt':proposal['createdAt'],
                    'digest':proposal['candidateDigest'],'revision':proposal['revision'],'canDecide':context['reviewPrincipal']==account and not context['facts'].get('strictPlayer'),
                    'changeSet':{} if compact else copy.deepcopy(proposal['changeSet']),'reports':[] if compact else copy.deepcopy(reports),'risks':risks,
                    'receipts':copy.deepcopy(decision.get('receipts',[])), 'publications':copy.deepcopy(publications)}
                from .change_policy import describe
                snapshot=state['snapshots'][proposal['contextRef']]
                item.update(describe(self.app.proposals.pack.contract,snapshot['state'],snapshot['artifact'],proposal['changeSet'],include_diff=not compact))
                if item['highRisk']:item['risks'].append({'id':'high-risk','question':'高危修改必须人工确认：请核对完整指令包和差异，填写接受理由','required':True})
                c_report = next((r for r in reports if r['level'] == 'C'), None)
                if c_report and c_report.get('evidence', {}).get('reviewBasis'):
                    from .c_review import basis, basis_binding, assessment
                    evidence = c_report['evidence']['reviewBasis']
                    evaluated = {k: evidence[k] for k in ('revision', 'metricOverrides', 'liveScenarios', 'notes')}
                    item['cAssessment'] = {**assessment(reports, evaluated),
                        'stale': basis_binding(basis(self.repository)) != basis_binding(evaluated),
                        'findings': copy.deepcopy(c_report['findings']),
                        'limitations': copy.deepcopy(c_report['evidence'].get('limitations', []))}
                    item['canRevalidate'] = item['cAssessment']['stale'] and status in ('pending','blocked') and item['canDecide']
                    if item['cAssessment']['stale'] and status == 'pending':
                        item.update(canDecide=False, blockingReason='C_BASIS_STALE')
                from .consultation import assessment
                item['consultationAssessment']=assessment(context)
                if item['consultationAssessment']['requiresAcceptance']:item['risks'].append({'id':'consultation-source','question':item['consultationAssessment']['notice'],'required':True})
                contexts[item['rulingId']]=context
                items.append(self.redact_stale(account,room,item,context,history_shared))
            items.extend(self.app.knowledge_requests.list(account,ruling_ids=ruling_ids))
            items.extend(self.app.player_requests.list(account,ruling_ids=ruling_ids))
            for item in items:self.app.queue.decorate(item,state=state,room=room)
            visible=sorted([i for i in items if session_id is None or i['sessionId']==session_id],key=lambda i:i['createdAt'],reverse=True)
            if delivered:
                from .ruling_history import remember
                remember(self.repository,room,account,visible,contexts)
            if compact:
                keys={'rulingId','kind','sessionId','requestId','initiator','summary','status','createdAt','digest','revision','sourceState','sourceError','sourceNotice','sourceUnavailable','sourceDetailsUnavailable','historicalReadOnly','queueTargetId','queueDigest','correlationId','queueStatus','archived','canArchive','canRestore','supersededBy','supersedes','archiveReason','resolution','highRisk','riskTags','reviewSessionId','generationError','blockingReason','consultationAssessment'}
                visible=[{**{k:v for k,v in i.items() if k in keys},'compact':True,'canDecide':False} for i in visible]
            return {'items':visible}

    def detail(self, account, ruling_id, *, delivered=False):
        require(isinstance(ruling_id,str) and re.fullmatch(r'(batch|proposal|knowledge|player):[a-f0-9]{32}',ruling_id),'INPUT_INVALID')
        items=self.list(account,delivered=delivered,ruling_ids={ruling_id})['items']
        require(bool(items),'NOT_VISIBLE')
        return items[0]

    def page(self, account, *, queue='active', before=None, limit=30, session_id=None, delivered=False):
        require(queue in ('active','archived','all') and type(limit) is int and 1<=limit<=100,'INPUT_INVALID')
        require(session_id is None or isinstance(session_id,str) and re.fullmatch('[a-f0-9]{32}',session_id),'INPUT_INVALID')
        with self.host.lock,self.repository.read_scope():
            self.host.kp(account);state=self.repository.read_state()
            room=self.host.state()
            published={(p['candidateDigest'],room['aiControl']['approvals'][p['approvalId']]['proposalId']) for p in room['aiControl']['publications'].values()}
            key=(self.repository.store.generation,id(state),frozenset(published))
            if getattr(self,'_page_index',None) is None or self._page_index[0]!=key:
                rows=[];meta=state['settings'].get('reviewQueue',{})
                for group,prefix in (('batches','batch:'),('knowledgeRequests',''),('playerRequests','')):
                    for k,v in state['settings'].get(group,{}).items():
                        status=v['status']
                        if status=='pending' and state['requests'].get(v['requestId'],{}).get('status')=='cancelled':status='cancelled'
                        rows.append((v['createdAt'],prefix+k,v.get('sessionId'),status))
                for k,v in state['proposals'].items():
                    p=v['revisions'][str(v['currentRevision'])];request=state['requests'][p['requestId']]
                    session=request_session(self.repository,request)
                    status=self.decision_for_revision(state['settings'].get('rulingDecisions',{}).get('proposal:'+k,{}),p).get('status',p['status'])
                    if state['requests'][p['requestId']]['status']=='cancelled':status='rejected'
                    if (p['candidateDigest'],k) in published:status='completed'
                    rows.append((p['createdAt'],'proposal:'+k,session['sessionId'] if session else None,status))
                rows.sort(key=lambda r:(r[0],r[1]),reverse=True)
                self._page_index=(key,[(rid,sid,bool(meta.get(rid,{}).get('archived') or meta.get(rid,{}).get('supersededBy') or status in ('completed','published','accepted','rejected','cancelled','failed','rolled_back'))) for _,rid,sid,status in rows],state)
            active_count=sum(not archived for rid,sid,archived in self._page_index[1] if session_id is None or sid==session_id)
            ids=[rid for rid,sid,archived in self._page_index[1] if (session_id is None or sid==session_id) and (queue=='all' or archived==(queue=='archived'))]
            if before is not None:
                require(before in ids,'CURSOR_INVALID');ids=ids[ids.index(before)+1:]
            chosen=ids[:limit];items=self.list(account,ruling_ids=set(chosen),compact=True,delivered=delivered)['items'];by_id={i['rulingId']:i for i in items}
            return {'items':[by_id[i] for i in chosen if i in by_id],'nextBefore':chosen[-1] if len(ids)>limit else None,'activeCount':active_count}

    def host_command(self, account, identifier, op, args):
        existing=self.host.receipt(account,identifier)
        if existing['status']!='unknown':return existing
        room=self.host.state();cat=self.host.catalog(account)
        return self.host.command(account,{'protocolVersion':1,'type':'command','requestId':identifier,'roomId':room['roomId'],
            'payload':{'commandId':identifier,'authorityEpoch':self.host.epoch,'runId':room['runId'],
                'catalogRevision':cat['revision'],'rulesetRevision':cat['rulesetRevision'],'op':op,'args':args}})

    def decide(self, account, args, *, automatic=False):
        with self.host.lock,self.lock:
            self.host.kp(account)
            self.app.queue.require_active(args['rulingId'])
            if args['rulingId'].startswith('player:'):
                require(not automatic,'PERMISSION_DENIED')
                return self.app.player_requests.decide(account,args)
            if args['rulingId'].startswith('knowledge:'):
                require(not automatic,'PERMISSION_DENIED')
                return self.app.knowledge_requests.decide(account,args)
            item=self.detail(account,args['rulingId'])
            require(item and item['digest']==args['digest'],'RULING_STALE')
            if item['status'] in ('completed','rejected'):return item
            require(not item.get('cAssessment', {}).get('stale'), 'C_BASIS_STALE')
            require(item['canDecide'],'PERMISSION_DENIED')
            require(item['status']=='pending','RULING_NOT_READY')
            if args['decision']=='approve' and item.get('consultationAssessment',{}).get('requiresAcceptance'):
                require(not automatic and args.get('consultationReview')=={'sourceDigest':item['consultationAssessment']['sourceDigest']},'CONSULTATION_REVIEW_REQUIRED')
                require(len(args.get('riskDecisions',{}).get('consultation-source','').strip())>=3,'RISK_REVIEW_REQUIRED')
            if item['kind']=='runtime':
                self.app.batches.execute(account,'ruling:'+item['rulingId'],'ai.batch.'+('approve' if args['decision']=='approve' else 'reject'),
                    {'batchId':item['rulingId'].split(':',1)[1],'digest':item['digest'],**({'consultationReview':args['consultationReview']} if args.get('consultationReview') else {})})
            else:
                pid=item['rulingId'].split(':',1)[1]
                if args['decision']=='reject':
                    proposal=self.app.proposals.get(account,pid)
                    self.host.ai_proposal_head(account,pid,proposal['revision']+1)
                    self.repository.update(lambda s:s['requests'][proposal['requestId']].update(status='cancelled'))
                else:
                    proposal=self.app.proposals.get(account,pid)
                    if item.get('cAssessment', {}).get('requiresAcceptance'):
                        proof = {k: item['cAssessment'][k] for k in ('basisRevision', 'basisDigest', 'reportDigest')}
                        require(not automatic and args.get('cReview') == proof, 'C_REVIEW_REQUIRED')
                    if item.get('highRisk'):
                        require(not automatic and args.get('explicitHighRiskDigest')==item['digest'], 'HIGH_RISK_REVIEW_REQUIRED')
                    decisions=args.get('riskDecisions',{})
                    require({r['id'] for r in item['risks']}<=set(decisions),'RISK_REVIEW_REQUIRED')
                    # Durable intent: restart/retry never starts a second publication.
                    record={'digest':item['digest'],'proposalRevision':item['revision'],'status':'executing','decidedBy':account,'receipts':[]}
                    def save():self.repository.update(lambda s:s['settings'].setdefault('rulingDecisions',{}).update({item['rulingId']:copy.deepcopy(record)}))
                    save()
                    for stage,op in (('approve','ai.proposal.approve'),('apply','publication.apply')):
                        params={'proposalId':pid,'proposalRevision':item['revision'],'riskDecisions':decisions} if stage=='approve' else {'approvalId':receipt['result']['approvalId']}
                        if stage=='approve' and item.get('highRisk'):params['explicitHighRiskDigest']=item['digest']
                        if stage=='approve' and args.get('cReview'):params['cReview']=args['cReview']
                        if stage=='approve' and args.get('consultationReview'):params['consultationReview']=args['consultationReview']
                        try:receipt=self.host_command(account,'ai-ruling:'+pid+':'+str(item['revision'])+':'+stage,op,params)
                        except Exception:record['status']='unknown';save();raise
                        record['receipts'].append(receipt)
                        if receipt['status']!='committed':
                            record['status']='unknown' if receipt['status'] in ('pending','unknown') else 'blocked';save()
                            return self.detail(account,item['rulingId'])
                        save()
                    record['status']='completed';save();self.app.proposals.reconcile()
            return self.detail(account,item['rulingId'])

    def confirm_session(self, account, session):
        require(session['accessLevel']=='administrator','PERMISSION_DENIED')
        items=[i for i in self.list(account,session['sessionId'])['items'] if i.get('queueStatus') not in ('archived','superseded')];pending=[i for i in items if i['status']=='pending']
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
        item=self.detail(account,'proposal:'+proposal_id)
        if item['status']!='pending' or item.get('highRisk') or item.get('consultationAssessment',{}).get('requiresAcceptance') or item.get('cAssessment', {}).get('requiresAcceptance') or self.app.player_requests.review_required(item.get('sessionId')):return
        self.decide(account,{'rulingId':item['rulingId'],'digest':item['digest'],'decision':'approve',
            'riskDecisions':{r['id']:'KP 已开启通过三检后的普通配置自动批准' for r in item['risks']}},automatic=True)
