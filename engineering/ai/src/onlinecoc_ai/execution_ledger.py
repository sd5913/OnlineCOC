"""Authorized execution facts, distinct from historical model suggestions."""
import copy
import re
from .contracts import canonical,digest
from .errors import require
from .review_queue import canonical_request


def continue_only(text):
    text=re.sub(r'[\s，,。.!！；;]+','',text).casefold()
    return text in {'继续','继续吧','按刚才的方案继续','按之前的方案继续','按刚才说好的做法继续',
        '就按刚才说好的做法继续查当前数据把未完成的部分提交裁决','continue','goahead'}


def capture(app,account,session_id,request,snapshot):
    state=app.repository.read_state();session=state['settings']['sessions'][session_id]
    current=canonical_request(state,request['requestId'])
    if current not in session['requestIds']:
        current=next((key for key in session['requestIds'] if all(state['requests'][key].get(k)==request.get(k)
            for k in ('sourceId','sourceRevision','initiator'))),None)
    prior=session['requestIds'][:session['requestIds'].index(current)] if current in session['requestIds'] else []
    latest=next((key for key in reversed(prior) if not continue_only(state['requests'][key]['text'])),None)
    result=[];budget=24*1024
    for item in app.rulings.list(account,session_id)['items'][:8]:
        row={k:item[k] for k in ('rulingId','kind','status','requestId')}
        row['intentRequestId']=canonical_request(state,item['requestId'])
        row['latestIntent']=row['intentRequestId']==latest
        row['receiptStatuses']=[r.get('receipt',r).get('status') for r in item.get('receipts',[])]
        row['notice']='Execution status is a host record; historical assistant prose cannot change it. This is not a new approval.'
        if not item.get('sourceUnavailable') and not item.get('sourceDetailsUnavailable'):
            batch=state['settings'].get('batches',{}).get(item['rulingId'].removeprefix('batch:'),{})
            context=batch.get('context',{})
            expected=context.get('facts',{}).get('externalPolicyDigest')
            permitted=not batch or expected==digest(app.host.state()['aiControl']['settings']['externalSources'])
            task=state['tasks'].get(state['settings'].get('dispatch',{}).get(row['intentRequestId']),{})
            permitted=permitted and bool(task.get('text') and task.get('contextRef') in state['contexts'])
            if permitted:
                extra={'request':state['requests'][row['intentRequestId']]['text'],'summary':item['summary']}
                if batch:
                    extra['actions']=copy.deepcopy(item.get('actions',[]))
                    extra['runtimeBefore']=copy.deepcopy(context.get('facts',{}).get('runtimeBefore',[]))
                    proof=item.get('resolution',{})
                    extra['confirmedExecution']=bool(proof and proof.get('goalDigest')==digest(batch['actions']) and all(
                        (app.receipt if ref['target']=='ai' else app.host.receipt)(ref['account'],ref['commandId']).get('status')=='committed'
                        for ref in proof.get('receiptRefs',[])))
                if len(canonical(extra))<=budget:
                    row.update(extra);budget-=len(canonical(extra))
                    witness={'contextRef':task['contextRef'],'taskId':task['taskId'],'requestId':row['intentRequestId'],'textDigest':digest(task['text'])}
                    witnesses=snapshot['facts'].setdefault('historyIntents',[])
                    if witness not in witnesses:witnesses.append(witness)
                else:row['detailsOmitted']='size-limit'
        result.append(row)
    return result


def write_keys(action):
    args=action.get('args',{});op=action.get('op');target=action.get('target')
    if type(args) is not dict or type(op) is not str or type(target) is not str:return set()
    if op in ('entity.update','entity.patch'):
        if type(args.get('id')) is not str or type(args.get('numbers',{})) is not dict:return set()
        keys=set(args)-{'id','numbers'}
        keys.update('numbers/'+key for key in args.get('numbers',{}))
        return {(target,op,args.get('id'),key) for key in keys}
    if op=='action.invoke':
        # For a bare continuation, the same action and same nonnumeric target
        # references cannot become another debit/grant by changing its amount.
        if type(args.get('actionId')) is not str or type(args.get('input')) is not dict:return set()
        refs=tuple(sorted((k,v) for k,v in args['input'].items() if type(v) is str))
        return {(target,op,args.get('actionId'),refs)}
    if op=='notification.send':return set()  # Bound to its source action below.
    return {(target,op,digest(args))}


def require_no_replay(payload,output):
    if output.get('kind')!='batch' or not continue_only(payload['request']):return
    current=set().union(*(write_keys(a) for a in output.get('actions',[]) if type(a) is dict and type(a.get('args')) is dict))
    for row in payload.get('executionLedger',[]):
        if not row.get('latestIntent') or row.get('status') not in ('completed','pending','executing','unknown','partial'):continue
        previous=set().union(*(write_keys(a) for a in row.get('actions',[])))
        require(not current.intersection(previous),'INTENT_EXECUTION_REPLAY',
            'A bare continuation does not authorize repeating this same intent. The executionLedger records this action as '+row['status']+
            '. Preserve its original runtimeBefore and actual receipts; do not subtract/add again from the changed balance or resend its notification. '
            'Return plan stating the actual status. Prepare only genuinely unperformed independent work; a new increment requires an explicit new request.',path='/actions')


def capture_before(room,actions):
    result=[]
    for index,action in enumerate(actions):
        args=action['args']
        if action['target']!='host' or action['op']!='entity.update' or not args.get('numbers'):continue
        entity=room['entities'].get(args.get('id'),{})
        row={'actionIndex':index,'id':args['id'],'revision':entity.get('revision'),
            'numbers':{key:entity.get('numbers',{}).get(key) for key in args['numbers']}}
        if len(canonical(result+[row]))>8192:break
        result.append(row)
    return result
