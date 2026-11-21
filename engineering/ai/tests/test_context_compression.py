"""Semantic compression boundaries, provenance, recall and billed repair path."""
import asyncio,copy,gzip,json
from types import SimpleNamespace
import pytest
from onlinecoc_ai.compression import Compactor,SECTIONS,INSTRUCTION,validate_summary
from onlinecoc_ai.context_budget import budget
from onlinecoc_ai.contracts import canonical,digest
from onlinecoc_ai.diagnostics import TaskTrace
from onlinecoc_ai.errors import AiError
from test_coordinator import setup,completion,Fake,wait_task
from test_entrypoints import application,command,committed
from test_sessions import submit
from test_context import enable


def summary(messages):
    records=json.loads(messages[1]['content'])['records'];result={s:[] for s in SECTIONS}
    for origin,section in [('user','confirmedParameters'),('reference','goals'),('tool','toolResults'),('assistant','currentPlan')]:
        rows=[r for r in records if r['origin']==origin]
        if rows:
            r=rows[-1];quote=r['content'][:300]
            result[section]=[{'text':quote,'sources':[{'refId':r['refId'],'quote':quote}]}]
    return result


def fixture(tmp_path,call=None,guard=lambda:None):
    profile={'model':'test','request':{'maxOutputTokens':4096,'contextWindowTokens':65536}}
    repo=SimpleNamespace(directory=tmp_path,read_state=lambda:{'scopeId':'scope'})
    async def default(messages,tools):return completion(summary(messages))
    return Compactor(repo,{'taskId':'task-a','account':'kp'},profile,call or default,guard,TaskTrace())


def messages():
    payload={'request':'最终价格7铜，其他不变','earlierRequirements':{'items':[{'text':'恢复3点生命，使用2次，不清除死亡，价格5铜。','requestId':'a'}]},
        'sources':{'guide':'已知背景资料。'*10000},'conversationHistory':[{'role':'user','content':'旧要求'},{'role':'assistant','content':'尚未确认的建议99'},{'role':'user','content':'最新更正7'},{'role':'assistant','content':'等待处理'}],
        'selectedReferences':[{'id':'exact','revision':3}],'contract':{'revision':'keep-exact'}}
    return [{'role':'system','content':'JSON policy exact'},{'role':'user','content':canonical(payload).decode()}]


def test_compacts_semantically_keeps_current_request_exact_and_recall_archives(tmp_path):
    c=fixture(tmp_path);before=messages();out=asyncio.run(c.fit(before,[]))
    assert before==messages() and len(canonical(out))<len(canonical(before))
    p=json.loads(out[1]['content']);old=json.loads(before[1]['content'])
    for key in ('request','selectedReferences','contract'):assert p[key]==old[key]
    assert p['conversationHistory']==old['conversationHistory']  # All short complete turns fit the retained budget.
    assert p['earlierRequirements']==old['earlierRequirements']
    assert json.loads(out[2]['content'])['contextSummary']['sections']
    original=next(r for r in c.records.values() if r['origin']=='reference')
    assert c.recall({'refIds':[original['refId']]})['records'][0]==original
    archive=tmp_path/'context-archives/objects'/ (original['refId']+'.json.gz')
    assert json.loads(gzip.decompress(archive.read_bytes()))==original
    assert c.trace.snapshot()['compression'][0]['status']=='compressed'
    assert c.trace.snapshot()['compression'][0]['afterBytes']<c.trace.snapshot()['compression'][0]['beforeBytes']
    with pytest.raises(AiError,match='NOT_VISIBLE'):c.recall({'refIds':['f'*64]})
    another=fixture(tmp_path/'different');assert not another.records
    with pytest.raises(AiError,match='NOT_VISIBLE'):another.recall({'refIds':[original['refId']]})


def test_invalid_summary_repairs_once_and_preserves_failed_feedback(tmp_path):
    calls=[]
    async def call(msgs,tools):
        calls.append(copy.deepcopy(msgs));return completion({'bad':True} if len(calls)==1 else summary(msgs))
    c=fixture(tmp_path,call);asyncio.run(c.fit(messages(),[]))
    assert 'COMPRESSION_INVALID' in calls[1][-1]['content']
    assert c.events[0]['repairs']==[{'attempt':1,'code':'COMPRESSION_INVALID'}]
    assert c.events[0]['repairCount']==1


