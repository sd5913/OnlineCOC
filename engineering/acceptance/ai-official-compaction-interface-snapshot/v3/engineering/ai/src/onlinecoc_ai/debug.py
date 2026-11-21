"""Read-only, current-authority diagnostic export; never a durable command result."""
import re
from .errors import require
from .access import can_use

SECRET = re.compile(r'(?i)(?:sk-[a-z0-9_-]{12,}|Bearer\s+[a-z0-9._~+/-]{8,}|(?:api[_ -]?key|password|authorization|token)\s*[=:]\s*[^\s,;"}]+)')
SENSITIVE={'credentialRef','apiKey','password','authorization','csrf','credential','secret','headers','endpoint','baseUrl'}
def redact(value):
    if isinstance(value,dict):return {k:('[redacted]' if k in SENSITIVE else redact(v)) for k,v in value.items()}
    if isinstance(value,list):return [redact(v) for v in value]
    if isinstance(value,str):return SECRET.sub('[redacted]',value)
    return value

def export(app, account, options):
    require(type(options) is dict and not set(options)-{'sessionId','requestId','rulingId','includeContent'},'INPUT_INVALID')
    include=options.get('includeContent',False)
    require(type(include) is bool or include in ('true','false'),'INPUT_INVALID')
    include=include is True or include=='true'
    ids={k:v for k,v in options.items() if k!='includeContent'}
    require(ids and all(type(v) is str and 0<len(v)<=200 for v in ids.values()),'INPUT_INVALID')
    with app.host.lock,app.lock:
        role=can_use(app.host,app.repository,account)
        ruling=None
        if ids.get('rulingId'):
            app.host.kp(account)
            ruling=next((r for r in app.rulings.list(account)['items'] if r['rulingId']==ids['rulingId']),None)
            require(ruling,'NOT_VISIBLE')
        session=None
        if ids.get('sessionId'):
            data=app.sessions.get(account,ids['sessionId']);session=data['session'];items=data['items']
        else:
            state=app.repository.state()
            wanted=ids.get('requestId') or (ruling or {}).get('requestId')
            if wanted:
                items=app.tasks(account,limit=100,request_ids={wanted})['items']
                # Configuration rulings can point at the dispatch copy.
                if not items and ruling:
                    original=next((rid for rid,tid in state['settings'].get('dispatch',{}).items() if tid==wanted),None)
                    if original:items=app.tasks(account,limit=100,request_ids={original})['items']
            else:items=[]
        if ids.get('requestId'):
            items=[i for i in items if i['requestId']==ids['requestId']]
            require(items,'NOT_VISIBLE')
        if ruling and session:require(ruling.get('sessionId')==session['sessionId'],'NOT_VISIBLE')
        rows=[]
        for item in items:
            row={k:item[k] for k in ('requestId','sessionId','taskId','status','createdAt','error','modelCalls') if k in item}
            if role=='kp' and item.get('diagnostics'):row['diagnostics']=item['diagnostics']
            if include:
                row['content']={k:item[k] for k in ('text','response','choices','reviewSource') if k in item}
            rows.append(row)
        result={'schemaVersion':1,'kind':'ai-debug','generatedAt':app.host.clock(),
            'locator':{'roomId':app.host.state()['roomId'],**ids},'audience':role,'includeContent':include,'items':rows,
            'notice':'Current authorized projection; metadata by default. Explicit content export may contain private game or conversation information. Credentials and provider/system payloads are excluded.'}
        if session:result['session']={k:session[k] for k in ('sessionId','accessLevel','owner','archived','revision')}
        if ruling:
            result['ruling']={k:ruling[k] for k in ('rulingId','kind','status','digest','requestId','sessionId') if k in ruling}
            if include:result['ruling']['content']={k:ruling[k] for k in ('summary','actions','changeSet','reports','receipts') if k in ruling}
        return redact(result)
