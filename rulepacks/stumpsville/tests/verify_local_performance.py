"""Isolate package transport cost from engine/model cost using real loopback HTTP."""
import argparse
import asyncio
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
from pathlib import Path
import secrets
import socket
import statistics
import sys
import threading
import time
from types import SimpleNamespace

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

PACK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PACK/'tools'))
from launch import Runtime, create_app


@contextmanager
def upstream():
    api=FastAPI()
    @api.api_route('/api/v1/{path:path}',methods=['GET','POST'])
    async def answer(path,request:Request):
        if path=='login':
            result=JSONResponse({'csrf':'fixture-csrf'})
            result.set_cookie('sid',(await request.json())['name'])
            return result
        return {'csrf':'fixture-csrf','cookie':request.headers.get('cookie',''),'items':['fixture']*256}
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(api,host='127.0.0.1',port=port,log_level='error'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    deadline=time.monotonic()+10
    while not server.started:
        if time.monotonic()>deadline:raise TimeoutError('fixture startup')
        time.sleep(.01)
    try:yield 'http://127.0.0.1:'+str(port)
    finally:server.should_exit=True;thread.join(10)


def stats(samples,elapsed):
    values=sorted(samples)
    return {'samples':len(values),'p50Ms':round(statistics.median(values),3),'p95Ms':round(values[min(len(values)-1,int(len(values)*.95))],3),'totalSeconds':round(elapsed,3),'requestsPerSecond':round(len(values)/elapsed,2)}


async def measure(operation,workers,count=12):
    samples=[];lock=asyncio.Semaphore(workers)
    async def one(i):
        async with lock:
            start=time.perf_counter();await operation(i);samples.append((time.perf_counter()-start)*1000)
    start=time.perf_counter();await asyncio.gather(*(one(i) for i in range(count)))
    return stats(samples,time.perf_counter()-start)


async def run(phase):
    output=PACK/'tests/output'/('local-performance-'+phase+'-'+secrets.token_hex(4));output.mkdir(parents=True)
    report={'phase':phase,'checkedAt':datetime.now().astimezone().isoformat(),'scope':'Package transport over real TCP; constant fixture, not full engine or model benchmark','externalModelCalls':0,'formalDataChanged':False,'evidenceDirectory':output.relative_to(PACK).as_posix(),'measurements':{},'checks':[]}
    with upstream() as base:
        runtime=SimpleNamespace(backend=base,origin='http://testserver',data=output,start=lambda:None,close=lambda:None,observe_request=lambda *a:None)
        app=create_app(runtime)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(base_url=base,trust_env=False) as direct, httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=runtime.origin,trust_env=False) as browser:
                async def direct_read(i):
                    response=await direct.get('/api/v1/view',headers={'Cookie':'sid=fixture-'+str(i%4)})
                    assert response.json()['cookie']=='sid=fixture-'+str(i%4)
                async def proxy_read(i):
                    response=await browser.get('/sessions/slot-'+str(i%4)+'/api/v1/view',headers={'Cookie':'sv_slot-'+str(i%4)+'__sid=fixture-'+str(i%4)})
                    assert response.json()['cookie']=='sid=fixture-'+str(i%4),response.text
                async def composed_read(i):
                    def read():
                        client=Runtime.client(runtime,'sid=fixture-'+str(i%4))
                        for _ in range(3):assert client.request('/view')['cookie']=='sid=fixture-'+str(i%4)
                    await asyncio.to_thread(read)
                for name,operation in [('direct',direct_read),('proxy',proxy_read),('composition4Requests',composed_read)]:
                    for workers in (1,4):
                        report['measurements'][name+'Concurrency'+str(workers)]=await measure(operation,workers)
                        print(name,workers,report['measurements'][name+'Concurrency'+str(workers)],flush=True)
                report['checks'].append('single and four concurrent clients retain per-request identities')
                response=await browser.post('/sessions/login/api/v1/login',headers={'Origin':runtime.origin},json={'name':'private-login'})
                assert 'sv_login__sid=private-login' in response.headers['set-cookie']
                response=await browser.get('/sessions/anonymous/api/v1/me',headers={'Cookie':''})
                assert response.json()['cookie']=='',response.text
                report['checks'].append('login cookie forwarded only to matching slot; anonymous caller inherits no session')
    report['sourceHashes']={name:hashlib.sha256((PACK/name).read_bytes()).hexdigest() for name in ['tools/launch.py','tools/client.py']}
    report['passed']=True
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    canonical=PACK/'tests/local-performance-results.json'
    previous=json.loads(canonical.read_text(encoding='utf-8')) if canonical.exists() else {'runs':[]}
    previous['runs'].append(report);canonical.write_text(json.dumps(previous,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':True,'phase':phase,'evidenceDirectory':report['evidenceDirectory']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',required=True,choices=['baseline','optimized']);asyncio.run(run(parser.parse_args().phase))
