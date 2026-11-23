"""Semantic citations and display-only choices survive the authorized task path."""
import asyncio
import copy
import json
import pytest
from onlinecoc_ai.answers import validate_answer, validate_choices
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.data_queries import DataQueryService, model_result
from onlinecoc_ai.references import References
from test_entrypoints import application, command, committed
from test_coordinator import setup, Fake, completion, wait_task
from test_access_batches import session, submit, access, tool_call
from test_context import enable, add_message

CHOICE={'prompt':'选择风格','options':[{'id':'a','label':'友好医师','text':'采用友好医师方案'},
    {'id':'b','label':'神秘访客','text':'采用神秘访客方案'}]}

@pytest.mark.parametrize('mutate',[
    lambda c:c.update(command='entity.create'),lambda c:c['options'][0].update(action='approve'),
    lambda c:c['options'].pop(),lambda c:c['options'][1].update(id='a'),
    lambda c:c['options'][0].update(text=' '*5),lambda c:c.update(prompt='x'*201)])
def test_choices_are_bounded_text_only(mutate):
    c=copy.deepcopy(CHOICE);mutate(c)
    with pytest.raises(AiError,match='MODEL_CHOICES_INVALID'):validate_choices(c)

def test_citations_require_issued_tokens_and_choices_cannot_approve():
    validate_answer({'kind':'plan','text':'使用 [[entity:lantern@1]]','choices':CHOICE},{'[[entity:lantern@1]]'})
    for output in ({'kind':'plan','text':'[[entity:secret@1]]'},
                   {'kind':'clarification','text':'[[entity:broken]]'},
                   {'kind':'batch','text':'批准','choices':CHOICE}):
        with pytest.raises(AiError):validate_answer(output,set())

def test_model_citations_are_exact_tokens_without_changing_evidence(application):
    app=application;enable(app.host,public=True,private=True,kp=True)
    add_message(app.host,'player1','测试聊天证据')
    r=submit(app,session(app));request=app.repository.state()['requests'][r['requestId']]
    snapshot,_=app.coordinator.context.capture('kp',request);q=DataQueryService(app.host)
    raw=q.attach('kp','search',{'types':['entity','config','chat']},snapshot)
    original=copy.deepcopy(raw);citations=q.citations('kp',raw,snapshot)
    shown=model_result(raw,{},citations)
    assert raw==original and len(shown['items'])==len(raw['items'])
    assert {i['ref']['kind'] for i in shown['items'] if 'citation' in i}=={'entity','config','chat'}
    for item in shown['items']:
        citation=item['citation'];resolved=References(app.host).resolve('kp',[citation['token']])['items'][0]
        assert resolved['label']==citation['label']
    app.host.validate_ai_sources(app.host.state(),'kp',snapshot[0])

def test_player_model_choices_and_references_are_visible_only_while_authorized(application):
    from test_known_runtime import install,observe
    app=application;install(app);observe(app)
    async def callback(count,messages,tools):
        if count==1:return tool_call('room_search_knowledge',{})
        page=json.loads(messages[-1]['content'])
        if count==2:return tool_call('room_read_knowledge',{'refs':[page['items'][0]['ref']]})
        return completion({'kind':'known','evidence':[page['items'][0]['evidenceId']],'next':'ask_kp'})
    async def run():
        app.coordinator.provider_factory=lambda p:Fake(callback);await app.coordinator.start()
        try:
            s=session(app,'player1');r=submit(app,s,who='player1');task=await wait_task(app.coordinator,r['taskId'])
            assert task['status']=='needs_input',task
            result=app.sessions.get('player1',s['sessionId'])['items'][0]
            assert result['choices']['options'][0]['id']=='ask_kp' and '[[knowledge:' in result['response']
            assert not app.host.state()['aiControl']['approvals'] and not app.batches.list('kp')['items']
            access(app,False)
            assert 'choices' not in app.sessions.get('kp',s['sessionId'])['items'][0]
        finally:await app.coordinator.close()
    asyncio.run(run())

def test_fabricated_model_citation_is_repaired_or_rejected(application):
    app=application
    async def callback(*args):return completion({'kind':'plan','text':'[[entity:made-up@1]]'})
    async def run():
        app.coordinator.provider_factory=lambda p:Fake(callback);await app.coordinator.start()
        try:
            r=submit(app,session(app));t=committed(command(app,'ai.request.dispatch',{'requestId':r['requestId']}))
            task=await wait_task(app.coordinator,t['taskId'])
            assert task['status']=='failed' and task['error']=='MODEL_OUTPUT_INVALID',task
            assert not task.get('text')
        finally:await app.coordinator.close()
    asyncio.run(run())
