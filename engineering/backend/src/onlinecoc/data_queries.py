"""Read-only, audience-filtered evidence projections. No room-format changes."""
import copy
from .ai_contracts import digest
from .errors import require
from .model import member, visible
from . import chat

KINDS = ('entity', 'config', 'rule', 'memory', 'channel', 'chat', 'event', 'ruling')


def row(state, source, kind, key, revision, label, data, visibility, authority):
    value = copy.deepcopy(data)
    return {'ref': {'sourceId': source, 'kind': kind, 'id': digest([source, kind, key]),
                   'revision': str(revision), 'digest': digest(value), 'scopeId': state['aiControl']['scopeId']},
            'label': str(label)[:160], 'visibility': visibility, 'authority': authority, 'data': value}


def rows(host, state, account, initiator=None, external=False, kinds=KINDS):
    principals = list(dict.fromkeys([account, initiator or account]))
    members = [member(state, p) for p in principals]
    policy = state['aiControl']['settings']['externalSources']
    kp = all(m['role'] == 'kp' for m in members)
    result = []

    def add(kind, key, revision, label, data, visibility='public', authority='host-state', source='host'):
        if kind not in kinds or (external and not policy[visibility]):return
        result.append(row(state, source, kind, key, revision, label, data, visibility, authority))

    for key, value in (state['entities'].items() if 'entity' in kinds else []):
        if value['lifecycle'] != 'active' or not all(visible(state, p, value) for p in principals):continue
        data = copy.deepcopy(value)
        if not kp or (external and not policy['kp']):data['metadata'].pop('secret', None)
        add('entity', key, value['revision'], value['name'], data,
            'private' if value['visibility'] == 'owner' else value['visibility'])
    for key, value in (state['configurations'].items() if 'config' in kinds else []):add('config', key, value['revision'], value.get('name', key), value)
    artifact = state['artifacts'].get(state['activeRuleset'], {})
    if kp and 'rule' in kinds:
        for key, value in artifact.get('sources', {}).items():add('rule', key, state['activeRuleset'], key, {'text':value}, 'kp', 'pack-rule')
    from .ai_sources import check_memory
    for key, value in (state['aiControl'].get('memoryFacts', {}).items() if 'memory' in kinds else []):
        try:
            for p in principals:check_memory(host, state, p, key, value['revision'], set())
        except Exception:continue
        add('memory', key, value['revision'], value['content'][:80], value, value['visibility'], 'kp-confirmed-memory')
    for cid, channel in (state['chat']['channels'].items() if set(kinds)&{'channel','chat','event'} else []):
        if not all(chat.can_read(state, p, channel) for p in principals):continue
        visibility = 'public' if channel['kind'] == 'room' else 'private'
        add('channel', cid, channel['revision'], channel['name'], {'channelId':cid, 'lastSequence':channel['lastSequence']}, visibility)
        for message in (state['chat']['messages'][cid] if set(kinds)&{'chat','event'} else []):
            if message['deleted']:continue
            add('chat', message['messageId'], message['revision'], message['text'][:80] or '行动结果', message, visibility, 'participant-statement')
            if message['kind'] == 'action' and 'event' in kinds:
                # A published card is readable; it does not grant access to the original command.
                card = message['card']
                bundle = {'messages':[copy.deepcopy(message)], 'actions':[], 'rulings':[],
                          'executions':[{'authority':'published-action-card', **copy.deepcopy(card), 'executionStatus':'committed'}],
                          'links':[], 'coverage':{'status':'partial','reason':'ONLY_PUBLISHED_CARD'}}
                reply = next((m for m in state['chat']['messages'][cid] if m['messageId']==message['replyTo'] and not m['deleted']), None)
                if reply:
                    bundle['messages'].insert(0, copy.deepcopy(reply))
                    bundle['links'].append({'type':'replies-to','from':message['messageId'],'to':reply['messageId'], 'authority':'host-chat'})
                add('event', message['messageId'], digest(bundle), '行动：'+card['ruleId'], bundle, visibility, 'published-action-card')
    adapter = getattr(host, 'ai_data_adapter', None)
    if adapter and set(getattr(adapter,'kinds',KINDS))&set(kinds):
        # Administrator-installed local adapter. Model input never selects executable code or paths.
        try:projections = [adapter.read(state, p) for p in principals]
        except Exception:
            require(False, 'DATA_SOURCE_UNAVAILABLE')
        allowed = [{(v['sourceId'],v['kind'],v['id']):v for v in projection} for projection in projections]
        for key, value in allowed[0].items():
            if any(key not in other or digest(other[key]) != digest(value) for other in allowed[1:]):continue
            require(value['kind'] in KINDS and value['visibility'] in ('public','private','kp'), 'INPUT_INVALID')
            add(value['kind'], value['id'], value['revision'], value['label'], value['data'], value['visibility'], 'package-record', value['sourceId'])
    return result


