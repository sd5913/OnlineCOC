"""AI/API facade over host-owned read projections and provenance checks."""
from onlinecoc.data_queries import query, KINDS
from .contracts import canonical, digest
from .errors import require

STRING={'type':'string','maxLength':120}
REF={'type':'object','additionalProperties':False,'properties':{k:{'type':'string','minLength':1,'maxLength':200} for k in ('sourceId','kind','id','revision','digest','scopeId')},'required':['sourceId','kind','id','revision','digest','scopeId']}
REFS={'type':'array','items':REF,'minItems':1,'maxItems':12}
PAGE={'limit':{'type':'integer','minimum':1,'maximum':50},'cursor':{'type':'string','maxLength':100}}
PARAMETERS={
    'search':{'types':{'type':'array','items':{'enum':list(KINDS)},'minItems':1,'maxItems':len(KINDS),
        'description':'Categories to enumerate, not search keywords.'},
        'query':{**STRING,'description':'Display-name substring only; omit or use an empty string to enumerate the selected types. This is not a type/configuration/location filter.'},
        'roomMode':{'enum':['state'],'description':'Stable room state excluding ordinary chat and delivery/audit/command traffic.'},**PAGE},
    'read':{'refs':REFS,'fields':{'type':'array','items':STRING,'maxItems':20}},
    'chat':{'channelId':{'type':'string','maxLength':200,'description':'Actual channelId from a channel detail data.channelId. First read the channel search reference with room_read_data. ref.id is opaque and is NOT a channelId.'},'after':{'type':'integer','minimum':0},'before':{'type':'integer','minimum':1},'query':STRING,**PAGE},
    'case':{'refs':REFS}}
NAMES={'room_search_data':'search','room_read_data':'read','room_read_chat':'chat','room_read_case':'case'}
TOOLS=[{'type':'function','function':{'name':name,'description':description,
    'parameters':{'type':'object','properties':PARAMETERS[op],'additionalProperties':False,
                  'required':{'read':['refs'],'chat':['channelId'],'case':['refs']}.get(op,[])}}}
    for (name,op),description in zip(NAMES.items(),[
        'Search permitted room data. Results are references, not proof that all history was searched.',
        'Read exact versioned references. Cite sources; participant statements are not host facts.',
        'Read a permitted channel window in sequence order. Paginate within the returned snapshot.',
        'Read event evidence. A confirmed decision does not imply execution succeeded.'])]


def generation_tools(tools, request, payload):
    """Only an explicitly selected chat source enables ordinary-chat discovery."""
    if request.get('sourceKind')=='chat' or any(r.get('kind')=='chat' for r in payload.get('selectedReferences',[])):return tools
    import copy
    result=copy.deepcopy([t for t in tools if t['function']['name']!='room_read_chat'])
    for t in result:
        if t['function']['name']=='room_search_data':
            schema=t['function']['parameters'];schema['required']=['types']
            schema['properties'].pop('roomMode',None)  # Server attaches stable mode only to room queries.
            schema['properties']['types']['items']['enum']=[k for k in KINDS if k not in ('channel','chat')]
    return result


class DataQueryService:
    def __init__(self, host):self.host=host

    def execute(self, account, operation, args, *, initiator=None, external=False, player=None, read_scope=None):
        from jsonschema import Draft202012Validator
        require(operation in PARAMETERS,'INPUT_INVALID')
        schema=next(t['function']['parameters'] for t in TOOLS if NAMES[t['function']['name']]==operation)
        require(not list(Draft202012Validator(schema).iter_errors(args)),'INPUT_INVALID')
        require(len(canonical(args))<=16*1024,'QUERY_INPUT_LIMIT')
        with self.host.lock:state=self.host.state()
        options={'read_scope':read_scope} if read_scope else {}
        return query(self.host,state,account,operation,args,initiator=initiator,external=external,player=player,**options)

    def attach(self, account, operation, args, snapshot, initiator=None):
        if operation=='search' and 'room' in args.get('types',[]):args={**args,'roomMode':'state'}
        player = snapshot[0]['facts'].get('sessionAccess', {})
        player = player.get('owner') if player.get('level') == 'player' else None
        scope=snapshot[0]['facts'].get('aiReadScope')
        result=self.execute(account,operation,args,initiator=initiator,external=True,player=player,read_scope=scope)
        context=snapshot[0]
        proofs=context['facts'].setdefault('dataQueries',[])
        require(len(proofs)<24,'QUERY_LIMIT')
        proof={'scopeId':context['scopeId'],'operation':operation,'args':args,'initiator':initiator,'player':player,'digest':digest(result)}
        proof['readRefs']=[{'ref':item['ref'],'visibility':item['visibility']} for item in result['items']]
        if scope:proof['readScope']=scope
        if proof not in proofs:proofs.append(proof)
        if any(item['ref']['sourceId'] not in ('host','host-room','host-room-state') for item in result['items']):context['facts']['consultationOnly']=True
        # Recheck also catches changes between reading the snapshot and obtaining evidence.
        with self.host.lock:self.host.validate_ai_sources(self.host.state(),account,context)
        return result

    def citations(self, account, result, snapshot, initiator=None):
        """Bridge opaque evidence IDs to existing UI tokens; never guess from labels."""
        from .references import References
        from .access import player_room
        access=snapshot[0]['facts'].get('sessionAccess',{})
        with self.host.lock:
            room=self.host.state()
            if access.get('level')=='player':
                account=access['owner'];room=player_room(room,account)
            else:account=initiator or account
            candidates={}
            for kind in {i['ref']['kind'] for i in result['items']} & {'entity','config','chat','event','ruling'}:
                for key,label,revision,scope,value in References(self.host)._items(room,account,kind):
                    evidence_id=digest(['host',kind,key]) if kind in ('entity','config') else key
                    candidates[kind,evidence_id]={'token':f'[[{kind}:{key}@{revision}]]','label':label}
            return {digest(i['ref']):candidates[i['ref']['kind'],i['ref']['id']]
                for i in result['items'] if (i['ref']['kind'],i['ref']['id']) in candidates}


def model_result(result, args, citations=None):
    """Presentation-only counts of this authorized page; proof hashes stay raw."""
    counts = {kind: 0 for kind in args.get('types', []) if kind in KINDS}
    for item in result['items']:
        kind = item['ref']['kind']
        counts[kind] = counts.get(kind, 0) + 1
    source_policy={'publication':'consultation-only','notice':'This result includes independently stored package data and cannot authorize a configuration publication. Keep it for advice; prepare a fresh draft from authoritative host templates via room_read_management(section=configurations) or active artifact data via pack_read_config_data.'} if any(i['ref']['sourceId'] not in ('host','host-room','host-room-state') for i in result['items']) else {'publication':'host-evidence'}
    return {**result, 'sourcePolicy':source_policy, 'items':[{**item,**({'citation':citations[digest(item['ref'])]} if citations and digest(item['ref']) in citations else {})} for item in result['items']],
        'pageSummary': {'returnedItems': len(result['items']),
        'countsByType': counts, 'hasMore': result['page']['nextCursor'] is not None,
        'isFirstPage': not bool(args.get('cursor'))}}
