"""Disposable loopback Host for SDK tests; never opens a user's room."""
import json
from pathlib import Path
import socket
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'backend/src'),str(ROOT/'data-management')]
import uvicorn
from fastapi.responses import JSONResponse,PlainTextResponse
from onlinecoc.host import Host
from onlinecoc.server import create_app
from onlinecoc_data import StoreError

host=Host(Path(sys.argv[1]),bootstrap='test-password')
sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
app=create_app(host,port=port)
counts={}

@app.api_route('/api/v1/probe/{kind}',methods=['GET','POST'])
def probe(kind:str):
    counts[kind]=counts.get(kind,0)+1
    if kind=='counts':return counts
    if kind=='plain':return PlainTextResponse('synthetic-private-response',status_code=500)
    if kind=='invalid-success':return PlainTextResponse('synthetic-private-response',status_code=200)
    if kind=='unexpected':raise OSError('synthetic-private-exception')
    if kind=='storage':raise StoreError('STORE_FULL')
    if kind=='unknown':return {'status':'unknown','commandId':'trace-command'}
    if kind=='json-error':return JSONResponse({'code':'INPUT_INVALID','status':200,'requestId':'forged',
        'operation':'forged','message':'synthetic-private-response','detail':'synthetic-private-response'},status_code=409)
    return JSONResponse({'code':'synthetic-private-response'},status_code=400)

# create_app ends with a root StaticFiles mount; test routes must precede it.
app.router.routes.insert(0,app.router.routes.pop())
print(json.dumps({'port':port}),flush=True)
try:uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False)).run(sockets=[sock])
finally:host.close();sock.close()
