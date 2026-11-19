"""Immutable, reviewed command batches; durable per-command receipts, no blind retries."""
import copy
import threading
import uuid
from jsonschema import Draft202012Validator
from onlinecoc.contracts import OPERATIONS as HOST_OPERATIONS
from .contracts import canonical, digest
from .errors import require
from .access import policy, binding

# Configuration/rule publication must use the existing A/B/C proposal path.
HOST_OPS = ('entity.create','entity.patch','entity.update','entity.archive','relation.set','relation.remove',
    'progress.set','asset.attach','asset.remove','flow.respond','flow.retry','flow.cancel','room.status',
    'member.add','member.update','action.invoke','behavior.invoke','chat.direct.open','chat.channel.create','chat.channel.update','chat.message.send','chat.message.share','chat.message.edit','chat.message.retract')
AI_OPS = ('ai.session.create','ai.session.update','ai.session.delete','ai.memory.create','ai.memory.confirm','ai.memory.revoke')
ACTION = {'type':'object','additionalProperties':False,'required':['target','op','args'],
    'properties':{'target':{'enum':['host','ai']},'op':{'type':'string','maxLength':80},'args':{'type':'object'}}}
ACTIONS = {'type':'array','minItems':1,'maxItems':8,'items':ACTION}


def world(host, repository):
    state = host.state()
    return digest({k:state[k] for k in ('roomId','runId','status','activeRuleset','entities','configurations','relations',
        'members','progress','flows','waits','chat','assets')} | {'sessions':repository.state()['settings'].get('sessions',{})})


