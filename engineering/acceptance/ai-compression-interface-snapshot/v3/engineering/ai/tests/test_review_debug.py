"""KP source role, explicit review, export boundaries, and provider identity."""
import asyncio
import copy
import json
import httpx
import pytest
from onlinecoc_ai.context import Context
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.providers import create_provider
from onlinecoc_ai.contracts import validate
from test_entrypoints import application,command,committed
from test_coordinator import setup,Fake,completion,wait_task
from test_access_batches import access,session,submit,tool_call
from test_player_requests import create,decide
from test_context import enable
from test_providers import profile,response

def source(**updates):
    return dict(kind='package',sourceId='test-pack',category='wait',id='one',revision='1',title='装备裁决',requestedBy='player1',summary='我想为我的角色制作火焰剑',context={'status':'pending'},**updates)

def review(app,**args):return committed(command(app,'ai.review.create',{'source':source(),**args}))

def test_review_source_is_separate_from_kp_message_and_deduplicated(application):
    app=application;access(app);r=review(app);again=review(app)
    assert r['sessionId']==again['sessionId'] and r['requestId']==again['requestId']
    item=app.sessions.get('kp',r['sessionId'])['items'][0]
    assert item['initiator']=='kp' and '火焰剑' not in item['text']
    assert item['reviewSource']['summary']==source()['summary']
    assert item['reviewSource']['requestedBy']=='player1'
    assert len(app.repository.state()['settings']['sessions'])==1
    with pytest.raises(AiError,match='NOT_VISIBLE'):app.sessions.get('player1',r['sessionId'])
    assert command(app,'ai.review.create',{'source':source()},'player1')['code']=='PERMISSION_DENIED'
    app.repository.verify(app.repository.state())

def test_forwarded_request_resolves_real_source_and_does_not_change_original(application):
    app=application;s,r=create(app)
    out=committed(command(app,'ai.review.create',{'source':{'kind':'request','requestId':r['requestId']}}))
    item=app.sessions.get('kp',out['sessionId'])['items'][0]
    assert item['reviewSource']['sessionId']==s['sessionId'] and item['reviewSource']['requestedBy']=='player1'
    assert app.player_requests.list('kp')[0]['status']=='pending'
    assert command(app,'ai.review.create',{'source':{'kind':'request','requestId':'missing'}})['code']=='NOT_VISIBLE'

