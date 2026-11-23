"""ISSUE-025: staged artifacts must not become active-state evidence."""
import copy
from types import SimpleNamespace

import pytest

from onlinecoc.ai_contracts import digest
from onlinecoc.data_queries import query, recheck, rows
from onlinecoc.errors import DomainError
from ai_helpers import ai_message, approval_args
from test_high_risk_host import world


def room():
    state = world()
    state.update(commands={}, flows={}, waits={})
    for revision in ('staged', 'pending', 'running', 'waiting', 'retry', 'done', 'cancelled'):
        state['artifacts'][revision] = copy.deepcopy(state['artifacts']['r1'])
        state['artifacts'][revision]['revision'] = revision
    state['commands'] = {'management': {'status': 'pending'},
                         'pending': {'status': 'pending', 'ruleset': 'pending'},
                         'done': {'status': 'committed', 'ruleset': 'done'}}
    state['flows'] = {key: {'status': status, 'ruleset': key} for key, status in (
        ('running', 'running'), ('waiting', 'waiting'), ('retry', 'needs_attention'),
        ('done', 'completed'), ('cancelled', 'cancelled'))}
    return SimpleNamespace(ai_room_read_authorizer=lambda account: True), state


def artifacts(host, state, mode='state'):
    return [r for r in rows(host, state, 'kp', kinds=('room',), read_scope='kp-room', room_mode=mode)
            if r['data']['path'][0] == 'artifacts']


def test_state_keeps_only_active_and_executable_versions_with_usage():
    host, state = room()
    before = copy.deepcopy(state)
    result = artifacts(host, state)
    assert {r['data']['path'][1] for r in result} == {'r1', 'pending', 'running', 'waiting', 'retry'}
    for item in result:
        revision = item['data']['path'][1]
        usage = 'active' if revision == 'r1' else 'in-flight'
        assert item['data']['artifactUsage'] == usage
        assert item['label'].startswith('[' + usage + '] ')
        assert item['data']['value'] == state['artifacts'][revision]
    assert state == before
    records = artifacts(host, state, 'records')
    assert {r['data']['path'][1] for r in records} == set(state['artifacts'])
    assert all('artifactUsage' not in r['data'] for r in records)


def test_staging_keeps_search_page_and_exact_read_proofs_stable():
    host, state = room()
    args = {'types': ['room'], 'query': 'artifacts', 'roomMode': 'state', 'limit': 1}
    page = query(host, state, 'kp', 'search', args, read_scope='kp-room')
    assert page['page']['nextCursor']
    ref = page['items'][0]['ref']
    detail = query(host, state, 'kp', 'read', {'refs': [ref]}, read_scope='kp-room')
    state['artifacts']['another-candidate'] = copy.deepcopy(state['artifacts']['r1'])
    assert query(host, state, 'kp', 'search', args, read_scope='kp-room') == page
    assert query(host, state, 'kp', 'read', {'refs': [ref]}, read_scope='kp-room') == detail
    assert query(host, state, 'kp', 'search', {**args, 'cursor': page['page']['nextCursor']}, read_scope='kp-room')['items']


def test_usage_is_retained_on_nested_and_chunked_artifact_data():
    host, state = room()
    state['artifacts']['r1']['sources']['base.lua'] = 'x' * 9000
    result = [r for r in artifacts(host, state) if r['data']['path'][1] == 'r1']
    chunks = [r for r in result if 'textOffset' in r['data']]
    assert len(chunks) > 1
    assert all(r['data']['artifactUsage'] == 'active' and r['label'].startswith('[active] ') for r in result)
    assert ''.join(r['data']['value'] for r in sorted(chunks, key=lambda r: r['data']['textOffset'])) == 'x' * 9000


def test_records_search_still_observes_staging():
    host, state = room()
    args = {'types': ['room'], 'query': 'artifacts'}
    original = query(host, state, 'kp', 'search', args, read_scope='kp-room')
    state['artifacts']['new-stage'] = copy.deepcopy(state['artifacts']['r1'])
    changed = query(host, state, 'kp', 'search', args, read_scope='kp-room')
    assert len(changed['items']) == len(original['items']) + 1
    assert changed['snapshotId'] != original['snapshotId']


@pytest.mark.parametrize('change', ['active-content', 'active-switch', 'inflight-content', 'inflight-finished', 'permission'])
def test_actual_artifact_lifecycle_or_permission_changes_invalidate_proof(change):
    host, state = room()
    args = {'types': ['room'], 'query': 'artifacts', 'roomMode': 'state'}
    result = query(host, state, 'kp', 'search', args, external=True, read_scope='kp-room')
    context = {'facts': {'dataQueries': [{'scopeId': state['aiControl']['scopeId'], 'operation': 'search',
        'args': args, 'initiator': None, 'readScope': 'kp-room', 'digest': digest(result)}]}}
    if change == 'active-content': state['artifacts']['r1']['data']['world.json']['secret'] = 'changed'
    elif change == 'active-switch': state['activeRuleset'] = 'running'
    elif change == 'inflight-content': state['artifacts']['running']['sources']['base.lua'] += ' changed'
    elif change == 'inflight-finished': state['flows']['running']['status'] = 'completed'
    else: host.ai_room_read_authorizer = lambda account: False
    with pytest.raises(DomainError, match='PERMISSION_DENIED' if change == 'permission' else 'SOURCE_STALE'):
        recheck(host, state, 'kp', context)


