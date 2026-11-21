"""Audience-bound summary receipts, never restored execution or source authority."""
from .contracts import digest
from .messages import audience_valid,_published


def key(state,account,item):
    return digest([state['scopeId'],account,item['rulingId'],item['digest'],item.get('revision'),item.get('sessionId')])


def restore(repository,room,account,item,context,original):
    state=repository.read_state();session=state['settings'].get('sessions',{}).get(item.get('sessionId'))
    member=room['members'].get(account,{})
    if not member or member.get('role')!='kp' or not context:return False
    principal=room['members'].get(context['reviewPrincipal'],{})
    if principal.get('authorizationEpoch')!=context['authorizationEpoch'] or principal.get('role')!='kp':return False
    if context['scopeId']!=room['aiControl']['scopeId']:return False
    if session and (session.get('deleted') or context['facts'].get('sessionAccess',{}).get('authorizationEpoch')!=room['members'].get(session['owner'],{}).get('authorizationEpoch')):return False
    proof=state['settings'].get('rulingDeliveries',{}).get(key(state,account,item))
    if proof and proof.get('audience')==account and proof.get('scopeId')==state['scopeId'] and proof.get('digest')==digest({k:v for k,v in proof.items() if k!='digest'}) and proof.get('authorizationEpoch')==member['authorizationEpoch'] and proof.get('contextDigest')==digest(context) and proof.get('summary')==original:return True
    if not audience_valid(room,context,session,account):return False
    from .review_queue import canonical_request
    for task in state['tasks'].values():
        if canonical_request(state,task['requestId'])!=canonical_request(state,item['requestId']):continue
        published=_published(state,task,session,account)
        if published and published['response']==original:return True
    return False


def remember(repository,room,account,items,contexts):
    state=repository.read_state();updates={}
    for item in items:
        context=contexts.get(item['rulingId'])
        if not context or item.get('sourceState')!='fresh' or not item.get('summary'):continue
        value={'summary':item['summary'],'audience':account,'scopeId':state['scopeId'],'authorizationEpoch':room['members'][account]['authorizationEpoch'],'contextDigest':digest(context)}
        value['digest']=digest(value);identifier=key(state,account,item)
        if state['settings'].get('rulingDeliveries',{}).get(identifier)!=value:updates[identifier]=value
    if updates:repository.update(lambda s:s['settings'].setdefault('rulingDeliveries',{}).update(updates))
