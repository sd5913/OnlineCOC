"""Public-API knowledge commands used by package workflows and UI."""
from knowledge_provider import POLICY,NAMESPACE


def capabilities(client):return client.request('/knowledge/capabilities')


def binding(client):
    return next((p for p in capabilities(client).get('policies',[]) if p['policyId']==POLICY),None)


def bind(job):
    data=capabilities(job.client)
    descriptor=next((p for p in data.get('descriptors',[]) if p['policyId']==POLICY),None)
    if descriptor is None:raise ValueError('知识提供方尚未安装，请更新宿主启动入口')
    current=next((p for p in data.get('policies',[]) if p['policyId']==POLICY),None)
    if current and current['descriptorDigest']==descriptor['descriptorDigest']:return current
    job.command('knowledge-policy','knowledge.policy.bind',{'policyId':POLICY,'descriptorDigest':descriptor['descriptorDigest'],
        'expectedRevision':current['revision'] if current else 0})
    return binding(job.client)


def disclose(job,account,entity,facet,*,live=False,key='disclose',reason='KP 明确向本人揭示当前内容'):
    policy=binding(job.client)
    if policy is None:raise ValueError('请先启用个人知识服务')
    member=next(m for m in job.client.request('/chat/members')['items'] if m['accountId']==account)
    resource={'namespace':NAMESPACE,'kind':'entity','id':entity}
    args={'policyId':POLICY,'expectedPolicyRevision':policy['revision'],'subjectMemberId':member['memberId'],
          'resource':resource,'facetIds':[facet],'reason':reason}
    if not live:
        preview=job.client.request('/knowledge/preview',{'policyId':POLICY,'resource':resource,'facetIds':[facet]})
        args['expectedSourceRevision']=preview['sourceRevision']
    return job.command(key,'knowledge.subscribe' if live else 'knowledge.observe',args)


def records(client, view=None, *, facet=None):
    # A complete authorized view already contains the first search page.
    # Read still verifies each ref. Fall back to normal pagination on overflow.
    summary = (view or {}).get('knowledge') or {}
    if summary.get('hasMore') is False and isinstance(summary.get('items'), list):
        refs = [row['ref'] for row in summary['items'] if facet is None or row['facetId'] == facet]
        items = []
        for offset in range(0, len(refs), 12):
            items.extend(client.request('/knowledge/read', {'refs': refs[offset:offset+12]})['items'])
        return items
    items=[];cursor=None
    for _ in range(8):
        page=client.request('/knowledge/search',{'limit':50,**({'cursor':cursor} if cursor else {})})
        refs=[i['ref'] for i in page['items']]
        for offset in range(0,len(refs),12):
            items.extend(client.request('/knowledge/read',{'refs':refs[offset:offset+12]})['items'])
        cursor=page['nextCursor']
        if cursor is None:return items
    raise ValueError('个人知识分页超限，请缩小读取范围')


def revoke_identity(job,account,entity):
    member=next(m for m in job.client.request('/chat/members')['items'] if m['accountId']==account)
    cursor=None
    # Collect before mutating so a successful revoke cannot invalidate a cursor.
    matches=[]
    for _ in range(20):
        page=job.client.request('/knowledge/grants/query',{'subjectMemberId':member['memberId'],'policyId':POLICY,
            'status':'active','limit':50,**({'cursor':cursor} if cursor else {})})
        matches.extend(g for g in page['items'] if g['resource']['id']==entity and 'identity' in g['facetIds'])
        cursor=page['nextCursor']
        if cursor is None:break
    if cursor:raise ValueError('授权记录过多，请在宿主管理界面分页撤回')
    for grant in matches:
        job.command('revoke-contact-'+grant['grantId'],'knowledge.revoke',{'grantId':grant['grantId'],
            'expectedRevision':grant['revision'],'reason':'KP 撤回该人物的身份披露'})


def locations(items):
    result={}
    for item in items:
        if item['facetId']!='scene':continue
        value={**item['data'],'known':True,'knowledgeRef':item['ref'],'observedAt':item['observedAt']}
        # Retain only observations of disclosed routes. Older snapshots have no
        # door status; unknown must not be presented as closed (or current truth).
        value['doors']={str(i):value.get('doors',{}).get(str(i),'unknown') for i in value['exits']}
        if value['index'] in result and result[value['index']]['observedAt']>value['observedAt']:continue
        result[value['index']]=value
    # Exits are themselves disclosed navigation, without destination lore.
    for place in list(result.values()):
        for index in place['exits']:
            if index not in result:
                result[index]={'index':index,'entityId':place.get('navigation',{}).get(str(index)),
                    'name':'未探索地点','description':'进入或由 KP 向本人揭示后可查看。',
                    'features':[],'clues':[],'exits':[],'doors':{},'known':False}
    return sorted(result.values(),key=lambda v:v['index'])
