"""Same-directory restart must preserve readable, authorized conversation history."""
import asyncio
from types import SimpleNamespace
from onlinecoc.host import Host
from onlinecoc_ai.api import Application
from onlinecoc_ai.context import Context
from onlinecoc_ai.coordinator import Coordinator
from onlinecoc_ai.proposals import Proposals
from test_entrypoints import application, command, committed
from test_coordinator import setup, Fake, completion, wait_task
from test_sessions import submit


def test_same_room_restart_keeps_conversation_and_fresh_followup(application):
    app=application
    sid=committed(command(app,'ai.session.create',{'title':'Restart continuity'}))['sessionId']
    async def callback(*args): return completion({'kind':'plan','text':'Verified historical advice'})
    async def run():
        app.coordinator.provider_factory=lambda p:Fake(callback)
        await app.coordinator.start()
        try:
            for text in ('First turn','Second turn'):
                req=submit(app,sid,text)
                task=committed(command(app,'ai.request.dispatch',{'requestId':req['requestId']}))
                assert (await wait_task(app.coordinator,task['taskId']))['status']=='review_ready'
        finally: await app.coordinator.close()
    asyncio.run(run())
    profile=next(iter(app.coordinator.profiles.values()));pack=app.proposals.pack
    directory=app.host.path;old_epoch=app.host.epoch
    app.proposals.close();app.host.close()
    host=Host(directory);proposals=Proposals(host,pack)
    try:
        coordinator=Coordinator(proposals,{profile['profileId']:profile},context=Context(proposals))
        current=Application(SimpleNamespace(proposals=proposals,coordinator=coordinator))
        assert host.epoch!=old_epoch
        page=current.sessions.get('kp',sid)
        assert len(page['items'])==2
        assert all(i.get('response')=='Verified historical advice' for i in page['items']),page['items']
        req=submit(current,sid,'Third turn after restart')
        _,payload=coordinator.context.capture('kp',current.repository.state()['requests'][req['requestId']])
        assert len([h for h in payload['conversationHistory'] if h['role']=='assistant'])==2
    finally: proposals.close();host.close()


def reopen(app, knowledge=False):
    profile=next(iter(app.coordinator.profiles.values()));pack=app.proposals.pack;directory=app.host.path
    app.proposals.close();app.host.close()
    host=Host(directory)
    if knowledge:
        import runpy
        from pathlib import Path
        runpy.run_path(str(Path(__file__).parents[1]/'examples/knowledge-investigation.py'))['install'](host)
    proposals=Proposals(host,pack)
    coordinator=Coordinator(proposals,{profile['profileId']:profile},context=Context(proposals))
    return Application(SimpleNamespace(proposals=proposals,coordinator=coordinator))


def test_player_restart_preserves_fixed_evidence_but_revocation_still_hides_it(application):
    import json
    from test_known_runtime import install,observe,host_call
    from test_access_batches import tool_call
    app=application;install(app);grant=observe(app)
    sid=committed(command(app,'ai.session.create',{'title':'Personal history'},'player1'))['sessionId']
    async def callback(count,messages,tools):
        if count==1:
            payload=json.loads(messages[1]['content'])
            return tool_call('room_read_knowledge',{'refs':[payload['knownIndex']['items'][0]['ref']]})
        evidence=json.loads(messages[-1]['content'])['items'][0]['evidenceId']
        return completion({'kind':'known','evidence':[evidence],'next':'none'})
    async def run():
        app.coordinator.provider_factory=lambda p:Fake(callback);await app.coordinator.start()
        try:
            for text in ('First personal turn','Second personal turn'):
                req=submit(app,sid,text,'player1');task=await wait_task(app.coordinator,req['taskId'])
                assert task['status']=='review_ready',task
        finally:await app.coordinator.close()
    asyncio.run(run())
    original=[i['response'] for i in app.sessions.get('player1',sid)['items']]
    current=reopen(app,knowledge=True)
    try:
        assert [i['response'] for i in current.sessions.get('player1',sid)['items']]==original
        req=submit(current,sid,'Continue after restart','player1')
        _,payload=current.coordinator.context.capture('kp',current.repository.state()['requests'][req['requestId']])
        assert len([h for h in payload['conversationHistory'] if h['role']=='assistant'])==2
        host_call(current,'knowledge.revoke',{'grantId':grant['grantId'],'expectedRevision':1,'reason':'Revoke disclosed evidence'})
        rows=current.sessions.get('player1',sid)['items'][:2]
        assert [i['response'] for i in rows]==original
        assert all(i['historicalReadOnly'] and not i.get('choices') for i in rows)
        # Displayed history survives, but revoked evidence is not fresh authority.
        _,revoked=current.coordinator.context.capture('kp',current.repository.state()['requests'][req['requestId']])
        assert not any(h['role']=='assistant' for h in revoked['conversationHistory'])
        assert current.sessions.list('player2')['items']==[]
    finally:current.proposals.close();current.host.close()


def test_restart_does_not_reauthorize_pending_runtime_batch(application):
    from test_access_batches import access
    app=application;access(app)
    sid=committed(command(app,'ai.session.create',{'title':'Pending mutation'}))['sessionId']
    request=submit(app,sid,'Rename an actor')
    original=app.repository.state()['requests'][request['requestId']]
    snapshot,_=app.coordinator.context.capture('kp',original)
    bid=app.batches.create('kp',original,[{'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'Must not run'}}],'Pending',snapshot[0])
    batch=app.repository.state()['settings']['batches'][bid]
    current=reopen(app)
    try:
        result=command(current,'ai.batch.approve',{'batchId':bid,'digest':batch['digest']})
        assert result['status']=='rejected' and result['code']=='STALE_AUTHORITY',result
        assert current.host.state()['entities']['actor-one']['name']!='Must not run'
    finally:current.proposals.close();current.host.close()