def test_all_forwarded_reviews_stay_manual_with_auto_on(application):
    app=application;access(app,auto=True);r=review(app)
    request=app.repository.state()['requests'][r['requestId']]
    snapshot,_=Context(app.proposals).capture('kp',request)
    before=app.host.state()['entities']['actor-one']['name']
    bid=app.batches.create('kp',request,[{'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'must approve'}}],'name',snapshot[0])
    assert app.repository.state()['settings']['batches'][bid]['status']=='pending'
    assert app.host.state()['entities']['actor-one']['name']==before

def test_review_source_obeys_external_scope(application):
    app=application;r=review(app);enable(app.host,public=True,private=True,kp=False)
    payload=app.reviews.payload(r['sessionId'])
    assert payload['omitted'] and payload['requiredScope']=='kp' and '火焰剑' not in str(payload)
    enable(app.host,public=True,private=True,kp=True)
    assert app.reviews.payload(r['sessionId'])['summary']==source()['summary']

def test_ruling_digest_and_snapshot_size_checked(application):
    app=application;_,r=create(app)
    assert command(app,'ai.review.create',{'source':{'kind':'ruling','rulingId':r['rulingId'],'digest':'stale'}})['code']=='RULING_STALE'
    big=source();big['context']={'data':'x'*40000}
    assert command(app,'ai.review.create',{'source':big})['code']=='INPUT_INVALID'

def test_debug_is_readonly_metadata_default_with_authorized_content_opt_in(application):
    app=application;s,r=create(app,text='仅本人的私密需求 sk-abcdefghijklmnopqrstuvwx')
    before=copy.deepcopy(app.repository.state())
    minimal=app.debug('player1',{'sessionId':s['sessionId']})
    assert '私密需求' not in json.dumps(minimal,ensure_ascii=False) and 'content' not in minimal['items'][0]
    full=app.debug('player1',{'requestId':r['requestId'],'includeContent':True})
    assert '私密需求' in str(full) and 'sk-abcdefghijklmnopqrstuvwx' not in str(full)
    assert 'diagnostics' not in str(full) and app.repository.state()==before
    for who in ('player2',):
        with pytest.raises(AiError,match='NOT_VISIBLE'):app.debug(who,{'sessionId':s['sessionId'],'includeContent':True})
    accepted=committed(decide(app,r))
    with pytest.raises(AiError,match='NOT_VISIBLE'):app.debug('player1',{'sessionId':accepted['reviewSessionId']})

@pytest.mark.parametrize('options',[{}, {'sessionId':''}, {'requestId':'x','includeContent':'yes'}, {'requestId':'x','account':'kp'}, {'requestId':'x'*201}])
def test_debug_rejects_ambiguous_or_invalid_options(application,options):
    with pytest.raises(AiError,match='INPUT_INVALID'):application.debug('kp',options)

def test_debug_rechecks_deleted_session_and_player_switch(application):
    app=application;s,r=create(app)
    fresh=app.sessions.get('player1',s['sessionId'])['session']
    committed(command(app,'ai.session.delete',{'sessionId':s['sessionId'],'revision':fresh['revision']},'player1'))
    with pytest.raises(AiError,match='NOT_VISIBLE'):app.debug('player1',{'requestId':r['requestId'],'includeContent':True})
    access(app,players=False)
    with pytest.raises(AiError,match='PLAYER_AI_DISABLED'):app.debug('player1',{'requestId':r['requestId']})

def test_pure_schema_catalog_available_without_kp_egress(application):
    app=application;access(app);enable(app.host,public=True,private=True,kp=False)
    async def callback(count,messages,tools):
        if count==1:
            payload=json.loads(messages[1]['content']);assert payload['currentActor']['accountId']=='kp' and payload['effectiveAccess']['kpMaterialExternal'] is False
            return tool_call('room_manage_catalog',{'operations':['entity.patch']})
        value=json.loads(messages[-1]['content']);assert value['host']['entity.patch'] and value['actions']['omitted']
        return completion({'kind':'plan','text':'可准备修改；私密资料尚未授权外发。'})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);await app.coordinator.start()
        try:
            r=submit(app,session(app));r=committed(command(app,'ai.request.dispatch',{'requestId':r['requestId']}));task=await wait_task(app.coordinator,r['taskId']);assert task['status']=='review_ready',task
        finally:await app.coordinator.close()
    asyncio.run(run())

def test_provider_records_actual_model_without_equating_alias_and_version():
    async def run():
        p=profile();p['model']='rolling-alias';p['versionInfo']={'label':'管理员核验版本','sourceUrl':'https://api.example.org/model','verifiedAt':'2026-11-19'};validate('Profile',p)
        provider=create_provider(p,transport=httpx.MockTransport(lambda r:httpx.Response(200,json=response(model='actual-returned-id',system_fingerprint='backend-config'))),credential_loader=lambda p:'test-only-key')
        try:
            result=await provider.complete([{'role':'user','content':'json'}]);assert result.model=='actual-returned-id' and result.system_fingerprint=='backend-config'
            assert p['model']=='rolling-alias'
        finally:await provider.close()
    asyncio.run(run())


def test_real_http_debug_authorization_no_store_and_no_receipt(application):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from onlinecoc.server import create_app
    app=application;s,r=create(app,text='本人的测试私密问题')
    async def idle():pass
    runtime=SimpleNamespace(application=app,start=idle,close=idle)
    before=copy.deepcopy(app.repository.state()['commands'])
    with TestClient(create_app(app.host,ai_runtime=runtime),base_url='http://127.0.0.1:8765') as client:
        path='/api/v1/ai/debug?sessionId='+s['sessionId']
        assert client.get(path).status_code==401
        client.headers['origin']='http://127.0.0.1:8765'
        client.post('/api/v1/login',json={'loginName':'player1','password':'test-password'})
        minimal=client.get(path);assert minimal.status_code==200 and minimal.headers['cache-control']=='no-store'
        assert '私密问题' not in minimal.text
        full=client.get(path+'&includeContent=true');assert '私密问题' in full.text
        assert client.get(path+'&includeContent=yes').json()['code']=='INPUT_INVALID'
        assert client.get(path+'&requestId='+r['requestId']+'&requestId=other').json()['code']=='INPUT_INVALID'
        assert client.get(path+'&account=kp').json()['code']=='INPUT_INVALID'
        assert client.get('/api/v1/ai/debug?rulingId='+r['rulingId']).status_code==403
    assert app.repository.state()['commands']==before


def test_legacy_accepted_review_retains_original_player_source(application):
    app=application;enable(app.host,public=True,private=True,kp=True)
    _,r=create(app,text='为我的角色设计一件道具');accepted=committed(decide(app,r));sid=accepted['reviewSessionId']
    app.repository.update(lambda s:s['settings'].pop('reviews'))
    source_id=app.repository.state()['requests'][accepted['reviewRequestId']]['sourceId']
    def legacy(data):
        for request in data['requests'].values():
            if request['sourceId']==source_id:request['text']='为我的角色设计一件道具'
    app.repository.update(legacy)
    original=copy.deepcopy(app.repository.state()['requests'])
    value=app.reviews.payload(sid)
    assert value['requestedBy']=='player1' and value['summary']=='为我的角色设计一件道具'
    assert value['sessionId']!=sid and value['rulingId']==r['rulingId']
    assert app.player_requests.review_required(sid) and app.repository.state()['requests']==original
    enable(app.host,public=True,private=False,kp=True)
    assert app.reviews.payload(sid)['omitted']
    item=app.sessions.get('kp',sid)['items'][0]
    assert '为我的角色' not in item['text'] and item['reviewSource']['legacy']
    request=app.repository.state()['requests'][accepted['reviewRequestId']]
    _,payload=Context(app.proposals).capture('kp',request)
    assert '为我的角色' not in json.dumps(payload,ensure_ascii=False)
    follow=submit(app,app.sessions.get('kp',sid)['session'],text='继续处理')
    _,payload=Context(app.proposals).capture('kp',app.repository.state()['requests'][follow['requestId']])
    assert '为我的角色' not in json.dumps(payload,ensure_ascii=False)
    assert all(app.repository.state()['requests'][rid]['text']==value['text'] for rid,value in original.items())


def test_task_and_debug_preserve_requested_and_actual_model_ids(application):
    from dataclasses import replace
    app=application
    async def callback(count,messages,tools):
        return replace(completion({'kind':'plan','text':'已准备审核说明。'}),model='actual-model-build',system_fingerprint='backend-config-id')
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);await app.coordinator.start()
        try:
            result=review(app);task=await wait_task(app.coordinator,result['taskId']);assert task['status']=='review_ready',task
            model=app.debug('kp',{'sessionId':result['sessionId']})['items'][0]['modelCalls'][0]
            assert model['requestedModel']==app.coordinator.profiles['deepseek-main']['model']
            assert model['returnedModel']=='actual-model-build' and model['systemFingerprint']=='backend-config-id'
            assert model['usage']['total_tokens']==20
        finally:await app.coordinator.close()
    asyncio.run(run())
