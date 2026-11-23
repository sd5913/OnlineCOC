"""Same engine, separate HTTP reads versus one authorized aggregate view."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import socket
import statistics
import sys
import threading
import time
OUT=Path(__file__).parent;name=sys.argv[1];root=OUT/'work'/name/'engineering'
sys.path[:0]=[str(root/p) for p in ('backend/src','data-management','ai/src','backend/tests')]
import httpx
import uvicorn
from onlinecoc.host import Host
from onlinecoc.server import create_app
from test_knowledge import install,observe
h=Host(OUT/'work'/name/('extras-room-'+str(time.time_ns())),bootstrap='test-password')
install(h);observe(h)
sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];origin=f'http://127.0.0.1:{port}'
server=uvicorn.Server(uvicorn.Config(create_app(h,port),log_level='error'))
thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
deadline=time.monotonic()+10
while not server.started and time.monotonic()<deadline:time.sleep(.01)
assert server.started
results={'transport':'local loopback TCP','samples':30,'flows':{}}
clients=[]
try:
    for account in ('kp','player1'):
        client=httpx.Client(base_url=origin,trust_env=False,headers={'origin':origin},timeout=10);clients.append(client)
        r=client.post('/api/v1/login',json={'loginName':account,'password':'test-password'});assert r.status_code==200
        client.headers['x-csrf-token']=r.json()['csrf']
        def call(aggregate):
            start=time.perf_counter();responses=[client.get('/api/v1/view'+('?extras=auto' if aggregate else ''))]
            if not aggregate:
                responses.append(client.get('/api/v1/knowledge/capabilities'))
                if account=='kp':responses.extend([client.post('/api/v1/knowledge/grants/query',json={'limit':50}),client.get('/api/v1/chat/members')])
                else:responses.append(client.get('/api/v1/notifications'))
            for r in responses:assert r.status_code==200,r.text
            if aggregate:
                ex=responses[0].json()['viewExtras'];assert ex['mode']==('keeper' if account=='kp' else 'player')
                assert ex['knowledgeStatus']=='ready'
            return {'ms':(time.perf_counter()-start)*1000,'httpRequests':len(responses),'bodyBytes':sum(len(r.content) for r in responses)}
        for concurrency in (1,4,8):
            for aggregate in (False,True):
                # Prime the view and existing connections before each comparison.
                call(aggregate)
                with ThreadPoolExecutor(max_workers=concurrency) as pool:rows=list(pool.map(lambda _:call(aggregate),range(30)))
                values=sorted(r['ms'] for r in rows)
                label=f'{account}.{concurrency}.'+('aggregate' if aggregate else 'separate')
                results['flows'][label]={'p50Ms':statistics.median(values),'p95Ms':values[28],
                    'httpRequests':sum(r['httpRequests'] for r in rows),'bodyBytes':sum(r['bodyBytes'] for r in rows),'failures':0,'samples':rows}
                print(label,round(statistics.median(values),2),round(values[28],2),flush=True)
finally:
    for client in clients:client.close()
    server.should_exit=True;thread.join(10);sock.close();h.close()
assert not thread.is_alive()
(OUT/(name+'-extras.json')).write_text(json.dumps(results,indent=2),encoding='utf-8')
