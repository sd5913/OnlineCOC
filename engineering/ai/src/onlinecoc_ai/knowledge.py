"""Strict player read port. No package guide, raw entity or visibility fallback."""
import copy
from .errors import require
from . import known_answers

REF = {'type':'object','additionalProperties':False,'properties':{
    'schemaVersion':{'const':1}, **{k:{'type':'string','minLength':1,'maxLength':200}
    for k in ('scopeId','id','revision')}, 'digest':{'type':'string','pattern':'^[0-9a-f]{64}$'}},
    'required':['schemaVersion','scopeId','id','revision','digest']}
TOOLS = [dict(type='function',function=dict(name=name,description=description,parameters=schema))
    for name,description,schema in [
        ('room_search_knowledge','Search only the bound player known records. Search results are labels; read refs for evidence.',
         {'type':'object','additionalProperties':False,'properties':{
             'query':{'type':'string','maxLength':200},'includeHistory':{'type':'boolean'},
             'limit':{'type':'integer','minimum':1,'maximum':50},'cursor':{'type':'string','maxLength':2048}}}),
        ('room_read_knowledge','Read exact known snapshots. Use returned evidenceId in the final answer.',
         {'type':'object','additionalProperties':False,'properties':{
             'refs':{'type':'array','items':REF,'minItems':1,'maxItems':12,'uniqueItems':True}},'required':['refs']})]]


def service(host, account, room=None):
    port = getattr(host, 'knowledge', None)
    require(port is not None, 'KNOWLEDGE_UNAVAILABLE')
    capability = port.capabilities(account, state=room, player=True)
    require(capability.get('status') == 'ready', 'KNOWLEDGE_UNAVAILABLE')
    port.require_egress(account,'ai',state=room)
    return port


def attach(host, context, name, args, pool):
    from jsonschema import Draft202012Validator
    schema = next((t['function']['parameters'] for t in TOOLS if t['function']['name']==name), None)
    require(schema is not None, 'TOOL_FORBIDDEN')
    require(Draft202012Validator(schema).is_valid(args), 'INPUT_INVALID')
    with host.lock:
        room=host.state(); owner=context['facts']['sessionAccess']['owner']
        port=service(host,owner,room)
        require(room['aiControl']['settings']['externalSources']['private'], 'EXTERNAL_SCOPE_DISABLED')
        operation=port.search if name=='room_search_knowledge' else port.read
        page=operation(owner,args,state=room,player=True)
        refs=[item['ref'] for item in page['items']]
        proofs=context['facts']['knowledgeProofs']
        require(len(proofs)<26,'QUERY_LIMIT')
        # Search labels have the same disclosure requirements as details.
        proof=port.evidence(owner,refs,state=room,player=True)
        if proof not in proofs:proofs.append(proof)
        page=copy.deepcopy(page)
        if name=='room_read_knowledge':page['items']=known_answers.register(pool,page['items'])
        return page


def recheck(host, room, context):
    facts=context['facts']; access=facts.get('sessionAccess',{})
    require(access.get('level')=='player','SESSION_ACCESS_CHANGED')
    owner=access['owner'];port=service(host,owner,room)
    proofs=facts.get('knowledgeProofs')
    require(isinstance(proofs,list) and 1<=len(proofs)<=26,'SOURCE_STALE')
    for proof in proofs:
        require(proof.get('accountId')==owner and proof.get('player') is True,'SOURCE_STALE')
    port.recheck_many(owner,proofs,state=room)
