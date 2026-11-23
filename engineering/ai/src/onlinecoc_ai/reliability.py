"""Technical feedback from declared contracts, never inferred user decisions."""
from jsonschema import Draft202012Validator
from .contracts import loads
from .errors import AiError,require


def answer_tool(message):
    """One display-only answer in the wrong envelope; never run a fake tool."""
    calls=message.get('tool_calls',[])
    if len(calls)!=1 or calls[0].get('function',{}).get('name') not in ('clarification','plan'):return None
    call=calls[0]['function']
    try:value=loads(call.get('arguments',''))
    except AiError:return None
    if type(value) is not dict or set(value)-{'kind','text','choices'}:return None
    if value.get('kind',call['name'])!=call['name']:return None
    from .answers import parse_answer
    from .contracts import canonical
    value={**value,'kind':call['name']}
    try:parse_answer(canonical(value).decode())
    except AiError:return None
    return {'role':'assistant','content':canonical(value).decode()}


def remember_targets(result,pool):
    """Only complete, already-authorized host entity details prove a target ID."""
    for item in result.get('items',[]):
        ref=item.get('ref',{});data=item.get('data',{})
        if item.get('authority')=='host-state' and ref.get('sourceId')=='host' and ref.get('kind')=='entity' and isinstance(data,dict) and data.get('instanceId'):
            key=ref['id'];value={'instanceId':data['instanceId'],'typeRef':data.get('typeRef')}
            if key in pool and pool[key]!=value:pool[key]=None
            elif key not in pool:pool[key]=value


def resolve_targets(actions,pool,artifact):
    """Replace exact opaque refs only at declared entity-reference positions."""
    import copy
    result=copy.deepcopy(actions);fixed=[]
    if type(result) is not list:return result,fixed
    for index,action in enumerate(result):
        if type(action) is not dict or type(action.get('args')) is not dict:continue
        if action.get('target')!='host':continue
        args=action.get('args',{});op=action.get('op');positions=[]
        if op in ('entity.patch','entity.update','entity.archive'):positions=[(args,'id',None,'/args/id')]
        if op=='action.invoke' and isinstance(args.get('actionId'),str) and type(args.get('input')) is dict:
            metadata=artifact['metadata'].get(args.get('actionId'),{})
            positions=[(args.get('input',{}),key,kind,'/args/input/'+key) for key,kind in metadata.get('inputs',{}).items()]
        for parent,key,kind,path in positions:
            raw=parent.get(key);target=pool.get(raw) if isinstance(raw,str) else None
            if target and (kind is None or kind==target['typeRef']) and raw!=target['instanceId']:
                parent[key]=target['instanceId'];fixed.append('/actions/'+str(index)+path)
    return result,fixed


def require_capability_evidence(payload,output):
    """Reject a specific observed false capability claim against the host index."""
    import re
    if output.get('kind') not in ('plan','clarification') or not payload.get('aiPermissions',{}).get('allowRuntimeChanges',False):return
    if 'entity.update' not in payload.get('operationIndex',{}).get('host',[]):return
    text=output.get('text','')
    if 'entity.patch' in text and 'entity.update' not in text and re.search(r'(没有|不存在)[^。！？\n]{0,40}(可改|可写|修改)[^。！？\n]{0,20}数值[^。！？\n]{0,20}(操作|命令)',text):
        raise AiError('MODEL_CAPABILITY_UNPROVEN','The complete host operation index includes entity.update for numeric fields. Reading only entity.patch is not proof that numeric mutation is unavailable. Remove the unsupported blanket limitation. If the requested numeric field is still ambiguous, ask only that genuine choice; otherwise read the entity.update schema and current target before preparing a candidate. Do not invent permission or execute.',path='/text')


def require_increment_intent(payload,output):
    """Reject the observed substitution of existing stock for a new grant."""
    import re
    request=payload.get('request','');text=output.get('text','')
    if output.get('kind')!='plan' or not payload.get('aiPermissions',{}).get('allowRuntimeChanges'):return
    if re.search(r'确保|保证.*有|ensure|make sure',request,re.I):return
    explicit=re.search(r'(发|给予|赠送|grant|give).{0,15}(一|两|[1-9]|one|two)',request,re.I)
    dismiss=re.search(r'(已有|已经有|现有).{0,150}(不需要再发|无需再发|不需要.*新增|no need)',text,re.I|re.S)
    if explicit and dismiss:
        raise AiError('REQUESTED_INCREMENT_OMITTED','The user explicitly requested a new grant, not merely ensuring ownership. Existing stock is the before-state, not a receipt for this request. Prepare the requested increment in a compatible free position and its requested notification; retain all existing stock. Query actual definitions and current capacity. Do not ask again whether the already explicit grant is wanted.',path='/text')


