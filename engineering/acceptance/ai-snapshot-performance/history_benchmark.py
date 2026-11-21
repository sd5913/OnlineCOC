"""Profile a real history DAG, including approved then changed dependencies."""
import asyncio
import copy
import cProfile
import json
import pstats
import sys
import time
from pathlib import Path
from types import SimpleNamespace

HERE=Path(__file__).parent;ROOT=HERE.resolve().parents[2]
sys.path[:0]=[str(ROOT/'engineering/ai/tests'),str(ROOT/'engineering/ai/src'),str(ROOT/'engineering/backend/src'),str(ROOT/'engineering/data-management')]
from onlinecoc import chat
from onlinecoc_ai.api import Application
from onlinecoc_ai.coordinator import Coordinator
from onlinecoc_ai.context import Context
from onlinecoc_ai.contracts import digest,canonical
from test_coordinator import setup,Fake,completion,wait_task
from test_entrypoints import command,committed
from test_access_batches import session,submit,tool_call
from test_context import enable


async def main():
    path=HERE/'work'/('history-benchmark-'+str(time.time_ns()));path.mkdir(parents=True)
    fixture=setup.__wrapped__(path);host,service,profile=next(fixture)
    c=Coordinator(service,{profile['profileId']:profile},context=Context(service,demand=True));app=Application(SimpleNamespace(proposals=service,coordinator=c))
    enable(host,public=True,kp=True,private=True);room=host.state()
    for i in range(26):
        value=copy.deepcopy(room['entities']['actor-one']);value.update(instanceId='sample-'+str(i),name='history actor '+str(i));room['entities'][value['instanceId']]=value
    now=host.clock()
    for i in range(1000):chat.apply(room,'kp','chat.message.send',{'channelId':'general','text':'历史非空内容。'*30},now-1000+i)
    host.commit(room);s=session(app);mode={'kind':'plan','change':False};metrics=[]
    async def callback(n,messages,tools):
        if mode['kind']=='plan':return completion({'kind':'plan','text':'记录需求，未执行变更。'})
        if n==1:return tool_call('room_search_data',{'types':['entity'],'query':'','limit':50})
        if n==2:
            refs=json.loads(messages[-1]['content'])['items'];ref=next(i['ref'] for i in refs if i['ref']['id']==digest(['host','entity','actor-one']))
            return tool_call('room_read_data',{'refs':[ref]})
        if mode['change']:
            state=host.state();state['entities']['actor-one']['name']='changed during generation';state['entities']['actor-one']['revision']+=1;host.commit(state)
        return completion({'kind':'batch','text':'改名候选','actions':[{'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'history-approved'}}]})
    c.provider_factory=lambda _:Fake(callback);await c.start()
    try:
        for index in range(14):
            if index==8:
                state=host.state();state['entities']['actor-one']['name']='prior world change';state['entities']['actor-one']['revision']+=1;host.commit(state)
            if index>=12:mode.update(kind='batch',change=index==13)
            start=time.perf_counter();request=submit(app,s,'第'+str(index)+'轮：记录当前需求' if index<12 else '独立改名需求'+str(index));task=committed(command(app,'ai.request.dispatch',{'requestId':request['requestId']}))
            result=await wait_task(c,task['taskId'],180);elapsed=time.perf_counter()-start
            metrics.append({'phase':'generate','index':index,'seconds':round(elapsed,3),'status':result['status'],'code':result.get('error')})
            print(json.dumps(metrics[-1]),flush=True)
            if index==12:
                batch=app.repository.state()['settings']['batches'][result['batchId']]
                committed(command(app,'ai.batch.approve',{'batchId':batch['batchId'],'digest':batch['digest']}))
        profiler=cProfile.Profile();start=time.perf_counter()
        profiler.enable();page=app.sessions.get('kp',s['sessionId']);profiler.disable()
        metrics.append({'phase':'session-get','seconds':round(time.perf_counter()-start,3),'rows':len(page['items'])})
        stats=pstats.Stats(profiler);top=[]
        for key,value in sorted(stats.stats.items(),key=lambda pair:pair[1][3],reverse=True)[:30]:
            top.append({'file':Path(key[0]).name,'line':key[1],'function':key[2],'calls':value[1],'totalSeconds':round(value[3],3)})
        state=app.repository.state()
        report={'metrics':metrics,'profile':top,'aiBytes':len(canonical(state)),
            'contexts':[{'history':len(v['facts'].get('historyContexts',[])),'intents':len(v['facts'].get('historyIntents',[])),'queries':len(v['facts'].get('dataQueries',[]))} for v in state['contexts'].values()]}
        (HERE/'history-performance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'read':metrics[-1],'top':top[:8]}),flush=True)
    finally:await c.close();fixture.close()


if __name__=='__main__':asyncio.run(main())
