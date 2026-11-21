"""Post-freeze adversarial provenance and transport checks."""
import asyncio
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'engineering/ai/tests'),str(ROOT/'engineering/ai/src'),str(ROOT/'engineering/backend/src'),str(ROOT/'engineering/data-management')]
from test_entrypoints import application
from test_coordinator import setup
from test_known_runtime import install, observe, host_call
from test_message_history import publish
from test_manager_ui import services
from test_chat_polish import browser_page
from test_access_batches import batch, session, submit
from test_review_followup import new_batch, row
from test_entrypoints import command, committed


@pytest.mark.parametrize('mutation',['generating','validating','failed','context-missing','context-tampered','owner-mismatch'])
def test_unproven_legacy_reply_never_migrates(application,mutation):
    app=application;install(app);grant=observe(app);s,r,task=asyncio.run(publish(app))
    def change(state):
        old=state['tasks'][task['taskId']];old.pop('messagePublication')
        if mutation in ('generating','validating','failed'):old['status']=mutation
        elif mutation=='context-missing':old.pop('contextRef')
        elif mutation=='context-tampered':state['contexts'][old['contextRef']]['facts']['unexpected']='tampered'
        else:state['contexts'][old['contextRef']]['facts']['sessionAccess']['owner']='player2'
    app.repository.update(change)
    host_call(app,'knowledge.revoke',{'grantId':grant['grantId'],'expectedRevision':1,'reason':'隔离撤回'})
    row=app.sessions.get('player1',s['sessionId'],delivered=True)['items'][0]
    assert not row.get('response') and row['text']=='我想吃掉奶酪回复一些生命'
    assert not app.repository.state()['tasks'][task['taskId']].get('messagePublication')


def test_http_error_does_not_attach_unsafe_identifiers(browser_page):
    page=browser_page
    result=page.evaluate(r"""async()=>{
      const {HttpTransport,AiClient}=await import('/ai-ui/client.js');const actual=fetch;
      window.fetch=async()=>new Response('SECRET_BODY',{status:502});const client=new AiClient(new HttpTransport());
      client.connected=true;client.view={authorityEpoch:1};let result;
      try{await client.aiCommand('ai.session.submit',{},'secret\nunsafe');}catch(e){result={message:e.message,...e};}
      window.fetch=actual;return result;
    }""")
    assert result['code']=='HTTP_ERROR' and result['status']==502
    assert 'aiRequestId' not in result and 'requestId' not in result and 'SECRET' not in str(result)


def test_resolution_never_reexposes_hidden_ruling_receipt_ids(application):
    app=application;first=batch(app);second=new_batch(app,first['sessionId'],related=first['requestId'])
    committed(command(app,'ai.batch.approve',{'batchId':second['batchId'],'digest':second['digest']}))
    room=app.host.state();room['members']['kp']['authorizationEpoch']+=1;app.host.commit(room)
    item=row(app,'batch:'+second['batchId'])
    assert item['sourceUnavailable'] and item['status']=='completed'
    assert 'resolution' not in item
    # A plain predecessor has no task context of its own; its completion proof
    # must still obey the successful batch's source authorization.
    conversation=session(app);original=submit(app,conversation)
    successor=new_batch(app,conversation['sessionId'],related=original['requestId'])
    committed(command(app,'ai.batch.approve',{'batchId':successor['batchId'],'digest':successor['digest']}))
    room=app.host.state();room['members']['kp']['authorizationEpoch']+=1;app.host.commit(room)
    request=app.tasks('kp',request_ids={original['requestId']})['items'][0]
    assert request['queueStatus']=='archived' and 'resolution' not in request
