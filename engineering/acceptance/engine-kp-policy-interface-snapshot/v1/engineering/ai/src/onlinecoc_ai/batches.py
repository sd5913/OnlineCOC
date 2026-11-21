"""Immutable, reviewed command batches; durable per-command receipts, no blind retries."""
import copy
import threading
import uuid
from jsonschema import Draft202012Validator
from onlinecoc.contracts import OPERATIONS as HOST_OPERATIONS
from .contracts import canonical, digest
from .errors import require, AiError
from .access import policy, binding

# Configuration/rule publication must use the existing A/B/C proposal path.
HOST_OPS = ('entity.create','entity.patch','entity.update','entity.archive','relation.set','relation.remove',
    'progress.set','asset.attach','asset.remove','flow.respond','flow.retry','flow.cancel','room.status',
    'member.add','member.update','notification.send','action.invoke','behavior.invoke','chat.direct.open','chat.channel.create','chat.channel.update','chat.message.send','chat.message.share','chat.message.edit','chat.message.retract')
AI_OPS = ('ai.session.create','ai.session.update','ai.session.delete','ai.memory.create','ai.memory.confirm','ai.memory.revoke')
ACTION = {'type':'object','additionalProperties':False,'required':['target','op','args'],
    'properties':{'target':{'enum':['host','ai']},'op':{'type':'string','maxLength':80},'args':{'type':'object'}}}
ACTIONS = {'type':'array','minItems':1,'items':ACTION}


def world(host, repository, version=2):
    state = host.state()
    value={k:state[k] for k in ('roomId','runId','status','activeRuleset','entities','configurations','relations',
        'members','progress','flows','waits','assets')}
    if version==1:value.update(chat=state['chat'],sessions=repository.state()['settings'].get('sessions',{}))
    return digest(value)


