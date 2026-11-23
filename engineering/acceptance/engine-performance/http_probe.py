"""Real loopback TCP timings; deliberately makes no LAN/WAN or TURN claim."""
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import shutil
import socket
import statistics
import sys
import threading
import time

OUT=Path(__file__).parent;name=sys.argv[1];root=OUT/'work'/name/'engineering'
repeat=sys.argv[2] if len(sys.argv)>2 else None
samples=90 if repeat else 30
if not (root/'test-console').exists():
    shutil.copytree(OUT/'work/candidate-v3/engineering/test-console',root/'test-console')
sys.path[:0]=[str(root/p) for p in ('backend/src','data-management','ai/src','backend/tests')]
import httpx
import uvicorn
from onlinecoc.host import Host
from onlinecoc.server import create_app,runtime_info
from test_host import message
results={'transport':'TCP over 127.0.0.1; no actual LAN/WAN/TURN','samplesPerFlow':samples,'flows':{}}
started=time.perf_counter();h=Host(OUT/'work'/name/('http-room-'+str(time.time_ns())),bootstrap='test-password')
results['hostColdBootstrapMs']=(time.perf_counter()-started)*1000
sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
app=create_app(h,port);server=uvicorn.Server(uvicorn.Config(app,log_level='error',lifespan='on'))
thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
deadline=time.monotonic()+10
while not server.started and time.monotonic()<deadline:time.sleep(.01)
assert server.started
origin=f'http://127.0.0.1:{port}'
client=httpx.Client(base_url=origin,headers={'Origin':origin},timeout=20,trust_env=False)
login=client.post('/api/v1/login',json={'loginName':'player1','password':'test-password'});assert login.status_code==200,(login.status_code,login.text,login.headers.get('location'))
client.headers['x-csrf-token']=login.json()['csrf']
def get_view(i):
    start=time.perf_counter();r=client.get('/api/v1/view');assert r.status_code==200,r.text
    assert 'secret-clue' not in r.json().get('entities',{})
    return {'ms':(time.perf_counter()-start)*1000,'responseBodyBytes':len(r.content)}
def command(i):
    msg=message(h,'player1','action.invoke',{'actionId':'demo.check','input':{'actor':'actor-player1','skill':'skill-player1'}},'http-'+str(i))
    start=time.perf_counter();r=client.post('/api/v1/commands',json=msg)
    assert r.status_code==200 and r.json()['status']=='committed',r.text
    return {'ms':(time.perf_counter()-start)*1000,'responseBodyBytes':len(r.content)}
try:
    flows=[('view.1',1,get_view),('view.4',4,get_view),('view.8',8,get_view)]
    if not repeat:flows.append(('action.check',1,command))
    for label,concurrency,fn in flows:
        start=time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as pool:rows=list(pool.map(fn,range(samples)))
        elapsed=time.perf_counter()-start;latencies=sorted(x['ms'] for x in rows)
        results['flows'][label]={'p50Ms':statistics.median(latencies),'p95Ms':latencies[math.ceil(samples*.95)-1],
            'requestsPerSecond':samples/elapsed,'failures':0,'responseBodyBytes':sum(x['responseBodyBytes'] for x in rows),'samples':rows}
        print(label,round(statistics.median(latencies),2),round(results['flows'][label]['p95Ms'],2),flush=True)
    results['memory']=runtime_info();results['commitPhases']=h.metrics.get('commitPhases',[])[-30:]
finally:
    client.close();server.should_exit=True;thread.join(10);sock.close();h.close()
assert not thread.is_alive()
(OUT/(name+'-http'+('-'+repeat if repeat else '')+'.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
