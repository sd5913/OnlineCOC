"""Authorization and provenance checks shared by context, approval and publish."""
from .ai_contracts import digest
from .errors import require
from .model import member, visible
from . import chat


def check_sources(host, state, account, sources, memory_refs=(), seen=None):
    member(state, account)
    seen = set() if seen is None else seen
    for source in sources:
        kind, key = source['kind'], source['id']
        if kind == 'knowledge':
            import base64,json
            try:ref=json.loads(base64.urlsafe_b64decode(key+'='*((-len(key))%4)))
            except Exception:require(False,'SOURCE_STALE')
            require(source['visibility']=='private','SOURCE_STALE')
            value=host.knowledge.read(account,{'refs':[ref]},state=state,player=True)['items'][0]['data']
            if source.get('digest'):require(digest(value)==source['digest'],'SOURCE_STALE')
            continue
        if kind == 'entity':
            value = state['entities'].get(key)
            require(value and visible(state, account, value) and str(value['revision']) == str(source['revision']), 'SOURCE_STALE')
            require(member(state,account)['role']=='kp' or not host.knowledge.managed(state,'entity',key,value),'SOURCE_STALE')
            require(source['visibility'] == ('private' if value['visibility'] == 'owner' else value['visibility']), 'SOURCE_STALE')
        elif kind == 'configuration':
            value = state['configurations'].get(key)
            require(value and str(value['revision']) == str(source['revision']), 'SOURCE_STALE')
        elif kind == 'message':
            channel = state['chat']['channels'].get(source.get('channelId'))
            require(channel and chat.can_read(state, account, channel), 'PERMISSION_DENIED')
            require(source['visibility'] == ('public' if channel['kind'] == 'room' else 'private'), 'SOURCE_STALE')
            value = next((m for m in state['chat']['messages'].get(source['channelId'], []) if m['messageId'] == key), None)
            require(value and not value['deleted'] and str(value['revision']) == str(source['revision']), 'SOURCE_STALE')
        elif kind == 'contract':
            require(source.get('digest') == state['aiControl']['packBinding']['digest'], 'SOURCE_STALE')
            continue
        elif kind == 'rule':
            require(str(source['revision']) == state['activeRuleset'], 'SOURCE_STALE')
            continue
        elif kind == 'memory':
            value = check_memory(host, state, account, key, source['revision'], seen)
            require(source['visibility'] == value['visibility'], 'SOURCE_STALE')
            if source.get('digest'):require(digest(value) == source['digest'], 'SOURCE_STALE')
            continue
        else:
            require(kind == 'manual' and source.get('accountId') == account, 'SOURCE_STALE')
            continue
        if source.get('digest'):
            require(digest(value) == source['digest'], 'SOURCE_STALE')
    for reference in memory_refs:
        require(reference['kind'] == 'memory', 'SOURCE_STALE')
        value = check_memory(host, state, account, reference['id'], reference['revision'], seen)
        if reference.get('digest'):require(digest(value) == reference['digest'], 'SOURCE_STALE')


def check_memory(host, state, account, key, revision, seen):
    require(key not in seen and len(seen) < 32, 'MEMORY_CYCLE')
    value = state['aiControl'].get('memoryFacts', {}).get(key)
    require(value and value['scopeId'] == state['aiControl']['scopeId'] and value['status'] == 'confirmed' and str(value['revision']) == str(revision), 'SOURCE_STALE')
    require(value['validUntil'] is None or host.clock() < value['validUntil'], 'SOURCE_STALE')
    require(value['visibility'] != 'private' or value['owner'] == account, 'PERMISSION_DENIED')
    require(value['visibility'] != 'kp' or member(state, account)['role'] == 'kp', 'PERMISSION_DENIED')
    check_sources(host, state, account, value['sourceRefs'], seen=seen | {key})
    return value
