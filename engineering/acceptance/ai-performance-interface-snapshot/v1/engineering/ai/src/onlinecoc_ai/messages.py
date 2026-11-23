"""Published conversation text is an audience-bound record, not source access."""
import copy
from .contracts import digest
from .references import References, TOKEN

NOTICE = '引用详情当前不可用；保留本会话已交付的原文，继续处理前需重新查询资料。'


def audience_valid(room,context,session,account):
    """Source age may change; a revoked audience must never be recreated."""
    if not context or not session or session.get('deleted'):return False
    access=context.get('facts',{}).get('sessionAccess',{})
    current=room['members'].get(account,{})
    return bool(current and context.get('scopeId')==room['aiControl']['scopeId'] and
        session['owner']==account and access.get('owner')==account and access.get('sessionId')==session['sessionId'] and
        access.get('level')==session.get('accessLevel') and access.get('authorizationEpoch')==current.get('authorizationEpoch') and
        (session['accessLevel']=='player' or current.get('role')=='kp'))


def labels(host, account, *texts):
    result = {}
    tokens = dict.fromkeys(m.group(0) for text in texts if isinstance(text, str) for m in TOKEN.finditer(text))
    for token in list(tokens)[:36]:
        try:
            item = References(host).resolve(account, [token])['items'][0]
            result[token] = item['label']
        except Exception:
            # Never obtain a missing label through another principal or source.
            pass
    return result


def publication(host, state, task, text, at):
    context = state['contexts'].get(task.get('contextRef'), {})
    access = context.get('facts', {}).get('sessionAccess', {})
    session = state['settings'].get('sessions', {}).get(access.get('sessionId'))
    if not session or session.get('deleted') or session['owner'] != access.get('owner'):
        return None
    if session.get('accessLevel') != access.get('level') or context.get('scopeId') != state['scopeId']:
        return None
    return {'scopeId':state['scopeId'], 'sessionId':session['sessionId'], 'account':session['owner'],
        'accessLevel':session['accessLevel'], 'contextRef':task['contextRef'], 'textDigest':digest(text),
        'responseAt':at, 'referenceLabels':labels(host, session['owner'], text)}


def _published(state, task, session, account):
    proof = task.get('messagePublication')
    if not proof or proof.get('scopeId') != state['scopeId'] or proof.get('sessionId') != session['sessionId']:
        return None
    if proof.get('account') != account or session['owner'] != account or proof.get('accessLevel') != session.get('accessLevel'):
        return None
    if proof.get('contextRef') != task.get('contextRef') or proof.get('textDigest') != digest(task.get('text')):
        return None
    return {'response':task['text'], 'responseAt':proof['responseAt'], 'referenceLabels':proof['referenceLabels']}


def legacy_publication(state, task, session):
    """Migrate a finalized, audience-bound session reply, never an in-flight draft."""
    if task.get('messagePublication') or task.get('status') not in ('review_ready','needs_input','approved','published') or not task.get('text'):
        return None
    context=state['contexts'].get(task.get('contextRef'),{})
    access=context.get('facts',{}).get('sessionAccess',{})
    if not context or digest(context)!=task.get('contextRef') or context.get('scopeId')!=state['scopeId']:
        return None
    if any(access.get(k)!=v for k,v in {'sessionId':session['sessionId'],'owner':session['owner'],'level':session.get('accessLevel')}.items()):
        return None
    from .review_queue import canonical_request
    rid=canonical_request(state,task['requestId']);request=state['requests'].get(rid,{})
    if rid not in session['requestIds'] or request.get('initiator')!=session['owner'] or request.get('sourceKind')!='manual':
        return None
    if context.get('reviewPrincipal')!=session['owner']:
        return None
    if session.get('accessLevel')=='player':
        facts=context['facts'];proofs=facts.get('knowledgeProofs')
        if facts.get('strictPlayer') is not True or not proofs or any(p.get('accountId')!=session['owner'] or p.get('player') is not True for p in proofs):
            return None
    return {'scopeId':state['scopeId'],'sessionId':session['sessionId'],'account':session['owner'],
        'accessLevel':session['accessLevel'],'contextRef':task['contextRef'],'textDigest':digest(task['text']),
        'responseAt':task.get('responseAt'),'referenceLabels':{},'origin':'legacy-final-task'}


def project(app, account, page, *, delivered=False):
    state = app.repository.state()
    updates = {};migrations={}
    for item in page['items']:
        rid = item['requestId']; session = state['settings'].get('sessions', {}).get(item.get('sessionId'))
        item['sentAt'] = item['createdAt']
        if not session or session.get('deleted'):
            continue
        request = state['requests'][rid]
        task = state['tasks'].get(state['settings'].get('dispatch', {}).get(rid, rid), {})
        key = digest({'scopeId':state['scopeId'], 'account':account, 'sessionId':session['sessionId'], 'requestId':rid})
        receipt = state['settings'].get('messageDeliveries', {}).get(key)
        if receipt and (receipt.get('scopeId') != state['scopeId'] or receipt.get('account') != account or
                        receipt.get('sessionId') != session['sessionId'] or receipt.get('requestId') != rid or
                        receipt.get('accessLevel') != session.get('accessLevel') or
                        receipt.get('digest') != digest({k:v for k,v in receipt.items() if k!='digest'})):
            receipt = None
        if not task.get('messagePublication'):
            proof=legacy_publication(state,task,session)
            if proof:
                task['messagePublication']=proof;migrations[task['taskId']]=proof
        published = _published(state, task, session, account)
        context=state['contexts'].get(task.get('contextRef'))
        if not audience_valid(app.host.state(),context,session,account):published=None;receipt=None
        saved = receipt if receipt and receipt.get('response') else published
        if not item.get('response') and saved and saved.get('response'):
            item.update(response=saved['response'], responseAt=saved.get('responseAt'),
                sourceState='stale', sourceError=item.pop('error', None), sourceNotice=NOTICE, historicalReadOnly=True)
            item.pop('choices', None)
        if request['initiator'] == account and request['sourceKind'] == 'manual':
            from .reviews import request_text
            item.setdefault('text', request_text(app.repository,request,state))
            item.setdefault('initiator',request['initiator'])
        if item.get('response'):
            item.setdefault('responseAt', task.get('responseAt'))
        retained = dict((receipt or {}).get('referenceLabels', {}))
        retained.update((published or {}).get('referenceLabels', {}))
        # Only a public delivery may persist labels newly obtained with live access.
        if delivered:
            retained.update(labels(app.host, account, item.get('text'), item.get('response')))
        if retained:
            item['referenceLabels'] = retained
        if delivered and (item.get('text') is not None or item.get('response') is not None):
            value = {'scopeId':state['scopeId'], 'account':account, 'sessionId':session['sessionId'],
                'requestId':rid, 'accessLevel':session['accessLevel'],
                **{k:copy.deepcopy(item[k]) for k in ('text','response','sentAt','responseAt') if k in item},
                'referenceLabels':retained}
            # Stable receipts do not turn polling into an unbounded write stream.
            value['digest'] = digest(value)
            if value != receipt:
                updates[key] = value
    if updates or migrations:
        def save(s):
            if updates:s['settings'].setdefault('messageDeliveries', {}).update(updates)
            for tid,proof in migrations.items():s['tasks'][tid]['messagePublication']=proof
        app.repository.update(save)
    return page
