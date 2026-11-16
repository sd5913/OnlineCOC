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
        'query':{**STRING,'description':'Display-name substring only; omit or use an empty string to enumerate the selected types. This is not a type/configuration/location filter.'},**PAGE},
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


class DataQueryService:
    def __init__(self, host):self.host=host

    def execute(self, account, operation, args, *, initiator=None, external=False):
        from jsonschema import Draft202012Validator
        require(operation in PARAMETERS,'INPUT_INVALID')
        schema=next(t['function']['parameters'] for t in TOOLS if NAMES[t['function']['name']]==operation)
        require(not list(Draft202012Validator(schema).iter_errors(args)),'INPUT_INVALID')
        require(len(canonical(args))<=16*1024,'QUERY_INPUT_LIMIT')
        with self.host.lock:state=self.host.state()
        return query(self.host,state,account,operation,args,initiator=initiator,external=external)

    def attach(self, account, operation, args, snapshot, initiator=None):
        result=self.execute(account,operation,args,initiator=initiator,external=True)
        context=snapshot[0]
        proofs=context['facts'].setdefault('dataQueries',[])
        require(len(proofs)<24,'QUERY_LIMIT')
        proof={'scopeId':context['scopeId'],'operation':operation,'args':args,'initiator':initiator,'digest':digest(result)}
        if proof not in proofs:proofs.append(proof)
        if any(item['ref']['sourceId']!='host' for item in result['items']):context['facts']['consultationOnly']=True
        # Recheck also catches changes between reading the snapshot and obtaining evidence.
        with self.host.lock:self.host.validate_ai_sources(self.host.state(),account,context)
        return result


def model_result(result, args):
    """Presentation-only counts of this authorized page; proof hashes stay raw."""
    counts = {kind: 0 for kind in args.get('types', []) if kind in KINDS}
    for item in result['items']:
        kind = item['ref']['kind']
        counts[kind] = counts.get(kind, 0) + 1
    return {**result, 'pageSummary': {'returnedItems': len(result['items']),
        'countsByType': counts, 'hasMore': result['page']['nextCursor'] is not None,
        'isFirstPage': not bool(args.get('cursor'))}}
