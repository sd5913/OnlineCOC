"""Bounded, room-local transactions for trusted composition (no HTTP bypass).

Business effects are staged in a detached room. Only intent/random journal and
one final business commit touch the store. Recovery requires the original room
digest; it never restores an old snapshot over intervening operations.
"""
import copy
import hashlib
import re
import secrets
import time

from jsonschema import Draft202012Validator
from onlinecoc_data import canonical, StoreError
from .contracts import _model_error, validate_operation
from .errors import DomainError, require
from .lua_runtime import execute
from .model import member, validate, visible, uid

SUPPORTED = frozenset(('entity.create', 'entity.patch', 'entity.update', 'entity.archive',
    'relation.set', 'relation.remove', 'progress.set', 'asset.attach', 'asset.remove',
    'room.status', 'member.update', 'notification.send', 'action.invoke', 'behavior.invoke',
    'chat.direct.open', 'chat.channel.create', 'chat.channel.update', 'chat.message.send',
    'chat.message.share', 'chat.message.edit', 'chat.message.retract'))
MAX_BYTES, MAX_ROLLS = 32768, 256
PREFLIGHT_SECONDS, EXECUTION_SECONDS = 10, 30
SCOPE = 'host.room.atomic.v1'
REASONS = {
    'INPUT_INVALID': '参数未满足契约，请检查参数路径。',
    'NOT_VISIBLE': '对象不存在或当前主体无权访问。',
    'PERMISSION_DENIED': '当前主体无权执行此操作。',
    'BATCH_UNSUPPORTED': '该操作或组合不在同一房间原子事务支持范围。',
    'BATCH_RUNTIME_REQUIRED': '需要正式运行判定；预检未消耗随机数。',
    'BATCH_DEPENDENCY_PENDING': '前项需要运行判定，当前项尚不能完成顺序预检。',
    'BATCH_PREFLIGHT_BUDGET': '预检时间预算已用尽，需要正式运行时重检。',
    'BATCH_TIMEOUT': '批次执行时间预算已用尽。',
    'BATCH_STATE_CHANGED': '执行期间或恢复前房间发生变化，暂存修改已丢弃。',
    'BATCH_PRECHECK_FAILED': '整批准入检查未通过，没有执行业务操作。',
    'BATCH_DEPENDENCY_FAILED': '前项检查失败，当前项未执行。',
    'COMMAND_ID_CONFLICT': '命令标识已绑定其他内容。',
    'RULE_FAILED': '规则拒绝执行；请检查安全规则错误码与业务前置条件。',
    'RULE_TIMEOUT': '规则工作进程超过执行预算。',
    'BATCH_INTERNAL_ERROR': '批次执行发生技术错误，暂存修改已丢弃。',
}


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def child_id(command_id, index):
    return 'batch-' + digest([command_id, index])


def room_digest(state, key):
    value=copy.deepcopy(state)
    value['commands'].pop(key, None)
    return digest(value)


def shape(actions):
    require(type(actions) is list and len(actions) >= 1, 'INPUT_INVALID')
    try: size=len(canonical(actions))
    except (TypeError, ValueError, RecursionError):raise DomainError('INPUT_INVALID') from None
    require(size <= MAX_BYTES, 'LIMIT_EXCEEDED')
    for index, action in enumerate(actions):
        require(type(action) is dict and set(action)=={'target','op','args'}
            and type(action['target']) is str and type(action['op']) is str
            and len(action['op'])<=100 and type(action['args']) is dict, 'INPUT_INVALID')


def item(action, index, status, command_id=None):
    value={'index':index,'target':action['target'],'op':action['op'],'status':status}
    if command_id:value['commandId']=child_id(command_id,index)
    if action['op']=='action.invoke' and type(action['args'].get('actionId')) is str:
        value['ruleId']=action['args']['actionId']
    return value


