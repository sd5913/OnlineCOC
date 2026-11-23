"""Host-only history authorization: real stores/providers, no AI module imports."""
import copy

import pytest

from onlinecoc import publication
from onlinecoc.ai_contracts import digest
from onlinecoc.data_queries import query
from onlinecoc.errors import DomainError, require
from onlinecoc.room_lifecycle import fork_scope
from onlinecoc_data import canonical
from ai_helpers import ai_message
from test_high_risk_commands import host, prepared, approve, approval_args, remove
from test_knowledge import descriptor, provider, install, observe, command


def context(host):
    value = prepared(host)['context']
    state = host.state()
    value['facts'].update(externalPolicyDigest=digest(state['aiControl']['settings']['externalSources']),
                          profileId=state['aiControl']['settings']['profileId'])
    return value


def restart(host):
    old_epoch = host.epoch
    host.close()
    host.__init__(host.path)
    assert host.epoch != old_epoch


def read(host, value, account='kp'):
    with host.lock:
        return publication.check_history_context(host, host.state(), account, value)


def test_same_directory_restart_reads_original_context_without_writes(host):
    value = context(host)
    before = canonical(value)
    scope = value['scopeId']
    restart(host)
    generation = host.store.generation
    identity_generation = host.identity.store.generation
    room = canonical(host.state())
    assert host.state()['aiControl']['scopeId'] == scope
    assert read(host, value) is None
    assert canonical(value) == before
    assert canonical(host.state()) == room
    assert host.store.generation == generation
    assert host.identity.store.generation == identity_generation
    with pytest.raises(DomainError, match='STALE_AUTHORITY'):
        publication.check_context(host, host.state(), 'kp', value)


def test_history_does_not_renew_old_approval_or_new_execution(host):
    bundle = prepared(host, [remove()])
    approval_id = approve(host, bundle)
    old_command = ai_message(host, 'entity.patch', {'id':'actor-player1','name':'must not execute'}, 'unexecuted')
    restart(host)
    assert read(host, bundle['context']) is None
    state = canonical(host.state())
    with pytest.raises(DomainError, match='STALE_AUTHORITY'):
        host.command('kp', old_command)
    assert canonical(host.state()) == state
    response = host.command('kp', ai_message(host, 'publication.apply', {'approvalId':approval_id}, 'publish-old'))
    assert response['status'] == 'rejected' and response['code'] == 'STALE_AUTHORITY'
    assert not host.state()['aiControl']['publications']
    assert host.state()['aiControl']['approvals'][approval_id]['status'] == 'approved'
    host.ai_prepared_resolver = lambda *args: copy.deepcopy(bundle)
    response = host.command('kp', ai_message(host, 'ai.proposal.approve', approval_args(bundle), 'approve-old'))
    assert response['status'] == 'rejected' and response['code'] == 'STALE_AUTHORITY'
    assert bundle['context']['authorityEpoch'] != host.epoch


def test_reading_history_does_not_depend_on_execution_validator_code(host, monkeypatch):
    value = context(host)
    state = host.state()
    state['aiControl']['packBinding']['validatorSetDigest'] = 'b' * 64
    host.commit(state)
    def no_validator_read():
        raise AssertionError('read-only history must not load execution checker files')
    monkeypatch.setattr(publication, 'validator_digest', no_validator_read)
    assert read(host, value) is None
    with pytest.raises(DomainError, match='VALIDATOR_STALE'):
        publication.check_context(host, host.state(), 'kp', value)
    assert value['validatorSetDigest'] == 'a' * 64


@pytest.mark.parametrize('change,code', [
    ('inactive','PERMISSION_DENIED'), ('role','PERMISSION_DENIED'),
    ('authorization','PERMISSION_DENIED'), ('scope','SCOPE_MISMATCH'),
    ('contract','VALIDATOR_STALE'), ('ruleset','BASELINE_STALE'),
    ('configuration','BASELINE_STALE'), ('world','BASELINE_STALE'),
    ('external','EXTERNAL_SCOPE_CHANGED'), ('profile','PROFILE_CHANGED'),
])
def test_history_preserves_authorization_scope_baseline_and_egress_checks(host, change, code):
    value = context(host)
    restart(host)
    state = host.state()
    if change == 'inactive':state['members']['kp']['active'] = False
    elif change == 'role':state['members']['kp']['role'] = 'player'
    elif change == 'authorization':state['members']['kp']['authorizationEpoch'] += 1
    elif change == 'scope':state = fork_scope(state)
    elif change == 'contract':state['aiControl']['packBinding']['digest'] = 'b' * 64
    elif change == 'ruleset':state['activeRuleset'] = 'new-rule-revision'
    elif change == 'configuration':state['configurations']['demo.actor']['revision'] = '2'
    elif change == 'world':state['entities']['actor-player1']['name'] = 'Changed'
    elif change == 'external':state['aiControl']['settings']['externalSources']['private'] = True
    elif change == 'profile':state['aiControl']['settings']['profileId'] = 'another-profile'
    before = canonical(value)
    with pytest.raises(DomainError, match=code):
        publication.check_history_context(host, state, 'kp', value)
    assert canonical(value) == before


