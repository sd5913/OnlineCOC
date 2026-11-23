"""ISSUE-019: queued/in-flight snapshot, retained candidates and live authority."""
import asyncio
import copy
import json
import pytest
from onlinecoc_ai.context import Context
from onlinecoc_ai.contracts import canonical
from test_coordinator import setup,Fake,completion,wait_task
from test_entrypoints import application,command,committed,delta
from test_access_batches import session,submit,tool_call
from test_context import enable,add_message


def dispatch(app,s):
    r=submit(app,s,'读取旧资料并准备修改')
    return committed(command(app,'ai.request.dispatch',{'requestId':r['requestId']}))


@pytest.mark.parametrize('when',['queued','provider'])
@pytest.mark.parametrize('change',['chat','entity'])
def test_frozen_tools_and_retained_batch(application,when,change):
    app=application;enable(app.host,public=True,private=True,kp=True)
    app.coordinator.context=Context(app.proposals,demand=True)
    original=app.host.state()['entities']['actor-one']['name']
    def mutate():
        if change=='chat':add_message(app.host,'player1','UNRELATED_LATER_CHAT')
        else:
            room=app.host.state();room['entities']['actor-one']['name']='LATER_ENTITY_NAME';room['entities']['actor-one']['revision']+=1;app.host.commit(room)
    async def callback(n,messages,tools):
        if n==1:
            if when=='provider':mutate()
            return tool_call('room_search_data',{'query':'','types':['entity']})
        data=json.loads(messages[-1]['content']);assert original in str(data)
        assert 'LATER_ENTITY_NAME' not in str(messages) and 'UNRELATED_LATER_CHAT' not in str(messages)
        return completion({'kind':'batch','text':'已保留基于发送时资料的候选','actions':[{'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'APPROVED_NAME'}}]})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback)
        s=session(app);r=dispatch(app,s)
        if when=='queued':mutate()
        await app.coordinator.start()
        try:
            result=await wait_task(app.coordinator,r['taskId']);assert result['status']=='review_ready',result
            check=result['dependencyCheck'];assert check['status']==('changed' if change=='entity' else 'unchanged'),check
            assert result['text'] and result['batchId']
            batch=app.repository.state()['settings']['batches'][result['batchId']]
            receipt=command(app,'ai.batch.approve',{'batchId':batch['batchId'],'digest':batch['digest']})
            if change=='chat':
                assert receipt['status']=='committed',receipt
                assert app.host.state()['entities']['actor-one']['name']=='APPROVED_NAME'
            else:
                assert receipt['status']=='rejected',receipt
                assert any(item['kind']=='entity' for item in check['changes'])
                assert app.host.state()['entities']['actor-one']['name']=='LATER_ENTITY_NAME'
            view=app.sessions.get('kp',s['sessionId'])['items'][0]
            assert view['response']==result['text'] and view['dependencyCheck']==check
            events=view['events'];assert [e['seq'] for e in events]==list(range(1,len(events)+1))
            assert {'provider_complete','tool_execute','output_validate','dependency_check','completed'} <= {e['stage'] for e in events}
            if change=='chat':assert any(e.get('receiptStatus')=='committed' for e in events)
            assert 'LATER_ENTITY_NAME' not in str(events)
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_draft_kept_and_checked_on_original_snapshot(application):
    app=application;enable(app.host,public=True,kp=True);app.coordinator.context=Context(app.proposals,demand=True)
    async def callback(n,messages,tools):
        if n==1:return tool_call('room_read_management',{'section':'configurations'})
        room=app.host.state();room['entities']['actor-one']['name']='CHANGED_WHILE_GENERATING';room['entities']['actor-one']['revision']+=1;app.host.commit(room)
        return completion({'kind':'draft','text':'候选保留并完成本地校验','changeSet':delta()})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);s=session(app);r=dispatch(app,s);await app.coordinator.start()
        try:
            result=await wait_task(app.coordinator,r['taskId']);assert result['status']=='review_ready',result
            assert result['proposalId'] and result['text']
            proposal=app.repository.state()['proposals'][result['proposalId']]['revisions']['1']
            assert len(proposal['reportRefs'])==3 and not app.host.state()['aiControl']['publications']
            assert {'validation_a','validation_b','validation_c'}<={e['stage'] for e in result['events']}
        finally:await app.coordinator.close()
    asyncio.run(run())


@pytest.mark.parametrize('change',['revoke','delete-session','disable-egress','cancel'])
def test_live_authority_still_discards_unpublished_output(application,change):
    app=application;enable(app.host,public=True,kp=True);s=session(app)
    async def callback(*args):
        if change=='delete-session':committed(command(app,'ai.session.delete',{'sessionId':s['sessionId'],'revision':app.sessions._record('kp',s['sessionId'])['revision']}))
        elif change=='cancel':app.coordinator.cancel('kp',app.coordinator.active_id)
        else:
            room=app.host.state()
            if change=='revoke':room['members']['kp']['authorizationEpoch']+=1
            else:room['aiControl']['settings']['externalSources']['kp']=False
            app.host.commit(room)
        return completion({'kind':'plan','text':'MUST_NOT_PUBLISH'})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);r=dispatch(app,s);await app.coordinator.start()
        try:
            result=await wait_task(app.coordinator,r['taskId']);assert result['status'] in ('failed','cancelled'),result
            assert result['text'] is None and not result.get('messagePublication')
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_progress_visible_while_provider_waits_and_no_extra_stage_writes(application):
    app=application;s=session(app)
    async def run():
        entered=asyncio.Event();release=asyncio.Event()
        async def callback(*args):entered.set();await release.wait();return completion({'kind':'plan','text':'完成'})
        app.coordinator.provider_factory=lambda _:Fake(callback);r=dispatch(app,s);await app.coordinator.start()
        try:
            await asyncio.wait_for(entered.wait(),5)
            before=app.repository.store.generation
            for _ in range(3):
                row=app.sessions.get('kp',s['sessionId'])['items'][0]
                assert row['events'][-1]['stage']=='provider_complete' and row['events'][-1]['status']=='running'
            assert app.repository.store.generation==before
            release.set();result=await wait_task(app.coordinator,r['taskId']);assert result['events'][-1]['status']=='completed'
            assert not app.coordinator.generations
        finally:release.set();await app.coordinator.close()
    asyncio.run(run())


def test_read_scope_snapshot_reuse_invalidation_and_rollback(application):
    repo=application.repository
    with repo.read_scope():
        first=repo.read_state();assert repo.read_state() is first
        external=repo.state();external['settings']['test']='not stored';assert 'test' not in repo.read_state()['settings']
        repo.update(lambda s:s['settings'].update(test='committed'))
        assert repo.read_state() is not first and repo.read_state()['settings']['test']=='committed'
        with pytest.raises(RuntimeError):
            with repo.transaction():
                repo.update(lambda s:s['settings'].update(test='rollback'))
                assert repo.read_state()['settings']['test']=='rollback'
                raise RuntimeError('rollback')
        assert repo.read_state()['settings']['test']=='committed'


def test_independent_adapter_is_frozen_and_change_is_reported(application):
    from onlinecoc_ai.contracts import digest
    app=application;enable(app.host,public=True,private=True,kp=True);app.coordinator.context=Context(app.proposals,demand=True)
    class Adapter:
        kinds=('event',)
        text='AT_SEND'
        def read(self,room,account):
            return [{'sourceId':'isolated-package','kind':'event','id':'case-one','revision':digest(self.text),
                'label':'案件','data':{'text':self.text},'visibility':'kp'}]
    adapter=Adapter();app.host.ai_data_adapter=adapter
    async def callback(n,messages,tools):
        if n==1:
            adapter.text='AFTER_SEND'
            return tool_call('room_search_data',{'types':['event'],'query':''})
        if n==2:return tool_call('room_read_data',{'refs':[json.loads(messages[-1]['content'])['items'][0]['ref']]})
        assert 'AT_SEND' in messages[-1]['content'] and 'AFTER_SEND' not in str(messages)
        return completion({'kind':'plan','text':'按发送时的案件资料回答'})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);s=session(app);r=dispatch(app,s);await app.coordinator.start()
        try:
            result=await wait_task(app.coordinator,r['taskId']);assert result['status']=='review_ready',result
            assert result['dependencyCheck']['status']=='changed'
            assert app.sessions.get('kp',s['sessionId'])['items'][0]['response']==result['text']
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_progress_does_not_persist_full_room_per_tool(application):
    from pathlib import Path
    from onlinecoc import chat
    app=application;enable(app.host,public=True,kp=True);app.coordinator.context=Context(app.proposals,demand=True)
    room=app.host.state();now=app.host.clock()
    for i in range(100):chat.apply(room,'kp','chat.message.send',{'channelId':'general','text':'隔离大记录。'*500},now-100+i)
    app.host.commit(room);before=len(canonical(app.repository.state()))
    async def callback(n,messages,tools):
        if n<=4:return tool_call('room_read_management',{'section':'configurations','limit':n})
        return completion({'kind':'plan','text':'资料读取已完成'})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);s=session(app);r=dispatch(app,s);await app.coordinator.start()
        try:
            result=await wait_task(app.coordinator,r['taskId']);assert result['status']=='review_ready',result
            store=app.repository.state();after=len(canonical(store));assert len(store['contexts'])==1
            assert after-before<100000 and not app.coordinator.generations
            evidence={'roomBytes':len(canonical(room)),'beforeAiBytes':before,'afterAiBytes':after,'incrementBytes':after-before,
                'contextCount':len(store['contexts']),'toolCalls':4,'events':len(result['events']),'realModelCalls':0}
            target=Path(__file__).resolve().parents[2]/'acceptance/ai-snapshot-performance/storage-growth.json'
            target.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_prior_world_changes_and_inflight_chat_do_not_break_first_tool(application):
    app=application;enable(app.host,public=True,private=True,kp=True);app.coordinator.context=Context(app.proposals,demand=True)
    mode={'batch':False}
    async def callback(n,messages,tools):
        if not mode['batch']:return completion({'kind':'plan','text':'已记下本轮需求，尚未执行修改'})
        if n==1:
            add_message(app.host,'player1','生成中的普通聊天')
            return tool_call('room_search_data',{'types':['entity'],'query':''})
        if n==2:
            from onlinecoc_ai.contracts import digest
            result=json.loads(next(m['content'] for m in reversed(messages) if m['role']=='tool'))
            ref=next(i['ref'] for i in result['items'] if i['ref']['id']==digest(['host','entity','actor-one']))
            return tool_call('room_read_data',{'refs':[ref]})
        return completion({'kind':'batch','text':'准备本次明确指定的改名','actions':[{'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'CURRENT_CANDIDATE'}}]})
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);s=session(app);await app.coordinator.start()
        try:
            for index in range(6):
                if index==3:
                    room=app.host.state();room['entities']['actor-one']['name']='PRIOR_WORLD_CHANGE';room['entities']['actor-one']['revision']+=1;app.host.commit(room)
                request=submit(app,s,'独立记录第'+str(index)+'轮')
                result=committed(command(app,'ai.request.dispatch',{'requestId':request['requestId']}))
                assert (await wait_task(app.coordinator,result['taskId']))['status']=='review_ready'
            mode['batch']=True;request=dispatch(app,s)
            result=await wait_task(app.coordinator,request['taskId']);assert result['status']=='review_ready',result
            assert result['dependencyCheck']['status']=='unchanged'
            batch=app.repository.state()['settings']['batches'][result['batchId']]
            receipt=committed(command(app,'ai.batch.approve',{'batchId':batch['batchId'],'digest':batch['digest']}))
            assert receipt['status']=='completed'
            assert app.host.state()['entities']['actor-one']['name']=='CURRENT_CANDIDATE'
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_history_shared_cache_keeps_each_roots_bound_and_checks_each_node_once(application,monkeypatch):
    from onlinecoc_ai import history
    from onlinecoc_ai.errors import AiError
    app=application;room=app.host.state();base=app.proposals.snapshot('kp')[0]
    state=app.repository.state();contexts=state['contexts'];shared={};checked=[]
    original=history.check_history_context
    def check(*args):checked.append(args[-1]['createdAt']);return original(*args)
    monkeypatch.setattr(history,'check_history_context',check)
    monkeypatch.setattr(app.repository,'read_state',lambda:state)
    for i in range(101):
        context=copy.deepcopy(base);context['createdAt']+=i+1;contexts[str(i)]=context
        assert history.assess(app.host,app.repository,room,context,shared=shared) is None
    assert len(checked)==101  # Independent roots do not share a global 100-node budget.
    root=copy.deepcopy(base);root['facts']['historyContexts']=[str(i) for i in range(99)]
    assert history.assess(app.host,app.repository,room,root,shared=shared) is None
    assert len(checked)==102  # Cached leaves still count, but are not rechecked.
    root['facts']['historyContexts'].append('99')
    with pytest.raises(AiError,match='SOURCE_STALE'):
        history.assess(app.host,app.repository,room,root,shared=shared)


def test_history_shared_cache_rejects_cycles_and_revocation_on_next_read(application,monkeypatch):
    from onlinecoc_ai import history
    from onlinecoc_ai.errors import AiError
    app=application;room=app.host.state();base=app.proposals.snapshot('kp')[0]
    state=app.repository.state();context=copy.deepcopy(base)
    context['facts']['historyContexts']=['cycle'];state['contexts']['cycle']=context
    monkeypatch.setattr(app.repository,'read_state',lambda:state)
    with pytest.raises(AiError,match='SOURCE_STALE'):
        history.assess(app.host,app.repository,room,context,shared={})
    assert history.assess(app.host,app.repository,room,base,shared={}) is None
    room['members']['kp']['authorizationEpoch']+=1
    with pytest.raises(AiError,match='PERMISSION_DENIED'):
        history.assess(app.host,app.repository,room,base,shared={})


def test_room_read_authorization_uses_current_supplied_state(application,monkeypatch):
    from onlinecoc.room_read import authorize
    from onlinecoc.errors import DomainError
    app=application;room=app.host.state()
    app.repository.update(lambda state:state['settings'].setdefault('accessPolicy',{}).update(allowAdminRoomRead=True))
    def no_copy():raise AssertionError('authorization must not copy the room again')
    monkeypatch.setattr(app.host,'state',no_copy)
    authorize(app.host,room,'kp')
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):authorize(app.host,room,'player1')
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):authorize(app.host,room,'kp','player1')
    app.repository.update(lambda state:state['settings']['accessPolicy'].update(allowAdminRoomRead=False))
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):authorize(app.host,room,'kp')