def test_persistent_bad_summary_fails_closed_keeps_originals(tmp_path):
    calls=[]
    async def call(*_):calls.append(1);return completion({'bad':True})
    c=fixture(tmp_path,call)
    with pytest.raises(AiError,match='COMPRESSION_INVALID'):asyncio.run(c.fit(messages(),[]))
    assert len(calls)==2 and c.events[0]['status']=='failed'
    assert (tmp_path/'context-archives/task-a/index.json').exists()
    assert len(c.events[0]['repairs'])==2


@pytest.mark.parametrize('origin,quote',[('assistant','not approval'),('user','not approval')])
def test_summary_cannot_forge_provenance_or_convert_ai_suggestion_to_confirmation(origin,quote):
    records={'a':{'origin':origin,'content':'not approval'}};value={s:[] for s in SECTIONS}
    value['confirmedParameters']=[{'text':'approved','sources':[{'refId':'a' if origin=='assistant' else 'unknown','quote':quote}]}]
    with pytest.raises(AiError,match='COMPRESSION_PROVENANCE_INVALID'):validate_summary(value,['a'],records)


def test_guard_change_during_summary_rejects_before_output_and_recall(tmp_path):
    stale=[]
    def guard():
        if stale:raise AiError('SOURCE_STALE')
    async def call(msgs,tools):stale.append(1);return completion(summary(msgs))
    c=fixture(tmp_path,call,guard)
    with pytest.raises(AiError,match='SOURCE_STALE'):asyncio.run(c.fit(messages(),[]))
    assert c.events[0]['code']=='SOURCE_STALE'
    with pytest.raises(AiError,match='SOURCE_STALE'):c.recall({'refIds':list(c.records)[:1]})


def test_tool_exchanges_stay_paired(tmp_path):
    c=fixture(tmp_path);msgs=messages()
    for n in range(3):
        msgs.extend([{'role':'assistant','content':None,'tool_calls':[{'id':str(n),'function':{'name':'tool','arguments':'{}'}}]}, {'role':'tool','tool_call_id':str(n),'content':'result'+str(n)*6000}])
    out=asyncio.run(c.fit(msgs,[]))
    assert [m['tool_call_id'] for m in out if m['role']=='tool']==['2']
    assert [t['id'] for m in out for t in m.get('tool_calls',[])]==['2']


def test_under_threshold_no_call_and_uncompressible_overflow_no_provider(tmp_path):
    async def forbidden(*_):raise AssertionError('unexpected model call')
    c=fixture(tmp_path,forbidden);short=[{'role':'user','content':'one'}]
    assert asyncio.run(c.fit(short,[])) is short
    pinned=[{'role':'system','content':'json'},{'role':'user','content':canonical({'request':'p'*100000}).decode()}]
    with pytest.raises(AiError,match='CONTEXT_LIMIT_EXCEEDED'):asyncio.run(c.fit(pinned,[]))


def test_model_budget_reserves_output_protocol_and_declared_window():
    known=budget({'model':'deepseek-flash','request':{'maxOutputTokens':8192}})
    assert known['contextWindowTokens']==1048576 and known['requestBytes']<known['inputBytes']<=768*1024
    unknown=budget({'model':'unknown','request':{'maxOutputTokens':4096}})
    assert unknown['inputBytes']+8192+4096==65536
    with pytest.raises(AiError,match='CONTEXT_WINDOW_INVALID'):budget({'model':'unknown','request':{'contextWindowTokens':16384,'maxOutputTokens':8192}})


def test_coordinator_bills_summary_and_final_reply_with_visible_progress(application):
    from onlinecoc_ai.context import Context
    app=application;enable(app.host,public=True,kp=True,private=True)
    app.coordinator.context=Context(app.proposals,demand=True)
    app.coordinator.profiles['deepseek-main']['request'].update(contextWindowTokens=131072,maxOutputTokens=8192)
    sid=committed(command(app,'ai.session.create',{'title':'压缩测试'}))['sessionId']
    for n in range(18):submit(app,sid,'参数'+str(n)+'；'+('背景信息无变化。'*600))
    calls=[]
    async def call(n,msgs,tools):
        calls.append(msgs)
        if msgs[0]['content']==INSTRUCTION:return completion(summary(msgs))
        assert any('contextSummary' in (m.get('content') or '') for m in msgs)
        assert any(t['function']['name']=='room_read_compressed' for t in tools)
        return completion({'kind':'plan','text':'已整理需求，未执行变更。'})
    async def run():
        app.coordinator.provider_factory=lambda p:Fake(call);await app.coordinator.start()
        try:
            req=submit(app,sid,'保留先前约定，汇总即可');tid=committed(command(app,'ai.request.dispatch',{'requestId':req['requestId']}))['taskId']
            task=await wait_task(app.coordinator,tid)
            assert task['status']=='review_ready',task
            assert task['usage']==len(calls)*20 and len(task['calls'])==len(calls)>1
            assert task['diagnostics']['compression'] and any(e['stage']=='context_compress' for e in task['events'])
            assert not task.get('proposalId') and not task.get('batchId')
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_identical_revalidated_records_reuse_persisted_semantic_summary(tmp_path):
    first=fixture(tmp_path);asyncio.run(first.fit(messages(),[]))
    async def no_call(*_):raise AssertionError('Unnecessary summary call')
    second=fixture(tmp_path,no_call);out=asyncio.run(second.fit(messages(),[]))
    assert second.events[0]['cacheHits']>0
    meta=json.loads((tmp_path/'context-archives/task-a/index.json').read_bytes())
    assert meta['summaries'] and meta['records']