def test_old_active_exact_reference_changes_when_retained_as_inflight():
    host, state = room()
    state['flows']['old'] = {'status': 'waiting', 'ruleset': 'r1'}
    old = next(r for r in artifacts(host, state) if r['data']['path'][1] == 'r1')
    state['activeRuleset'] = 'running'
    with pytest.raises(DomainError, match='SOURCE_STALE'):
        query(host, state, 'kp', 'read', {'refs': [old['ref']]}, read_scope='kp-room')


def candidate(ai_case):
    from onlinecoc_ai.data_queries import DataQueryService
    host, service, _, _ = ai_case
    state = host.state()
    state['aiControl']['settings']['externalSources'].update(public=True, kp=True, private=True)
    host.commit(state)
    host.ai_room_read_authorizer = lambda account: True
    snapshot = service.snapshot('kp')
    snapshot[0]['facts']['aiReadScope'] = 'kp-room'
    result = DataQueryService(host).attach('kp', 'search', {'types': ['room'], 'query': 'artifacts', 'limit': 50}, snapshot)
    assert result['items'] and result['page']['nextCursor'] is None
    old = snapshot[2]
    filename = next(iter(old['sources']))
    delta = {'schemaVersion': 1, 'configurations': [], 'sources': {filename: old['sources'][filename] + '\n-- ISSUE-025 candidate\n'},
             'data': {}, 'suggestions': []}
    proposal = service.create('kp', 'Append a comment without changing behavior', delta, snapshot=snapshot)
    validated = service.validate('kp', proposal['proposalId'], 1)
    assert validated['proposal']['status'] == 'review_ready', validated
    proposal = validated['proposal']
    prepared = service.prepared('kp', proposal['proposalId'], 1)
    assert {r['level']: r['status'] for r in prepared['reports']} == dict(A='pass', B='pass', C='pass')
    args = approval_args(host, service, proposal)
    if not any(r['risk'] in ('medium', 'high', 'unknown') for r in prepared['reports']) and not prepared.get('cAssessment', {}).get('requiresAcceptance'):
        args['riskDecisions'].pop('gameplay-risk', None)
    response = host.command('kp', ai_message(host, 'ai.proposal.approve', args, 'approve-comment'))
    assert response['status'] == 'committed', response
    assert prepared['artifact']['revision'] in host.state()['artifacts']
    assert host.state()['activeRuleset'] == old['revision']
    return host, response['result']['approvalId'], prepared


def test_real_abc_approve_stage_then_publish_once_without_self_stale(ai_case):
    host, approval, prepared = candidate(ai_case)
    message = ai_message(host, 'publication.apply', {'approvalId': approval}, 'publish-comment')
    result = host.command('kp', message)
    assert result['status'] == 'committed', result
    assert host.state()['activeRuleset'] == prepared['artifact']['revision']
    assert host.command('kp', message) == result
    again = host.command('kp', ai_message(host, 'publication.apply', {'approvalId': approval}, 'publish-again'))
    assert again['result'] == result['result']
    assert len(host.state()['aiControl']['publications']) == 1


@pytest.mark.parametrize('change,code', [('business', 'BASELINE_STALE'), ('active', 'BASELINE_STALE'),
                                       ('permission', 'PERMISSION_DENIED'), ('artifact', 'SOURCE_STALE')])
def test_real_approval_still_rejects_external_change_and_revocation(ai_case, change, code):
    host, approval, prepared = candidate(ai_case)
    state = host.state()
    if change == 'business':
        state['entities']['actor-one']['name'] = 'External change'
        host.commit(state)
    elif change == 'active':
        state['activeRuleset'] = prepared['artifact']['revision']
        host.commit(state)
    elif change == 'permission': host.ai_room_read_authorizer = lambda account: False
    else:
        # The real store rejects modified content-addressed artifacts; exercise the read validator directly.
        state['artifacts'][state['activeRuleset']]['data']['changed.json'] = {'external': True}
        with pytest.raises(DomainError, match=code): recheck(host, state, 'kp', prepared['context'])
        return
    result = host.command('kp', ai_message(host, 'publication.apply', {'approvalId': approval}, 'stale-publish'))
    assert result['status'] == 'rejected' and result['code'] == code, result
    assert not host.state()['aiControl']['publications']
