"""Pressure/tail adaptation, bounded pruning, rolling checkpoints and recovery."""
import asyncio,copy,json
import httpx
import pytest
from onlinecoc_ai.compression import INSTRUCTION,SECTIONS
from onlinecoc_ai.compaction_units import PRUNE_MARKER,tool_units,split_tail,history_units
from onlinecoc_ai.context_budget import budget
from onlinecoc_ai.contracts import canonical
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.providers.base import ProviderError
from test_context_compression import fixture,messages,summary
from test_coordinator import completion,Fake,wait_task,setup
from test_providers import call as wire_call,response
from test_entrypoints import application,command,committed
from test_context import enable
from test_sessions import submit


def exchange(key,content,name='room_read_data'):
    return [{'role':'assistant','content':None,'tool_calls':[{'id':key,'type':'function','function':{'name':name,'arguments':'{}'}}]},
            {'role':'tool','tool_call_id':key,'content':content}]


def minimal():return [{'role':'system','content':'json policy'},{'role':'user','content':'{"request":"retain exact"}'}]


@pytest.mark.parametrize('window,output',[(32768,8192),(65536,4096),(1048576,8192),(2097152,8192)])
def test_policy_headroom_and_tail_fit_small_window_and_application_limit(window,output):
    b=budget({'model':'declared','request':{'contextWindowTokens':window,'maxOutputTokens':output}})
    assert 0<b['retainBytes']<b['compressAtBytes']<b['requestBytes']<768*1024
    assert b['headroomTokens']<=65536 and b['headroomTokens']<=((window-output)//4)
    assert b['measurement']=='conservative-utf8-bytes'


def test_prune_relief_is_no_model_call_idempotent_exactly_recallable(tmp_path):
    async def forbidden(*_):raise AssertionError('Pruning should be sufficient')
    c=fixture(tmp_path,forbidden);long='begin '+('historical observation '*2500)+' final'
    before=minimal()+exchange('old',canonical({'text':long,'revision':4,'ref':{'id':'opaque','digest':'fixed'}}).decode())+exchange('latest','{"text":"latest exact"}')
    old=copy.deepcopy(before);out=asyncio.run(c.fit(before,[]))
    assert before==old and len(canonical(out))<len(canonical(before))
    result=json.loads(out[3]['content']);assert result['revision']==4 and result['ref']=={'id':'opaque','digest':'fixed'}
    assert PRUNE_MARKER in result['text'] and out[-2:]==before[-2:]
    assert c.events[0]['kind']=='prune' and not c.summaries
    records=len(c.records);assert asyncio.run(c.fit(out,[]))==out and len(c.records)==records
    assert c.recall({'refIds':list(c.records)[:1]})['records'][0]['origin']=='tool'
    assert 'final' in str(list(c.records.values())[-1])


@pytest.mark.parametrize('name,payload',[('pack_read_config_data',{'editRef':'pending','text':'x'*80000}),
    ('room_manage_catalog',{'schema':{'description':'x'*80000}}),('room_read_data',{'errors':[{'text':'x'*80000}]})])
def test_pending_handles_schema_and_validation_are_never_pruned_or_summarized(tmp_path,name,payload):
    async def forbidden(*_):raise AssertionError('Pinned data cannot be summarized')
    c=fixture(tmp_path,forbidden);before=minimal()+exchange('protected',canonical(payload).decode(),name)+exchange('latest','{}')
    with pytest.raises(AiError,match='CONTEXT_LIMIT_EXCEEDED'):asyncio.run(c.fit(before,[]))
    assert not c.summaries and not c.records


def test_compaction_preserves_multi_call_pairs_and_rejects_orphan_result(tmp_path):
    c=fixture(tmp_path);outgoing=exchange('a','[]')[0];outgoing['tool_calls']+=exchange('b','[]')[0]['tool_calls']
    payload=canonical(list(range(9000))).decode()
    old=[outgoing,{'role':'tool','tool_call_id':'a','content':payload},{'role':'tool','tool_call_id':'b','content':payload}]
    newer=exchange('c','{}')
    out=asyncio.run(c.fit(minimal()+old+newer,[]))
    assert [x['tool_call_id'] for x in out if x['role']=='tool']==['c']
    assert [v['id'] for x in out for v in x.get('tool_calls',[])]==['c']
    with pytest.raises(AiError,match='COMPRESSION_PAIRING_INVALID'):tool_units([{'role':'tool','tool_call_id':'orphan','content':'{}'}])
    incomplete=[outgoing,old[1]]
    unchanged=minimal()+incomplete
    assert asyncio.run(fixture(tmp_path/'incomplete-small').fit(unchanged,[]))==unchanged
    incomplete[1]={**old[1],'content':canonical(list(range(20000))).decode()}
    with pytest.raises(AiError,match='CONTEXT_LIMIT_EXCEEDED'):
        asyncio.run(fixture(tmp_path/'incomplete').fit(minimal()+incomplete,[]))


def test_rolling_checkpoint_replaces_prior_without_resending_old_raw_history(tmp_path):
    seen=[]
    async def merge(msgs,_):
        data=json.loads(msgs[1]['content']);seen.append(data)
        result=copy.deepcopy(data.get('previousCheckpoint') or {s:[] for s in SECTIONS})
        record=data['records'][0]
        result['goals']=(result['goals']+[{'text':'remember source','sources':[{'refId':record['refId'],'quote':record['content'][:200]}]}])[-12:]
        return completion(result)
    c=fixture(tmp_path,merge);out=asyncio.run(c.fit(messages(),[]));first=json.loads(out[2]['content'])
    for n in range(2):
        out+=exchange('large'+str(n),canonical(list(range(12000))).decode())+exchange('recent'+str(n),'{}')
        out=asyncio.run(c.fit(out,[],force=True))
        checkpoints=[json.loads(m['content']) for m in out if m.get('role')=='user' and 'contextSummary' in json.loads(m.get('content','{}'))]
        assert len(checkpoints)==1 and len(checkpoints[0]['contextSummary']['sections'])==1
        assert set(first['contextSummary']['recordRefs'])<=set(checkpoints[0]['contextSummary']['recordRefs'])
    assert len(c.summaries)==1 and c.events[-1]['checkpointReplaced']
    folded=[d for d in seen if d.get('previousCheckpoint')];assert folded
    assert all(set(d['previousRecordOrigins'])<=set(c.records) for d in folded)


def test_recent_denial_replacement_and_complete_dialogue_remain_verbatim(tmp_path):
    c=fixture(tmp_path);msgs=messages();payload=json.loads(msgs[1]['content'])
    latest='撤销之前HP3及旧目标A；替换成目标B，生命7，尚未批准执行。'
    payload['earlierRequirements']['items']=[{'text':'older background '*4000},{'text':latest}]
    payload['conversationHistory']=[{'role':'user','content':'提出方案'},{'role':'assistant','content':'建议HP3'},
        {'role':'user','content':'同意你的建议值，但不批准执行'},{'role':'assistant','content':'收到方案选择'}]
    msgs[1]['content']=canonical(payload).decode();out=asyncio.run(c.fit(msgs,[]));kept=json.loads(out[1]['content'])
    assert kept['earlierRequirements']['items'][-1]['text']==latest
    assert kept['conversationHistory']==payload['conversationHistory']
    old,tail,_=split_tail(history_units(payload['conversationHistory']),1)
    assert tail==[payload['conversationHistory'][-2:]] and old==[payload['conversationHistory'][:2]]


def test_prune_and_extract_diagnostics_measure_distinct_actual_surfaces(tmp_path):
    c=fixture(tmp_path);before=messages()+exchange('old',canonical({'text':'large observation '*3000}).decode())+exchange('latest','{}')
    asyncio.run(c.fit(before,[]))
    pruning=next(e for e in c.events if e['kind']=='prune')
    semantic=next(e for e in c.events if e['kind']=='summary')
    assert semantic['beforeBytes']==pruning['beforeBytes']==len(canonical({'messages':before,'tools':[]}))
    assert semantic['afterPruneBytes']==pruning['afterBytes']
    assert semantic['afterExtractionBytes']<semantic['afterPruneBytes']
    assert semantic['summaryCalls']>0 and semantic['summaryDurationMs']>=0


def test_long_recent_background_cannot_displace_short_acceptance_and_correction(tmp_path):
    c=fixture(tmp_path);messages_=messages();payload=json.loads(messages_[1]['content'])
    acceptance={'text':'同意你建议的HP，尚未批准执行。'}
    correction={'text':'更正：在建议数值上加1。'}
    withdrawal={'text':'撤回旧目标A，改为B；禁止重新创建A。'}
    payload['conversationHistory']=[{'role':'assistant','content':'建议模板A，HP=3；仅提案，尚未批准。'}]
    # A contiguous-only tail would keep this nearer bulky background and lose
    # the much older acceptance while retaining the assistant proposal.
    payload['earlierRequirements']={'items':[acceptance]+[{'text':'背景未改变决定。'*250} for _ in range(20)]+[correction,withdrawal]}
    messages_[1]['content']=canonical(payload).decode()
    out=asyncio.run(c.fit(messages_,[]));kept=json.loads(out[1]['content'])
    assert kept['conversationHistory']==payload['conversationHistory']
    assert all(row in kept['earlierRequirements']['items'] for row in [acceptance,correction,withdrawal])
    assert kept['earlierRequirements']['items'].index(acceptance)<kept['earlierRequirements']['items'].index(correction)<kept['earlierRequirements']['items'].index(withdrawal)
    assert 'HP=3' in canonical(out).decode() and c.events[-1]['retainedBytes']<=c.trace.context_policy['retainBytes']


@pytest.mark.parametrize('limit',[0,2048])
def test_oversized_last_historical_requirement_cannot_evict_short_acceptance(limit):
    from onlinecoc_ai.compaction_units import requirement_tail
    acceptance={'text':'同意建议HP3，但尚未批准执行。'}
    background={'text':'仅补充长背景。'*1000}
    rows=[acceptance,background]
    old,kept,used=requirement_tail(rows,limit)
    assert used<=limit and background in old and background not in kept
    assert kept==([acceptance] if limit else [])
    assert old==([background] if limit else rows)
    assert rows==[acceptance,background]


@pytest.mark.parametrize('status,body,expected',[
    (400,{'error':{'code':'context_length_exceeded','message':'private'}},'PROVIDER_CONTEXT_OVERFLOW'),
    (422,{'error':{'code':'context_window_exceeded'}},'PROVIDER_CONTEXT_OVERFLOW'),
    (400,{'error':{'code':'quota_limit_reached','message':'Input token exceed the limit (request id: private)'}},'PROVIDER_CONTEXT_OVERFLOW'),
    (400,{'message':"This model's maximum context length is 100 tokens. However, you requested 200 tokens."},'PROVIDER_CONTEXT_OVERFLOW'),
    (400,{'error':{'message':'max_tokens must be less than maximum context length'}},'PROVIDER_REQUEST_INVALID'),
    (422,{'error':{'code':'quota_limit_reached','message':'credit limit reached'}},'PROVIDER_REQUEST_INVALID'),
    (413,{'error':{'code':'context_length_exceeded'}},'PROVIDER_REQUEST_TOO_LARGE'),
    (400,{'error':{'code':'context_length_exceeded','message':'x'*40000}},'PROVIDER_REQUEST_INVALID')])
def test_only_explicit_bounded_context_overflow_is_classified(status,body,expected):
    with pytest.raises(ProviderError) as exc:wire_call(lambda _:httpx.Response(status,json=body))
    assert exc.value.code==expected and 'private' not in str(exc.value)


def test_output_length_is_not_input_overflow():
    body=response();body['choices'][0]['finish_reason']='length'
    with pytest.raises(ProviderError,match='PROVIDER_OUTPUT_TRUNCATED'):wire_call(lambda _:httpx.Response(200,json=body))


@pytest.mark.parametrize('code,always,expected,business_calls',[
    ('PROVIDER_CONTEXT_OVERFLOW',False,'review_ready',2),
    ('PROVIDER_CONTEXT_OVERFLOW',True,'failed',2),
    ('PROVIDER_REQUEST_INVALID',True,'failed',1)])
def test_coordinator_overflow_compacts_once_bills_uncertain_and_does_not_execute(application,code,always,expected,business_calls):
    from onlinecoc_ai.context import Context
    app=application;enable(app.host,public=True,kp=True,private=True);app.coordinator.context=Context(app.proposals,demand=True)
    app.coordinator.profiles['deepseek-main']['request'].update(contextWindowTokens=1048576,maxOutputTokens=8192)
    sid=committed(command(app,'ai.session.create',{'title':'overflow recovery'}))['sessionId']
    for n in range(14):submit(app,sid,'旧资料 '+str(n)+' '+('背景无新决策。'*500))
    seen=[];before=app.host.state()['entities']
    async def provider(n,msgs,tools):
        if msgs[0]['content']==INSTRUCTION:return completion(summary(msgs))
        seen.append(copy.deepcopy(msgs))
        if len(seen)==1 or always:raise ProviderError(code,status=400)
        return completion({'kind':'plan','text':'已按原请求整理，未执行。'})
    async def run():
        app.coordinator.provider_factory=lambda p:Fake(provider);await app.coordinator.start()
        try:
            req=submit(app,sid,'总结，不改变配置');tid=committed(command(app,'ai.request.dispatch',{'requestId':req['requestId']}))['taskId']
            task=await wait_task(app.coordinator,tid)
            assert task['status']==expected,task
            assert len(seen)==business_calls and app.host.state()['entities']==before
            if business_calls==2:assert len(canonical(seen[1]))<len(canonical(seen[0]))
            budgets=app.repository.state()['budgets'];calls=[v for b in budgets.values() for v in b['calls'].values()]
            uncertain=[v for v in calls if v['outcome']=='uncertain']
            assert uncertain and all(v['status']=='reserved' and v['charged']==v['reserved']>0 for v in uncertain)
        finally:await app.coordinator.close()
    asyncio.run(run())
