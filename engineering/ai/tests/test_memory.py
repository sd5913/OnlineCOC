import copy
import pytest
from onlinecoc_ai.context import source,Context
from onlinecoc_ai.memory import Memory
from onlinecoc_ai.errors import AiError
from onlinecoc.errors import DomainError
from onlinecoc_ai.proposals import Proposals
from test_coordinator import setup


def create(memory,host,**options):
    entity=host.state()['entities']['actor-one']
    return memory.create('kp','角色记住了城门线索',[source('entity','actor-one',entity,'public')],**options)


def test_draft_is_not_fact_and_confirmed_memory_survives_restart(setup):
    host,service,_=setup;memory=Memory(service);entry=create(memory,host)
    assert memory.search('kp')==[]
    entry=memory.confirm('kp',entry['memoryId'],1)
    assert memory.search('kp','城门')[0]['revision']==2
    pack=service.pack;service.close();host.close();host.__init__(host.path)
    restarted=Proposals(host,pack)
    try:assert Memory(restarted).search('kp','城门')[0]['memoryId']==entry['memoryId']
    finally:restarted.close()


def test_source_change_invalidates_memory_and_descendants(setup):
    host,service,_=setup;memory=Memory(service);entry=create(memory,host);entry=memory.confirm('kp',entry['memoryId'],1)
    derived=memory.create('kp','根据上一条形成的摘要',[source('memory',entry['memoryId'],entry,'kp')]);memory.confirm('kp',derived['memoryId'],1)
    assert len(memory.search('kp'))==2
    state=host.state();state['entities']['actor-one']['revision']+=1;host.commit(state)
    assert memory.search('kp')==[]


def test_stale_ai_store_draft_cannot_reconfirm_revoked_room_memory(setup):
    host, service, _ = setup;memory = Memory(service)
    draft = create(memory, host);confirmed = memory.confirm('kp', draft['memoryId'], 1)
    memory.revoke('kp', draft['memoryId'], confirmed['revision'])
    service.repository.update(lambda data: data['memory'].update({draft['memoryId']: draft}))
    with pytest.raises(AiError, match='MEMORY_STALE'):memory.confirm('kp', draft['memoryId'], 1)
    assert host.state()['aiControl']['memoryFacts'][draft['memoryId']]['status'] == 'revoked'
    assert memory.search('kp')==[]


def test_revoke_and_expiry_never_leave_usable_summary(setup):
    host,service,_=setup;memory=Memory(service);entry=create(memory,host,valid_until=host.clock()+10);entry=memory.confirm('kp',entry['memoryId'],1)
    memory.revoke('kp',entry['memoryId'],2)
    assert memory.search('kp')==[]
    second=create(memory,host,valid_until=host.clock()+10);memory.confirm('kp',second['memoryId'],1)
    now=host.clock()+20;host.clock=lambda:now
    assert memory.search('kp')==[]


def test_secret_summary_cannot_be_downgraded_to_public(setup):
    host,service,_=setup;state=host.state();state['entities']['actor-one']['metadata']['secret']='KP only';host.commit(state)
    with pytest.raises(AiError,match='MEMORY_VISIBILITY_CONFLICT'):create(Memory(service),host,visibility='public')


def test_player_cannot_confirm_and_private_memory_is_not_shared(setup):
    host,service,_=setup;memory=Memory(service);entry=create(memory,host,visibility='private')
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):memory.confirm('player1',entry['memoryId'],1)
    memory.confirm('kp',entry['memoryId'],1)
    assert memory.search('player1')==[]


def test_scope_fork_does_not_reuse_old_memory(setup):
    host,service,_=setup;memory=Memory(service);entry=create(memory,host);memory.confirm('kp',entry['memoryId'],1)
    from onlinecoc.room_lifecycle import fork_scope
    state=fork_scope(host.state());host.commit(state)
    assert memory.search('kp')==[]


def test_context_approval_binding_tracks_memory_revision(setup):
    host,service,_=setup;memory=Memory(service);entry=create(memory,host);entry=memory.confirm('kp',entry['memoryId'],1)
    state=host.state();state['aiControl']['settings']['externalSources']['kp']=True;host.commit(state)
    context=Context(service);snapshot,payload=context.capture('kp',{'sourceKind':'manual','text':'request'})
    assert snapshot[0]['memoryRefs'] and payload['roomFacts']['memory']
    memory.revoke('kp',entry['memoryId'],2)
    with pytest.raises(DomainError,match='SOURCE_STALE'):context.recheck('kp',snapshot)
