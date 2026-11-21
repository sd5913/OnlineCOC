"""Small authorized pre-reads for explicitly requested template editing."""
import re
from .contracts import canonical
from .errors import AiError
from .access import policy
from .context import MAX_CONTEXT_BYTES


def prepare(app,account,request,snapshot,payload,trace):
    facts=snapshot[0]['facts'];access=facts.get('sessionAccess',{})
    if access.get('level')!='administrator' or not policy(app.repository)['allowDataQueries']:return 0
    catalog=app.batches.catalog_query(account,public_only=True)
    payload['operationIndex']={k:catalog[k] for k in ('host','ai')}
    payload['operationIndex']['notice']='Names only, not permission or complete argument schemas. Read the required schemas; a query for a subset cannot prove other operations are unavailable. entity.patch changes the name while entity.update accepts numbers; use its actual schema.'
    if not app.host.state()['aiControl']['settings']['externalSources']['kp']:return 0
    text=request['text']
    if not (re.search(r'模板|配置|template|configuration',text,re.I) and re.search(r'新增|创建|添加|修改|调整|改为|设为|删除|移除|替换|准备|草稿|add|creat|modif|chang|updat|delet|remov|replac|draft',text,re.I)):return 0
    entry=trace.tool('room_read_management',{'section':'configurations','limit':5});entry['automatic']=True
    try:value=app.batches.read(account,'configurations',0,5)
    except AiError as exc:
        if exc.code!='QUERY_RESULT_LIMIT':raise
        entry.update(status='deferred',code=exc.code);return 0
    if len(canonical(value))>8*1024 or len(canonical(payload))+len(canonical(value))+1024>MAX_CONTEXT_BYTES:
        entry.update(status='deferred',code='CONTEXT_PREFETCH_LIMIT');return 0
    payload['preparedFacts']={'configurations':value,'notice':'Authoritative templates pre-read under current permissions; nextOffset means additional pages remain. Reuse these exact values. This is not permission to execute or publish.'}
    facts.setdefault('managementReads',{})['configurations']=value['snapshot']
    facts.setdefault('managementReadKeys',{})['configurations']=[i['id'] for i in value['items']]
    entry.update(status='completed');return 1