@pytest.mark.parametrize('path,offset,allowed',[(['entities','actor-one'],None,True),(['entities','actor-two'],None,False),(['entities','actor-one','name'],None,False),(['entities','actor-one'],0,False)])
def test_current_entity_evidence_accepts_only_complete_stable_room_path(path,offset,allowed):
    from onlinecoc_ai.history import require_current_evidence
    ref={'sourceId':'host-room-state','kind':'room','id':digest(['host-room-state','room',digest([path,offset])])}
    context={'sourceRefs':[],'facts':{'dataQueries':[{'operation':'read','args':{'refs':[ref]}}]}}
    output={'kind':'batch','actions':[{'target':'host','op':'entity.update','args':{'id':'actor-one','numbers':{'hp':4}}}]}
    if allowed:require_current_evidence(context,output,required=True)
    else:
        with pytest.raises(AiError,match='HISTORY_REQUERY_REQUIRED'):require_current_evidence(context,output,required=True)


def test_nonverbatim_quote_becomes_explicit_record_locator_not_fabricated_quote():
    records={'a':{'origin':'user','content':'**HP=3** 原文记录'}};value={s:[] for s in SECTIONS}
    value['goals']=[{'text':'模型摘要','sources':[{'refId':'a','quote':'HP 等于 3'}]}]
    validate_summary(value,['a'],records)
    assert value['goals'][0]['sources']==[{'refId':'a','quote':'**HP=3** 原文记录','quoteRole':'record-locator'}]
    validate_summary(value,['a'],records)  # Persisted form is revalidated too.


@pytest.mark.parametrize('quote',['用户已经批准HP=30','尚未同意HP=3'])
def test_paraphrase_cannot_invent_confirmation_or_change_numeric_anchor(quote):
    records={'a':{'origin':'user','content':'尚未同意HP=3'}};value={s:[] for s in SECTIONS}
    value['confirmedParameters']=[{'text':'用户已经批准HP=30','sources':[{'refId':'a','quote':quote}]}]
    validate_summary(value,['a'],records)
    assert '已经批准' not in str(value) and '30' not in str(value)
    if quote.startswith('用户'):assert value['confirmedParameters']==[] and value['openQuestions']
    else:assert value['confirmedParameters'][0]['text']=='尚未同意HP=3'


def test_concurrent_object_and_summary_publication_has_unique_temporaries(tmp_path,monkeypatch):
    import threading,os
    from concurrent.futures import ThreadPoolExecutor
    from onlinecoc_ai.compression import atomic_write
    barrier=threading.Barrier(2);replace=os.replace;temporaries=[]
    def simultaneous(source,target):
        if str(target).endswith(('.json.gz','.summary.json')) and str(source) not in temporaries:
            temporaries.append(str(source));barrier.wait(timeout=10)
        return replace(source,target)
    monkeypatch.setattr(os,'replace',simultaneous)
    first=fixture(tmp_path);second=fixture(tmp_path);second.task['taskId']='task-b'
    for c in (first,second):c._record({'text':'identical shared source'},'user')
    with ThreadPoolExecutor(2) as pool:
        futures=[pool.submit(c._save) for c in (first,second)]
        for future in futures:future.result(timeout=20)
        cache=tmp_path/'context-archives/objects/shared.summary.json'
        futures=[pool.submit(atomic_write,cache,b'{"same":true}') for _ in range(2)]
        for future in futures:future.result(timeout=20)
    assert len(temporaries)==len(set(temporaries))==4
    assert json.loads(cache.read_bytes())=={'same':True}
    assert not list((tmp_path/'context-archives').rglob('*.tmp'))
    for file in (tmp_path/'context-archives/objects').glob('*.json.gz'):assert json.loads(gzip.decompress(file.read_bytes()))['refId']==file.name.split('.')[0]
