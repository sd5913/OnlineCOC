"""Opt-in, bounded DeepSeek trials against isolated host/configuration copies."""
import asyncio
import copy
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'engineering/ai/tests'),str(ROOT/'engineering/ai/src'),
    str(ROOT/'engineering/backend/src'),str(ROOT/'engineering/data-management')]
from fastapi.testclient import TestClient
from onlinecoc.server import create_app
from onlinecoc_ai.api import Application
from onlinecoc_ai.coordinator import Coordinator
from onlinecoc_ai.context import Context
from onlinecoc_ai.contracts import canonical, digest
from onlinecoc_ai.profiles import load_profiles, DEFAULT_PATH
from onlinecoc_ai.providers import create_provider
from onlinecoc_ai.providers.base import ProviderError
from test_coordinator import setup, wait_task
from test_entrypoints import command, committed
from test_access_batches import session, submit, access
from test_known_runtime import install, observe, host_call
from test_context import enable

OUT=Path(__file__).parent
REPORT={'limits':{'providerCalls':16,'tokens':200000,'callsPerTask':4},'calls':[],'cases':[],
    'latency':[],'usageTokens':0,'reservedOrUsedTokens':0,'formalDataChanged':False}


def save():
    REPORT['providerCalls']=len(REPORT['calls'])
    (OUT/'live-results.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


class Bounded:
    def __init__(self, profile, client):
        self.provider=create_provider(profile);self.client=client;self.profile=profile;self.calls=0

    async def complete(self,messages,tools):
        reserve=len(canonical({'messages':messages,'tools':tools}))+self.profile['request']['maxOutputTokens']
        if self.calls>=4 or len(REPORT['calls'])>=16 or REPORT['reservedOrUsedTokens']+reserve>200000:
            raise ProviderError('EXPERIMENT_BUDGET_EXCEEDED')
        self.calls+=1;REPORT['reservedOrUsedTokens']+=reserve
        entry={'number':len(REPORT['calls'])+1,'requestedModel':self.profile['model'],'reserved':reserve,'status':'started'}
        REPORT['calls'].append(entry);save()
        def probe():
            for route in ('/api/v1/ai/tasks','/api/v1/ai/rulings','/api/v1/view'):
                start=time.perf_counter()
                try:
                    response=self.client.get(route)
                    REPORT['latency'].append({'providerCall':entry['number'],'route':route,'seconds':round(time.perf_counter()-start,4),'status':response.status_code})
                except Exception as exc:
                    REPORT['latency'].append({'providerCall':entry['number'],'route':route,'seconds':round(time.perf_counter()-start,4),'error':type(exc).__name__})
        probing=asyncio.create_task(asyncio.to_thread(probe));start=time.perf_counter()
        try:
            value=await self.provider.complete(messages,tools)
            total=value.usage['total_tokens'];REPORT['usageTokens']+=total;REPORT['reservedOrUsedTokens']+=total-reserve
            entry.update(status='completed',usage=value.usage,returnedModel=value.model,seconds=round(time.perf_counter()-start,3))
            return value
        except Exception as exc:
            entry.update(status='failed',code=getattr(exc,'code',type(exc).__name__),seconds=round(time.perf_counter()-start,3))
            raise
        finally:
            await probing;save()

    async def close(self):await self.provider.close()


async def run_case(name, callback, profile):
    case={'name':name,'status':'started','tasks':[]};REPORT['cases'].append(case);save()
    directory=OUT/'work'/('live-'+str(time.time_ns())+'-'+name);directory.mkdir(parents=True)
    fixture=setup.__wrapped__(directory);host,proposals,_=next(fixture)
    coordinator=Coordinator(proposals,{profile['profileId']:copy.deepcopy(profile)},context=Context(proposals))
    runtime=SimpleNamespace(proposals=proposals,coordinator=coordinator);app=Application(runtime);runtime.application=app
    async def idle():pass
    runtime.start=idle;runtime.close=idle
    async def wait(result):
        if not result.get('taskId'):
            result={**result,**committed(command(app,'ai.request.dispatch',{'requestId':result['requestId']}))}
        task=await wait_task(coordinator,result['taskId'],timeout=190)
        case['tasks'].append({'taskId':task['taskId'],'status':task['status'],'error':task.get('error'),
            'usage':task['usage'],'calls':len(task['calls']),'responseDigest':digest(task.get('text'))})
        save();return task
    try:
        with TestClient(create_app(host,ai_runtime=runtime),base_url='http://127.0.0.1:8765') as client:
            client.headers['origin']='http://127.0.0.1:8765'
            assert client.post('/api/v1/login',json={'loginName':'kp','password':'test-password'}).status_code==200
            coordinator.provider_factory=lambda p:Bounded(p,client)
            await coordinator.start()
            try:await callback(app,case,wait)
            finally:await coordinator.close()
        case['status']='passed'
    except Exception as exc:
        case.update(status='failed',error=getattr(exc,'code',type(exc).__name__))
    finally:
        fixture.close();save();print(json.dumps({'case':name,'status':case['status'],'error':case.get('error')},ensure_ascii=False),flush=True)


async def player_case(app,case,wait):
    install(app);grant=observe(app);s=session(app,'player1')
    result=submit(app,s,'请读取本人已知的角色身份，给出姓名与已知描述的资料引用。不要推测未知内容。',who='player1')
    task=await wait(result)
    assert task['status']=='review_ready' and '[[knowledge:' in task['text']
    before=app.sessions.get('player1',s['sessionId'],delivered=True)['items'][0]
    # Also exercise pre-fix final replies with no browser-read or publication ledger.
    def legacy(state):
        state['settings'].pop('messageDeliveries',None)
        state['tasks'][task['taskId']].pop('messagePublication')
        state['tasks'][task['taskId']].pop('responseAt')
    app.repository.update(legacy)
    host_call(app,'knowledge.revoke',{'grantId':grant['grantId'],'expectedRevision':1,'reason':'隔离实验撤回详情'})
    after=app.sessions.get('player1',s['sessionId'],delivered=True)['items'][0]
    assert before['response']==after['response'] and after['responseAt'] is None and after['historicalReadOnly']
    again=submit(app,s,'请重新查询我现在能访问的资料；没有匹配资料就明确说明，不使用此前已撤回资料。',who='player1')
    fresh=await wait(again)
    assert fresh['status'] in ('review_ready','needs_input') and '[[knowledge:' not in fresh['text']
    case.update(legacyRetained=True,revokedSourceNotReused=True,missingTimeNotInvented=True)


async def completion_case(app,case,wait):
    access(app);enable(app.host,public=True,private=True,kp=True);s=session(app)
    first=submit(app,s,'请查询实体 actor-one 的当前资料及 entity.patch 接口，准备把它的名称改为“实验向导甲”的运行批次。只改名称，等我批准后执行，不改配置。')
    old=await wait(first);assert old.get('batchId'),old['status']
    second=committed(command(app,'ai.session.submit',{'sessionId':s['sessionId'],'replyToRequestId':first['requestId'],
        'text':'继续同一改名需求，把目标名称确定为“实验向导乙”。重新核对 actor-one 的当前资料，准备只改名称的运行批次，等我批准。'}))
    new=await wait(second);assert new.get('batchId'),new['status']
    record=app.repository.state()['settings']['batches'][new['batchId']]
    receipt=committed(command(app,'ai.batch.approve',{'batchId':record['batchId'],'digest':record['digest']}))
    assert receipt['status']=='completed' and app.host.state()['entities']['actor-one']['name']=='实验向导乙'
    previous=app.queue.fields('batch:'+old['batchId'])
    assert previous['queueStatus']=='archived' and previous.get('resolution')
    independent=submit(app,s,'同一个角色的另一个独立需求：暂不处理，只记录。')
    assert app.queue.fields('request:'+independent['requestId'])['correlationId']!=previous['correlationId']
    case.update(explicitPredecessorArchived=True,independentGoalNotMerged=True,committedActions=len(receipt['receipts']))


async def main():
    initial=DEFAULT_PATH.read_bytes();profile=copy.deepcopy(load_profiles()['deepseek-main'])
    profile['limits'].update(maxToolRounds=4,maxRepairAttempts=1,maxTransportRetries=0,taskTimeoutMs=180000,dailyTokenBudget=200000)
    REPORT['model']=profile['model'];REPORT['sourceConfigDigest']=digest(initial.hex());save()
    for name,callback in (('published-player-history',player_case),('explicit-goal-completion',completion_case)):
        await run_case(name,callback,profile)
    REPORT['sourceConfigUnchanged']=DEFAULT_PATH.read_bytes()==initial
    REPORT['successes']=sum(c['status']=='passed' for c in REPORT['cases']);REPORT['total']=len(REPORT['cases'])
    REPORT['latencyPassed']=bool(REPORT['latency']) and all(x.get('status')==200 and x['seconds']<5 for x in REPORT['latency'])
    save()


if __name__=='__main__':asyncio.run(main())
