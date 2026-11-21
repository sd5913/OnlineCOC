"""A fresh proposal revision must not inherit another revision's ruling receipt."""
import copy

import pytest

from onlinecoc_ai.rulings import Rulings
from test_coordinator import setup
from test_entrypoints import application, command, committed, delta
from test_session_restart import reopen


def item(app):
    return app.rulings.list('kp')['items'][0]


def approve_args(value):
    return {'rulingId': value['rulingId'], 'digest': value['digest'], 'decision': 'approve',
            'explicitHighRiskDigest': value['digest'],
            'riskDecisions': {r['id']: 'Explicitly accept this test risk' for r in value['risks']}}


def create_checked(app):
    proposal = committed(command(app, 'ai.draft.create', {'text': 'Change configuration', 'changeSet': delta()}))
    check = committed(command(app, 'ai.proposal.validate', {'proposalId': proposal['proposalId'], 'revision': 1}))
    assert all(r['status'] == 'pass' for r in check['reports'])
    assert item(app)['highRisk'] and item(app)['status'] == 'pending'
    return proposal


@pytest.mark.parametrize('legacy', [False, True])
def test_restart_revise_same_digest_requires_fresh_manual_approval(application, legacy):
    original = application
    proposal = create_checked(original)
    before = original.repository.state()['contexts'][proposal['contextRef']]
    current = reopen(original)
    try:
        args = approve_args(item(current))
        blocked = committed(command(current, 'ai.ruling.decide', args, identifier='old-approval'))
        assert blocked['status'] == 'blocked'
        assert len(blocked['receipts']) == 1
        old_receipt = copy.deepcopy(blocked['receipts'][0])
        assert old_receipt['status'] == 'rejected' and old_receipt['code'] == 'STALE_AUTHORITY'
        assert not current.host.state()['aiControl']['approvals']
        assert not current.host.state()['aiControl']['publications']
        if legacy:
            current.repository.update(lambda s: s['settings']['rulingDecisions'][args['rulingId']].pop('proposalRevision', None))
        old_decision = copy.deepcopy(current.repository.state()['settings']['rulingDecisions'])
        assert item(current)['status'] == 'blocked'  # same revision remains rejected
        assert command(current, 'ai.ruling.decide', args)['code'] == 'RULING_NOT_READY'
        revised = committed(command(current, 'ai.proposal.revise', {
            'proposalId': proposal['proposalId'], 'revision': 1, 'changeSet': delta()}))
        assert revised['revision'] == 2 and revised['candidateDigest'] == proposal['candidateDigest']
        context = current.repository.state()['contexts'][revised['contextRef']]
        assert context['authorityEpoch'] == current.host.epoch != before['authorityEpoch']
        assert context['sourceRefs'] == before['sourceRefs'] and context['facts'] == before['facts']
        assert item(current)['status'] == 'draft' and item(current)['receipts'] == []
        assert command(current, 'ai.ruling.decide', args)['code'] == 'RULING_NOT_READY'
        check = committed(command(current, 'ai.proposal.validate', {'proposalId': proposal['proposalId'], 'revision': 2}))
        assert all(r['status'] == 'pass' for r in check['reports'])
        fresh = item(current)
        assert fresh['status'] == 'pending' and fresh['receipts'] == [] and fresh['publications'] == []
        assert current.repository.state()['settings']['rulingDecisions'] == old_decision  # read does not migrate/delete history
        args = approve_args(fresh)
        assert command(current, 'ai.ruling.decide', args, 'player1')['code'] == 'PERMISSION_DENIED'
        assert command(current, 'ai.ruling.decide', {k: v for k, v in args.items() if k != 'explicitHighRiskDigest'})['code'] == 'HIGH_RISK_REVIEW_REQUIRED'
        assert command(current, 'ai.ruling.decide', {**args, 'riskDecisions': {}})['code'] == 'RISK_REVIEW_REQUIRED'
        assert not current.host.state()['aiControl']['publications']
        done = committed(command(current, 'ai.ruling.decide', args))
        assert done['status'] == 'completed'
        assert len(done['receipts']) == 2
        assert all(r['commandId'].startswith('ai-ruling:' + proposal['proposalId'] + ':2:') for r in done['receipts'])
        assert current.repository.state()['settings']['rulingDecisions'][args['rulingId']]['proposalRevision'] == 2
        assert current.host.receipt('kp', old_receipt['commandId']) == old_receipt
        assert current.receipt('kp', 'old-approval')['result']['receipts'] == [old_receipt]
        assert current.host.state()['configurations']['fixture.token']['defaults']['bonus'] == 15
        assert committed(command(current, 'ai.ruling.decide', args))['status'] == 'completed'
        assert len(current.host.state()['aiControl']['publications']) == 1
        current = reopen(current)
        assert item(current)['status'] == 'completed'
        assert committed(command(current, 'ai.ruling.decide', args))['status'] == 'completed'
        assert len(current.host.state()['aiControl']['publications']) == 1
        assert current.host.receipt('kp', old_receipt['commandId']) == old_receipt
    finally:
        current.proposals.close()
        current.host.close()


