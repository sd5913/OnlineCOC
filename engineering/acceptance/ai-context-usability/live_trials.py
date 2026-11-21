"""Paired synthetic-room scenarios; real model, unchanged local provider config."""
import argparse,asyncio,copy,json,sys,time
from pathlib import Path
from types import SimpleNamespace
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
parser=argparse.ArgumentParser();parser.add_argument('--tree',required=True);parser.add_argument('--mode',required=True);parser.add_argument('--case');parser.add_argument('--bonus',type=int,default=15);args=parser.parse_args()
tree=Path(args.tree);eng=tree/'engineering'
sys.path[:0]=[str(eng/'ai/src'),str(eng/'backend/src'),str(eng/'data-management'),str(eng/'ai/tests')]
from test_coordinator import setup,wait_task
from test_entrypoints import command,committed
from test_sessions import submit
from test_context import enable
from onlinecoc_ai.api import Application
from onlinecoc_ai.coordinator import Coordinator
from onlinecoc_ai.context import Context
from onlinecoc_ai.profiles import load_profiles
from onlinecoc_ai.answers import parse_answer
from onlinecoc_ai.local_lock import file_lock
from bounded_provider import BoundedProvider,save

GOAL=f'修改 fixture.token 道具配置模板：默认 bonus 设为{args.bonus}，修订从1改为2，其他字段、规则和现有实例保持不变。请准备草稿。'
CASES=[('single-request',[],GOAL),('older-parameters',[GOAL,'该需求已经确定；仅准备候选，之后由我审核。','说明简短即可。','不需要修改描述文案。','请保留原有规则实现。','不要另增其他道具。'],'按前面确定的参数，准备配置草稿。'),('genuine-choice',[],'给 player1 的角色加1点。')]


async def run_case(profile,folder,identifier,history,text):
    fixture=setup.__wrapped__(folder);host,proposals,_=next(fixture)
    app=Application(SimpleNamespace(proposals=proposals,coordinator=Coordinator(proposals,{profile['profileId']:profile},context=Context(proposals,demand=True))))
    enable(host,public=True,kp=True,private=True)
    providers=[];row={'mode':args.mode,'caseId':identifier,'status':'running','historyRequests':history,'request':text};start=time.monotonic()
    before=copy.deepcopy(host.state()['configurations'])
    try:
        sid=committed(command(app,'ai.session.create',{'title':'上下文真实模型对照'}))['sessionId']
        for prior in history:submit(app,sid,prior)
        def factory(p):
            provider=BoundedProvider(p,args.mode,identifier,'context-usability');providers.append(provider);return provider
        app.coordinator.provider_factory=factory;await app.coordinator.start()
        request=submit(app,sid,text);task=committed(command(app,'ai.request.dispatch',{'requestId':request['requestId']}))
        result=await wait_task(app.coordinator,task['taskId'],timeout=310);row['task']=result
        assert host.state()['configurations']==before,'generation changed live templates'
        calls=[a for a in json.loads((HERE/'live-ledger.json').read_text(encoding='utf-8'))['attempts'] if a['stage']==args.mode and a['caseId']==identifier]
        outputs=[]
        for call in calls:
            message=call.get('output',{})
            if message.get('content') and not message.get('tool_calls'):
                try:outputs.append(parse_answer(message['content']))
                except Exception:pass
        row['modelCalls']=len(calls);row['unnecessaryClarifications']=sum(o['kind']=='clarification' or bool(o.get('choices')) for o in outputs) if identifier!='genuine-choice' else 0
        row['tokens']=sum(c.get('chargedTokens',c['reservedTokens']) for c in calls)
        def correct(output):
            if identifier=='genuine-choice':return output['kind']=='clarification' or bool(output.get('choices'))
            changes=output.get('changeSet',{}).get('configurations',[])
            return output['kind']=='draft' and len(changes)==1 and changes[0]['kind']=='replace' and changes[0]['id']=='fixture.token' and changes[0]['expectedRevision']=='1' and changes[0]['value']['revision']=='2' and changes[0]['value']['defaults']['bonus']==args.bonus
        row['firstUsable']=bool(outputs and correct(outputs[0]));row['status']='passed' if outputs and correct(outputs[-1]) and result['status'] in ('needs_input','review_ready') else 'failed'
        if row['status']=='passed' and identifier!='genuine-choice':
            item=next(i for i in app.rulings.list('kp')['items'] if i['rulingId']=='proposal:'+result['proposalId'])
            expected=copy.deepcopy(before);expected['fixture.token']['revision']='2';expected['fixture.token']['defaults']['bonus']=args.bonus
            changes=item['changeSet']['configurations'];assert changes[0]['value']==expected['fixture.token']
            approval={'rulingId':item['rulingId'],'digest':item['digest'],'decision':'approve','riskDecisions':{r['id']:'合成验收接受该项风险' for r in item['risks']}}
            if item.get('highRisk'):approval['explicitHighRiskDigest']=item['digest']
            if item.get('cAssessment',{}).get('requiresAcceptance'):approval['cReview']={k:item['cAssessment'][k] for k in ('basisRevision','basisDigest','reportDigest')}
            receipt=committed(command(app,'ai.ruling.decide',approval));assert receipt['status']=='completed' and host.state()['configurations']==expected
            row['actualExecution']=True
        if row['status']=='failed':row['code']=result.get('error','OUTPUT_NOT_USABLE')
    except Exception as exc:row.update(status='failed',code=getattr(exc,'code',type(exc).__name__),reason=str(exc)[:300])
    finally:
        row['seconds']=round(time.monotonic()-start,2);await app.coordinator.close()
        try:next(fixture)
        except StopIteration:pass
    return row


async def main():
    path=ROOT/'engineering/ai/config/ai-providers.json';original=path.read_bytes();profile=copy.deepcopy(load_profiles(path)['deepseek-main'])
    profile['request']['maxOutputTokens']=2200;profile['limits'].update(maxRepairAttempts=2,maxTransportRetries=0,maxToolRounds=4,taskTimeoutMs=300000)
    run_id=str(time.time_ns());work=HERE/'work'/('live-'+args.mode+'-'+run_id);work.mkdir(parents=True)
    rows=[];output=HERE/('live-'+args.mode+'-'+run_id+'.json')
    for identifier,history,text in CASES:
        if args.case and identifier!=args.case:continue
        row=await run_case(profile,work/identifier,identifier,history,text);rows.append(row)
        save(output,{'tree':str(tree),'mode':args.mode,'cases':rows,'sourceConfigUnchanged':path.read_bytes()==original})
        print(json.dumps({k:row.get(k) for k in ('caseId','status','code','firstUsable','unnecessaryClarifications','modelCalls','tokens','actualExecution')},ensure_ascii=False),flush=True)
        if row.get('code')=='EXPERIMENT_BUDGET_EXCEEDED':break
    assert path.read_bytes()==original

if __name__=='__main__':
    with file_lock(HERE/'work/external-single-writer'):asyncio.run(main())
