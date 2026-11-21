"""Server-owned session ceilings. Model input never selects its principal."""
import copy
from onlinecoc.model import member
from .errors import require

DEFAULT_POLICY = {'revision': 1, 'allowPlayerChat': False, 'autoApproveBatches': False, 'autoApproveConfigurations': False,
    'allowAdminRoomRead': True, 'allowDataQueries': True, 'allowRuntimeChanges': True,
    'allowConfigurationChanges': True, 'allowKnowledgeRequests': True, 'allowPlayerRequests': True, 'principal': None}


def policy(repository):
    # Embedding ports may implement only the existing state() protocol.
    read=getattr(repository,'read_state',repository.state)
    return {**DEFAULT_POLICY, **read()['settings'].get('accessPolicy', {})}


def can_use(host, repository, account):
    role = member(host.state(), account)['role']
    require(role == 'kp' or policy(repository)['allowPlayerChat'], 'PLAYER_AI_DISABLED')
    return role


def request_session(repository, request):
    state = repository.read_state()
    original = next((r for r in state['requests'].values() if r['sourceId'] == request['sourceId'] and
        r['sourceRevision'] == request['sourceRevision'] and r['initiator'] == request.get('initiator')), request)
    return next((s for s in state['settings'].get('sessions', {}).values() if original.get('requestId') in s['requestIds']), None)


def binding(host, repository, request):
    session = request_session(repository, request)
    if not session:return None
    owner = member(host.state(), session['owner'])
    require(not session.get('deleted'), 'SESSION_DELETED')
    level = session.get('accessLevel', 'player')
    if level == 'administrator':require(owner['role'] == 'kp', 'PERMISSION_DENIED')
    else:can_use(host, repository, session['owner'])
    return {'sessionId': session['sessionId'], 'owner': session['owner'], 'level': level,
        'authorizationEpoch': owner['authorizationEpoch'], 'policyRevision': policy(repository)['revision']}


def validate_context(host, repository, room, context):
    current = policy(repository)
    facts = context.get('facts', {})
    if 'aiPolicyRevision' in facts:
        require(facts['aiPolicyRevision'] == current['revision'], 'SESSION_ACCESS_CHANGED')
    if facts.get('aiReadScope') == 'kp-room':
        require(current['allowAdminRoomRead'] and member(room, context['reviewPrincipal'])['role'] == 'kp'
            and facts.get('sessionAccess', {}).get('level') != 'player', 'PERMISSION_DENIED')
    # Assistant history can depend on package queries or older conversations.
    # Revalidate its complete provenance, with bounded traversal and no recursion.
    from onlinecoc.publication import check_history_context
    pending=list(context.get('facts',{}).get('historyContexts',[]));seen=set()
    contexts=repository.read_state()['contexts'] if pending else {}
    while pending:
        key=pending.pop()
        if key in seen:continue
        require(len(seen)<100 and key in contexts,'SOURCE_STALE');seen.add(key)
        previous=copy.deepcopy(contexts[key])
        pending.extend(previous['facts'].pop('historyContexts',[]))
        if previous['facts'].get('generationSnapshot')==1:
            # A prior answer is read evidence, not a prior execution approval.
            # Preserve every source/policy check; the enclosing candidate keeps
            # its own unchanged execution worldDigest and current Host checks.
            from .validation.common import world_digest
            previous['worldDigest']=world_digest(room)
        check_history_context(host,room,previous['reviewPrincipal'],previous)
    from .history import validate_intents
    validate_intents(host,repository,room,facts.get('historyIntents',[]))
    from .intent_context import validate as validate_requirements
    validate_requirements(repository,context)
    access = context.get('facts', {}).get('sessionAccess')
    if context.get('facts',{}).get('strictPlayer'):
        from .knowledge import recheck
        recheck(host,room,context)
    if not access:return
    session = repository.read_state()['settings'].get('sessions', {}).get(access['sessionId'])
    require(session and not session.get('deleted') and session['owner'] == access['owner'] and
        session.get('accessLevel', 'player') == access['level'], 'SESSION_ACCESS_CHANGED')
    owner = member(room, access['owner'])
    require(owner['authorizationEpoch'] == access['authorizationEpoch'], 'SESSION_ACCESS_CHANGED')
    if access['level'] == 'administrator':require(owner['role'] == 'kp', 'PERMISSION_DENIED')
    else:
        require(owner['role'] == 'kp' or policy(repository)['allowPlayerChat'], 'PLAYER_AI_DISABLED')
        require(policy(repository)['revision'] == access['policyRevision'], 'SESSION_ACCESS_CHANGED')
    for sid, revision in context['facts'].get('sessionReads', {}).items():
        record = repository.read_state()['settings'].get('sessions', {}).get(sid)
        require(record and not record.get('deleted') and record['revision']==revision,'SOURCE_STALE')
    from .contracts import digest
    for section, expected in context['facts'].get('managementReads', {}).items():
        value={k:room[k] for k in ('roomId','name','runId','status','activeRuleset')} if section=='room' else room[section]
        require(digest(value)==expected,'SOURCE_STALE')
    selected = context['facts'].get('playerReferences')
    if selected:
        from .references import References
        from .contracts import digest
        value = References(host).from_text(access['owner'],selected['text'],room=player_room(room,access['owner']),
            external_policy={**room['aiControl']['settings']['externalSources'],'kp':False})
        require(digest(value)==selected['digest'],'SOURCE_STALE')


def player_room(room, account):
    """A read-only projection, including when a KP chooses a player session."""
    member(room, account)
    result = copy.deepcopy(room)
    result['members'][account]['role'] = 'player'
    return result
