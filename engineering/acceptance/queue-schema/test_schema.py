"""Queue metadata contracts: strict inputs and compatibility with existing callers."""
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
OPERATIONS = json.loads((ROOT / 'contracts/ai-operations.json').read_text(encoding='utf-8'))
DEFS = json.loads((ROOT / 'contracts/ai.json').read_text(encoding='utf-8'))['$defs']
ID = 'a' * 32
DIGEST = 'b' * 64
PACKAGE = {'kind': 'package', 'sourceId': 'stumpsville', 'category': 'event', 'id': 'event-1',
           'revision': '1', 'title': 'Review', 'summary': 'Review this event'}


def valid(op, args):
    return Draft202012Validator({**OPERATIONS[op], '$defs': DEFS}).is_valid(args)


def archive(**changes):
    return {'targetId': 'request:' + ID, 'digest': DIGEST, 'archived': True, 'reason': 'Reviewed', **changes}


def test_all_operation_schemas_are_well_formed():
    for schema in OPERATIONS.values():Draft202012Validator.check_schema({**schema, '$defs': DEFS})


@pytest.mark.parametrize('op,args', [
    ('ai.session.submit', {'sessionId': ID, 'text': 'Existing submit'}),
    ('ai.player.request', {'sessionId': ID, 'text': 'Existing request'}),
    ('ai.player.request', {'sessionId': ID, 'requestId': ID}),
    ('ai.review.create', {'source': PACKAGE}),
    ('ai.review.create', {'source': {'kind': 'request', 'requestId': ID}}),
    ('ai.review.create', {'source': {'kind': 'ruling', 'rulingId': 'proposal:' + ID, 'digest': DIGEST}}),
])
def test_legacy_call_shapes_remain_valid(op, args):
    assert valid(op, args)


@pytest.mark.parametrize('kind', ['request', 'batch', 'proposal', 'player', 'knowledge'])
def test_archive_targets_and_conditional_reason(kind):
    for reason in ['x', 'x'*500]:
        assert valid('ai.queue.archive', archive(targetId=kind+':'+ID, reason=reason))
    restore = {'targetId': kind+':'+ID, 'digest': DIGEST, 'archived': False}
    assert valid('ai.queue.archive', restore)
    assert valid('ai.queue.archive', {**restore, 'reason': 'Restore to queue'})
    assert not valid('ai.queue.archive', {**restore, 'archived': True})


@pytest.mark.parametrize('size', [1, 200])
@pytest.mark.parametrize('op', ['ai.session.submit', 'ai.player.request', 'ai.review.create'])
def test_optional_keys_accept_both_length_boundaries(op, size):
    args = {'sessionId': ID, 'text': 'new text', 'submissionKey': 'k'*size}
    if op == 'ai.session.submit':args['replyToRequestId'] = ID
    if op == 'ai.review.create':args = {'source': {**PACKAGE, 'correlationKey': 'k'*size}}
    assert valid(op, args)


@pytest.mark.parametrize('target', ['request', 'request:'+ID[:-1], 'request:'+ID+'a', 'request:'+ID.upper(),
    'request:'+'g'*32, 'unknown:'+ID, 'request:'+ID+'\n', 'batch:'+ID+'\n', 'request:'+ID+':extra'])
def test_archive_target_is_an_exact_typed_identifier(target):
    assert not valid('ai.queue.archive', archive(targetId=target))


@pytest.mark.parametrize('change', [
    {'digest': DIGEST[:-1]}, {'digest': DIGEST+'b'}, {'digest': DIGEST.upper()}, {'digest': DIGEST+'\n'},
    {'digest': None}, {'archived': 'true'}, {'archived': 1}, {'archived': None},
    {'reason': ''}, {'reason': 'x'*501}, {'reason': None}, {'reason': 1},
    {'status': 'cancelled'}, {'queueDigest': DIGEST}, {'accountId': 'kp'},
])
def test_archive_rejects_bad_types_lengths_and_unknown_fields(change):
    assert not valid('ai.queue.archive', archive(**change))


@pytest.mark.parametrize('field', ['targetId', 'digest', 'archived'])
def test_archive_required_fields(field):
    args = archive(); del args[field]
    assert not valid('ai.queue.archive', args)


@pytest.mark.parametrize('value', ['', 'x'*201, None, 123])
def test_optional_key_constraints_apply_in_all_three_modes(value):
    assert not valid('ai.session.submit', {'sessionId': ID, 'text': 'x', 'submissionKey': value})
    assert not valid('ai.player.request', {'sessionId': ID, 'text': 'x', 'submissionKey': value})
    assert not valid('ai.review.create', {'source': {**PACKAGE, 'correlationKey': value}})


@pytest.mark.parametrize('value', [ID[:-1], ID+'a', ID.upper(), ID+'\n', None])
def test_reply_requires_exact_lowercase_id(value):
    assert not valid('ai.session.submit', {'sessionId': ID, 'text': 'x', 'replyToRequestId': value})


def test_new_fields_cannot_leak_into_other_modes():
    assert not valid('ai.player.request', {'sessionId': ID, 'requestId': ID, 'submissionKey': 'key'})
    assert not valid('ai.player.request', {'sessionId': ID, 'requestId': ID, 'text': 'x', 'submissionKey': 'key'})
    assert not valid('ai.player.request', {'sessionId': ID, 'text': 'x', 'replyToRequestId': ID})
    for source in [{'kind': 'ruling', 'rulingId': 'proposal:'+ID}, {'kind': 'request', 'requestId': ID}]:
        assert not valid('ai.review.create', {'source': {**source, 'correlationKey': 'key'}})
    assert not valid('ai.review.create', {'source': PACKAGE, 'correlationKey': 'key'})
    assert not valid('ai.session.submit', {'sessionId': ID, 'text': 'x', 'extra': True})
    assert valid('ai.session.submit', {'sessionId': ID, 'text': 'x', 'replyToRequestId': ID})
