"""Check immutable real-pack fixtures against an isolated engineering tree."""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--tree',required=True);p.add_argument('--old',required=True)
    p.add_argument('--new',required=True);p.add_argument('--artifact',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();tree=Path(args.tree)/'engineering'
    sys.path[:0]=[str(tree/'ai/src'),str(tree/'backend/src'),str(tree/'data-management')]
    from onlinecoc_ai.pack import Pack,fixture_state,merge_changes
    from onlinecoc_ai.sandbox import stage
    from onlinecoc_ai.validation.common import static_context
    from onlinecoc_ai.validation.base import check_base
    raw=json.loads(Path(args.artifact).read_text(encoding='utf8'));artifact=stage(raw['sources'],raw['data'])
    rows=[]
    def check(pack,artifact,data,label,expected):
        state=fixture_state(pack.json(pack.scenarios[0]['fixtureRef']),pack.configurations)
        context=static_context(pack,state,artifact)
        changes=merge_changes(artifact,{'schemaVersion':1,'configurations':[],'sources':{},'data':data,'suggestions':[]})
        result,next_artifact=check_base(pack,state,artifact,context,changes)
        outcome=result['findings'][0]['code'] if result['findings'] else result['status']
        rows.append({'case':label,'expected':expected,'actual':outcome,'success':outcome==expected,
            'unrelatedSceneUnchanged':changes['data']['scene-actions.json']==artifact['data']['scene-actions.json']})
        return next_artifact
    old=Pack(args.old);new=Pack(args.new)
    game=copy.deepcopy(artifact['data']['game.json']);item=copy.deepcopy(game['items'][0]);item.update(id='ai-proof-one',name='验收针剑一');game['items'].append(item)
    check(old,artifact,{'game.json':game},'old-schema-item-add','PACK_SCHEMA_INVALID')
    next_artifact=check(new,artifact,{'game.json':game},'new-schema-item-add','pass')
    game=copy.deepcopy(game);item=copy.deepcopy(item);item.update(id='ai-proof-two',name='验收针剑二');game['items'].append(item)
    check(new,next_artifact,{'game.json':game},'second-item-next-baseline','pass')
    for key in ('items','locations','npcs','rules'):
        value=copy.deepcopy(artifact['data']['game.json'])
        container=value[key]
        if isinstance(container,list) and container and isinstance(container[0],dict):
            row=container[0];field=next(k for k in ('description','name','title') if isinstance(row.get(k),str));row[field]+='（验收修改）'
        elif isinstance(container,dict):
            field=next(k for k,v in container.items() if isinstance(v,str));container[field]+='（验收修改）'
        else:raise ValueError('Unsupported test fixture '+key)
        check(new,artifact,{'game.json':value},key+'-edit-without-scene-coupling','pass')
    scene=copy.deepcopy(artifact['data']['scene-actions.json']);scene['presentationDigest']='0'*64
    check(new,artifact,{'scene-actions.json':scene},'changed-compact-digest','PACK_PROJECTION_EDIT_FORBIDDEN')
    scene=copy.deepcopy(artifact['data']['scene-actions.json']);scene['actions']=[]
    check(new,artifact,{'scene-actions.json':scene},'changed-compact-actions','PACK_PROJECTION_EDIT_FORBIDDEN')
    check(new,artifact,{'scene-actions.json':new.data['scene-actions.json']},'complete-author-form','pass')
    result={'oldPackDigest':old.digest,'newPackDigest':new.digest,
        'artifactFileSha256':hashlib.sha256(Path(args.artifact).read_bytes()).hexdigest(),
        'scope':'real artifact A validation; no HTTP, provider calls or runtime publication in this script',
        'tests':rows,'passed':sum(r['success'] for r in rows),'total':len(rows)}
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,ensure_ascii=False));return int(result['passed']!=result['total'])

if __name__=='__main__':raise SystemExit(main())
