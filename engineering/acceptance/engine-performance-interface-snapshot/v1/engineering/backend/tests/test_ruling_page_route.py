"""HTTP/SDK query wiring; application authorization remains live in Rulings."""
import base64
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import ModuleType,SimpleNamespace

import pytest
from fastapi import FastAPI,HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from onlinecoc.ai_api import install
from onlinecoc.errors import DomainError


@pytest.fixture
def api(monkeypatch):
    class AiError(Exception):
        def __init__(self,code):self.code=code
    modules={'onlinecoc_ai':{},'onlinecoc_ai.errors':{'AiError':AiError},
             'onlinecoc_ai.contracts':{'loads':json.loads},
             'onlinecoc_ai.references':{'References':lambda h:None},
             'onlinecoc_ai.data_queries':{'DataQueryService':lambda h:None,'TOOLS':{}}}
    for name,values in modules.items():
        module=ModuleType(name);module.__dict__.update(values)
        if name=='onlinecoc_ai':module.__path__=[]
        monkeypatch.setitem(sys.modules,name,module)
    calls=[]
    def invoke(kind,account,**kw):
        if account=='denied':raise AiError('PERMISSION_DENIED')
        calls.append((kind,account,kw));return {'kind':kind,**kw}
    rulings=SimpleNamespace(list=lambda account,delivered=False:invoke('list',account,delivered=delivered),
        page=lambda account,**kw:invoke('page',account,**kw),
        detail=lambda account,ruling_id,**kw:invoke('detail',account,ruling_id=ruling_id,**kw))
    def auth(request,write=False):
        assert write is False
        account=request.cookies.get('onlinecoc')
        if not account:raise HTTPException(401)
        return account
    app=FastAPI();install(app,SimpleNamespace(application=SimpleNamespace(host=None,rulings=rulings)),auth)
    @app.exception_handler(DomainError)
    async def error(request,exc):return JSONResponse({'code':exc.code},status_code=409)
    with TestClient(app) as client:
        client.cookies.set('onlinecoc','player1');yield client,calls


def test_page_and_detail_preserve_delivery_and_old_list(api):
    client,calls=api
    assert client.get('/api/v1/ai/rulings').json()=={'kind':'list','delivered':True}
    result=client.get('/api/v1/ai/rulings',params={'compact':'true','queue':'archived','before':'batch:before','sessionId':'session1','limit':2}).json()
    assert result=={'kind':'page','queue':'archived','before':'batch:before','limit':2,'session_id':'session1','delivered':True}
    assert client.get('/api/v1/ai/rulings/batch:abc').json()=={'kind':'detail','ruling_id':'batch:abc','delivered':True}
    assert all(row[1]=='player1' for row in calls)
    client.cookies.set('onlinecoc','denied')
    assert client.get('/api/v1/ai/rulings?compact=true').status_code==403
    client.cookies.clear();assert client.get('/api/v1/ai/rulings?invalid=1').status_code==401


@pytest.mark.parametrize('query',['compact=false','compact=TRUE','queue=active','compact=true&queue=invalid',
    'compact=true&limit=0','compact=true&limit=101','compact=true&limit=1.0','compact=true&limit=-1',
    'compact=true&limit=1&limit=2','compact=true&before=','compact=true&sessionId=',
    'compact=true&accountId=kp','compact=true&before='+('x'*201)])
def test_invalid_paging_stops_at_boundary(api,query):
    client,calls=api
    assert client.get('/api/v1/ai/rulings?'+query).json()=={'code':'INPUT_INVALID'}
    assert calls==[]


def test_sdk_paging_and_detail_preserve_urls():
    node=shutil.which('node');assert node
    path=Path(__file__).resolve().parents[2]/'client-sdk/client.js'
    encoded=base64.b64encode(path.read_bytes()).decode()
    script="""
import assert from 'node:assert/strict';
const {Client}=await import('data:text/javascript;base64,SDK');
const calls=[];const c=new Client({request:async p=>{calls.push(p);return {};}});
await c.aiRulings();assert.equal(calls.pop(),'ai/rulings');
await c.aiRulings({queue:'archived',sessionId:'s&?',before:'batch:x',limit:2});
const u=new URL('http://fixture/'+calls.pop());assert.equal(u.searchParams.get('sessionId'),'s&?');
assert.equal(u.searchParams.get('compact'),'true');assert.equal(u.searchParams.get('limit'),'2');
await c.aiRuling('batch:x&?');assert.equal(calls.pop(),'ai/rulings/batch%3Ax%26%3F');
""".replace('SDK',encoded)
    subprocess.run([node,'--input-type=module','-e',script],check=True,capture_output=True,text=True)
