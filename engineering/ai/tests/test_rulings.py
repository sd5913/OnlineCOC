import pytest
from onlinecoc_ai.answers import parse_answer
from onlinecoc_ai.errors import AiError
from test_entrypoints import application,command,committed,delta
from test_access_batches import batch,submit
from test_coordinator import setup

def test_chat_approval_is_bound_to_batch_and_not_another_model_request(application):
    app=application;b=batch(app);session=app.sessions.get('kp',b['sessionId'])['session'];before=len(app.repository.state()['requests'])
    result=submit(app,session,'批准');assert result['ruling']['status']=='completed'
    assert len(app.repository.state()['requests'])==before
    assert submit(app,session,'批准')['ruling']['status']=='completed'
    assert len([r for r in app.host.state()['commands'].values() if r['id'].startswith('ai-batch:')])==1

def test_config_is_one_checked_ruling_and_publishes_once(application):
    app=application;p=committed(command(app,'ai.draft.create',{'text':'配置修改','changeSet':delta()}))
    result=committed(command(app,'ai.proposal.validate',{'proposalId':p['proposalId'],'revision':1}))
    assert result['proposal']['status']=='review_ready'
    item=app.rulings.list('kp')['items'][0];assert item['status']=='pending' and item['risks']
    args={'rulingId':item['rulingId'],'digest':item['digest'],'decision':'approve','explicitHighRiskDigest':item['digest']}
    assert command(app,'ai.ruling.decide',args)['code']=='RISK_REVIEW_REQUIRED'
    args['riskDecisions']={r['id']:'验收接受该项风险' for r in item['risks']}
    assert committed(command(app,'ai.ruling.decide',args))['status']=='completed'
    assert committed(command(app,'ai.ruling.decide',args))['status']=='completed'
    assert len(app.host.state()['aiControl']['publications'])==1

def test_high_risk_config_never_uses_auto_approval(application):
    app=application
    committed(command(app,'ai.access.update',{'revision':1,'allowPlayerChat':False,'autoApproveBatches':False,'autoApproveConfigurations':True}))
    p=committed(command(app,'ai.draft.create',{'text':'自动配置','changeSet':delta()}))
    committed(command(app,'ai.proposal.validate',{'proposalId':p['proposalId'],'revision':1}))
    assert app.rulings.list('kp')['items'][0]['status']=='pending'
    assert app.rulings.list('kp')['items'][0]['highRisk']
    assert not app.host.state()['aiControl']['publications']

def test_player_cannot_decide_and_stale_digest_cannot_execute(application):
    app=application;b=batch(app);args={'rulingId':'batch:'+b['batchId'],'digest':b['digest'],'decision':'approve'}
    assert command(app,'ai.ruling.decide',args,'player1')['code']=='PERMISSION_DENIED'
    assert command(app,'ai.ruling.decide',{**args,'digest':'0'*64})['code']=='RULING_STALE'
    assert app.rulings.list('kp')['items'][0]['status']=='pending'

def test_consultation_only_evidence_cannot_enter_publish_queue_or_auto_approve(application):
    app=application
    committed(command(app,'ai.access.update',{'revision':1,'allowPlayerChat':False,'autoApproveBatches':False,'autoApproveConfigurations':True}))
    snapshot=app.proposals.snapshot('kp');snapshot[0]['facts']['consultationOnly']=True
    p=app.proposals.create('kp','只读包证据候选',delta(),snapshot=snapshot)
    committed(command(app,'ai.proposal.validate',{'proposalId':p['proposalId'],'revision':1}))
    item=app.rulings.list('kp')['items'][0]
    assert item['status']=='blocked' and item['blockingReason']=='CONSULTATION_ONLY' and not item['canDecide']
    assert not app.host.state()['aiControl']['publications']