class Batches:
    def __init__(self, app):
        self.app, self.host, self.repository = app, app.host, app.repository
        self.lock = threading.RLock()

    def read(self, account, section, offset=0, limit=20):
        self.host.kp(account)
        state=self.host.state()
        require(section in ('members','relations','progress','flows','waits','assets','room','configurations') and
            type(offset) is int and offset>=0 and type(limit) is int and 1<=limit<=50,'INPUT_INVALID')
        value={k:state[k] for k in ('roomId','name','runId','status','activeRuleset')} if section=='room' else state[section]
        keys=sorted(value)
        result={'section':section,'snapshot':digest(value),'items':[{ 'id':key,'value':value[key]} for key in keys[offset:offset+limit]],
            'nextOffset':offset+limit if offset+limit<len(keys) else None}
        require(len(canonical(result))<=32*1024,'QUERY_RESULT_LIMIT')
        return result

    def catalog(self, account):
        self.host.kp(account)
        from .api import OPERATIONS
        from .contracts import SCHEMAS
        def local_schema(schema):
            definitions={}
            def visit(value):
                if isinstance(value,dict):
                    ref=value.get('$ref','')
                    if ref.startswith('#/$defs/'):
                        key=ref.split('/')[-1]
                        if key not in definitions:definitions[key]=SCHEMAS['$defs'][key];visit(definitions[key])
                    for item in value.values():visit(item)
                elif isinstance(value,list):
                    for item in value:visit(item)
            visit(schema)
            return {**schema,**({'$defs':definitions} if definitions else {})}
        host_operations={op:copy.deepcopy(HOST_OPERATIONS[op]) for op in HOST_OPS if op in HOST_OPERATIONS}
        if 'notification.send' in host_operations:
            schema=host_operations['notification.send']
            for field in ('sourceCommandId','sourceOp'):schema['properties'].pop(field,None)
            schema['required']=[field for field in schema['required'] if field not in ('sourceCommandId','sourceOp')]+['sourceActionIndex']
            schema['properties']['sourceActionIndex']={'type':'integer','minimum':0,'description':'Zero-based index of an earlier non-notification host action in this same reviewed batch. The server supplies its command ID and operation only after a committed receipt.'}
        from onlinecoc.atomic_batches import SUPPORTED
        from .batch_execution import LOCAL,MEMORY
        execution_scopes={'host.room.atomic.v1':{'target':'host','operations':sorted(set(HOST_OPS)&SUPPORTED),
                'constraints':'Public action-mode rules only; cannot update the executor member. No flows or external waits.'},
            'ai.store.atomic.v1':{'target':'ai','operations':sorted(LOCAL)},
            'host.memory.single.v1':{'target':'ai','operations':sorted(MEMORY),'singleActionOnly':True},
            'unsupportedHostOperations':sorted(set(HOST_OPS)-SUPPORTED),
            'combinationPolicy':'All actions must fit one scope. Do not split a requested batch or omit unsupported actions. Unsupported candidates are blocked before business effects.'}
        return {'host':host_operations,
            'ai':{op:local_schema(OPERATIONS[op]) for op in AI_OPS},
            'actions':self.host.catalog(account),
            'executionScopes':execution_scopes,
            'notice':'Propose immutable actions as kind=batch; every change awaits administrator approval. Configuration/rule edits use kind=draft and A/B/C review. No filesystem, credentials or permission-setting commands.'}

    def validate_actions(self, account, actions):
        require(policy(self.repository)['allowRuntimeChanges'], 'RUNTIME_CHANGES_DISABLED')
        require(Draft202012Validator(ACTIONS).is_valid(actions), 'INPUT_INVALID')
        require(len(canonical(actions)) <= 32*1024, 'BATCH_PAYLOAD_TOO_LARGE')
        catalog = self.catalog(account)
        for index,action in enumerate(actions):
            schema = catalog[action['target']].get(action['op'])
            require(schema is not None, 'BATCH_OPERATION_FORBIDDEN',path=f'/actions/{index}/op')
            error=next(Draft202012Validator(schema).iter_errors(action['args']),None)
            if error:
                path='/'.join(str(part).replace('~','~0').replace('/','~1') for part in error.absolute_path)
                raise AiError('BATCH_ARGUMENTS_INVALID',error.message[:400],path=f'/actions/{index}/args'+('/'+path if path else ''))
            if action['target']=='host' and action['op']=='action.invoke':
                rule=next((row for row in catalog['actions']['actions'] if row['id']==action['args']['actionId']),None)
                require(rule is not None,'ACTION_NOT_FOUND',path=f'/actions/{index}/args/actionId')
                error=next(Draft202012Validator(rule['schema']).iter_errors(action['args']['input']),None)
                if error:
                    path='/'.join(map(str,error.absolute_path))
                    raise AiError('RULE_INPUT_INVALID',error.message[:400],path=f'/actions/{index}/args/input'+('/'+path if path else ''))
            if action['op']=='notification.send':
                source=action['args']['sourceActionIndex']
                require(action['target']=='host' and type(source) is int and 0<=source<index and actions[source]['target']=='host' and actions[source]['op'] in HOST_OPERATIONS['notification.send']['properties']['sourceOp']['enum'],'NOTIFICATION_SOURCE_ACTION_INVALID')

    def catalog_query(self, account, operations=None, *, public_only=False):
        catalog=self.catalog(account)
        if public_only:catalog['actions']={'omitted':True,'code':'EXTERNAL_SCOPE_DISABLED','requiredScope':'kp'}
        if operations is None:
            return {'mode':'index','host':list(catalog['host']),'ai':list(catalog['ai']),
                'actions':catalog['actions'],
                'executionScopes':catalog['executionScopes'],
                'notice':'Call room_manage_catalog with operations:[exact operation names] for the required parameter schemas before proposing actions. No command has been executed.'}
        require(set(operations)<=set(catalog['host'])|set(catalog['ai']), 'INPUT_INVALID')
        return {'mode':'schemas',**{target:{op:schema for op,schema in catalog[target].items() if op in operations} for target in ('host','ai')},
            'actions':catalog['actions'],'executionScopes':catalog['executionScopes'],'notice':catalog['notice']}

    def create(self, account, request, actions, summary, context, *, generation=None):
        with self.host.lock, self.lock:
            context=copy.deepcopy(context)
            context['facts']['batchBaselineVersion']=2
            context['facts']['batchExecutionVersion']=2
            access = binding(self.host, self.repository, request)
            require(access and access['level'] == 'administrator', 'PERMISSION_DENIED')
            state=self.repository.state()
            from .review_queue import canonical_request
            existing=next((b for b in state['settings'].get('batches',{}).values() if canonical_request(state,b['requestId'])==canonical_request(state,request['requestId'])),None)
            if existing:
                require(existing['actions']==actions and existing['summary']==summary,'REQUEST_CANDIDATE_CONFLICT')
                return existing['batchId']
            self.validate_actions(account, actions)
            from .history import require_current_evidence
            require_current_evidence(context,{'kind':'batch','actions':actions})
            if generation:generation.guard()
            else:self.host.validate_ai_sources(self.host.state(), account, context)
            preflight=(generation.app.batches if generation else self).preflight(account,actions)
            identifier = uuid.uuid4().hex
            record = {'batchId':identifier, 'sessionId':access['sessionId'], 'requestId':request['requestId'],
                'creator':account, 'summary':summary, 'actions':copy.deepcopy(actions), 'context':copy.deepcopy(context),
                'baseline':world(generation.host,generation.repository) if generation else world(self.host,self.repository), 'authorityEpoch':self.host.epoch,
                'status':'blocked' if preflight['status'] in ('blocked','unsupported') else 'pending',
                'preflight':preflight,'revision':1, 'createdAt':self.host.clock(), 'receipts':[]}
            record['digest'] = digest({k:record[k] for k in ('batchId','sessionId','requestId','creator','actions','context','baseline','authorityEpoch')})
            def save(state):
                batches=state['settings'].setdefault('batches',{})
                batches[identifier]=record
            self.repository.update(save)
            if record['status']=='pending':self.app.queue.ready('batch:'+identifier)
            if record['status']=='pending' and policy(self.repository)['autoApproveBatches'] and not self.app.player_requests.review_required(access['sessionId']) and (not generation or generation.check()['status']=='unchanged'):
                principal = policy(self.repository)['principal']
                self.execute(principal,'auto:'+identifier,'ai.batch.approve',{'batchId':identifier,'digest':record['digest']})
            return identifier

    def preflight(self,account,actions):
        from .batch_execution import AtomicExecution
        return AtomicExecution(self).preflight(account,actions)

    def list(self, account):
        with self.host.lock:self.host.kp(account)
        return {'items':sorted([self.public(account,b) for b in self.repository.state()['settings'].get('batches',{}).values()],key=lambda b:b['createdAt'],reverse=True)}

    def public(self,account,record):
        item={k:copy.deepcopy(v) for k,v in record.items() if k not in ('context','baseline','batchReceipt')}
        return self.app.rulings.redact_stale(account,self.host.state(),item,record['context'])

    def _save(self, record):
        if record['status']=='completed':record.setdefault('completedAt',self.host.clock())
        self.repository.update(lambda s:s['settings']['batches'].update({record['batchId']:copy.deepcopy(record)}))
        if record['status']=='completed':self.app.queue.reconcile_completed()

    def execute(self, account, identifier, op, args):
        with self.host.lock, self.lock:
            self.host.kp(account)
            record = self.repository.state()['settings'].get('batches',{}).get(args['batchId'])
            require(record is not None,'NOT_VISIBLE')
            require(record['digest'] == args['digest'],'BATCH_VERSION_CONFLICT')
            if op == 'ai.batch.reconcile':
                require(record['status'] in ('executing','unknown'),'BATCH_NOT_UNCERTAIN')
                if record['context']['facts'].get('batchExecutionVersion')==2:
                    from .batch_execution import AtomicExecution
                    return AtomicExecution(self).reconcile(account,record)
                # Recover committed results, never replay an ambiguous side effect.
                for entry in record['receipts']:
                    if entry['receipt']['status'] in ('pending','unknown'):
                        entry['receipt'] = self.app.receipt(entry['account'],entry['id']) if entry['target']=='ai' else self.host.receipt(entry['account'],entry['id'])
                statuses=[r['receipt']['status'] for r in record['receipts']]
                record['status']='unknown' if any(s in ('pending','unknown') for s in statuses) else 'completed' if len(statuses)==len(record['actions']) and all(s=='committed' for s in statuses) else 'partial' if any(s=='committed' for s in statuses) else 'failed'
                self._save(record);return record
            self.app.queue.require_active('batch:'+record['batchId'])
            require(record['status']=='pending','BATCH_NOT_PENDING')
            require(op in ('ai.batch.approve','ai.batch.reject'),'INPUT_INVALID')
            record.update(decidedBy=account,decidedAt=self.host.clock(),revision=record['revision']+1)
            if op == 'ai.batch.reject':
                record['status']='rejected';self._save(record);return record
            require(record['context']['facts'].get('batchExecutionVersion')==2,'BATCH_REGENERATE_REQUIRED','Legacy pending candidates have no atomic guarantee; generate a new candidate before execution')
            require(self.repository.state()['requests'][record['requestId']]['status']!='cancelled','REQUEST_CANCELLED')
            require(record['authorityEpoch']==self.host.epoch,'STALE_AUTHORITY')
            self.host.validate_ai_sources(self.host.state(),record['creator'],record['context'])
            require(record['baseline']==world(self.host,self.repository,record['context']['facts'].get('batchBaselineVersion',1)),'BATCH_STALE')
            self.validate_actions(account,record['actions'])
            record['preflight']=self.preflight(account,record['actions'])
            if record['preflight']['status'] in ('blocked','unsupported'):
                record['status']='blocked';self._save(record);return record
            from .batch_execution import AtomicExecution
            return AtomicExecution(self).run(account,record)

