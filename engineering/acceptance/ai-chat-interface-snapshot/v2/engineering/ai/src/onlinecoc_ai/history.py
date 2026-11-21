"""Read-only history authorization. Never returns renewed execution evidence."""
import copy
from onlinecoc.model import member
from onlinecoc.publication import check_history_context
from .contracts import digest
from .errors import require

NOTICE = '历史回答的资料依据已变化，仅用于理解此前意图；涉及修改时必须重新查询当前资料并另行审核。'


def identity(ref):
    return tuple(ref.get(k) for k in ('sourceId','kind','id','scopeId'))


def _retained_nodes(old,current):
    """Configuration-file access is unchanged, but deleted subobjects stay hidden.

    Scalar edits are versions of the same field. Lists require stable unique IDs
    or an unchanged prefix; arbitrary index reuse is not identity evidence.
    """
    if type(old) is dict:
        return type(current) is dict and ('id' not in old or old['id']==current.get('id')) and all(k in current and _retained_nodes(v,current[k]) for k,v in old.items())
    if type(old) is list:
        if type(current) is not list:return False
        if old and all(type(v) is dict and type(v.get('id')) is str for v in old+current):
            original={v['id']:v for v in old};present={v['id']:v for v in current}
            if len(original)==len(old) and len(present)==len(current):
                return all(k in present and _retained_nodes(v,present[k]) for k,v in original.items())
        return current[:len(old)]==old
    return not isinstance(current,(dict,list))


def _sources(host, room, account, sources, scope):
    from onlinecoc.ai_sources import check_sources
    for original in sources:
        ref=copy.deepcopy(original);kind=ref['kind'];key=ref['id']
        if kind=='entity':value=room['entities'].get(key)
        elif kind=='configuration':value=room['configurations'].get(key)
        elif kind=='message':
            value=next((m for m in room['chat']['messages'].get(ref.get('channelId'),[]) if m['messageId']==key and not m['deleted']),None)
        elif kind=='rule':
            require(key in room['artifacts'][room['activeRuleset']]['sources'],'SOURCE_STALE')
            ref['revision']=room['activeRuleset'];value=None
        else:
            # Memory, knowledge and contracts can conceal nested dependencies.
            # Retain their exact original checks, including expiry and revocation.
            check_sources(host,room,account,[ref],read_scope=scope);continue
        if kind!='rule':
            require(value is not None,'SOURCE_STALE')
            ref['revision']=value['revision'];ref['digest']=digest(value)
        check_sources(host,room,account,[ref],read_scope=scope)


def _queries(host,room,account,proofs):
    from onlinecoc.data_queries import query,rows
    for proof in proofs:
        require(proof['scopeId']==room['aiControl']['scopeId'] and not proof.get('player'),'SCOPE_MISMATCH')
        options=dict(initiator=proof.get('initiator'),external=True,read_scope=proof.get('readScope'))
        try:
            current=query(host,room,account,proof['operation'],proof['args'],**options)
            if digest(current)==proof['digest']:continue
        except Exception:pass
        witnesses=proof.get('readRefs')
        if witnesses is None and proof['operation'] in ('read','case'):
            witnesses=[{'ref':ref} for ref in proof['args']['refs']]
        require(witnesses is not None,'HISTORY_PROVENANCE_INCOMPLETE',
            'This legacy search has no retained object identities; a changed result cannot prove historical access')
        kinds=list({item['ref']['kind'] for item in witnesses})
        if proof['args'].get('roomMode')=='state' or any(item['ref']['sourceId']=='host-room-state' for item in witnesses):options['room_mode']='state'
        available={identity(row['ref']):row for row in rows(host,room,account,kinds=kinds,**options)} if kinds else {}
        for item in witnesses:
            ref=item['ref'];current=available.get(identity(ref))
            require(current is not None,'SOURCE_STALE')
            if 'visibility' in item:require(item['visibility']==current['visibility'],'PERMISSION_DENIED')
            # Opaque adapters and bundles may change field-level grants or lose
            # nested messages. Existence of their outer ID is not enough.
            if ref['sourceId']!='host' or ref['kind'] in ('event','ruling','memory','knowledge'):
                require(ref['digest']==current['ref']['digest'],'SOURCE_STALE')


