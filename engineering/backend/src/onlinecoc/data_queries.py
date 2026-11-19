"""Read-only, audience-filtered evidence projections. No room-format changes."""
import copy
from .ai_contracts import digest
from .errors import require
from .model import member, visible
from . import chat

KINDS = ('entity', 'config', 'rule', 'memory', 'channel', 'chat', 'event', 'ruling', 'knowledge', 'room')


def entity_projection(host, state, account):
    """Trusted package may project player knowledge, never client-selected code."""
    if member(state, account)['role']=='kp':return copy.deepcopy(state['entities'])
    adapter=getattr(host,'ai_data_adapter',None)
    if adapter and hasattr(adapter,'entities'):
        try:values=adapter.entities(state,account)
        except Exception:require(False,'DATA_SOURCE_UNAVAILABLE')
        require(type(values) is dict and all(k in state['entities'] and type(v) is dict and v.get('instanceId')==k for k,v in values.items()),'INPUT_INVALID')
    else:values={k:v for k,v in state['entities'].items() if v['lifecycle']=='active' and visible(state,account,v)}
    values=copy.deepcopy(values)
    values={k:v for k,v in values.items() if not host.knowledge.managed(state,'entity',k,state['entities'][k])}
    for value in values.values():value.get('metadata',{}).pop('secret',None)
    return values


def configuration_projection(host, state, account):
    if member(state,account)['role']=='kp':return copy.deepcopy(state['configurations'])
    known={e['configurationId'] for e in entity_projection(host,state,account).values()}
    adapter=getattr(host,'ai_data_adapter',None)
    if adapter and hasattr(adapter,'known_configurations'):
        try:known &= set(adapter.known_configurations(state,account))
        except Exception:require(False,'DATA_SOURCE_UNAVAILABLE')
    return {k:copy.deepcopy(v) for k,v in state['configurations'].items() if k in known}


def row(state, source, kind, key, revision, label, data, visibility, authority):
    value = copy.deepcopy(data)
    return {'ref': {'sourceId': source, 'kind': kind, 'id': digest([source, kind, key]),
                   'revision': str(revision), 'digest': digest(value), 'scopeId': state['aiControl']['scopeId']},
            'label': str(label)[:160], 'visibility': visibility, 'authority': authority, 'data': value}


def rows(host, state, account, initiator=None, external=False, kinds=KINDS, *, read_scope=None):
    principals = list(dict.fromkeys([account, initiator or account]))
    members = [member(state, p) for p in principals]
    policy = state['aiControl']['settings']['externalSources']
    kp = all(m['role'] == 'kp' for m in members)
    full_room = read_scope == 'kp-room'
    if full_room:
        from .room_read import authorize
        authorize(host, state, account, initiator)
    result = []

    def add(kind, key, revision, label, data, visibility='public', authority='host-state', source='host'):
        if kind not in kinds or (external and not policy[visibility]):return
        result.append(row(state, source, kind, key, revision, label, data, visibility, authority))

    audience=[p for p in principals if member(state,p)['role']!='kp']
    projections=[entity_projection(host,state,p) for p in audience] if audience and set(kinds)&{'entity','config'} else []
    entities=projections[0] if projections else state['entities']
    entities={k:v for k,v in entities.items() if all(k in other and digest(other[k])==digest(v) for other in projections[1:])}
    for key, value in (entities.items() if 'entity' in kinds else []):
        if value['lifecycle'] != 'active' and not kp:continue
        visibility = 'private' if value['visibility'] == 'owner' else value['visibility']
        if external and not policy[visibility]:continue
        data = copy.deepcopy(value)
        if not kp or (external and not policy['kp']):data['metadata'].pop('secret', None)
        label = value['name']
        if kp:
            # A trusted package can clarify a candidate's binding, never its
            # identity or audience. Player knowledge does not use this hook.
            try:
                labeler = getattr(getattr(host, 'ai_data_adapter', None), 'reference_label', None)
                custom = labeler('entity', key, label) if callable(labeler) else None
                if type(custom) is str and 1 <= len(custom.strip()) <= 160:
                    custom = custom.strip();custom.encode('utf-8')
                    label = custom
            except Exception:
                pass
        add('entity', key, value['revision'], label, data, visibility)
    known_configs = set(state['configurations'])
    if 'config' in kinds:
        for p in audience:known_configs &= set(configuration_projection(host,state,p))
    for key, value in (state['configurations'].items() if 'config' in kinds else []):
        if kp or key in known_configs:add('config', key, value['revision'], value.get('name', key), value)
    artifact = state['artifacts'].get(state['activeRuleset'], {})
    if kp and 'rule' in kinds:
        for key, value in artifact.get('sources', {}).items():add('rule', key, state['activeRuleset'], key, {'text':value}, 'kp', 'pack-rule')
    from .ai_sources import check_memory
    for key, value in (state['aiControl'].get('memoryFacts', {}).items() if 'memory' in kinds else []):
        try:
            for p in principals:check_memory(host, state, p, key, value['revision'], set(), read_scope=read_scope)
        except Exception:continue
        add('memory', key, value['revision'], value['content'][:80], value, value['visibility'], 'kp-confirmed-memory')
    for cid, channel in (state['chat']['channels'].items() if set(kinds)&{'channel','chat','event'} else []):
        if not full_room and not all(chat.can_read(state, p, channel) for p in principals):continue
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
    if full_room and 'room' in kinds and (not external or all(policy.get(k) for k in ('public','kp','private'))):
        from .room_read import fragments
        for data in fragments(state):
            key = digest([data['path'],data.get('textOffset')])
            label = '/' + '/'.join(str(p).replace('~','~0').replace('/','~1') for p in data['path'])
            if 'textOffset' in data:label += ' ['+str(data['textOffset'])+']'
            add('room',key,digest(data),label,data,'kp','host-room','host-room')
    adapter = getattr(host, 'ai_data_adapter', None)
    if adapter and set(getattr(adapter,'kinds',KINDS))&set(kinds):
        # Administrator-installed local adapter. Model input never selects executable code or paths.
        try:
            scoped_reader = getattr(adapter, 'read_scoped', None)
            projections = [scoped_reader(state, p, read_scope='kp-room' if full_room else None)
                           if callable(scoped_reader) else adapter.read(state, p) for p in principals]
        except Exception:
            require(False, 'DATA_SOURCE_UNAVAILABLE')
        allowed = [{(v['sourceId'],v['kind'],v['id']):v for v in projection} for projection in projections]
        for key, value in allowed[0].items():
            if any(key not in other or digest(other[key]) != digest(value) for other in allowed[1:]):continue
            require(value['kind'] in KINDS and value['visibility'] in ('public','private','kp'), 'INPUT_INVALID')
            add(value['kind'], value['id'], value['revision'], value['label'], value['data'], value['visibility'], 'package-record', value['sourceId'])
    return result


