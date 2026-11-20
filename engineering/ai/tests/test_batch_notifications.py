"""Real Host receipts gate separately reviewed targeted notifications."""
import copy
import pytest
from onlinecoc_ai.errors import AiError
from test_entrypoints import application,command,committed
from test_coordinator import setup
from test_access_batches import batch,decide


def actions():
    return [{'target':'host','op':'entity.patch','args':{'id':'actor-one','name':'Reviewed result'}},
        {'target':'host','op':'notification.send','args':{'recipientAccountIds':['player1'],'text':'你的角色修改已完成。','sourceActionIndex':0}}]


def inbox(app,account):return app.host.notifications(account)['items']


def test_review_catalog_exposes_only_server_bound_source_index(application):
    schema=application.batches.catalog('kp')['host']['notification.send']
    assert set(schema['required'])=={'recipientAccountIds','text','sourceActionIndex'}
    assert 'sourceCommandId' not in schema['properties'] and 'sourceOp' not in schema['properties']
    candidate=actions();candidate[1]['args']['sourceCommandId']='forged'
    with pytest.raises(AiError):application.batches.validate_actions('kp',candidate)


@pytest.mark.parametrize('index',[-1,1,2,True])
def test_notification_rejects_nonprior_source(application,index):
    candidate=actions();candidate[1]['args']['sourceActionIndex']=index
    with pytest.raises(AiError):application.batches.validate_actions('kp',candidate)


@pytest.mark.parametrize('source',[{'target':'ai','op':'ai.session.create','args':{'title':'a'}},
    {'target':'host','op':'room.status','args':{'status':'paused'}}])
def test_notification_rejects_unsupported_source(application,source):
    candidate=actions();candidate[0]=source
    with pytest.raises(AiError):application.batches.validate_actions('kp',candidate)


def test_reviewed_notification_waits_for_approval_and_is_targeted_once(application):
    app=application;b=batch(app,actions())
    assert not inbox(app,'player1')
    assert decide(app,b,who='player1')['code']=='PERMISSION_DENIED'
    result=committed(decide(app,b));assert result['status']=='completed',result
    notices=inbox(app,'player1');assert len(notices)==1
    assert notices[0]['source']['commandId']=='ai-batch:'+b['batchId']+':0'
    assert notices[0]['source']['op']=='entity.patch' and not inbox(app,'player2')
    assert decide(app,b)['code']=='BATCH_NOT_PENDING' and len(inbox(app,'player1'))==1


def test_failed_source_cannot_claim_success(application):
    app=application;candidate=actions();candidate[0]['args']['id']='missing'
    result=committed(decide(app,batch(app,candidate)))
    assert result['status']=='partial' and len(result['receipts'])==1 and not inbox(app,'player1')


def test_rejected_batch_sends_nothing(application):
    app=application;result=committed(decide(app,batch(app,actions()),'reject'))
    assert result['status']=='rejected' and not inbox(app,'player1')


@pytest.mark.parametrize('lost_index',[0,1])
def test_lost_reply_never_blindly_replays_or_sends_early(application,lost_index):
    app=application;b=batch(app,actions());original=app.host.command;calls=[]
    def lost(account,envelope):
        value=original(account,envelope);calls.append(envelope['payload']['op'])
        if len(calls)==lost_index+1:raise OSError('lost durable response')
        return value
    app.host.command=lost
    try:result=committed(decide(app,b))
    finally:app.host.command=original
    assert result['status']=='unknown'
    result=committed(decide(app,b,'reconcile'))
    assert result['status']==('partial' if lost_index==0 else 'completed')
    assert len(calls)==lost_index+1 and len(inbox(app,'player1'))==lost_index
    assert decide(app,b)['code']=='BATCH_NOT_PENDING'
