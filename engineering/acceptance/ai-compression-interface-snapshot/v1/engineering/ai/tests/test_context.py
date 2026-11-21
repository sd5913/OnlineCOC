import copy
import pytest
from onlinecoc import chat
from onlinecoc.errors import DomainError
from onlinecoc_ai.context import Context
from onlinecoc_ai.errors import AiError
from test_coordinator import setup


def request(text='请给出方案'):
    return {'sourceKind':'manual','sourceId':'manual-one','sourceRevision':'1','text':text}


def enable(host,**values):
    state=host.state();state['aiControl']['settings']['externalSources'].update(values);host.commit(state)


def add_message(host,account,text,channel='general'):
    state=host.state();chat.apply(state,account,'chat.message.send',{'channelId':channel,'text':text},host.clock());host.commit(state)
    return host.state()['chat']['messages'][channel][-1]


def test_default_excludes_room_and_pack_text(setup):
    host,service,_=setup
    snapshot,payload=Context(service).capture('kp',request())
    assert payload['roomFacts']=={'entities':{},'configurations':{},'messages':[],'memory':[]}
    assert payload['sources']=={} and payload['rules']=={}
    assert snapshot[0]['omittedSources']


def test_public_context_strips_secret_and_never_reads_others_private_chat(setup):
    host,service,_=setup;enable(host,public=True,private=True)
    state=host.state();state['entities']['actor-one']['metadata']['secret']='hidden-secret'
    state['chat']['channels']['private']=chat.channel('private','direct','private',['player1','player2']);state['chat']['messages']['private']=[]
    host.commit(state)
    add_message(host,'player1','public message');add_message(host,'player1','private-message','private')
    snapshot,payload=Context(service).capture('kp',request())
    from onlinecoc_ai.contracts import canonical
    raw=canonical(payload).decode()
    assert 'public message' not in raw and 'private-message' not in raw and 'hidden-secret' not in raw
    assert payload['rules'] == {}
    assert len(payload['roomFacts']['configurations'])==2
    assert payload['roomFacts']['messages']==[]


@pytest.mark.parametrize('change',['edit','delete','policy','revoke','profile'])
def test_context_rechecks_source_and_policy_after_generation(setup,change):
    host,service,_=setup;enable(host,public=True)
    message=add_message(host,'player1','original');context=Context(service)
    selected={'sourceKind':'chat','sourceId':message['messageId'],'sourceRevision':str(message['revision']),'text':message['text']}
    snapshot,_=context.capture('kp',selected)
    state=host.state()
    if change=='policy':state['aiControl']['settings']['externalSources']['public']=False
    elif change=='profile':state['aiControl']['settings']['profileId']='other-provider'
    elif change=='revoke':state['members']['kp']['authorizationEpoch']+=1
    else:
        message=state['chat']['messages']['general'][0];message['revision']+=1
        if change=='edit':message['text']='changed'
        else:message.update(deleted=True,text='')
    host.commit(state)
    with pytest.raises((AiError,DomainError)):context.recheck('kp',snapshot)


def test_manual_revision_keeps_original_source_authorization(setup):
    from pathlib import Path
    from onlinecoc_ai.contracts import loads
    host, service, _ = setup;enable(host, public=True)
    message=add_message(host, 'player1', 'source information')
    selected={'sourceKind':'chat','sourceId':message['messageId'],'sourceRevision':str(message['revision']),'text':message['text']}
    snapshot, _ = Context(service).capture('kp', selected)
    delta = loads((Path(__file__).parents[1] / 'examples/bonus-15.json').read_bytes())
    proposal = service.create('kp', 'draft from sources', delta, snapshot=snapshot)
    revised = service.revise('kp', proposal['proposalId'], 1, delta)
    state = host.state();state['chat']['messages']['general'][0].update(deleted=True, text='', revision=2);host.commit(state)
    with pytest.raises(DomainError, match='SOURCE_STALE'):service.get('kp', revised['proposalId'])


def test_chat_source_requires_actual_current_text_and_external_permission(setup):
    host,service,_=setup;message=add_message(host,'player1','source request')
    data={'sourceKind':'chat','sourceId':message['messageId'],'sourceRevision':str(message['revision']),'text':message['text']}
    with pytest.raises(AiError,match='EXTERNAL_SCOPE_DISABLED'):Context(service).capture('kp',data)
    enable(host,public=True)
    data['text']='forged request'
    with pytest.raises(AiError,match='SOURCE_STALE'):Context(service).capture('kp',data)


def test_unrelated_read_position_and_ai_history_do_not_change_world(setup):
    host,service,_=setup;context=Context(service);snapshot,_=context.capture('kp',request())
    state=host.state();state['chat']['readPositions']['kp']={'general':0};state['audit'].append({'note':'unrelated'});host.commit(state)
    context.recheck('kp',snapshot)


def test_scope_mismatch_rejects_cross_room_context(setup):
    host,service,_=setup;snapshot,_=Context(service).capture('kp',request());snapshot[0]['scopeId']='another-room'
    with pytest.raises(DomainError,match='SCOPE_MISMATCH'):Context(service).recheck('kp',snapshot)


def test_context_size_is_bounded(setup):
    host,service,_=setup;enable(host,public=True)
    state=host.state()
    for i in range(30):
        entity=copy.deepcopy(state['entities']['token-one']);entity.update(instanceId='large-'+str(i));entity['metadata']['notes']='x'*4000;state['entities'][entity['instanceId']]=entity
    host.commit(state)
    with pytest.raises(AiError,match='CONTEXT_LIMIT_EXCEEDED'):Context(service).capture('kp',request())


def test_two_actual_demo_directories_do_not_share_secrets_or_memory(setup,tmp_path):
    host,service,_=setup;enable(host,kp=True,public=True)
    state=host.state();state['entities']['actor-one']['metadata']['secret']='first-room-secret';host.commit(state)
    from onlinecoc.host import Host
    from onlinecoc_ai.proposals import Proposals
    from onlinecoc_ai.contracts import canonical
    second=Host(tmp_path/'second-room',bootstrap='test-password');other=Proposals(second,service.pack)
    try:
        enable(second,kp=True,public=True)
        first_context,first_payload=Context(service).capture('kp',request())
        second_context,second_payload=Context(other).capture('kp',request())
        assert first_context[0]['scopeId']!=second_context[0]['scopeId']
        assert 'first-room-secret' in canonical(first_payload).decode() and 'first-room-secret' not in canonical(second_payload).decode()
        assert other.repository.store.path!=service.repository.store.path
    finally:other.close();second.close()