def diagnostic(error, index, action):
    code=error.code if isinstance(error, DomainError) else 'BATCH_INTERNAL_ERROR'
    if isinstance(error,StoreError) and str(error)=='VERSION_CONFLICT':code='BATCH_STATE_CHANGED'
    if not isinstance(code,str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{1,79}',code):code='BATCH_INTERNAL_ERROR'
    result={'code':code,'reason':REASONS.get(code, '操作未满足当前规则或状态约束。'),
        'path':f'/actions/{index}/args'}
    detail=getattr(error,'detail',None)
    if isinstance(detail,dict):
        path=detail.get('path')
        if isinstance(path,str) and path.startswith('/') and len(path)<=512:
            result['path']+=path
        rule_code=detail.get('ruleCode')
        if isinstance(rule_code,str) and re.fullmatch(r'[A-Z][A-Z0-9_]{2,79}',rule_code):
            result['ruleCode']=rule_code
            result['reason']+=' 规则原因：'+rule_code+'。'
    # Caller-supplied object identifiers only; never copy hidden state or args.
    args=action['args']; args=args.get('input',args)
    if isinstance(args,dict):
        for field in ('id','entityId','actor','item','ownerId'):
            if type(args.get(field)) is str and len(args[field])<=200:
                result['object']=args[field];break
    return result


def arguments(actions, index, command_id):
    action=actions[index];args=copy.deepcopy(action['args'])
    if action['op']=='notification.send' and 'sourceActionIndex' in args:
        source=args.pop('sourceActionIndex')
        require(type(source) is int and 0<=source<index and 'sourceCommandId' not in args
            and 'sourceOp' not in args, 'INPUT_INVALID')
        args['sourceCommandId']=child_id(command_id,source)
        args['sourceOp']=actions[source]['op']
    return args


def resolve_rule(host, state, account, op, args, *, admission_only=False):
    m=member(state,account)
    if op=='behavior.invoke':
        entity=state['entities'].get(args['entityId'])
        if m['role']!='kp' and host.knowledge.managed(state,'entity',args['entityId'],entity):
            require(args['entityId'] in host.knowledge.full_entities(state,account),'NOT_VISIBLE')
        require(entity and visible(state,account,entity),'NOT_VISIBLE')
        binding=entity['rules'].get(args['event']) or state['configurations'][entity['configurationId']].get('behaviors',{}).get(args['event'])
        require(binding,'NOT_VISIBLE')
        args={'actionId':binding['ruleId'],'input':args['input']}
    rule=args['actionId']; artifact=state['artifacts'][state['activeRuleset']]
    metadata=artifact['metadata'].get(rule)
    require(metadata and metadata['public'] and (not metadata['kp'] or m['role']=='kp'),'PERMISSION_DENIED')
    require(metadata['mode']=='action','BATCH_UNSUPPORTED')
    error=next(Draft202012Validator(metadata['schema']).iter_errors(args['input']),None)
    if error is not None:_model_error(rule,error,('input',))
    if not admission_only:
        host.knowledge.authorize_operation(state,account,rule,args['input'])
        require(state['status']=='active','ROOM_PAUSED')
    return rule,args['input'],artifact


def admission(host,state,account,actions,command_id):
    """Check every item before executing any; unsupported combinations fail closed."""
    member(state,account);rows=[]
    for index,action in enumerate(actions):
        row=item(action,index,'passed',command_id)
        try:
            require(action['target']=='host' and action['op'] in SUPPORTED,'BATCH_UNSUPPORTED')
            args=arguments(actions,index,command_id)
            validate_operation(action['op'],args)
            require(account+':'+row['commandId'] not in state['commands'],'COMMAND_ID_CONFLICT')
            if action['op']=='member.update':
                require(args['accountId']!=account,'BATCH_UNSUPPORTED')
            if action['op'] in ('action.invoke','behavior.invoke'):
                # Resolve modes/permissions before any effects. Later rule inputs
                # and room conditions are rechecked against the staged state.
                resolve_rule(host,state,account,action['op'],args,admission_only=True)
        except DomainError as error:
            row.update(diagnostic(error,index,action))
            row['status']='unsupported' if error.code=='BATCH_UNSUPPORTED' else 'blocked'
        rows.append(row)
    return rows


def run_item(host,state,account,actions,index,command_id,random,deadline):
    require(time.monotonic()<deadline,'BATCH_TIMEOUT')
    action=actions[index];op=action['op'];args=arguments(actions,index,command_id)
    validate_operation(op,args);member(state,account)
    cid=child_id(command_id,index);key=account+':'+cid
    rec={'id':cid,'account':account,'op':op,'args':copy.deepcopy(args),'signature':digest([op,args]),
        'status':'pending','random':[],'batchCommandId':command_id}
    state['commands'][key]=rec
    before=host.snapshot_for_execution(state)
    if op in ('action.invoke','behavior.invoke'):
        rule,inputs,artifact=resolve_rule(host,state,account,op,args)
        def roll(sides):
            value=random(index,sides)
            rec['random'].append({'sides':sides,'value':value})
            return value
        out=execute(artifact['sources'],{'kind':'run','rule':rule,'input':inputs,'mode':'action',
            'state':before,'account':account,'data':artifact['data']},roll,
            timeout=max(.001,min(10,deadline-time.monotonic())))
        require(time.monotonic()<deadline,'BATCH_TIMEOUT')
        for eid,entity in out['entities'].items():
            if entity!=before['entities'].get(eid):
                entity['revision']=state['entities'].get(eid,{}).get('revision',0)+1
                state['entities'][eid]=entity
        if out['relations']!=before['relations']:
            state['relations']=out['relations'];state['collectionRevision']+=1
        rec.update(rule=rule,input=inputs,ruleset=state['activeRuleset'],reads=out['reads'])
        result=out['result']
        state['audit'].append({'commandId':cid,'account':account,'rule':rule,'ruleset':rec['ruleset'],
            'random':rec['random'],'effects':out['effects'],'at':host.clock()})
        state['outbox'].append({'id':uid(),'commandId':cid})
        host.knowledge.derive(state,account,cid,{'commandId':cid,'operation':rule,'input':inputs,
            'result':result,'effects':out['effects']},previous=before)
    else:
        result=host.manage(state,account,op,args,command_id=cid)
        if op in ('entity.create','entity.update','entity.patch'):
            host.knowledge.derive(state,account,cid,{'commandId':cid,'operation':op,'input':args,
                'result':result,'effects':[]},previous=before)
        state['audit'].append({'commandId':cid,'account':account,'op':op,'at':host.clock()})
    rec.update(status='committed',receipt={'status':'committed','commandId':cid,'result':result})
    validate(state)
    return rec


def preflight(host,account,actions):
    shape(actions);actions=copy.deepcopy(actions)
    require(host.capacity.acquire(blocking=False),'LIMIT_EXCEEDED')
    try:
        with host.lock:
            state=host.state();command_id='preflight-'+uid()
            rows=admission(host,state,account,actions,command_id)
            outcome={'status':'passed','checkedAt':host.clock(),'scope':SCOPE,'items':rows}
            if any(r['status'] in ('blocked','unsupported') for r in rows):
                outcome['status']='unsupported' if any(r['status']=='unsupported' for r in rows) else 'blocked'
                for row in rows:
                    row.pop('commandId',None)
                    if row['status']=='passed':
                        row.update(status='runtime_required',code='BATCH_PRECHECK_FAILED',
                            reason='整批准入检查未通过，当前项尚未执行业务预检。')
                return redact_preflight(state,account,outcome)
            deadline=time.monotonic()+PREFLIGHT_SECONDS;deferred=False;blocked=False
            def no_roll(index,sides):raise DomainError('BATCH_RUNTIME_REQUIRED')
            for index,action in enumerate(actions):
                row=rows[index];row.pop('commandId',None)
                try:
                    if blocked:raise DomainError('BATCH_DEPENDENCY_FAILED')
                    if deferred:raise DomainError('BATCH_DEPENDENCY_PENDING')
                    if time.monotonic()>=deadline:raise DomainError('BATCH_PREFLIGHT_BUDGET')
                    run_item(host,state,account,actions,index,command_id,no_roll,deadline)
                    projected=host._receipt(state,account,child_id(command_id,index))
                    if 'result' in projected:row.update(result=projected['result'],preview=True)
                except DomainError as error:
                    runtime=error.code in ('BATCH_RUNTIME_REQUIRED','BATCH_DEPENDENCY_PENDING',
                        'BATCH_PREFLIGHT_BUDGET','BATCH_TIMEOUT','RULE_TIMEOUT')
                    row.update(diagnostic(error,index,action));row['status']='runtime_required' if runtime else 'blocked'
                    if runtime:deferred=True
                    else:blocked=True
                except Exception as error:
                    row.update(diagnostic(error,index,action));row['status']='blocked';blocked=True
            outcome['status']='blocked' if blocked else 'runtime_required' if deferred else 'passed'
            return redact_preflight(state,account,outcome)
    finally:host.capacity.release()


def execution_result(rows,status):
    return {'status':status,'scope':SCOPE,'items':rows,
        'committedCount':sum(r['status']=='committed' for r in rows),
        'failedCount':sum(r['status']=='failed' for r in rows),
        'notExecutedCount':sum(r['status']=='not_executed' for r in rows),
        'rolledBackCount':sum(r['status']=='rolled_back' for r in rows)}


def terminal(host,key,rows,status,code=None,state=None):
    generation,current=host.store.snapshot();record=current['commands'][key]
    if record['status']!='pending':return
    if state is None:state=current
    else:require(room_digest(current,key)==record['baseDigest'],'BATCH_STATE_CHANGED')
    record=copy.deepcopy(record)
    record['status']='committed' if status=='committed' else 'rejected'
    record['receipt']={'status':record['status'],'commandId':record['id'],
        'result':execution_result(rows,status)}
    if code:record['receipt']['code']=code
    state['commands'][key]=record
    host.hit('before_batch_terminal');host.commit(state,expected_generation=generation);host.hit('after_batch_terminal')


def submit(host,account,actions,command_id):
    shape(actions);require(type(command_id) is str and 1<=len(command_id)<=100,'INPUT_INVALID')
    actions=copy.deepcopy(actions);signature=digest({'op':'batch.execute','actions':actions})
    require(host.capacity.acquire(blocking=False),'LIMIT_EXCEEDED')
    try:
        with host.lock:
            state=host.state();member(state,account);key=account+':'+command_id
            previous=state['commands'].get(key)
            if previous:
                require(previous['signature']==signature and previous.get('op')=='batch.execute','COMMAND_ID_CONFLICT')
                if previous['status']=='pending':resume(host,key)
                return host.receipt(account,command_id)
            rows=admission(host,state,account,actions,command_id)
            record={'signature':signature,'op':'batch.execute','id':command_id,'account':account,
                'status':'pending','actions':actions,'random':[],
                'baseDigest':room_digest(state,key),'createdAt':host.clock()}
            state['commands'][key]=record
            generation=host.store.generation
            host.hit('before_batch_intent');host.commit(state,expected_generation=generation);host.hit('after_batch_intent')
            if any(r['status'] in ('blocked','unsupported') for r in rows):
                for row in rows:row['status']='failed' if row['status'] in ('blocked','unsupported') else 'not_executed'
                terminal(host,key,rows,'failed','BATCH_PRECHECK_FAILED')
            else:resume(host,key)
            return host.receipt(account,command_id)
    finally:host.capacity.release()


def resume(host,key):
    """Caller holds room lock. Every durable random value is reused on retry."""
    state=host.state();record=state['commands'][key]
    if record['status']!='pending':return
    account=record['account'];actions=record['actions'];cid=record['id']
    rows=[item(a,i,'not_executed',cid) for i,a in enumerate(actions)]
    ordinal=0;index=0;deadline=time.monotonic()+EXECUTION_SECONDS
    def unchanged(current):
        require(room_digest(current,key)==record['baseDigest'],'BATCH_STATE_CHANGED')
    def random(step,sides):
        nonlocal ordinal
        require(time.monotonic()<deadline,'BATCH_TIMEOUT')
        generation,current=host.store.snapshot();unchanged(current);rec=current['commands'][key]
        require(ordinal<MAX_ROLLS,'LIMIT_EXCEEDED')
        if ordinal<len(rec['random']):
            draw=rec['random'][ordinal]
            require(draw['index']==step and draw['sides']==sides,'RANDOM_TRACE_CONFLICT')
            ordinal+=1;return draw['value']
        value=secrets.randbelow(sides)+1
        rec['random'].append({'index':step,'sides':sides,'value':value});ordinal+=1
        host.commit(current,expected_generation=generation);host.hit('after_batch_random');return value
    try:
        unchanged(state);member(state,account)
        checks=admission(host,state,account,actions,cid)
        if any(row['status'] in ('blocked','unsupported') for row in checks):
            for row in checks:row['status']='failed' if row['status'] in ('blocked','unsupported') else 'not_executed'
            terminal(host,key,checks,'failed','BATCH_PRECHECK_FAILED');return
        for index,action in enumerate(actions):
            run_item(host,state,account,actions,index,cid,random,deadline)
            rows[index]['status']='committed'
            host.hit('after_batch_item')
        current=host.state();unchanged(current)
        require(ordinal==len(current['commands'][key]['random']),'RANDOM_TRACE_CONFLICT')
        terminal(host,key,rows,'committed',state=state)
    except Exception as error:
        # Publication can succeed while its reply is lost. Never turn such a
        # durable success into rejection or restore the previous room.
        current=host.state()
        if current['commands'][key]['status']!='pending':return
        for row in rows:
            if row['status']=='committed':row['status']='rolled_back'
        rows[index].update(diagnostic(error,index,actions[index]),status='failed')
        terminal(host,key,rows,'rolled_back' if any(r['status']=='rolled_back' for r in rows) else 'failed',
            rows[index]['code'])


def project_receipt(host,state,account,record):
    receipt=copy.deepcopy(record['receipt'])
    # Batch rows contain diagnostics/locators, not raw rule results. Actual
    # committed child results must pass the existing receipt projection again.
    kp=member(state,account)['role']=='kp'
    for row in receipt.get('result',{}).get('items',[]):
        if row['status']=='committed':
            child=host._receipt(state,account,row['commandId'])
            if 'result' in child:row['result']=child['result']
        if not kp:
            row.pop('object',None);row.pop('ruleCode',None)
            row['reason']=REASONS.get(row.get('code'),'操作未满足当前规则或状态约束。') if row.get('code') else row.get('reason','')
    return receipt


def redact_preflight(state,account,outcome):
    if member(state,account)['role']!='kp':
        for row in outcome['items']:
            row.pop('object',None);row.pop('ruleCode',None)
            if row.get('code'):row['reason']=REASONS.get(row['code'],'操作未满足当前规则或状态约束。')
    return outcome


def commit_memory_fact(host,account,fact,command_id,expected_revision):
    """Single authoritative fact + receipt, for the trusted AI memory service.

    The caller has already validated memory ownership/source refs and builds the
    exact next MemoryEntry. Its independent mirror reconciles from this receipt;
    this is deliberately not admitted to a mixed/multi-operation transaction.
    """
    require(type(command_id) is str and 1<=len(command_id)<=100 and type(fact) is dict
        and type(expected_revision) is int and expected_revision>=0,'INPUT_INVALID')
    fact=copy.deepcopy(fact)
    signature=digest({'op':'ai.memory.fact','fact':fact,'expectedRevision':expected_revision})
    with host.lock:
        generation,state=host.store.snapshot()
        require(member(state,account)['role']=='kp','PERMISSION_DENIED')
        key=account+':'+command_id;previous=state['commands'].get(key)
        if previous:
            require(previous.get('op')=='ai.memory.fact' and previous['signature']==signature,'COMMAND_ID_CONFLICT')
            return host.receipt(account,command_id)
        require(fact.get('scopeId')==state['aiControl']['scopeId'],'SCOPE_MISMATCH')
        require(fact.get('status') in ('confirmed','revoked'),'INPUT_INVALID')
        require(type(fact.get('memoryId')) is str and 1<=len(fact['memoryId'])<=200,'INPUT_INVALID')
        facts=state['aiControl'].setdefault('memoryFacts',{})
        old=facts.get(fact['memoryId']);revision=old['revision'] if old else 0
        require(revision==expected_revision,'VERSION_CONFLICT')
        require(type(fact.get('revision')) is int and fact['revision']>revision,'VERSION_CONFLICT')
        facts[fact['memoryId']]=fact
        receipt={'status':'committed','commandId':command_id,'result':{'memory':copy.deepcopy(fact)}}
        state['commands'][key]={'op':'ai.memory.fact','id':command_id,'account':account,
            'signature':signature,'status':'committed','receipt':receipt}
        try:
            host.hit('before_memory_fact_commit');host.commit(state,expected_generation=generation)
            host.hit('after_memory_fact_commit')
        except Exception:
            saved=host.state()['commands'].get(key)
            if not saved or saved.get('signature')!=signature or saved.get('status')!='committed':raise
        return host.receipt(account,command_id)