class Batches:
    def __init__(self, app):
        self.app, self.host, self.repository = app, app.host, app.repository
        self.lock = threading.RLock()

    def read(self, account, section, offset=0, limit=20):
        self.host.kp(account)
        state=self.host.state()
        require(section in ('members','relations','progress','flows','waits','assets','room') and
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
        return {'host':{op:HOST_OPERATIONS[op] for op in HOST_OPS if op in HOST_OPERATIONS},
            'ai':{op:local_schema(OPERATIONS[op]) for op in AI_OPS},
            'actions':self.host.catalog(account),
            'notice':'Propose immutable actions as kind=batch; every change awaits administrator approval. Configuration/rule edits use kind=draft and A/B/C review. No filesystem, credentials or permission-setting commands.'}

    def validate_actions(self, account, actions):
        require(Draft202012Validator(ACTIONS).is_valid(actions) and len(canonical(actions)) <= 32*1024, 'INPUT_INVALID')
        catalog = self.catalog(account)
        for action in actions:
            schema = catalog[action['target']].get(action['op'])
            require(schema is not None and Draft202012Validator(schema).is_valid(action['args']), 'BATCH_OPERATION_FORBIDDEN')

    def create(self, account, request, actions, summary, context):
        with self.host.lock, self.lock:
            access = binding(self.host, self.repository, request)
            require(access and access['level'] == 'administrator', 'PERMISSION_DENIED')
            self.validate_actions(account, actions)
            self.host.validate_ai_sources(self.host.state(), account, context)
            identifier = uuid.uuid4().hex
            record = {'batchId':identifier, 'sessionId':access['sessionId'], 'requestId':request['requestId'],
                'creator':account, 'summary':summary, 'actions':copy.deepcopy(actions), 'context':copy.deepcopy(context),
                'baseline':world(self.host,self.repository), 'authorityEpoch':self.host.epoch,
                'status':'pending', 'revision':1, 'createdAt':self.host.clock(), 'receipts':[]}
            record['digest'] = digest({k:record[k] for k in ('batchId','sessionId','requestId','creator','actions','context','baseline','authorityEpoch')})
            def save(state):
                batches=state['settings'].setdefault('batches',{})
                require(len(batches)<1000,'LIMIT_EXCEEDED');batches[identifier]=record
            self.repository.update(save)
            if policy(self.repository)['autoApproveBatches']:
                principal = policy(self.repository)['principal']
                self.execute(principal,'auto:'+identifier,'ai.batch.approve',{'batchId':identifier,'digest':record['digest']})
            return identifier

    def list(self, account):
        with self.host.lock:self.host.kp(account)
        return {'items':sorted([{k:copy.deepcopy(v) for k,v in b.items() if k not in ('context','baseline')}
            for b in self.repository.state()['settings'].get('batches',{}).values()],key=lambda b:b['createdAt'],reverse=True)}

    def _save(self, record):
        self.repository.update(lambda s:s['settings']['batches'].update({record['batchId']:copy.deepcopy(record)}))

    def execute(self, account, identifier, op, args):
        with self.host.lock, self.lock:
            self.host.kp(account)
            record = self.repository.state()['settings'].get('batches',{}).get(args['batchId'])
            require(record is not None,'NOT_VISIBLE')
            require(record['digest'] == args['digest'],'BATCH_VERSION_CONFLICT')
            if op == 'ai.batch.reconcile':
                require(record['status'] in ('executing','unknown'),'BATCH_NOT_UNCERTAIN')
                # Recover committed results, never replay an ambiguous side effect.
                for entry in record['receipts']:
                    if entry['receipt']['status'] in ('pending','unknown'):
                        entry['receipt'] = self.app.receipt(entry['account'],entry['id']) if entry['target']=='ai' else self.host.receipt(entry['account'],entry['id'])
                statuses=[r['receipt']['status'] for r in record['receipts']]
                record['status']='unknown' if any(s in ('pending','unknown') for s in statuses) else 'completed' if len(statuses)==len(record['actions']) and all(s=='committed' for s in statuses) else 'partial'
                self._save(record);return record
            require(record['status']=='pending','BATCH_NOT_PENDING')
            require(op in ('ai.batch.approve','ai.batch.reject'),'INPUT_INVALID')
            record.update(decidedBy=account,decidedAt=self.host.clock(),revision=record['revision']+1)
            if op == 'ai.batch.reject':
                record['status']='rejected';self._save(record);return record
            require(self.repository.state()['requests'][record['requestId']]['status']!='cancelled','REQUEST_CANCELLED')
            require(record['authorityEpoch']==self.host.epoch,'STALE_AUTHORITY')
            self.host.validate_ai_sources(self.host.state(),record['creator'],record['context'])
            require(record['baseline']==world(self.host,self.repository),'BATCH_STALE')
            self.validate_actions(account,record['actions'])
            record['status']='executing';self._save(record)
            for index, action in enumerate(record['actions']):
                cid='ai-batch:'+record['batchId']+':'+str(index)
                entry={'id':cid,'account':account,'target':action['target'],'receipt':{'status':'pending'}}
                record['receipts'].append(entry);self._save(record)
                try:
                    if action['target']=='ai':
                        receipt=self.app.command(account,{'requestId':cid,'authorityEpoch':self.host.epoch,'op':action['op'],'args':action['args']})
                    else:
                        state=self.host.state();cat=self.host.catalog(account)
                        receipt=self.host.command(account,{'protocolVersion':1,'type':'command','requestId':cid,'roomId':state['roomId'],
                            'payload':{'commandId':cid,'authorityEpoch':self.host.epoch,'runId':state['runId'],'catalogRevision':cat['revision'],
                                'rulesetRevision':cat['rulesetRevision'],'op':action['op'],'args':action['args']}})
                    entry['receipt']=receipt
                except Exception as exc:
                    entry['receipt']={'status':'unknown','code':getattr(exc,'code','RESULT_UNKNOWN')}
                if entry['receipt']['status']!='committed':
                    record['status']='unknown' if entry['receipt']['status'] in ('pending','unknown') else 'partial'
                    self._save(record);return record
                self._save(record)
            record['status']='completed';self._save(record);return record
