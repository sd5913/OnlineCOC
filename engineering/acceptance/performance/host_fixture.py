"""Disposable, instrumented real Host. No production room or AI credentials."""
import collections
import functools
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time

ENGINEERING = Path(os.environ.get('PERFORMANCE_ENGINEERING',Path(__file__).resolve().parents[2]))
sys.path[:0] = [str(ENGINEERING/'backend/src'), str(ENGINEERING/'data-management')]
import uvicorn
from fastapi.responses import HTMLResponse
from onlinecoc.host import Host
from onlinecoc.server import create_app
from onlinecoc import host as host_module, chat
from onlinecoc_data import store as store_module

directory, messages, generations = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
padding=int(sys.argv[4]) if len(sys.argv)>4 else 0
host = Host(directory, bootstrap='test-password')
state = host.state()
for i in range(messages):
    result = chat.apply(state, 'player1' if i % 2 else 'player2', 'chat.message.send',
                        {'channelId':'general','text':'synthetic history ' + 'x'*256}, 1000 + i * 11)
    key = 'player1:historical-' + str(i)
    state['commands'][key] = {'id':key.split(':')[1], 'account':'player1', 'op':'chat.message.send',
        'status':'committed','signature':'synthetic','args':{'channelId':'general','text':'synthetic'},
        'receipt':{'status':'committed','commandId':key.split(':')[1],'result':result}, 'random':[]}
if padding:
    state['audit']=[{'account':'player1','commandId':'historical-'+str(i),'op':'chat.message.send',
                     'at':1000+i,'detail':'synthetic '+ 'x'*(padding//max(1,messages))} for i in range(max(1,messages))]
for _ in range(generations):
    host.commit(state)

samples = collections.defaultdict(list)
metrics_lock = threading.Lock()
def measured(target, name, label):
    original = getattr(target,name)
    @functools.wraps(original)
    def call(*args,**kwargs):
        started=time.perf_counter()
        try:return original(*args,**kwargs)
        finally:
            elapsed=(time.perf_counter()-started)*1000
            with metrics_lock:samples[label].append(elapsed)
    setattr(target,name,call)

for name in ('snapshot','commit','_disk_bytes'):
    measured(store_module.FileDataStore,name,'store.'+name)
measured(store_module,'canonical','store.canonical')
measured(os,'fsync','fsync')
measured(host_module,'validate','room.validate')
measured(host_module,'execute','rule.execute')
for name in ('project','tick','dispatch'):
    measured(host,name,'host.'+name)

sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
app=create_app(host,port=port)
@app.get('/performance-fixture')
def page():
    return HTMLResponse('<!doctype html><meta charset="utf-8"><title>Isolated performance fixture</title>'
                        '<script type="module" src="/performance-client.js"></script>')
@app.get('/performance-client.js')
def script():
    from fastapi.responses import Response
    return Response("import {Client,HttpTransport} from '/sdk/client.js';window.perfProtocol={resets:0,closes:0};class Transport extends HttpTransport{open(message,close){return super.open(m=>{if(m.type==='reset')perfProtocol.resets++;message(m);},()=>{perfProtocol.closes++;close();});}}window.client=new Client(new Transport());",media_type='text/javascript')
@app.get('/performance-metrics')
def metrics(reset:bool=False):
    with metrics_lock:
        value={k:list(v) for k,v in samples.items()}
        if reset:samples.clear()
    # Inclusive method times overlap; never sum these as disjoint stages.
    return {'samplesMs':value,'dispatch':host.metrics['commands'][-1000:],
            'stateBytes':len(store_module.canonical(host.state())),
            'generation':host.store.generation,'storeBytes':host.store.inspect()['bytes']}
# These test-only routes must precede the root StaticFiles mount.
for _ in range(3):app.router.routes.insert(0,app.router.routes.pop())
print(json.dumps({'port':port,'messages':messages,'generations':host.store.generation}),flush=True)
try:uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False)).run(sockets=[sock])
finally:host.close();sock.close()
