"""Actual Coordinator + strict author pack + real API, isolated Host only.

Fault injections are explicit provider-boundary experiments. Original HTTP
responses remain in the ledger; injected responses are recorded separately.
Neither expected actions nor controlled dice enter model messages.
"""
import argparse
import asyncio
import copy
import importlib.util
import json
import time
import traceback
from pathlib import Path
from valid_cases import HERE,ROOT,MATRIX,application,close,session,submit,command,committed,Context,digest,stage
from bounded_provider import BoundedProvider,save
from onlinecoc_ai.local_lock import file_lock
from onlinecoc_ai.profiles import load_profiles
from onlinecoc_ai.providers.base import Completion
from onlinecoc_ai.reliability import business_unsuccessful
from test_coordinator import wait_task


CASES=[
    {'id':'slot-natural','kind':'runtime','slot':5,'text':'让 player1 的唯一角色消耗一格口粮用量。按当前背包定位，保持其他物品和属性不变，并通知该玩家。准备待审核批次。'},
    {'id':'slot-moved-fault','kind':'runtime','slot':7,'fault':'slot','text':'让 player1 的唯一角色消耗一格口粮用量。按当前背包定位，保持其他物品和属性不变，并通知该玩家。准备待审核批次。'},
    {'id':'config-add-tool-fault','kind':'configuration','fault':'tool','text':'新增 NPC 配置 sv.ext.npc.reliability，完整沿用当前 sv.npc 的类型与全部默认值，仅把默认 hp 和 maxHp 都改成5；配置修订为1，不改任何现存实例。请直接准备配置草稿。'},
    {'id':'config-replace','kind':'configuration','text':'将当前 sv.npc 配置默认 hp 和 maxHp 都改成5，修订从1升为2，其余字段全部保留，不修改现存实例。请直接准备配置草稿。'},
    {'id':'config-remove','kind':'configuration','text':'删除未被任何实例引用的 sv.item.reliability 配置，当前修订1；保留其他配置。直接准备删除草稿，后续由我独立审核。'},
    {'id':'data-append','kind':'data','text':'在 game.json 的 items 数组末尾新增一种物品：id=reliability-ration，名称=试验口粮，kind=item，占1槽，uses=3，description=隔离验收用口粮。只追加这一项，保留其他物品、数组顺序以及所有无关字段。使用局部数据编辑准备草稿。'},
    {'id':'ambiguous-business','kind':'clarification','text':'给 player1 的唯一角色加1点。'}]


def business(host):
    state=host.state()
    return {k:copy.deepcopy(state[k]) for k in ('entities','relations','configurations','activeRuleset','artifacts','progress','members','chat','outbox')}


class FaultProvider:
    def __init__(self,profile,case,row):
        self.inner=BoundedProvider(profile,case.get('stage','coordinator-v1'),case['id'],case['kind']);self.case,self.row=case,row;self.injected=False
    async def complete(self,messages,tools):
        result=await self.inner.complete(messages,tools)
        if self.injected or not self.case.get('fault'):return result
        value=copy.deepcopy(result.message);changed=False
        if self.case['fault']=='tool' and value.get('tool_calls'):
            call=value['tool_calls'][0];args=json.loads(call['function']['arguments']);args['unexpectedAcceptanceField']=True
            call['function']['arguments']=json.dumps(args);changed=True
        elif self.case['fault']=='slot' and value.get('content'):
            try:answer=json.loads(value['content'])
            except ValueError:return result
            for action in answer.get('actions',[]):
                if action.get('op')=='action.invoke' and action.get('args',{}).get('actionId')=='sv.inventory':
                    action['args']['input']['slot']=3;changed=True
            if changed:value['content']=json.dumps(answer,ensure_ascii=False)
        if not changed:return result
        self.injected=True;self.row['injectedFault']={'kind':self.case['fault'],'afterAttempt':self.inner.calls[-1],'deliveredMessage':value}
        return Completion(value,result.usage,result.finish_reason,digest(value),result.model)
    async def close(self):await self.inner.close()


