"""Isolated HTTP/SDK wiring: AI projection policy is tested in the AI module."""
import base64
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import ModuleType,SimpleNamespace

import pytest
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from onlinecoc.ai_api import install

ENGINEERING=Path(__file__).resolve().parents[2]


@pytest.fixture
def api(monkeypatch):
    # Avoid importing the independently edited AI implementation. These are
    # installation ports only; the real authenticated account reaches debug.
    class AiError(Exception):
        def __init__(self,code):self.code=code
    def require(ok,code='INPUT_INVALID'):
        if not ok:raise AiError(code)
    modules={
        'onlinecoc_ai':{},
        'onlinecoc_ai.errors':{'AiError':AiError,'require':require},
        'onlinecoc_ai.contracts':{'loads':json.loads},
        'onlinecoc_ai.references':{'References':lambda host:None},
        'onlinecoc_ai.data_queries':{'DataQueryService':lambda host:None,'TOOLS':{}},
    }
    for name,values in modules.items():
        module=ModuleType(name);module.__dict__.update(values)
        if name=='onlinecoc_ai':module.__path__=[]
        monkeypatch.setitem(sys.modules,name,module)
    calls=[]
    class Service:
        host=object()
        def debug(self,account,options):
            require(options.get('sessionId')!='forbidden','PERMISSION_DENIED')
            calls.append((account,options))
            return {'accountId':account,'filters':options,**({'content':'authorized fixture'} if options['includeContent'] else {})}
        def command(self,*args):raise AssertionError('debug must not dispatch a command')
        def receipt(self,*args):raise AssertionError('debug must not create/read an export receipt')
    def auth(request,write=False):
        assert write is False
        account={'kp-token':'kp','pl-token':'player1'}.get(request.cookies.get('onlinecoc'))
        if not account:raise HTTPException(401,detail='AUTH_REQUIRED')
        return account
    app=FastAPI();install(app,SimpleNamespace(application=Service()),auth)
    with TestClient(app) as client:
        client.cookies.set('onlinecoc','pl-token')
        yield client,calls


def test_debug_default_metadata_uses_authenticated_account_and_no_store(api):
    client,calls=api
    response=client.get('/api/v1/ai/debug?sessionId=s1')
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    assert 'content' not in response.json()
    assert calls==[('player1',{'sessionId':'s1','includeContent':False})]


@pytest.mark.parametrize('literal,expected',[('false',False),('true',True)])
def test_debug_content_is_explicit_boolean_and_filters_are_decoded(api,literal,expected):
    client,calls=api
    response=client.get('/api/v1/ai/debug',params={'sessionId':'s/1','requestId':'r&x','rulingId':'rule+id','includeContent':literal})
    assert response.status_code==200
    assert calls[-1]==('player1',{'sessionId':'s/1','requestId':'r&x','rulingId':'rule+id','includeContent':expected})
    assert ('content' in response.json()) is expected


@pytest.mark.parametrize('query',[
    '', 'includeContent=false', 'sessionId=', 'sessionId='+('x'*201),
    'sessionId=s&sessionId=other', 'sessionId=s&includeContent=false&includeContent=true',
    'sessionId=s&accountId=kp', 'sessionId=s&includeContent=1',
    'sessionId=s&includeContent=yes', 'sessionId=s&includeContent=TRUE', 'sessionId=s&includeContent=',
])
def test_invalid_debug_options_do_not_reach_application(api,query):
    client,calls=api;response=client.get('/api/v1/ai/debug?'+query)
    assert response.status_code==409 and response.json()=={'code':'INPUT_INVALID'}
    assert calls==[]


def test_debug_authentication_precedes_options_and_policy_denial_is_preserved(api):
    client,calls=api;client.cookies.clear()
    assert client.get('/api/v1/ai/debug?accountId=kp').status_code==401
    client.cookies.set('onlinecoc','kp-token')
    assert client.get('/api/v1/ai/debug?sessionId=forbidden').status_code==403
    assert calls==[]
    assert client.post('/api/v1/ai/debug',json={'sessionId':'s'}).status_code==405


def test_sdk_debug_encodes_options_without_command_or_session_bypass():
    node=shutil.which('node');assert node,'Node is required for the SDK acceptance'
    encoded=base64.b64encode((ENGINEERING/'client-sdk/client.js').read_bytes()).decode()
    script="""
import assert from 'node:assert/strict';
const {Client}=await import('data:text/javascript;base64,SDK');
const calls=[];
const client=new Client({request:async(path,options)=>{calls.push({path,options});return {ok:true};}});
await client.aiDebug({sessionId:'s/& ?'});
let parsed=new URL('http://fixture/'+calls[0].path);
assert.equal(parsed.pathname,'/ai/debug');assert.equal(parsed.searchParams.get('sessionId'),'s/& ?');
assert.equal(parsed.searchParams.get('includeContent'),'false');assert.equal(calls[0].options,undefined);
await client.aiDebug({requestId:'r',rulingId:'u',includeContent:true});
parsed=new URL('http://fixture/'+calls[1].path);assert.equal(parsed.searchParams.get('includeContent'),'true');
assert.equal(parsed.searchParams.get('requestId'),'r');assert.equal(parsed.searchParams.get('rulingId'),'u');
for(const options of [{},{sessionId:''},{sessionId:'x'.repeat(201)},{sessionId:'s',accountId:'kp'},
 {sessionId:'s',includeContent:'false'},{sessionId:'s',includeContent:null},null,[]]){
 await assert.rejects(client.aiDebug(options),/INPUT_INVALID/);
}
assert.equal(calls.length,2);assert.equal(client.pending.size,0);assert.equal(client.aiPending,undefined);
let resolve;const delayed=new Client({request:()=>new Promise(r=>{resolve=r;})});
const pending=delayed.aiDebug({sessionId:'s'});delayed.resetSession();resolve({content:'old-session'});
await assert.rejects(pending,/SESSION_CHANGED/);
console.log('SDK debug: encoding, strict options, no commands and session generation passed');
""".replace('SDK',encoded,1)
    result=subprocess.run([node,'--input-type=module','-'],input=script,text=True,capture_output=True,timeout=20)
    assert result.returncode==0,result.stderr


