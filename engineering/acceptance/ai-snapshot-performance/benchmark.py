"""Reproducible nonempty AI-history HTTP and store baseline; no real provider."""
import argparse
import copy
import json
import math
import statistics
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'engineering/ai/tests'),str(ROOT/'engineering/ai/src'),str(ROOT/'engineering/backend/src'),str(ROOT/'engineering/data-management')]
from fastapi.testclient import TestClient
from onlinecoc import chat
from onlinecoc.server import create_app
from onlinecoc_ai.api import Application
from onlinecoc_ai.coordinator import Coordinator
from onlinecoc_ai.context import Context
from onlinecoc_ai.contracts import canonical,digest
from test_coordinator import setup
from test_access_batches import batch
from test_entrypoints import command,committed

HERE=Path(__file__).parent


def seed(app,count):
    created=batch(app);base=app.repository.state()['settings']['batches'][created['batchId']]
    original=app.repository.state()['requests'][base['requestId']]
    dispatched=committed(command(app,'ai.request.dispatch',{'requestId':original['requestId']}))
    state=app.repository.state();task=state['tasks'][dispatched['taskId']]
    task_request=state['requests'][task['requestId']]
    context=app.coordinator.context.capture('kp',task_request)[0][0]
    old_session=state['settings']['sessions'][base['sessionId']]
    state['requests']={};state['tasks']={};state['contexts']={};state['commands']={};state['dedup']={}
    for key in ('sessions','batches','dispatch','requestLinks','reviewQueue','submissions'):state['settings'][key]={}
    now=app.host.clock();sessions=[]
    for index in range(count):
        if index%100==0:
            sid=uuid.uuid4().hex;sessions.append(sid)
            state['settings']['sessions'][sid]={**old_session,'sessionId':sid,'requestIds':[]}
            ctx=copy.deepcopy(context);ctx['facts']['sessionAccess']['sessionId']=sid
            ref=digest(ctx);state['contexts'][ref]=ctx
        rid,tid=uuid.uuid4().hex,uuid.uuid4().hex
        common={'sourceId':rid,'sourceRevision':'1','status':'review_ready','createdAt':now+index*.001}
        state['requests'][rid]={**original,**common,'requestId':rid,'text':'历史请求 '+str(index),'dedupKey':digest(rid)}
        state['requests'][tid]={**task_request,**common,'requestId':tid,'text':'历史请求 '+str(index),'dedupKey':digest(tid)}
        state['settings']['sessions'][sid]['requestIds'].append(rid)
        state['settings']['dispatch'][rid]=tid
        state['tasks'][tid]={**copy.deepcopy(task),'taskId':tid,'requestId':tid,'status':'review_ready','lease':None,'contextRef':ref,
            'createdAt':now+index*.001,'text':('已完成历史内容，仅作隔离性能数据。'*80),'calls':[
                {'requestedModel':'fixture','returnedModel':'fixture','profileRevision':1,'usage':{'total_tokens':100}} for _ in range(4)]}
        if index%10==0:
            bid=uuid.uuid4().hex
            record={**copy.deepcopy(base),'batchId':bid,'sessionId':sid,'requestId':tid,'context':copy.deepcopy(ctx),'createdAt':now+index*.001}
            record['digest']=digest({k:record[k] for k in ('batchId','sessionId','requestId','creator','actions','context','baseline','authorityEpoch')})
            state['settings']['batches'][bid]=record;state['tasks'][tid]['batchId']=bid
    app.repository.commit(state)
    room=app.host.state()
    for i in range(1000):chat.apply(room,'kp','chat.message.send',{'channelId':'general','text':'历史聊天 '+str(i)+' '+('上下文记录。'*20)},now-1000+i)
    app.host.commit(room)
    return {'sessions':sessions,'tasks':count,'requests':len(state['requests']),'batches':len(state['settings']['batches']),
        'chatMessages':1000,'aiBytes':len(canonical(state)),'hostBytes':len(canonical(room))}


def measure(name,fn,samples=12,workers=1):
    durations=[];errors=[];counts=[]
    def once(_):
        start=time.perf_counter()
        try:
            value=fn()
            return time.perf_counter()-start,None,len(value.get('items',[])) if isinstance(value,dict) else None
        except Exception as exc:return time.perf_counter()-start,getattr(exc,'code',type(exc).__name__),None
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for elapsed,error,count in pool.map(once,range(samples)):
            durations.append(elapsed);counts.append(count)
            if error:errors.append(error)
    result={'name':name,'samples':samples,'workers':workers,'p50ms':round(statistics.median(durations)*1000,2),
        'p95ms':round(sorted(durations)[math.ceil(.95*len(durations))-1]*1000,2),'errors':errors,'returnedCounts':counts}
    print(json.dumps(result,ensure_ascii=False),flush=True);return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);parser.add_argument('--tasks',type=int,default=200);parser.add_argument('--samples',type=int,default=12);args=parser.parse_args()
    directory=HERE/'work'/('benchmark-'+args.label+'-'+str(time.time_ns()));directory.mkdir(parents=True)
    fixture=setup.__wrapped__(directory);host,proposals,profile=next(fixture)
    runtime=SimpleNamespace(proposals=proposals,coordinator=Coordinator(proposals,{profile['profileId']:profile},context=Context(proposals)))
    app=Application(runtime);runtime.application=app
    async def idle():pass
    runtime.start=idle;runtime.close=idle
    output={'label':args.label,'fixture':seed(app,args.tasks),'measurements':[]}
    path=HERE/(args.label+'.json')
    def record(value):output['measurements'].append(value);path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    try:
        with TestClient(create_app(host,ai_runtime=runtime),base_url='http://127.0.0.1:8765') as client:
            client.headers['origin']='http://127.0.0.1:8765'
            assert client.post('/api/v1/login',json={'loginName':'kp','password':'test-password'}).status_code==200
            routes={'tasks':'/api/v1/ai/tasks?limit=30','session':'/api/v1/ai/sessions/'+output['fixture']['sessions'][0],'rulings':'/api/v1/ai/rulings','view':'/api/v1/view'}
            def get(route):
                response=client.get(route);assert response.status_code==200,response.status_code;return response.json()
            for name,route in routes.items():
                # First delivery has its own durable cost; warm polling separately.
                record(measure(name+'-cold',lambda r=route:get(r),samples=1))
                record(measure(name,lambda r=route:get(r),samples=args.samples))
            counter=iter(routes.values())
            record(measure('tasks-four-clients',lambda:get(routes['tasks']),samples=args.samples,workers=4))
            record(measure('repository-snapshot',app.repository.state,samples=args.samples))
            record(measure('task-status-write',lambda:app.coordinator._set(next(iter(app.repository.state()['tasks'])),'review_ready'),samples=args.samples))
    finally:fixture.close()


if __name__=='__main__':main()