def test_history_rechecks_session_access_callback(host):
    value = context(host)
    restart(host)
    called = []
    def denied(state, saved):
        called.append(saved['authorityEpoch'])
        require(False, 'PERMISSION_DENIED')
    host.ai_access_validator = denied
    with pytest.raises(DomainError, match='PERMISSION_DENIED'):
        read(host, value)
    assert called == [value['authorityEpoch']]


@pytest.mark.parametrize('change', ['revised', 'deleted', 'permission'])
def test_history_rechecks_chat_sources_after_restart(host, change):
    result = command(host, 'chat.message.send', {'channelId':'general','text':'original testimony'})
    assert result['status'] == 'committed'
    value = context(host)
    state = host.state()
    message = state['chat']['messages']['general'][0]
    value['sourceRefs'] = [{'kind':'message','id':message['messageId'],'revision':str(message['revision']),
                            'channelId':'general','visibility':'public','digest':digest(message)}]
    restart(host)
    assert read(host, value) is None
    state = host.state()
    if change == 'revised':state['chat']['messages']['general'][0]['revision'] += 1
    elif change == 'deleted':state['chat']['messages']['general'][0]['deleted'] = True
    else:
        state['chat']['channels']['general'].update(kind='direct', participants=['player1','player2'])
    with pytest.raises(DomainError, match='SOURCE_STALE|PERMISSION_DENIED'):
        publication.check_history_context(host, state, 'kp', value)


def test_history_replays_query_proofs_against_current_sources(host):
    state = host.state()
    state['aiControl']['settings']['externalSources'].update(public=True, kp=True, private=True)
    host.commit(state)
    result = command(host, 'chat.message.send', {'channelId':'general','text':'original testimony'})
    assert result['status'] == 'committed'
    value = context(host)
    args = {'channelId':'general'}
    response = query(host, host.state(), 'kp', 'chat', args, initiator='kp', external=True)
    value['facts']['dataQueries'] = [{'scopeId':value['scopeId'], 'operation':'chat', 'args':args,
                                     'initiator':'kp', 'digest':digest(response)}]
    restart(host)
    assert read(host, value) is None
    result = command(host, 'chat.message.send', {'channelId':'general','text':'new testimony'})
    assert result['status'] == 'committed'
    with pytest.raises(DomainError, match='SOURCE_STALE'):
        read(host, value)


def player_context(host):
    install(host)
    observation = observe(host)
    value = context(host)
    refs = [row['ref'] for row in host.knowledge.search('player1', {})['items']]
    value.update(initiator='player1', reviewPrincipal='player1',
                 authorizationEpoch=host.state()['members']['player1']['authorizationEpoch'])
    value['facts'].update(strictPlayer=True, sessionAccess={'level':'player','owner':'player1'},
                          knowledgeProofs=[host.knowledge.evidence('player1', refs, player=True)])
    return value, observation


@pytest.mark.parametrize('change', ['none', 'revoke', 'missing-provider', 'hard-guard', 'other-account', 'scope', 'policy', 'authorization', 'inactive'])
def test_player_history_uses_current_knowledge_authorization(host, change):
    value, observation = player_context(host)
    before = canonical(value)
    restart(host)
    if change != 'missing-provider':host.register_knowledge_provider(descriptor(), provider())
    if change == 'none':
        assert read(host, value, 'player1') is None
        with pytest.raises(DomainError, match='STALE_AUTHORITY'):
            publication.check_context(host, host.state(), 'player1', value)
    else:
        state = host.state()
        if change == 'revoke':
            result = command(host, 'knowledge.revoke', {'grantId':observation['grantId'], 'expectedRevision':1, 'reason':'withdraw'})
            assert result['status'] == 'committed'
            state = host.state()
        elif change == 'hard-guard':state['entities']['actor-player1']['metadata']['knowledgeRevoked'] = True
        elif change == 'other-account':value['facts']['sessionAccess']['owner'] = 'player2'
        elif change == 'scope':state = fork_scope(state)
        elif change == 'policy':state['knowledge']['policies']['case-files']['descriptorDigest'] = 'b' * 64
        elif change == 'authorization':state['members']['player1']['authorizationEpoch'] += 1
        elif change == 'inactive':state['members']['player1']['active'] = False
        with pytest.raises(DomainError):
            publication.check_history_context(host, state, 'player1', value)
    if change != 'other-account':assert canonical(value) == before


def test_history_requires_complete_context_and_does_not_allow_player_to_read_kp(host):
    value = context(host)
    with pytest.raises(DomainError, match='PERMISSION_DENIED'):
        read(host, value, 'player1')
    value.pop('authorityEpoch')
    with pytest.raises(DomainError, match='AI_INPUT_INVALID'):
        read(host, value)


def test_history_does_not_restore_revoked_kp_room_read_access(host):
    value = context(host)
    value['facts']['aiReadScope'] = 'kp-room'
    restart(host)
    with pytest.raises(DomainError, match='PERMISSION_DENIED'):
        read(host, value)
    host.ai_room_read_authorizer = lambda account: account == 'kp'
    assert read(host, value) is None
    host.ai_room_read_authorizer = lambda account: False
    with pytest.raises(DomainError, match='PERMISSION_DENIED'):
        read(host, value)