def _intent_contexts(repository,room,entries):
    state=repository.read_state()
    for entry in entries:
        task=state['tasks'].get(entry.get('taskId'),{})
        request=state['requests'].get(entry.get('requestId'),{})
        require(task.get('contextRef')==entry.get('contextRef') and task.get('text') and
            digest(task['text'])==entry.get('textDigest') and request and request['status']!='cancelled','SOURCE_STALE')
        session=next((s for s in state['settings'].get('sessions',{}).values() if request['requestId'] in s['requestIds']),None)
        require(session and not session.get('deleted'),'SESSION_ACCESS_CHANGED')
        yield entry['contextRef']


def assess(host,repository,room,context,seen=None,*,shared=None):
    """Raise on revoked/unprovable access; return a stale code or None otherwise.

    ``shared`` belongs to one locked public read, never another request. Cached
    closures still count towards each root's 100-context and cycle checks.
    """
    require(context is not None,'SOURCE_STALE')
    if context['facts'].get('strictPlayer'):
        check_history_context(host,room,context['reviewPrincipal'],context);return None
    seen={'active':set(),'memo':{}} if seen is None else seen
    closures=seen.setdefault('closures',{})
    key=digest(context)
    if key in seen['memo']:return seen['memo'][key]
    if shared is not None and key in shared:
        value,footprint=shared[key]
        require(not (seen['active'] & footprint) and len(set(seen['memo']) | seen['active'] | footprint)<=100,'SOURCE_STALE')
        for node in footprint:
            seen['memo'][node]=shared[node][0];closures[node]=shared[node][1]
        return value
    require(key not in seen['active'] and len(seen['active'])+len(seen['memo'])<100,'SOURCE_STALE')
    seen['active'].add(key);closure={key}
    def finish(value):
        seen['active'].remove(key);seen['memo'][key]=value;closures[key]=frozenset(closure)
        if shared is not None:shared[key]=(value,closures[key])
        return value
    def dependency(previous):
        value=assess(host,repository,room,previous,seen,shared=shared)
        closure.update(closures.get(digest(previous),()))
        return value
    account=context['reviewPrincipal'];principal=member(room,account)
    require(principal['role']=='kp' and principal['authorizationEpoch']==context['authorizationEpoch'],'PERMISSION_DENIED')
    require(context['scopeId']==room['aiControl']['scopeId'],'SCOPE_MISMATCH')
    require(context['contractDigest']==room['aiControl']['packBinding']['digest'],'VALIDATOR_STALE')
    facts=context['facts'];policy=room['aiControl']['settings']['externalSources']
    if 'externalPolicyDigest' in facts:require(facts['externalPolicyDigest']==digest(policy),'EXTERNAL_SCOPE_CHANGED')
    if 'profileId' in facts:require(facts['profileId']==room['aiControl']['settings']['profileId'],'PROFILE_CHANGED')
    # Intent dependencies must remain readable, but their age never makes a
    # freshly captured task stale. Only reused factual contexts propagate age.
    for ref in _intent_contexts(repository,room,facts.get('historyIntents',[])):
        dependency(repository.read_state()['contexts'].get(ref))
    dependency_stale=False
    for ref in facts.get('historyContexts',[]):
        previous=repository.read_state()['contexts'].get(ref)
        dependency_stale=bool(dependency(previous)) or dependency_stale
    baseline=copy.deepcopy(context)
    baseline['facts'].pop('historyContexts',None);baseline['facts'].pop('historyIntents',None)
    if facts.get('generationSnapshot')==1:
        # Reading a generated answer depends on its actual sources, not every
        # unrelated entity in the execution baseline. Never modify stored proof.
        from .validation.common import world_digest
        baseline['worldDigest']=world_digest(room)
    try:
        check_history_context(host,room,account,baseline)
        if not dependency_stale:return finish(None)
        code='BASELINE_STALE'
    except Exception as exc:
        code=getattr(exc,'code',None)
        if code not in ('BASELINE_STALE','SOURCE_STALE'):raise
    # Keep current permissions, session ceilings, policy and personal knowledge
    # checks exact. Remove only freshness checks which are rechecked below.
    from .access import validate_context,policy as access_policy
    permissions=copy.deepcopy(baseline)
    for name in ('sessionReads','managementReads','dataQueries','configDataEdits','configDataReads'):
        permissions['facts'].pop(name,None)
    validate_context(host,repository,room,permissions)
    if facts.get('dataQueries') or facts.get('configDataReads') or facts.get('managementReads'):
        require(access_policy(repository)['allowDataQueries'],'DATA_QUERIES_DISABLED')
    scope=facts.get('aiReadScope')
    _sources(host,room,account,context['sourceRefs']+context['memoryRefs'],scope)
    old=room['artifacts'].get(context['baseRuleset'])
    current=room['artifacts'][room['activeRuleset']]
    require(old is not None and set(old['sources'])<=set(current['sources']),'SOURCE_STALE')
    _queries(host,room,account,facts.get('dataQueries',[]))
    sessions=repository.read_state()['settings'].get('sessions',{})
    for sid in facts.get('sessionReads',{}):
        require(sid in sessions and not sessions[sid].get('deleted'),'SESSION_ACCESS_CHANGED')
    for section,expected in facts.get('managementReads',{}).items():
        value={k:room[k] for k in ('roomId','name','runId','status','activeRuleset')} if section=='room' else room[section]
        if digest(value)==expected:continue
        keys=facts.get('managementReadKeys',{}).get(section)
        require(keys is not None,'HISTORY_PROVENANCE_INCOMPLETE')
        require(all(k in value for k in keys),'SOURCE_STALE')
    from .data_edits import node
    from .errors import AiError
    for proof in facts.get('configDataReads',[]):
        require(proof['file'] in current['data'] and proof['file'] in old['data'],'SOURCE_STALE')
        try:
            previous=node(old['data'][proof['file']],proof['path'])
            require(digest(previous)==proof['targetDigest'],'HISTORY_PROVENANCE_INCOMPLETE')
            for size in range(len(proof['path'])):
                before=node(old['data'][proof['file']],proof['path'][:size])
                after=node(current['data'][proof['file']],proof['path'][:size])
                if type(before) is dict and 'id' in before:
                    require(type(after) is dict and before['id']==after.get('id'),'SOURCE_STALE')
            require(_retained_nodes(previous,node(current['data'][proof['file']],proof['path'])),'SOURCE_STALE')
        except AiError as exc:
            if exc.code=='INPUT_INVALID':raise AiError('SOURCE_STALE') from None
            raise
    if facts.get('configDataEdits') and not facts.get('configDataReads'):
        require(context['baseRuleset']==room['activeRuleset'],'HISTORY_PROVENANCE_INCOMPLETE')
    return finish(code)