def query(host, state, account, operation, args, *, initiator=None, external=False, player=None, read_scope=None):
    require(read_scope in (None,'kp-room'),'INPUT_INVALID')
    if read_scope == 'kp-room':
        from .room_read import authorize
        require(player is None, 'PERMISSION_DENIED')
        authorize(host,state,account,initiator)
    if player is not None or member(state, account)['role'] != 'kp':
        return knowledge_query(host,state,player or account,operation,args,external=external)
    if player is not None:
        member(state, player)
        state = copy.deepcopy(state)
        state['members'][player]['role'] = 'player'
        initiator = player
    require(type(args) is dict and operation in ('search','read','chat','case'), 'INPUT_INVALID')
    common = {'limit','cursor'}
    allowed = {'search':common|{'types','query'}, 'read':{'refs','fields'},
               'chat':common|{'channelId','after','before','query'}, 'case':{'refs'}}[operation]
    require(not set(args)-allowed, 'INPUT_INVALID')
    limit = args.get('limit',20)
    require(type(limit) is int and 1 <= limit <= 50, 'INPUT_INVALID')
    needle = args.get('query','')
    require(type(needle) is str and len(needle)<=120, 'INPUT_INVALID')
    defaults=[kind for kind in KINDS if kind!='room' or read_scope=='kp-room']
    requested=args.get('types',defaults) if operation=='search' else ['channel','chat'] if operation=='chat' else [r.get('kind') for r in args.get('refs',[]) if type(r) is dict]
    require(type(requested) is list and all(type(k) is str and k in KINDS for k in requested),'INPUT_INVALID')
    require('room' not in requested or read_scope=='kp-room','PERMISSION_DENIED')
    values = rows(host,state,account,initiator,external,requested,read_scope=read_scope)
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
    snapshot=digest([state['aiControl']['scopeId'],account,initiator,external,player,read_scope,
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


def knowledge_query(host,state,account,operation,args,*,external=False):
    """Strict player evidence has no legacy public/adapter fallback."""
    require(isinstance(args,dict),'INPUT_INVALID')
    host.knowledge.capture(account,state=state,player=True)
    host.knowledge.require_egress(account,'ai',state=state)
    require(operation in ('search','read'),'PERMISSION_DENIED')
    if operation=='search':
        require(set(args)<={'types','query','limit','cursor'},'INPUT_INVALID')
        require(set(args.get('types',['knowledge'])) <= {'knowledge'},'PERMISSION_DENIED')
        query_args={k:v for k,v in args.items() if k!='types'}
        page=host.knowledge.search(account,query_args,state=state,player=True)
    else:
        require(set(args)=={'refs'} and isinstance(args['refs'],list) and 1<=len(args['refs'])<=12,'INPUT_INVALID')
        refs=[]
        for ref in args['refs']:
            require(set(ref)=={'sourceId','kind','scopeId','id','revision','digest'} and ref['sourceId']=='knowledge' and ref['kind']=='knowledge','NOT_VISIBLE')
            refs.append({'schemaVersion':1,**{k:v for k,v in ref.items() if k not in ('sourceId','kind')}})
        page=host.knowledge.read(account,{'refs':refs},state=state,player=True)
    if external and not state['aiControl']['settings']['externalSources']['private']:
        require(operation=='search','PERMISSION_DENIED')
        page=dict(page,items=[],nextCursor=None,viewRevision=digest([]))
    items=[]
    for item in page['items']:
        value={'ref':{'sourceId':'knowledge','kind':'knowledge',**{k:v for k,v in item['ref'].items() if k!='schemaVersion'}},
               'label':item['label'],'visibility':'private','authority':'host-disclosure'}
        if 'data' in item:value['data']=item['data']
        items.append(value)
    return {'schemaVersion':1,'snapshotId':page['viewRevision'],'items':items,'page':{'nextCursor':page['nextCursor']},
            'coverage':{'status':'partial' if page['nextCursor'] else 'complete','within':'requested-authorized-scope'}}


def recheck(host, state, account, context):
    proofs=context['facts'].get('dataQueries',[])
    require(type(proofs) is list and len(proofs)<=24,'INPUT_INVALID')
    for proof in proofs:
        require(proof['scopeId']==state['aiControl']['scopeId'],'SCOPE_MISMATCH')
        result=query(host,state,account,proof['operation'],proof['args'],initiator=proof['initiator'],external=True,player=proof.get('player'),read_scope=proof.get('readScope'))
        require(digest(result)==proof['digest'],'SOURCE_STALE')