def require_search_evidence(request,payload,snapshot,output):
    """An unloaded demand context cannot support a claimed negative search result."""
    import re
    if output.get('kind')!='plan' or payload.get('dataAccess',{}).get('mode')!='demand':return
    if not re.search(r'查询|查找|搜索|检索|找出|search|look up|find',request,re.I):return
    if not re.search(r'没有找到|未找到|不存在|没有[^\s，。；,.;]{0,12}(记录|对象)|not found|could not find|no records',output.get('text',''),re.I):return
    facts=snapshot.get('facts',{})
    if facts.get('dataQueries') or facts.get('managementReads') or facts.get('sessionReads'):return
    raise AiError('MODEL_EVIDENCE_REQUIRED','The room data is not loaded. No successful room query supports this negative search claim. Use the authorized room search/read tools, read matching records, and answer only from their results. If tools are unavailable or a query fails, explicitly state that the search could not be completed; do not claim the target is absent.',path='/text')


def tool_arguments(raw,schema):
    try:args=loads(raw)
    except AiError:raise AiError('TOOL_ARGUMENTS_INVALID','Arguments must be one valid JSON object',path='/arguments') from None
    require(type(args) is dict,'TOOL_ARGUMENTS_INVALID','Arguments must be an object',path='/arguments')
    error=next(Draft202012Validator(schema).iter_errors(args),None)
    if error:
        parts=[str(p).replace('~','~0').replace('/','~1') for p in error.absolute_path]
        raise AiError('INPUT_INVALID',error.message[:400],path='/arguments'+('/'+'/'.join(parts) if parts else ''))
    return args


def tool_feedback(exc,schema):
    return {'error':{'code':exc.code,'path':getattr(exc,'path','')[:300],'reason':getattr(exc,'detail','')[:400]},
        'schema':schema,'notice':'No data was returned and no change was executed. Correct only these technical parameters using the declared schema and already authorized facts. Re-query a unique reference if needed; do not ask the user to correct syntax, invent an ID, change the target/cost/effect, or broaden permissions. An ambiguous business choice still requires clarification.'}


def batch_feedback(preflight,catalog):
    return {'error':{'code':'BATCH_PREFLIGHT_BLOCKED'},'preflight':preflight,
        'catalog':catalog,'notice':'This is a read-only deterministic preflight, not execution. Correct only technical identifiers, inventory slot references, exact enum values and argument structure. Re-query authorized current records to resolve a unique reference. Preserve the original requested subject, target, cost and effect; do not omit failing actions, substitute a cheaper action, broaden permissions, or reroll a game result. Item definition IDs are not inventory slot numbers. Use the slot containing the intended item and its current quantity; grant operations may instead require a definition ID. Missing or ambiguous business decisions require clarification. If current facts make the requested action impossible, retain the blocked candidate and explain the unmet condition.'}


def rule_feedback(artifact,rule_ids):
    """Exact bounded source excerpts, including declared dependencies; KP-only caller."""
    import re
    from .contracts import canonical
    identifiers=set(rule_ids);pending=list(identifiers)
    while pending:
        for identifier in artifact['metadata'].get(pending.pop(),{}).get('dependencies',[]):
            if identifier not in identifiers:identifiers.add(identifier);pending.append(identifier)
    sources={name:body for name,body in artifact['sources'].items() if any(
        re.search(r'\brule\s*\(\s*[\x22\x27]'+re.escape(identifier)+r'[\x22\x27]',body) for identifier in identifiers)}
    return {'rulesetRevision':artifact['revision'],'sources':sources} if len(canonical(sources))<=16384 else {'rulesetRevision':artifact['revision'],'omitted':'Query the relevant rule sources; excerpts exceed the feedback byte limit.'}


def repairable(preflight):
    if preflight['status']!='blocked':return False
    forbidden=('PERMISSION','FORBIDDEN','DISABLED','UNSUPPORTED','NOT_AUTHORIZED')
    return not any(any(word in row.get('code','') for word in forbidden) for row in preflight['items'])


def business_unsuccessful(result):
    """Recognize explicit negative business outcomes, without rerolling them."""
    if result is False:return True
    if not isinstance(result,dict):return False
    if result.get('passed') is False or result.get('outcome') in ('blocked','failure','failed'):return True
    return any(business_unsuccessful(result[key]) for key in ('public','result') if key in result)
