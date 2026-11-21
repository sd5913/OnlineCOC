"""Requirements retention, bounded pre-reading and only proven repeated choices."""
import asyncio
import json
import pytest
from onlinecoc_ai.context import Context
from onlinecoc_ai.contracts import canonical,digest
from onlinecoc_ai.errors import AiError
from test_entrypoints import application,command,committed
from test_coordinator import setup,Fake,completion,wait_task
from test_sessions import submit
from test_context import enable


def session(app):return committed(command(app,'ai.session.create',{'title':'需求保留'}))['sessionId']


def capture(app,sid,text):
    req=submit(app,sid,text)
    return Context(app.proposals,demand=True).capture('kp',app.repository.state()['requests'][req['requestId']])


def test_old_parameters_survive_four_turn_window_without_factual_authority(application):
    app=application;sid=session(app)
    first=submit(app,sid,'制作治疗药剂：单次恢复3点生命，使用次数2，不清除死亡状态，价格5铜。')
    for text in ('名称叫苔露','不要新增稀有材料','改成价格7铜，其他参数保留','描述一句话即可','仅准备配置草稿'):submit(app,sid,text)
    snap,payload=capture(app,sid,'按前面参数继续')
    earlier=payload['earlierRequirements']
    assert '恢复3点' in str(earlier) and '名称叫苔露' in str(earlier)
    assert len(payload['conversationHistory'])==4 and '价格7铜' in str(payload['conversationHistory'])
    assert snap[0]['facts']['intentRequests'][0]['requestId']==first['requestId']
    assert not snap[0]['sourceRefs'] and not snap[0]['facts'].get('dataQueries')
    from onlinecoc_ai.history import require_current_evidence
    with pytest.raises(AiError,match='HISTORY_REQUERY_REQUIRED'):require_current_evidence(snap[0],{'kind':'batch','actions':[{'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'苔露'}}]})


@pytest.mark.parametrize('change',['cancelled','session_deleted'])
def test_retained_requirements_recheck_original_provenance(application,change):
    app=application;sid=session(app);first=submit(app,sid,'目标生命5')
    for n in range(5):submit(app,sid,'细节'+str(n))
    snap,_=capture(app,sid,'继续')
    from onlinecoc_ai.intent_context import validate
    validate(app.repository,snap[0])
    if change=='cancelled':committed(command(app,'ai.request.cancel',{'requestId':first['requestId']}))
    else:committed(command(app,'ai.session.delete',{'sessionId':sid,'revision':app.sessions.get('kp',sid)['session']['revision']}))
    with pytest.raises(AiError,match='SOURCE_STALE'):validate(app.repository,snap[0])


def test_retention_is_bounded_reports_omissions_and_respects_history_off(application):
    app=application;sid=session(app);other=session(app);submit(app,other,'禁止串会话的私密目标')
    for n in range(18):submit(app,sid,str(n)+'界'*600)
    _,payload=capture(app,sid,'继续')
    earlier=payload['earlierRequirements'];assert earlier['omittedRequests']>0 and len(canonical(earlier['items']))<=12*1024
    assert earlier['items'][0]['text'].startswith('0界') and '禁止串会话' not in str(payload)
    committed(command(app,'ai.session.update',{'sessionId':sid,'revision':app.sessions.get('kp',sid)['session']['revision'],'historyTurns':0}))
    snap,payload=capture(app,sid,'无历史模式')
    assert not payload['conversationHistory'] and not payload.get('earlierRequirements') and not snap[0]['facts'].get('intentRequests')


CHOICES={'prompt':'恢复哪一项？','options':[{'id':'hp','label':'生命','text':'给 player1 的角色恢复1点生命。'},{'id':'armor','label':'护甲','text':'给 player1 的角色增加1点护甲。'}]}


def test_only_exact_previously_answered_choices_trigger_bounded_correction(application):
    app=application;enable(app.host,public=True,kp=True,private=True);sid=session(app)
    app.coordinator.context=Context(app.proposals,demand=True)
    async def run():
        async def ask(*_):return completion({'kind':'clarification','text':'请选恢复项。','choices':CHOICES})
        app.coordinator.provider_factory=lambda _:Fake(ask);await app.coordinator.start()
        try:
            first=submit(app,sid,'给角色加1点');task=committed(command(app,'ai.request.dispatch',{'requestId':first['requestId']}))
            assert (await wait_task(app.coordinator,task['taskId']))['status']=='needs_input'
        finally:await app.coordinator.close()
        from onlinecoc_ai.coordinator import Coordinator
        app.coordinator=Coordinator(app.proposals,app.coordinator.profiles,context=Context(app.proposals,demand=True))
        app.runtime.coordinator=app.coordinator;app.coordinator.application=app
        calls=[]
        async def follow(n,messages,tools):
            calls.append(n)
            if n==1:
                payload=json.loads(messages[1]['content']);assert payload['resolvedChoices'][0]['selectedText']==CHOICES['options'][0]['text']
                return completion({'kind':'clarification','text':'请再次选择。','choices':CHOICES})
            assert json.loads(messages[-1]['content'])['error']['code']=='REPEATED_RESOLVED_CHOICE'
            return completion({'kind':'plan','text':'已保留生命选项；当前仅整理方案，不执行。'})
        app.coordinator.provider_factory=lambda _:Fake(follow);await app.coordinator.start()
        try:
            req=submit(app,sid,CHOICES['options'][0]['text']);task=committed(command(app,'ai.request.dispatch',{'requestId':req['requestId']}));result=await wait_task(app.coordinator,task['taskId'])
            assert result['status']=='review_ready' and len(calls)==2,result
            assert any(x['code']=='REPEATED_RESOLVED_CHOICE' for x in result['diagnostics']['outputFailures'])
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_new_material_choice_is_not_suppressed():
    from onlinecoc_ai.intent_context import require_new_question,resolved_choices
    payload={'resolvedChoices':[{'optionTexts':[i['text'] for i in CHOICES['options']]}]}
    require_new_question(payload,{'kind':'clarification','choices':{'prompt':'消耗什么？','options':[{'text':'消耗铜币'},{'text':'消耗药剂'}]}})
    assert resolved_choices({'request':'我改主意了，重新选择','conversationHistory':[{'role':'assistant','content':'选择','choices':CHOICES},{'role':'user','content':CHOICES['options'][0]['text']}]})==[]


def test_recorded_false_numeric_capability_claim_is_rejected_without_suppressing_real_choice():
    from onlinecoc_ai.reliability import require_capability_evidence
    payload={'aiPermissions':{'allowRuntimeChanges':True},'operationIndex':{'host':['entity.patch','entity.update']}}
    output={'kind':'clarification','text':'目前宿主目录里可写的角色数值操作只有 entity.patch，而它仅接受 id 和 name，不含 target/hp 等数值字段，也没有其他可改数值的目录操作，因此无法提交。','choices':CHOICES}
    with pytest.raises(AiError,match='MODEL_CAPABILITY_UNPROVEN'):require_capability_evidence(payload,output)
    require_capability_evidence(payload,{'kind':'clarification','text':'加1点指生命还是护甲？','choices':CHOICES})
    require_capability_evidence(payload,{'kind':'plan','text':'entity.patch 只改名称；数值需要读取 entity.update 的参数。'})
    payload['aiPermissions']['allowRuntimeChanges']=False
    require_capability_evidence(payload,output)


@pytest.mark.parametrize('allowed',[True,False])
def test_configuration_request_preloads_only_authorized_templates(application,allowed):
    app=application;enable(app.host,public=True,kp=allowed,private=True);sid=session(app);app.coordinator.context=Context(app.proposals,demand=True)
    seen=[]
    async def callback(n,messages,tools):
        payload=json.loads(messages[1]['content']);seen.append(payload)
        assert 'entity.update' in payload['operationIndex']['host']
        if allowed:
            page=payload['preparedFacts']['configurations'];assert page['items'] and 'snapshot' in page and page['nextOffset'] is None
        else:assert 'preparedFacts' not in payload
        return completion({'kind':'plan','text':'只报告预读范围，不修改模板。'})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);await app.coordinator.start()
        try:
            req=submit(app,sid,'修改配置模板默认值，先核对模板');task=committed(command(app,'ai.request.dispatch',{'requestId':req['requestId']}));result=await wait_task(app.coordinator,task['taskId'])
            assert result['status']=='review_ready',result
            proof=app.repository.state()['contexts'][result['contextRef']]['facts']
            assert bool(proof.get('managementReads'))==allowed
        finally:await app.coordinator.close()
    asyncio.run(run());assert len(seen)==1
