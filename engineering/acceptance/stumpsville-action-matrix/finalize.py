"""Prepare minimal synthetic input contexts separately from answers/oracles."""
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

cases=load(HERE/'cases.json')['cases'];prestates=load(HERE/'prestates.json')
catalog=load(HERE/'catalog.json');result=load(HERE/'results.json')
game=load(ROOT/'rulepacks/stumpsville/config/game.json')
scenes=load(ROOT/'rulepacks/stumpsville/config/scene-actions.json')
contexts=[]
for case in cases:
    state=prestates[case['caseId']];inventory=[];item_indices=set();location_indices=set()
    for key,entity in state['entities'].items():
        numbers=entity['numbers']
        if 'location' in numbers:location_indices.add(numbers['location'])
        if entity['configurationId']=='sv.location':location_indices.add(numbers['index'])
        for slot in range(1,21):
            index=numbers.get('item'+str(slot),0)
            if index:
                item_indices.add(index)
                inventory.append({'entityId':key,'slot':slot,'definitionIndex':index,
                    'itemId':game['items'][index-1]['id'],'itemName':game['items'][index-1]['name'],
                    'uses':numbers['uses'+str(slot)],'ticks':numbers['ticks'+str(slot)]})
    # Relevant definitions are explicit reference material, not guessed IDs.
    args=case['action']['args']['input']
    if type(args.get('item')) is int:item_indices.add(args['item'])
    if type(args.get('location')) is int:location_indices.add(args['location'])
    scene_options=[x for x in scenes['actions'] if x['location'] in location_indices] if case['actionId']=='sv.scene.resolve' else []
    contexts.append({'caseId':case['caseId'],'request':case['intent'],
        'principal':{'accountId':case['principal'],**state['members'][case['principal']]},
        'catalogRef':'catalog.json#/actions','state':copy.deepcopy(state),
        'inventorySlots':inventory,
        'referenceData':{'items':[{'definitionIndex':i,**game['items'][i-1]} for i in sorted(item_indices)],
            'locations':[x for x in game['locations'] if x['index'] in location_indices],
            'sceneActions':scene_options}})
write(HERE/'contexts.json',{'schemaVersion':1,
    'purpose':'Synthetic authoritative generation input; deliberately excludes expected args, oracle, and scripted dice.',
    'contexts':contexts})
assert len(contexts)==result['uniqueCases']==24
assert all('oracle' not in c and 'randomPolicy' not in c and 'action' not in c for c in contexts)
result['contextArtifact']='contexts.json';result['preStateArtifact']='prestates.json';result['caseArtifact']='cases.json'
result['initialExecuteCalls']=len(cases);result['receiptReplayCalls']=len(cases);result['preflightCalls']=len(cases)
result['modelSuccessRate']=None
result['scopeNote']='17 public actionIds each have one legal execution example. Not exhaustive scene choices/branches, not model generation accuracy, not HTTP/UI integration.'
files=sorted(p for p in HERE.rglob('*') if p.is_file() and 'work-tmp' not in p.parts and '__pycache__' not in p.parts)
result['newFiles']=[str(p.relative_to(ROOT)).replace('\\','/') for p in files]
result['artifactSha256']={str(p.relative_to(HERE)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.name!='results.json'}
write(HERE/'results.json',result)
print(json.dumps({'uniqueCases':result['uniqueCases'],'passed':result['passed'],'failed':result['failed'],
    'positiveActions':result['countsByCategory']['positive']['passed'],'newFiles':len(files),
    'unchangedProductionFiles':len(result['productionSha256']),'realApiCalls':0},ensure_ascii=False))
