"""One opt-in DeepSeek task in an isolated host. No official room writes."""
import argparse
import asyncio
import copy
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'engineering/ai/tests'),str(ROOT/'engineering/ai/src'),str(ROOT/'engineering/backend/src'),str(ROOT/'engineering/data-management')]
from onlinecoc_ai.api import Application
from onlinecoc_ai.coordinator import Coordinator,SYSTEM,TOOLS,ADMIN_TOOLS
from onlinecoc_ai.context import Context
from onlinecoc_ai.contracts import canonical,digest
from onlinecoc_ai.profiles import DEFAULT_PATH,load_profiles
from onlinecoc_ai.providers import create_provider
from onlinecoc_ai.providers.base import ProviderError
from test_coordinator import setup,wait_task
from test_entrypoints import command,committed
from test_access_batches import session,submit
from test_context import enable,add_message

HERE=Path(__file__).parent


async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',action='store_true');parser.add_argument('--budget',type=int,default=20000);args=parser.parse_args()
    original=DEFAULT_PATH.read_bytes();profile=copy.deepcopy(load_profiles()['deepseek-main'])
    profile['limits'].update(maxToolRounds=2,maxRepairAttempts=1,maxTransportRetries=0,taskTimeoutMs=180000,dailyTokenBudget=args.budget)
    profile['request']['maxOutputTokens']=1500
    report={'limits':{'providerCalls':4,'repairAttempts':1,'reservedOrUsedBudget':args.budget},'realCalls':[],
        'formalDataChanged':False,'sourceConfigDigest':digest(original.hex()),'requestedModel':profile['model'],'status':'started'}
    output=HERE/('live-results.json' if args.run else 'live-preflight.json')
    def save():output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    directory=HERE/'work'/('live-'+str(time.time_ns()));directory.mkdir(parents=True)
    fixture=setup.__wrapped__(directory);host,proposals,_=next(fixture)
    coordinator=Coordinator(proposals,{profile['profileId']:profile},context=Context(proposals,demand=True))
    app=Application(SimpleNamespace(proposals=proposals,coordinator=coordinator));enable(host,public=True,kp=True,private=True)
    class Bounded:
        def __init__(self,p):self.provider=create_provider(p)
        async def complete(self,messages,tools):
            if len(report['realCalls'])>=4:raise ProviderError('EXPERIMENT_CALL_LIMIT')
            entry={'number':len(report['realCalls'])+1,'status':'started','reserved':len(canonical({'messages':messages,'tools':tools}))+1500};report['realCalls'].append(entry);save()
            start=time.perf_counter()
            try:
                pending=asyncio.create_task(self.provider.complete(messages,tools))
                if entry['number']==1:
                    await asyncio.sleep(.05)
                    add_message(host,'player1','隔离实验：发送后的无关聊天')
                    report['unrelatedChatInserted']=True
                    row=app.sessions.get('kp',s['sessionId'])['items'][0]
                    report['liveProgressVisible']=any(e['stage']=='provider_complete' and e['status']=='running' for e in row.get('events',[]))
                value=await pending
                entry.update(status='completed',usage=value.usage,returnedModel=value.model,seconds=round(time.perf_counter()-start,3))
                return value
            except Exception as exc:
                entry.update(status='failed',code=getattr(exc,'code',type(exc).__name__),seconds=round(time.perf_counter()-start,3));raise
            finally:save()
        async def close(self):await self.provider.close()
    try:
        s=session(app);request=submit(app,s,'请先读取房间配置模板，然后准备 fixture.token 的配置修改候选：仅将 defaults.bonus 从当前值改为15，修订号递增，保留其他字段。输出完整合法 draft，等我另行审核；不改实体，不直接执行。')
        task=committed(command(app,'ai.request.dispatch',{'requestId':request['requestId']}))
        frozen=coordinator.generations[task['taskId']]
        payload=copy.deepcopy(frozen.payload);payload.update(sessionAccess={'level':'administrator'},currentActor={'accountId':'kp','role':'kp','sessionLevel':'administrator'})
        report['preflightReserved']=len(canonical({'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':canonical(payload).decode()}],'tools':TOOLS+ADMIN_TOOLS}))+1500
        if not args.run:
            report['status']='budget-blocked' if report['preflightReserved']>args.budget else 'ready';save();return
        coordinator.provider_factory=Bounded;await coordinator.start()
        result=await wait_task(coordinator,task['taskId'],190)
        report.update(taskStatus=result['status'],error=result.get('error'),usageTokens=result['usage'],responseDigest=digest(result.get('text')),
            dependencyCheck=result.get('dependencyCheck'),stages=[e['stage'] for e in result.get('events',[])])
        if result.get('proposalId'):
            record=proposals.repository.state()['proposals'][result['proposalId']];p=record['revisions'][str(record['currentRevision'])]
            report['reports']=[{k:proposals.repository.state()['reports'][r][k] for k in ('level','status')} for r in p['reportRefs']]
        assert result['status']=='review_ready' and result.get('proposalId'),result.get('error') or result['status']
        assert result['dependencyCheck']['status']=='unchanged'
        item=next(i for i in app.rulings.list('kp')['items'] if i['rulingId']=='proposal:'+result['proposalId'])
        decision=committed(command(app,'ai.ruling.decide',{'rulingId':item['rulingId'],'digest':item['digest'],'decision':'approve',
            'explicitHighRiskDigest':item['digest'],'riskDecisions':{r['id']:'隔离验收接受该项风险' for r in item['risks']}}))
        assert decision['status']=='completed'
        assert host.state()['configurations']['fixture.token']['defaults']['bonus']==15
        report.update(status='passed',publishedInIsolatedRoom=True,publications=len(host.state()['aiControl']['publications']))
    except Exception as exc:report.update(status='failed',failureCode=getattr(exc,'code',type(exc).__name__))
    finally:
        await coordinator.close();fixture.close();report['sourceConfigUnchanged']=DEFAULT_PATH.read_bytes()==original;save()
        print(json.dumps({k:report.get(k) for k in ('status','preflightReserved','usageTokens','taskStatus','error','failureCode','sourceConfigUnchanged')},ensure_ascii=False))


if __name__=='__main__':asyncio.run(main())