@pytest.mark.parametrize('status', ['unknown', 'executing'])
def test_legacy_unbound_intent_still_blocks_after_revision_and_reopen(application, status):
    app = application
    proposal = create_checked(app)
    old = {'digest': proposal['candidateDigest'], 'status': status, 'decidedBy': 'kp', 'receipts': []}
    rid = 'proposal:' + proposal['proposalId']
    app.repository.update(lambda s: s['settings'].setdefault('rulingDecisions', {}).update({rid: old}))
    committed(command(app, 'ai.proposal.revise', {'proposalId': proposal['proposalId'], 'revision': 1, 'changeSet': delta()}))
    committed(command(app, 'ai.proposal.validate', {'proposalId': proposal['proposalId'], 'revision': 2}))
    current = reopen(app)
    try:
        assert item(current)['status'] == status
        assert command(current, 'ai.ruling.decide', approve_args(item(current)))['code'] == 'RULING_NOT_READY'
        assert current.repository.state()['settings']['rulingDecisions'][rid] == old
        assert not current.host.state()['aiControl']['approvals']
        assert not current.host.state()['aiControl']['publications']
    finally:
        current.proposals.close()
        current.host.close()


@pytest.mark.parametrize('revision,receipt_ids,keep', [
    (1, [], False), (2, [], True),
    (None, ['ai-ruling:p:1:approve'], False),
    (None, ['ai-ruling:p:1:approve', 'ai-ruling:p:1:apply'], False),
    (None, ['ai-ruling:p:2:approve', 'ai-ruling:p:2:apply'], True),
    (None, ['ai-ruling:other:1:approve'], True),
    (None, ['ai-ruling:p:1:approve:extra'], True),
    (None, ['ai-ruling:p:1:approve', 'ai-ruling:p:2:apply'], True),
    (None, ['ai-ruling:p:0:approve'], True),
    (None, ['ai-ruling:p:01:approve'], True),
    (None, ['ai-ruling:p:1:approve', 'unrelated'], True),
    (2, ['ai-ruling:p:1:approve'], True),
    (True, [], True), ('1', [], True),
])
def test_decision_binding_requires_unambiguous_exact_revision(revision, receipt_ids, keep):
    decision = {'digest': 'same', 'status': 'blocked', 'receipts': [{'commandId': x} for x in receipt_ids]}
    if revision is not None:decision['proposalRevision'] = revision
    before = copy.deepcopy(decision)
    result = Rulings.decision_for_revision(decision, {'proposalId': 'p', 'revision': 2, 'candidateDigest': 'same'})
    assert result == (decision if keep else {})
    assert decision == before


@pytest.mark.parametrize('status,keep', [('blocked', False), ('completed', False), ('unknown', True), ('executing', True)])
def test_unbound_unknown_intent_cannot_be_erased_by_a_different_digest(status, keep):
    decision = {'digest': 'old', 'status': status, 'receipts': []}
    result = Rulings.decision_for_revision(decision, {'proposalId': 'p', 'revision': 2, 'candidateDigest': 'new'})
    assert result == (decision if keep else {})


def test_same_revision_different_candidate_never_inherits_decision_receipts():
    decision = {'digest': 'old', 'status': 'blocked', 'proposalRevision': 2,
                'receipts': [{'commandId': 'ai-ruling:p:2:approve'}]}
    assert Rulings.decision_for_revision(decision, {'proposalId': 'p', 'revision': 2, 'candidateDigest': 'new'}) == {}
