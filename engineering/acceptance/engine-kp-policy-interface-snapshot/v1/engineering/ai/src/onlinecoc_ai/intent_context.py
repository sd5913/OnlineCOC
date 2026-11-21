"""Bounded extractive user requirements, never model facts or execution approval."""
import re
from .contracts import canonical,digest
from .errors import require
from .reviews import request_text,legacy_record

MAX_BYTES=12*1024
MAX_REQUESTS=32


def chat_dependent(context,state,seen=None):
    """Legacy/explicit chat evidence must not become a later default dependency."""
    seen=set() if seen is None else seen
    if not context:return True
    key=digest(context)
    if key in seen:return False
    if len(seen)>=100:return True
    seen.add(key);facts=context['facts']
    if any(r['kind']=='message' for r in context['sourceRefs']):return True
    for proof in facts.get('dataQueries',[]):
        args=proof['args'];refs=[i['ref'] for i in proof.get('readRefs',[])]
        if proof['operation']=='chat' or set(args.get('types',[])) & {'chat','channel'}:return True
        if 'room' in args.get('types',[]) and args.get('roomMode')!='state':return True
        if any(r['kind'] in ('chat','channel') or r['sourceId']=='host-room' for r in refs):return True
    return any(chat_dependent(state['contexts'].get(ref),state,seen) for ref in facts.get('historyContexts',[]))


def capture(repository,account,request,target,remaining):
    from .access import request_session
    session=request_session(repository,request)
    if not session or session.get('accessLevel')!='administrator' or session['owner']!=account or not session.get('historyTurns',4):return None
    state=repository.read_state()
    original=next((k for k in session['requestIds'] if state['requests'][k]['sourceId']==request['sourceId']),None)
    if not original:return None
    prior=session['requestIds'][:session['requestIds'].index(original)]
    older=prior[:-session.get('historyTurns',4)]
    if not older:return None
    candidates=[]
    for key in older:
        row=state['requests'][key]
        if row['status']=='cancelled' or row['sourceKind']!='manual' or legacy_record(repository,row):continue
        candidates.append({'requestId':key,'text':request_text(repository,row,state),'authority':'user-requirement-only'})
    # Keep the original goal and newest details; never silently cut a sentence.
    selected=[];seen=set();budget=max(0,min(MAX_BYTES,remaining-1024))
    order=candidates[:1]+list(reversed(candidates[1:]))
    for item in order:
        if len(selected)>=MAX_REQUESTS:break
        fingerprint=digest(item['text'])
        if fingerprint in seen:continue
        if len(canonical(selected+[item]))>budget:continue
        selected.append(item);seen.add(fingerprint)
    positions={k:n for n,k in enumerate(older)};selected.sort(key=lambda i:positions[i['requestId']])
    target['facts']['intentRequests']=[{'sessionId':session['sessionId'],'requestId':i['requestId'],'textDigest':digest(i['text'])} for i in selected]
    return {'mode':'extractive-user-requests','items':selected,'omittedRequests':len(candidates)-len(selected),'limitBytes':MAX_BYTES,
        'notice':'Quoted earlier user requirements, not current room facts or execution approval. Preserve stated parameters; later user corrections supersede earlier wording. Missing entries were omitted, not withdrawn. Query current facts before preparing changes; ask only about actual unresolved conflicts or preferences.'}


def validate(repository,context):
    state=repository.read_state();access=context['facts'].get('sessionAccess',{})
    for proof in context['facts'].get('intentRequests',[]):
        session=state['settings'].get('sessions',{}).get(proof['sessionId'],{})
        row=state['requests'].get(proof['requestId'],{})
        require(session and not session.get('deleted') and session['sessionId']==access.get('sessionId') and
            session['owner']==access.get('owner') and session.get('accessLevel')=='administrator' and
            row.get('requestId') in session['requestIds'] and row.get('sourceKind')=='manual' and row.get('status')!='cancelled' and
            not legacy_record(repository,row) and digest(request_text(repository,row,state))==proof['textDigest'],'SOURCE_STALE')


def normalized(value):return re.sub(r'[\s。！？!?，,；;]+','',value).casefold()


def resolved_choices(payload):
    history=payload.get('conversationHistory',[]);result=[]
    for turn in history:
        choices=turn.get('choices',{})
        if turn['role']!='assistant' or not choices:continue
        replies=[payload['request']]  # A later change of mind must remain a new decision.
        for option in choices.get('options',[]):
            if any(normalized(reply)==normalized(option['text']) for reply in replies):
                result.append({'prompt':choices['prompt'],'selectedText':option['text'],
                    'optionTexts':[o['text'] for o in choices['options']],'authority':'explicit-user-choice-not-execution-approval'})
    return result


def require_new_question(payload,output):
    if output.get('kind')!='clarification' or not output.get('choices'):return
    proposed={normalized(o['text']) for o in output['choices']['options']}
    for choice in payload.get('resolvedChoices',[]):
        require(proposed!={normalized(v) for v in choice['optionTexts']},'REPEATED_RESOLVED_CHOICE',
            'These exact alternatives already have an explicit user answer in resolvedChoices. Retain that selectedText, read missing current facts and prepare the requested candidate. Ask only a different, genuinely unresolved decision. This does not approve execution.')
