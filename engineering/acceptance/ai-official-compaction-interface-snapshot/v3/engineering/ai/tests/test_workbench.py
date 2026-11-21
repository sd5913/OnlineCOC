from test_entrypoints import application, command, committed
from test_coordinator import setup


def test_task_session_lookup_respects_owner_archive_and_delete(application):
    app=application
    committed(command(app,'ai.access.update',{'revision':1,'allowPlayerChat':True,'autoApproveBatches':False}))
    sessions={owner:committed(command(app,'ai.session.create',{'title':owner},owner)) for owner in ('kp','player1','player2')}
    requests={owner:committed(command(app,'ai.session.submit',{'sessionId':s['sessionId'],'text':'lookup'},owner))['requestId'] for owner,s in sessions.items()}
    mine=app.tasks('player1')['items']
    assert len(mine)==1 and mine[0]['sessionId']==sessions['player1']['sessionId']
    assert {r['sessionId'] for r in app.tasks('kp')['items']}=={s['sessionId'] for s in sessions.values()}
    selected=app.tasks('kp',request_ids={requests['player1']})['items']
    assert [r['requestId'] for r in selected]==[requests['player1']]
    current=app.sessions.get('player1',sessions['player1']['sessionId'])['session']
    archived=committed(command(app,'ai.session.update',{'sessionId':current['sessionId'],'revision':current['revision'],'archived':True},'player1'))
    assert app.tasks('player1')['items'][0]['sessionId']==archived['sessionId']
    committed(command(app,'ai.session.delete',{'sessionId':archived['sessionId'],'revision':archived['revision']},'player1'))
    assert not app.tasks('player1')['items']
    assert archived['sessionId'] not in {r['sessionId'] for r in app.tasks('kp')['items']}