def validate_intents(host,repository,room,entries):
    for ref in _intent_contexts(repository,room,entries):
        assess(host,repository,room,repository.read_state()['contexts'].get(ref))


def require_current_evidence(context,output):
    """Historical prose may select intent, but a mutation needs current reads."""
    facts=context['facts']
    if not (facts.get('historyIntents') or facts.get('intentRequests')) or output.get('kind') not in ('batch','draft'):return
    refs=context['sourceRefs']
    reads=[ref for proof in facts.get('dataQueries',[]) if proof['operation'] in ('read','case') for ref in proof['args']['refs']]
    if output['kind']=='draft':
        available=bool(facts.get('managementReads',{}).get('configurations') or facts.get('configDataReads') or any(r['kind'] in ('configuration','rule') for r in refs) or any(r['kind'] in ('config','rule') and r['sourceId']=='host' for r in reads))
    else:
        available=bool(refs or reads or facts.get('managementReads') or facts.get('sessionReads'))
        # Existing actor targets must themselves be read this turn. Reading a
        # different actor cannot upgrade a stale plan's actor values.
        known={r['id'] for r in refs if r['kind']=='entity'}
        known_hashes={r['id'] for r in reads if r['sourceId']=='host' and r['kind']=='entity'}
        for action in output['actions']:
            for field in ('id','instanceId','entityId','actorId','targetId','sourceId'):
                target=action['args'].get(field)
                if type(target) is str and action['target']=='host' and (field in ('instanceId','entityId','actorId') or action['op'].startswith('relation.') or field=='id' and action['op'].startswith('entity.') and action['op']!='entity.create'):
                    available=available and (target in known or digest(['host','entity',target]) in known_hashes)
    require(available,'HISTORY_REQUERY_REQUIRED','Retain the already stated intent and recipient. Read current target details before preparing changes; do not ask the user to confirm the same plan again.')
