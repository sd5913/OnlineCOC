"""Characterize current HTTP outcomes without changing the host implementation."""
import json
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'backend/src'),str(ROOT/'data-management')]
from onlinecoc.host import Host
from onlinecoc.server import create_app
from onlinecoc_data import StoreError


@pytest.fixture
def host(tmp_path):
    value=Host(tmp_path/'host',bootstrap='test-password')
    yield value
    value.close()


def login(client,account='player1'):
    client.headers['origin']='http://127.0.0.1:8765'
    response=client.post('/api/v1/login',json={'loginName':account,'password':'test-password'})
    assert response.status_code==200
    client.headers['x-csrf-token']=response.json()['csrf']


def envelope(host,account,op,args,identifier):
    view=host.project(account)
    return {'protocolVersion':1,'type':'command','requestId':'request-'+identifier,'roomId':view['roomId'],
        'payload':{'commandId':identifier,'authorityEpoch':view['authorityEpoch'],'runId':view['runId'],
        'catalogRevision':view['catalog']['revision'],'rulesetRevision':view['catalog']['rulesetRevision'],
        'op':op,'args':args}}


def record(tmp_path,name,response,operation,request_id=None):
    try:value=response.json()
    except ValueError:value=None
    result={'scenario':name,'operation':operation,'requestId':request_id,'httpStatus':response.status_code,
        'code':value.get('code') if isinstance(value,dict) else None,
        'receiptStatus':value.get('status') if isinstance(value,dict) else None,
        'contentType':response.headers.get('content-type'),'cacheControl':response.headers.get('cache-control')}
    (tmp_path/'diagnostic.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')


def test_http_refusal_is_distinct_from_committed_rejection_receipt(host,tmp_path):
    with TestClient(create_app(host),base_url='http://127.0.0.1:8765') as client:
        login(client)
        denied=envelope(host,'player1','entity.update',{'id':'actor-player1','numbers':{'hp':7}},'business-denial')
        response=client.post('/api/v1/commands',json=denied)
        assert response.status_code==200
        assert response.json()['status']=='rejected' and response.json()['code']=='PERMISSION_DENIED'
        assert host.receipt('player1','business-denial')==response.json()
        assert host.state()['entities']['actor-player1']['numbers']['hp']==9
        record(tmp_path,'business-denial',response,'entity.update',denied['requestId'])
        bad=envelope(host,'player1','entity.update',{'notAnArgument':True},'invalid-arguments')
        response=client.post('/api/v1/commands',json=bad)
        assert response.status_code==409 and response.json()=={'code':'INPUT_INVALID'}
        assert host.receipt('player1','invalid-arguments')['status']=='unknown'
        (tmp_path/'http-refusal.json').write_text(json.dumps({'operation':'entity.update','requestId':bad['requestId'],
            'httpStatus':response.status_code,'code':response.json()['code']})+'\n',encoding='utf-8')


@pytest.mark.parametrize('error,expected_status,expected_code', [
    (StoreError('STORE_FULL'),503,'STORAGE_UNAVAILABLE'),
    (OSError('synthetic-private-marker'),500,None),
    (RuntimeError('synthetic-private-marker'),500,None),
])
def test_server_exception_shapes_do_not_prove_network_disconnect(host,tmp_path,monkeypatch,error,expected_status,expected_code):
    def fail(*args,**kwargs):raise error
    monkeypatch.setattr(host,'project',fail)
    with TestClient(create_app(host),base_url='http://127.0.0.1:8765',raise_server_exceptions=False) as client:
        login(client)
        response=client.get('/api/v1/view')
        assert response.status_code==expected_status
        assert 'synthetic-private-marker' not in response.text
        if expected_code:assert response.json()=={'code':expected_code}
        else:assert response.text=='Internal Server Error'
        record(tmp_path,type(error).__name__,response,'GET /api/v1/view')
