"""Public HTTP acceptance: checked NPC templates/rules, one KP ruling and restart recovery."""
import copy,json,secrets
from datetime import datetime
from harness import PACK,running,provision,Account
from integrations import write_json
from verify_integrations import provider,ai,result

def main():
    output=PACK/'tests/output'/('ai-extensions-'+secrets.token_hex(4));output.mkdir(parents=True);checks=[]
    with provider(output,lambda r:{'role':'assistant','content':json.dumps({'kind':'plan','text':'离线验收'})}) as (config,calls):
        with running('ai-extensions',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
            kp,p1,p2=provision(runtime,password)
            baseline=kp.request('/api/v1/admin')['configurations']['sv.npc']
            value=copy.deepcopy(baseline);value.update(configurationId='sv.ext.npc.guide',revision='1');value['defaults'].update(hp=6,maxHp=6,isNpc=1)
            source="""return rule('sv.ext.heal', {'actor'}, function(r, actor)
              r.set(actor, 'hp', math.min(r.number(actor, 'maxHp'), r.number(actor, 'hp') + 1))
              return r.number(actor, 'hp')
            end, {kp=true})"""
            calculation="""return rule('sv.ext.score', {'actor'}, function(r, actor)
              return r.number(actor, 'str') + r.number(actor, 'wil')
            end, {mode='calculation',kp=true})"""
            delta={'schemaVersion':1,'configurations':[{'kind':'add','id':value['configurationId'],'expectedRevision':None,'value':value}],
                'sources':{'npc-extension.lua':source,'npc-score.lua':calculation},'data':{},'suggestions':[]}
            proposal=result(ai(kp,'ai.draft.create',{'text':'新增庭院向导模板和动作／计算规则','changeSet':delta}))
            checked=result(ai(kp,'ai.proposal.validate',{'proposalId':proposal['proposalId'],'revision':1}))
            assert checked['proposal']['status']=='review_ready',[(r['level'],r['status'],r['findings']) for r in checked['reports']]
            assert [r['level'] for r in checked['reports']]==['A','B','C'];checks.append('A/B/C validate a new NPC template, action and calculation with actual existing NPC sandbox coverage')
            item=next(i for i in kp.request('/api/v1/ai/rulings')['items'] if i['rulingId']=='proposal:'+proposal['proposalId'])
            assert item['status']=='pending' and len(item['changeSet']['configurations'])==1
            assert p1.request('/api/v1/ai/rulings',allow_error=True)['code']=='PERMISSION_DENIED'
            decision={'rulingId':item['rulingId'],'digest':item['digest'],'decision':'approve','riskDecisions':{r['id']:'验收接受该风险与覆盖限制' for r in item['risks']}}
            if item.get('highRisk'):decision['explicitHighRiskDigest']=item['digest']
            assert result(ai(kp,'ai.ruling.decide',decision))['status']=='completed'
            assert result(ai(kp,'ai.ruling.decide',decision))['status']=='completed'
            checks.append('one whole configuration ruling publishes atomically; repeated approval is idempotent; PL cannot access the queue')
            entity=result(kp.command('entity.create',{'configurationId':value['configurationId'],'name':'庭院向导','owner':'kp','visibility':'kp','numbers':{'location':3,'hp':4}}))
            assert result(kp.command('action.invoke',{'actionId':'sv.ext.heal','input':{'actor':entity}}))==5
            assert kp.request('/api/v1/preview',{'rule':'sv.ext.score','input':{'actor':entity}})['result']==20
            state=kp.state();assert any(n['instanceId']==entity for n in state['npcs'])
            assert runtime.package.state['activeRevision']==kp.request('/api/v1/view')['catalog']['rulesetRevision']
            kp.action('morale',{'actor':entity})
            checks.append('published action/calculation execute; extension NPC appears in KP roster and existing morale operation; package active revision follows host')
            invalid=copy.deepcopy(delta);invalid['configurations'][0]['id']='sv.ext.npc.bad';invalid['configurations'][0]['value']['configurationId']='sv.ext.npc.bad';invalid['configurations'][0]['value']['defaults']['hp']=999;invalid['sources']={}
            bad=result(ai(kp,'ai.draft.create',{'text':'越界字段','changeSet':invalid}));blocked=result(ai(kp,'ai.proposal.validate',{'proposalId':bad['proposalId'],'revision':1}))
            assert blocked['proposal']['status']=='blocked';checks.append('out-of-range extension defaults cannot enter approval-ready state')
            revised=copy.deepcopy(value);revised['revision']='2';revised['defaults']['armor']=1
            access=kp.request('/api/v1/ai/access');result(ai(kp,'ai.access.update',{'revision':access['revision'],'allowPlayerChat':False,'autoApproveBatches':False,'autoApproveConfigurations':True}))
            auto=result(ai(kp,'ai.draft.create',{'text':'自动通过模板修订','changeSet':{'schemaVersion':1,'configurations':[{'kind':'replace','id':value['configurationId'],'expectedRevision':'1','value':revised}],'sources':{},'data':{},'suggestions':[]}}))
            # Extension-owned existing IDs are admitted under the same namespace.
            auto_checked=result(ai(kp,'ai.proposal.validate',{'proposalId':auto['proposalId'],'revision':1}))
            assert auto_checked['proposal']['status']=='review_ready',auto_checked
            assert any(i['rulingId']=='proposal:'+auto['proposalId'] and i['status']=='completed' for i in kp.request('/api/v1/ai/rulings')['items'])
            assert kp.request('/api/v1/view')['entities'][entity]['numbers']['armor']==0
            checks.append('separate automatic configuration policy publishes only after A/B/C; existing instance values are preserved')
        with running('ai-extension-restart',data=output/'game',ai_config=config,no_browser=True) as (runtime,_):
            kp=Account(runtime.origin,'kp',password,'restart');state=kp.state()
            assert any(n['name']=='庭院向导' for n in state['npcs'])
            assert 'npc-extension.lua' in kp.request('/package/bundle')['sources']
            checks.append('restart reconciles authoritative published rules and keeps extension NPCs and package export content')
        assert not calls
    record={'checkedAt':datetime.now().astimezone().isoformat(),'passed':len(checks),'checks':checks,'provider':'no model calls; isolated public HTTP','realSaveChanged':False}
    write_json(PACK/'tests/ai-extensions-results.json',record);print(json.dumps(record,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
