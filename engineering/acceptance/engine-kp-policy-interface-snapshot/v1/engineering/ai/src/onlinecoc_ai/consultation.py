"""KP acceptance of independently stored evidence; never PL write authority."""
from .contracts import digest
from .errors import require

HOST_SOURCES={'host','host-room','host-room-state'}

def assessment(context):
    facts=context['facts']
    refs={digest(i['ref']) for p in facts.get('dataQueries',[]) for i in p.get('readRefs',[]) if i['ref']['sourceId'] not in HOST_SOURCES}
    return {'requiresAcceptance':bool(facts.get('consultationOnly') or refs),'sourceCount':len(refs),'sourceDigest':digest(context),
        'notice':'独立包资料用于方案依据，可能不具备跨存储原子保证。请核对当前目标、完整变更及检查结果后决定；摘要或资料本身不授权执行。'}

def require_acceptance(context,review):
    require(not context['facts'].get('strictPlayer'),'CONSULTATION_ONLY')
    value=assessment(context)
    if value['requiresAcceptance']:require(review=={'sourceDigest':value['sourceDigest']},'CONSULTATION_REVIEW_REQUIRED')
    elif review is not None:require(review=={'sourceDigest':value['sourceDigest']},'DIGEST_MISMATCH')

def require_current(context,output):
    if not assessment(context)['requiresAcceptance']:return
    require(not context['facts'].get('strictPlayer'),'CONSULTATION_ONLY')
    from .history import require_current_evidence
    import copy
    check=copy.deepcopy(context);check['facts']['intentRequests']=check['facts'].get('intentRequests') or [True]
    require_current_evidence(check,output)