def query(host, state, account, operation, args, *, initiator=None, external=False):
    require(type(args) is dict and operation in ('search','read','chat','case'), 'INPUT_INVALID')
    common = {'limit','cursor'}
    allowed = {'search':common|{'types','query'}, 'read':{'refs','fields'},
               'chat':common|{'channelId','after','before','query'}, 'case':{'refs'}}[operation]
    require(not set(args)-allowed, 'INPUT_INVALID')
    limit = args.get('limit',20)
    require(type(limit) is int and 1 <= limit <= 50, 'INPUT_INVALID')
    needle = args.get('query','')
    require(type(needle) is str and len(needle)<=120, 'INPUT_INVALID')
    requested=args.get('types',list(KINDS)) if operation=='search' else ['channel','chat'] if operation=='chat' else [r.get('kind') for r in args.get('refs',[]) if type(r) is dict]
    require(type(requested) is list and all(type(k) is str and k in KINDS for k in requested),'INPUT_INVALID')
    values = rows(host,state,account,initiator,external,requested)
    if operation == 'search':
        kinds=args.get('types',list(KINDS))
        require(type(kinds) is list and 1<=len(kinds)<=len(KINDS) and all(k in KINDS for k in kinds), 'INPUT_INVALID')
        values=[v for v in values if v['ref']['kind'] in kinds and needle.casefold() in v['label'].casefold()]
    elif operation == 'chat':
        cid=args.get('channelId');require(type(cid) is str and len(cid)<=200,'INPUT_INVALID')
        require(any(v['ref']['kind']=='channel' and v['data']['channelId']==cid for v in values),'NOT_VISIBLE')
        after,before=args.get('after',0),args.get('before',2**53-1)
        require(type(after) is int and type(before) is int and 0<=after<before<=2**53-1,'INPUT_INVALID')
        values=[v for v in values if v['ref']['kind']=='chat' and v['data']['channelId']==cid and
                after<v['data']['sequence']<before and needle.casefold() in v['data']['text'].casefold()]
        values.sort(key=lambda v:v['data']['sequence'])
    else:
        refs=args.get('refs');require(type(refs) is list and 1<=len(refs)<=12,'INPUT_INVALID')
        found=[]
        for ref in refs:
            require(type(ref) is dict,'INPUT_INVALID')
            value=next((v for v in values if v['ref']==ref),None)
            require(value is not None,'SOURCE_STALE')
            require(operation!='case' or ref['kind'] in ('event','ruling'), 'INPUT_INVALID')
            if value not in found:found.append(copy.deepcopy(value))
        values=found
        fields=args.get('fields')
        if fields is not None:
            require(type(fields) is list and len(fields)<=20 and all(type(k) is str and len(k)<=100 for k in fields),'INPUT_INVALID')
            for value in values:
                require(all(k in value['data'] for k in fields),'INPUT_INVALID')
                value['data']={k:value['data'][k] for k in fields}
    # Cursor binds the authorized result and policy, never a global or hidden record count.
    snapshot=digest([state['aiControl']['scopeId'],account,initiator,external,
                     getattr(host,'ai_data_adapter_digest',None),
                     state['aiControl']['settings']['externalSources'],operation,
                     {k:v for k,v in args.items() if k!='cursor'},values])
    offset=0
    if 'cursor' in args:
        cursor=args['cursor'];require(type(cursor) is str and len(cursor)<=100,'INPUT_INVALID')
        parts=cursor.split(':');require(len(parts)==2 and parts[0]==snapshot and parts[1].isdigit(),'SOURCE_STALE')
        offset=int(parts[1]);require(0<=offset<=len(values),'SOURCE_STALE')
    selected=copy.deepcopy(values[offset:offset+limit])
    if operation=='search':
        for item in selected:item.pop('data')
    more=offset+limit<len(values)
    result={'schemaVersion':1,'snapshotId':snapshot,'items':selected,
            'page':{'nextCursor':snapshot+':'+str(offset+limit) if more else None},
            'coverage':{'status':'partial' if more else 'complete','within':'requested-authorized-scope'}}
    from onlinecoc_data import canonical
    require(len(canonical(result))<=16*1024,'QUERY_RESULT_LIMIT')
    return result


def recheck(host, state, account, context):
    proofs=context['facts'].get('dataQueries',[])
    require(type(proofs) is list and len(proofs)<=24,'INPUT_INVALID')
    for proof in proofs:
        require(proof['scopeId']==state['aiControl']['scopeId'],'SCOPE_MISMATCH')
        result=query(host,state,account,proof['operation'],proof['args'],initiator=proof['initiator'],external=True)
        require(digest(result)==proof['digest'],'SOURCE_STALE')
