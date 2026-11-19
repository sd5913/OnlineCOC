"""Pack-declared NPC-family probes for explicitly invoked action/calculation extensions."""
import copy
from ..errors import require
from ..pack import local_schema, fixture_state
from ..sandbox import run_scenario, execute


def configuration_checks(pack, state, baseline, artifact, changes):
    spec=getattr(pack,'extension_validation',None)
    if not spec:return
    validator=local_schema(pack.json(spec['defaultsSchema']))
    for value in state['configurations'].values():
        if value['configurationId']==spec['baseConfiguration'] or value['configurationId'].startswith(spec['namespace']):
            require(value['typeRef']=='actor' and validator.is_valid(value['defaults']) and (value['configurationId']==spec['baseConfiguration'] or value['defaults'].get('isNpc')==1),'EXTENSION_DEFAULTS_INVALID')
    for name,text in changes['sources'].items():
        if baseline['sources'].get(name)==text:continue
        metadata=execute({name:text},{'kind':'inspect'})['metadata']
        require(bool(metadata),'EXTENSION_RULE_MISSING')
        for key,value in metadata.items():
            require(key.startswith(spec['rulePrefix']) and value['mode'] in ('action','calculation') and value['public'] and value['kp']
                and value['inputs']=={'actor':'actor'},'EXTENSION_RULE_INTERFACE')


def assess_extensions(pack, state, baseline, artifact, changes, account):
    spec=getattr(pack,'extension_validation',None)
    if not spec:return None
    # This exception to global instance coverage is limited to explicit NPC rules.
    require(changes['data']==baseline['data'],'EXTENSION_DATA_FORBIDDEN')
    changed=[]
    for name,text in changes['sources'].items():
        if baseline['sources'].get(name)!=text:changed.extend(execute({name:text},{'kind':'inspect'})['metadata'])
    require(len(changed)<=8,'EXTENSION_RULE_LIMIT')
    require(all(k.startswith(spec['rulePrefix']) for k in changed),'EXTENSION_FORBIDDEN')
    configurations=copy.deepcopy(state['configurations'])
    for delta in changes['configurations']:configurations[delta['id']]=delta['value']
    configuration_checks(pack,{'configurations':configurations},baseline,artifact,changes)
    validator=local_schema(pack.json(spec['defaultsSchema']));fixture=pack.json(spec['fixtureRef'])
    targets=[(key,value) for key,value in configurations.items() if key==spec['baseConfiguration'] or key.startswith(spec['namespace'])]
    require(len(targets)<=32,'EXTENSION_TEMPLATE_LIMIT')
    comparisons=[];probes=[]
    for key,value in targets:
        before=state['configurations'].get(key,state['configurations'][spec['baseConfiguration']])['defaults']
        comparisons.append({'configurationId':key,'baseline':before,'candidate':value['defaults'],
            'deltas':{k:v-before.get(k,0) for k,v in value['defaults'].items() if v!=before.get(k,0)}})
        sample=copy.deepcopy(fixture);sample['instances'][0]['configurationId']=key
        probes.append(('template:'+key,fixture_state(sample,configurations),sample['instances'][0]['instanceId'],fixture['accounts'][0]['accountId']))
    for key,value in state['entities'].items():
        if value['lifecycle']=='active' and (value['configurationId']==spec['baseConfiguration'] or value['configurationId'].startswith(spec['namespace'])):
            probes.append(('existing:'+key,state,key,account))
    require(len(probes)<=64,'EXTENSION_INSTANCE_LIMIT')
    evidence=[]
    for rule in changed:
        for label,world,actor,principal in probes:
            scenario={'account':principal,'steps':[{'rule':rule,'input':{'actor':actor}}], 'randomPolicy':{'mode':'fixed','sides':20}}
            variants=[('candidate',artifact)]+([('baseline',baseline)] if rule in baseline['metadata'] else [])
            for variant,rules in variants:
                trials=run_scenario(rules,world,scenario,[[n]*64 for n in (1,10,20)])
                for trial in trials:
                    step=trial['steps'][0];require(step['ok'],'EXTENSION_SCENARIO_FAILED')
                    numbers=copy.deepcopy(world['entities'][actor]['numbers'])
                    for effect in step['effects']:
                        require(effect['type']=='number' and effect['id']==actor,'EXTENSION_EFFECT_FORBIDDEN')
                        numbers[effect['key']]=effect['value']
                    require(validator.is_valid(numbers),'EXTENSION_EFFECT_RANGE')
                evidence.append({'rule':rule,'target':label,'variant':variant,'trials':trials})
    return {'templateComparisons':comparisons,'ruleProbes':evidence,'changedRules':changed,
        'existingInstancesPreserved':True,'limitations':['Only explicit NPC-family inputs are covered','d20 probes use 1, 10 and 20; not exhaustive probabilities','Package discoveries, dialogue and scene side effects are outside this transaction']}