@pytest.mark.parametrize('text,code',[('[]','MODEL_OBJECT_REQUIRED'),('null','MODEL_OBJECT_REQUIRED'),('broken','MODEL_JSON_INVALID'),('{"kind":"other","text":"a"}','MODEL_KIND_INVALID')])
def test_invalid_model_output_has_specific_cause(text,code):
    with pytest.raises(AiError,match=code):parse_answer(text)

def test_single_json_fence_is_accepted_without_extracting_arbitrary_text():
    assert parse_answer('```json\n{"kind":"plan","text":"结论"}\n```')['text']=='结论'
    with pytest.raises(AiError,match='MODEL_JSON_INVALID'):parse_answer('解释：{"kind":"plan","text":"结论"}')

@pytest.mark.parametrize('valid_last',[True,False])
def test_five_repairs_do_not_consume_tool_rounds(setup,valid_last):
    import asyncio
    from test_coordinator import Coordinator,Fake,Completion,completion,wait_task
    _,service,profile=setup
    assert profile['limits']['maxRepairAttempts']==5
    profile['limits']['maxToolRounds']=1
    async def callback(count,messages,tools):
        if count==1:
            return Completion({'role':'assistant','content':None,'tool_calls':[{'id':'context','type':'function','function':{'name':'room_read_context','arguments':'{}'}}]},
                {'prompt_tokens':10,'completion_tokens':10,'total_tokens':20},'tool_calls','f'*64)
        if count==7 and valid_last:return completion({'kind':'plan','text':'已修正。'})
        return completion({'kind':'unknown','text':'格式错误'})
    provider=Fake(callback)
    async def run():
        c=Coordinator(service,{profile['profileId']:profile},provider_factory=lambda p:provider);await c.start()
        try:
            task=c.enqueue('kp','five-repairs','查询资料');result=await wait_task(c,task['taskId'])
            assert provider.calls==7  # One tool round + first output + five repairs.
            assert result['status']==('review_ready' if valid_last else 'failed'),result
            if not valid_last:assert result['error']=='MODEL_OUTPUT_INVALID'
            assert not c.repository.state()['proposals']
        finally:await c.close()
    asyncio.run(run())

@pytest.mark.parametrize('kind',['clarification','plan'])
def test_user_decision_pauses_instead_of_retrying(setup,kind):
    import asyncio
    from test_coordinator import Coordinator,Fake,completion,wait_task
    _,service,profile=setup
    answer={'kind':kind,'text':'这位 NPC 的立场是？','choices':{'prompt':'选择立场','options':[
        {'id':'friendly','label':'友好','text':'设为友好'}, {'id':'neutral','label':'中立','text':'设为中立'}]}}
    async def callback(*args):return completion(answer)
    provider=Fake(callback)
    async def run():
        c=Coordinator(service,{profile['profileId']:profile},provider_factory=lambda p:provider);await c.start()
        try:
            task=c.enqueue('kp','decision','设计 NPC');result=await wait_task(c,task['taskId'])
            assert result['status']=='needs_input' and result['choices']==answer['choices']
            assert provider.calls==1 and not c.repository.state()['proposals']
        finally:await c.close()
    asyncio.run(run())

def test_basic_lua_error_repairs_same_proposal_before_review(setup):
    import asyncio,copy
    from test_coordinator import Coordinator,Fake,completion,wait_task
    _,service,profile=setup
    change=delta();broken=copy.deepcopy(change)
    broken['sources'][next(iter(service.pack.sources))]='return rule('
    async def callback(count,*args):return completion({'kind':'draft','text':'调整属性','changeSet':broken if count==1 else change})
    provider=Fake(callback)
    async def run():
        c=Coordinator(service,{profile['profileId']:profile},provider_factory=lambda p:provider);await c.start()
        try:
            task=c.enqueue('kp','repair-lua','调整属性');result=await wait_task(c,task['taskId'],60)
            assert result['status']=='review_ready',result
            records=c.repository.state()['proposals'];assert provider.calls==2 and len(records)==1
            assert next(iter(records.values()))['currentRevision']==2
        finally:await c.close()
    asyncio.run(run())