def setup_case(folder,pack,case):
    app=application(folder,pack)
    if case['kind'] in ('runtime','clarification'):
        document=json.loads((MATRIX/'cases.json').read_text(encoding='utf-8'))
        row=next(c for c in document['cases'] if c['category']=='positive' and c['actionId']=='sv.inventory')
        spec=importlib.util.spec_from_file_location('engine_matrix_fixture',MATRIX/'run_matrix.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        artifact=stage(app.proposals.pack.sources,app.proposals.pack.data)
        module.fixture(app.host,row,app.proposals.pack.configurations,artifact)
        state=app.host.state();numbers=state['entities']['actor']['numbers'];numbers.update(item3=6,uses3=0)
        slot=case.get('slot',5)
        if slot!=5:numbers.update(item5=0,uses5=0);numbers.update({f'item{slot}':3,f'uses{slot}':3})
        app.host.commit(state)
    if case['id']=='config-remove':
        state=app.host.state();state['configurations']['sv.item.reliability']={'configurationId':'sv.item.reliability','revision':'1','typeRef':'item','defaults':{'uses':3}};app.host.commit(state)
    app.coordinator.context=Context(app.proposals,demand=True)
    return app


def approve(app,item,cid):
    args={'rulingId':item['rulingId'],'digest':item['digest'],'decision':'approve'}
    if item.get('highRisk'):args['explicitHighRiskDigest']=item['digest']
    if item.get('risks'):args['riskDecisions']={r['id']:'Isolated acceptance explicitly accepts this recorded risk.' for r in item['risks']}
    first=command(app,'ai.ruling.decide',args,identifier=cid);after=business(app.host)
    second=command(app,'ai.ruling.decide',args,identifier=cid)
    assert second==first and business(app.host)==after,'Repeated approval changed state'
    return first


def verify_configuration(case,before,after):
    expected=copy.deepcopy(before['configurations'])
    if case['id']=='config-add-tool-fault':
        value=copy.deepcopy(expected['sv.npc']);value.update(configurationId='sv.ext.npc.reliability',revision='1');value['defaults'].update(hp=5,maxHp=5);expected[value['configurationId']]=value
    elif case['id']=='config-replace':expected['sv.npc']['revision']='2';expected['sv.npc']['defaults'].update(hp=5,maxHp=5)
    elif case['id']=='config-remove':del expected['sv.item.reliability']
    assert after['configurations']==expected,'Configuration changed outside the stated intent'
    assert after['entities']==before['entities'] and after['relations']==before['relations'],'Instance migration'
    old=before['artifacts'][before['activeRuleset']];new=after['artifacts'][after['activeRuleset']]
    if case['kind']=='data':
        data=copy.deepcopy(old['data']);data['game.json']['items'].append({'id':'reliability-ration','name':'试验口粮','kind':'item','slots':1,'uses':3,'description':'隔离验收用口粮'})
        assert new['data']==data and new['sources']==old['sources'],'Unrelated data or rule changed'
    else:assert new['sources']==old['sources'] and new['data']==old['data'],'Unexpected rule/data change'


async def run_case(case,folder,pack,profile):
    row={'caseId':case['id'],'category':case['kind'],'faultInjection':case.get('fault'),'status':'running'};app=None
    try:
        app=setup_case(folder,pack,case);before=business(app.host);row['before']=before
        app.coordinator.profiles={profile['profileId']:copy.deepcopy(profile)}
        providers=[]
        def factory(p):
            value=FaultProvider(p,case,row);providers.append(value);return value
        app.coordinator.provider_factory=factory
        await app.coordinator.start()
        s=session(app);r=submit(app,s,case['text']);dispatched=committed(command(app,'ai.request.dispatch',{'requestId':r['requestId']}))
        task=await wait_task(app.coordinator,dispatched['taskId'],timeout=280);row['task']=task
        row['attemptIds']=[n for p in providers for n in p.inner.calls]
        row['beforeApprovalUnchanged']=business(app.host)==before
        assert row['beforeApprovalUnchanged'],'Model generation changed business state'
        if case['kind']=='clarification':
            assert task['status']=='needs_input' and not task.get('batchId') and not task.get('proposalId')
            row.update(status='passed',clarification=task['text']);return row
        if task['status']!='review_ready':row.update(status='failed',reason=task.get('error') or task['status']);return row
        if case.get('fault'):assert row.get('injectedFault'),'No requested fault was injected'
        if case['kind']=='runtime':
            batch=app.repository.state()['settings']['batches'][task['batchId']];row['candidate']=batch
            actions=batch['actions'];inventory=[a for a in actions if a['op']=='action.invoke']
            assert len(inventory)==1 and inventory[0]['args']=={'actionId':'sv.inventory','input':{'actor':'actor','operation':'use','slot':case['slot'],'value':1}},'Wrong target, slot, cost or effect'
            assert len(actions)==2 and actions[1]['op']=='notification.send' and actions[1]['args']['recipientAccountIds']==['player1'] and actions[1]['args']['sourceActionIndex']==0
            rid='batch:'+batch['batchId']
        else:
            proposal=app.proposals.get('kp',task['proposalId']);row['candidate']=proposal
            row['reports']=[app.repository.state()['reports'][ref] for ref in proposal['reportRefs']]
            assert all(r['status']=='pass' for r in row['reports'])
            rid='proposal:'+proposal['proposalId']
        item=next(i for i in app.rulings.list('kp')['items'] if i['rulingId']==rid)
        row['approvalReceipt']=approve(app,item,'e2e-approve:'+case['id']);result=committed(row['approvalReceipt']);assert result['status']=='completed',result
        after=business(app.host);row['after']=after;row['idempotentReplay']=True
        if case['kind']=='runtime':
            expected=copy.deepcopy(before['entities']);expected['actor']['numbers'][f'uses{case["slot"]}']-=1;expected['actor']['revision']+=1
            assert after['entities']==expected,'Unexpected inventory/HP change'
            assert not business_unsuccessful(result.get('execution',{}))
        else:verify_configuration(case,before,after)
        row.update(status='passed')
    except Exception as exc:row.update(status='failed',code=getattr(exc,'code',type(exc).__name__),reason=str(exc),traceback=traceback.format_exc())
    finally:
        if app:
            row['durableTaskCount']=len(app.repository.state()['tasks']);await app.coordinator.close();close(app)
    return row


async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',action='store_true');parser.add_argument('--cases',nargs='*');parser.add_argument('--pack-v2',action='store_true');args=parser.parse_args()
    profilepath=ROOT/'engineering/ai/config/ai-providers.json';original=profilepath.read_bytes();profile=copy.deepcopy(load_profiles(profilepath)['deepseek-main'])
    profile['limits'].update(maxRepairAttempts=2,maxTransportRetries=2,maxToolRounds=5,taskTimeoutMs=300000)
    profile['request']['maxOutputTokens']=3000
    manifest=json.loads((HERE/'valid-input-source.json').read_text(encoding='utf-8'));pack=Path(manifest['strictPack'])
    if args.pack_v2:pack=HERE/'work/strict-real-pack-v2/integrations/ai-pack-6e53556afda3b5f63824'
    run_id=str(time.time_ns());work=HERE/'work'/('coordinator-'+run_id);work.mkdir(parents=True)
    rows=[];path=HERE/('coordinator-'+run_id+'.json')
    for case in CASES:
        if args.cases and case['id'] not in args.cases:continue
        if args.pack_v2:
            case=copy.deepcopy(case);case['stage']='coordinator-v2'
            if case['id']=='slot-moved-fault':case['id']='slot-moved-natural';case.pop('fault',None)
        if not args.run:
            app=setup_case(work/case['id'],pack,case);print(case['id'],len(app.host.state()['entities']),app.proposals.pack.digest);close(app);continue
        row=await run_case(case,work/case['id'],pack,profile);rows.append(row)
        save(path,{'runId':run_id,'realProvider':True,'strictPack':str(pack),'cases':rows,'sourceConfigUnchanged':profilepath.read_bytes()==original})
        print(json.dumps({k:row.get(k) for k in ('caseId','status','code','reason','attemptIds')},ensure_ascii=False),flush=True)
        if any(a.get('code')=='EXPERIMENT_BUDGET_EXCEEDED' for a in [row,row.get('task',{}).get('error',{})] if isinstance(a,dict)):break
    assert profilepath.read_bytes()==original


if __name__=='__main__':
    with file_lock(HERE/'live-ledger.json'):asyncio.run(main())
