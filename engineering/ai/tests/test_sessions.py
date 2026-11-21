import asyncio
import copy

import pytest

from onlinecoc_ai.context import Context
from onlinecoc_ai.errors import AiError
from test_entrypoints import application, command, committed
from test_coordinator import setup, Fake, completion, wait_task


def submit(app, sid, text, account='kp'):
    return committed(command(app, 'ai.session.submit', {'sessionId': sid, 'text': text}, account))


def test_history_reuses_response_when_unread_world_data_changes(application):
    app = application
    sid = committed(command(app, 'ai.session.create', {'title': '上下文连续性'}))['sessionId']
    async def callback(*args):return completion({'kind': 'plan', 'text': '以前的未批准方案'})
    async def run():
        app.coordinator.provider_factory = lambda p: Fake(callback)
        await app.coordinator.start()
        try:
            first = submit(app, sid, '第一次需求')
            task = committed(command(app, 'ai.request.dispatch', {'requestId': first['requestId']}))
            assert (await wait_task(app.coordinator, task['taskId']))['status'] == 'review_ready'
            second = submit(app, sid, '继续完善')
            request = app.repository.state()['requests'][second['requestId']]
            _, payload = Context(app.proposals).capture('kp', request)
            assert [(h['role'], h['content']) for h in payload['conversationHistory']] == [('user', '第一次需求'), ('assistant', '以前的未批准方案')]
            assert payload['conversationHistory'][1]['authority'] == 'unapproved-model-response'
            room = app.host.state();room['entities']['actor-one']['name'] = '世界已改变';app.host.commit(room)
            snapshot, changed = Context(app.proposals).capture('kp', request)
            assert [h['role'] for h in changed['conversationHistory']] == ['user','assistant']
            assert changed['conversationHistory'][1]['authority']=='unapproved-model-response'
            assert not snapshot[0]['facts'].get('historyIntents')
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_history_is_bounded_and_never_reads_other_sessions(application):
    from test_known_runtime import install
    install(application)
    app = application
    sid = committed(command(app, 'ai.session.create', {'title': '我的会话'}, 'player1'))['sessionId']
    other = committed(command(app, 'ai.session.create', {'title': '他人会话'}, 'player2'))['sessionId']
    submit(app, other, '其他人的私密想法', 'player2')
    for i in range(6):last = submit(app, sid, '需求' + str(i), 'player1')
    request = app.repository.state()['requests'][last['requestId']]
    snapshot, payload = Context(app.proposals).capture('kp', request)
    assert payload['conversationHistory']==[]  # Queued requests have no verified evidence context yet.
    assert any(s.startswith('session-history:') for s in snapshot[0]['omittedSources'])
    assert '其他人的私密想法' not in str(payload)
    assert command(app, 'ai.session.submit', {'sessionId': other, 'text': '越权'}, 'player1')['code'] == 'NOT_VISIBLE'


@pytest.mark.parametrize('mutation', ['foreign', 'missing', 'duplicate', 'title'])
def test_repository_rejects_broken_conversation_links(application, mutation):
    app = application
    sid = committed(command(app, 'ai.session.create', {'title': '会话'}))['sessionId']
    submit(app, sid, '原始需求')
    state = app.repository.state();record = state['settings']['sessions'][sid]
    if mutation == 'foreign':record['owner'] = 'player1'
    if mutation == 'missing':record['requestIds'] = ['missing']
    if mutation == 'duplicate':record['requestIds'] *= 2
    if mutation == 'title':record['title'] = ' '
    with pytest.raises(AiError):app.repository.commit(state)
    assert app.sessions.get('kp', sid)['session']['title'] == '会话'


def test_session_preferences_owner_conflict_and_persistence(application):
    app=application
    committed(command(app,'ai.access.update',{'revision':1,'allowPlayerChat':True,'autoApproveBatches':False}))
    session=committed(command(app,'ai.session.create',{'title':'旧格式兼容'},'player1'));sid=session['sessionId']
    assert session['historyTurns']==4 and session['renderMode']=='formatted' and session['showDiagnostics'] is True
    changes={'sessionId':sid,'revision':1,'title':'置顶灯具讨论','pinned':True,'historyTurns':2,'renderMode':'plain','showDiagnostics':False}
    assert command(app,'ai.session.update',changes,'player2')['code']=='NOT_VISIBLE'
    assert app.sessions.get('kp',sid)['session']['owner']=='player1'
    saved=committed(command(app,'ai.session.update',changes,'player1'))
    assert saved['revision']==2
    assert command(app,'ai.session.update',changes,'player1')['code']=='SESSION_VERSION_CONFLICT'
    app.repository.verify(app.repository.store.snapshot()[1])
    assert app.repository.store.snapshot()[1]['settings']['sessions'][sid]['historyTurns']==2
    assert app.sessions.list('player2')['items']==[]
    assert app.sessions.get('player1',sid)['session']==saved
    committed(command(app,'ai.session.create',{'title':'较新的会话'},'player1'))
    assert app.sessions.list('player1')['items'][0]['sessionId']==sid
    saved=committed(command(app,'ai.session.update',{'sessionId':sid,'revision':2,'archived':True},'player1'))
    assert app.sessions.list('player1',True)['items'][0]['pinned']
    committed(command(app,'ai.session.update',{'sessionId':sid,'revision':saved['revision'],'archived':False},'player1'))
    assert app.sessions.get('player1',sid)['session']['renderMode']=='plain'


@pytest.mark.parametrize('turns',[0,2,4])
def test_configured_history_bound_preserves_records(application,turns):
    app=application;sid=committed(command(app,'ai.session.create',{'title':'历史设置'}))['sessionId']
    committed(command(app,'ai.session.update',{'sessionId':sid,'revision':1,'historyTurns':turns}))
    for i in range(6):last=submit(app,sid,'需求'+str(i))
    _,payload=Context(app.proposals).capture('kp',app.repository.state()['requests'][last['requestId']])
    assert [h['content'] for h in payload['conversationHistory']]==['需求'+str(i) for i in range(5-turns,5)]
    assert len(app.sessions.get('kp',sid)['items'])==6


@pytest.mark.parametrize('key,value',[('historyTurns',-1),('historyTurns',5),('historyTurns',True),('historyTurns',1.5),('renderMode','html'),('pinned',1),('showDiagnostics','false')])
def test_session_preferences_validate_command_and_stored_data(application,key,value):
    app=application;sid=committed(command(app,'ai.session.create',{'title':'边界'}))['sessionId']
    with pytest.raises(AiError,match='INPUT_INVALID'):
        command(app,'ai.session.update',{'sessionId':sid,'revision':1,key:value})
    state=app.repository.state();state['settings']['sessions'][sid][key]=value
    with pytest.raises(AiError,match='SESSION_STATE_INVALID'):app.repository.commit(state)
