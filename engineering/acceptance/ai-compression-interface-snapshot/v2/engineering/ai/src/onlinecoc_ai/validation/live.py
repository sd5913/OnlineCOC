"""Author-declared probes instantiated with actual room entity IDs, without writes."""
from ..errors import require, AiError
from ..sandbox import run_scenario, execute, author_private_rules
from ..pack import apply_configurations


def assess_live(pack, state, baseline, artifact, changes, account, *, additional=None):
    path=pack.contract['contextMapping'].get('liveScenarios')
    if not path and not additional:return None
    declarations=pack.json(path) if path else []
    if additional:declarations=declarations+additional
    require(isinstance(declarations,list) and declarations, 'LIVE_SCENARIO_POLICY_INVALID')
    changed_data={n for n,v in changes['data'].items() if baseline['data'].get(n)!=v}
    sources={n:t for n,t in changes['sources'].items() if baseline['sources'].get(n)!=t}
    changed_rules=set(execute(sources,{'kind':'inspect'})['metadata']) if sources else set()
    covered_data,covered_rules=set(),set();evidence=[]
    candidate=apply_configurations(state,changes)
    for declaration in declarations:
        required={'configurationId','rule','actorInput','input','coversData','coversRules'}
        require(isinstance(declaration,dict) and required<=set(declaration)<=required|{'expectedErrors','randomSides'}, 'LIVE_SCENARIO_POLICY_INVALID')
        require(all(isinstance(declaration[k],str) and declaration[k] for k in ('configurationId','rule','actorInput')) and isinstance(declaration['input'],dict), 'LIVE_SCENARIO_POLICY_INVALID')
        require(all(isinstance(declaration[k],list) and all(isinstance(v,str) for v in declaration[k]) for k in ('coversData','coversRules')), 'LIVE_SCENARIO_POLICY_INVALID')
        expected=declaration.get('expectedErrors',[])
        require(isinstance(expected,list) and all(isinstance(v,str) and v and v!='*' for v in expected), 'LIVE_SCENARIO_POLICY_INVALID')
        sides=declaration.get('randomSides',20)
        require(type(sides) is int and 2<=sides<=10000, 'LIVE_SCENARIO_POLICY_INVALID')
        rolls=sorted({1,max(1,sides//2),sides})
        rule=declaration['rule']
        require(all(r==rule for r in declaration['coversRules']), 'LIVE_SCENARIO_POLICY_INVALID')
        if not (changed_data.intersection(declaration['coversData']) or changed_rules.intersection(declaration['coversRules'])):
            evidence.append({'configurationId':declaration['configurationId'],'rule':rule,'status':'skipped-unaffected'})
            continue
        require(rule in baseline['metadata'] and rule in artifact['metadata'], 'LIVE_SCENARIO_RULE_MISSING')
        ids=[key for key,value in state['entities'].items() if value['configurationId']==declaration['configurationId'] and value['lifecycle']=='active']
        trials=[]
        for identifier in ids:
            scenario={'account':account,'steps':[{'rule':rule,'input':{**declaration['input'],declaration['actorInput']:identifier}}], 'randomPolicy':{'mode':'fixed','sides':sides}}
            variants=[]
            for variant,world,rules in (('baseline',state,baseline),('candidate',candidate,artifact)):
                results=run_scenario(rules,world,scenario,[[n]*64 for n in rolls],private_rule_ids=author_private_rules(rules,scenario))
                variants.append(results)
                trials.append({'entityId':identifier,'variant':variant,'results':results})
            for before,after in zip(*variants):
                require(len(before['steps'])==len(after['steps'])==1,'LIVE_SCENARIO_FAILED')
                a,b=before['steps'][0],after['steps'][0]
                blocked=not a['ok'] and not b['ok'] and a.get('code')==b.get('code') and a.get('code') in expected
                if not (a['ok'] and b['ok'] or blocked):
                    error=AiError('LIVE_SCENARIO_FAILED', 'baseline='+str(a.get('code','ok'))+'; candidate='+str(b.get('code','ok')), '/live/'+identifier+'/'+rule)
                    error.evidence={'entityId':identifier,'rule':rule,'baseline':a,'candidate':b,'completedScenarios':evidence}
                    raise error
                if blocked:trials.append({'entityId':identifier,'status':'blocked-compatible','code':a['code']})
        covered_data.update(declaration['coversData']);covered_rules.update(declaration['coversRules'])
        evidence.append({'configurationId':declaration['configurationId'],'rule':rule,'matched':len(ids),'randomSides':sides,'fixedRolls':rolls,'trials':trials})
    if not (changed_data<=covered_data and changed_rules<=covered_rules):
        error=AiError('LIVE_SCENARIO_COVERAGE_MISSING',
            'Missing data: '+','.join(sorted(changed_data-covered_data))+'; rules: '+','.join(sorted(changed_rules-covered_rules)))
        error.evidence={'missingData':sorted(changed_data-covered_data),'missingRules':sorted(changed_rules-covered_rules),
            'coveredData':sorted(covered_data),'coveredRules':sorted(covered_rules),'scenarios':evidence}
        raise error
    return {'scenarios':evidence,'coveredData':sorted(changed_data),'coveredRules':sorted(changed_rules),
        'limitations':['Declared compatibility probes, not exhaustive gameplay or narrative coverage','Existing values are preserved; no live command is executed','Each declaration uses fixed low/mid/high rolls of its stated die (default d20); zero matching entities means no live samples']}
