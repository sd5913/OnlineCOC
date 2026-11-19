"""Author-owned AI extension contract and finite B/C fixtures, copied into the companion."""
import copy

def materials(contract, configurations):
    npc=next(c for c in configurations if c['configurationId']=='sv.npc')
    bounds={'hp':(0,40),'maxHp':(1,40),'str':(1,20),'dex':(1,20),'wil':(1,20),
        'strMax':(1,20),'dexMax':(1,20),'wilMax':(1,20),'armor':(0,3),'location':(1,10),'incapacitated':(0,1),'lastRoll':(0,20)}
    schema={'type':'object','required':list(bounds),'maxProperties':32,
        'properties':{k:{'type':'integer','minimum':a,'maximum':b} for k,(a,b) in bounds.items()},
        'additionalProperties':{'type':'number','minimum':-100,'maximum':100}}
    schema['properties']['isNpc']={'const':1}
    contract['extensionPoints']=[{'namespace':'sv.ext.npc.','typeRefs':['actor'],'allowedPaths':['/defaults'],
        'allowExistingIds':['sv.npc'],'allowNamespaceReplace':True,'rulePrefixes':['sv.ext.']}]
    contract['contextMapping']['extensionValidation']='ai/extension-validation.json'
    contract['reviewPolicy']['items']=[{'id':'npc-extension-impact','question':'NPC 默认值、规则效果及未覆盖的剧情联动是否可接受？','required':True}]
    files={'ai/npc-defaults.schema.json':schema,'ai/extension-validation.json':{'namespace':'sv.ext.npc.','baseConfiguration':'sv.npc',
        'rulePrefix':'sv.ext.','defaultsSchema':'ai/npc-defaults.schema.json','fixtureRef':'ai/npc-world.json'}}
    files['ai/npc-world.json']={'accounts':[{'accountId':'kp','role':'kp'},{'accountId':'player1','role':'player'}],
        'instances':[{'instanceId':'ai-npc','configurationId':'sv.npc','owner':'kp','name':'验收 NPC','visibility':'public','numbers':{}}]}
    checks=[]
    for key,(minimum,maximum) in bounds.items():
        cid='npc-'+key;refs=[]
        for outcome,value in [('pass',npc['defaults'][key]),('fail',minimum-1)]:
            path='ai/cases/'+cid+'-'+outcome+'.json';refs.append(path)
            files[path]={'checkId':cid,'configurationId':'sv.npc','pointer':'/defaults/'+key,'value':value,'expected':outcome}
        checks.append({'checkId':cid,'sourceRef':'stumpsville-guide','selector':{'collection':'configurations','ids':['sv.npc']},
            'checkerId':'core.numeric-range@1','parameters':{'pointer':'/defaults/'+key,'minimum':minimum,'maximum':maximum},'required':True,'caseRefs':refs})
    files['ai/checks.json']=checks;contract['requiredChecks']=[c['checkId'] for c in checks]
    scenario={'schemaVersion':1,'scenarioId':'npc-morale','fixtureRef':'ai/npc-world.json','account':'kp',
        'steps':[{'rule':'sv.morale','input':{'actor':'ai-npc'}}],'randomPolicy':{'mode':'enumerate','sides':20,'samples':20,'seed':1},
        'maxSteps':1,'metricIds':['npc-morale-success']}
    denied=copy.deepcopy(scenario);denied.update(scenarioId='npc-player-denied',account='player1',metricIds=[])
    denied['randomPolicy'].update(mode='fixed',values=[1]);denied['steps'][0]['expectError']='PERMISSION_DENIED'
    files['ai/npc-morale.json']=scenario;files['ai/npc-player-denied.json']=denied
    contract['scenarios']=['ai/npc-morale.json','ai/npc-player-denied.json'];contract['requiredMetrics']=['npc-morale-success']
    files['ai/metrics.json']=[{'metricId':'npc-morale-success','calculatorId':'core.success-rate@1','parameters':{'pointer':'/result/passed','stepIndex':0},
        'unit':'probability','required':True,'threshold':{'absoluteDelta':0.1,'risk':'high'}}]
    return files
