"""Real HTTP boundary and application workflows; no provider credentials."""
import copy
import uuid
from types import SimpleNamespace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from onlinecoc.server import create_app
from onlinecoc import chat
from onlinecoc_ai.api import Application
from onlinecoc_ai.context import Context
from onlinecoc_ai.coordinator import Coordinator
from onlinecoc_ai.contracts import loads
from onlinecoc_ai.errors import AiError
from test_coordinator import setup
from test_context import add_message, enable


@pytest.fixture
def application(setup):
    host, proposals, profile = setup
    coordinator = Coordinator(proposals, {profile['profileId']: profile}, context=Context(proposals))
    runtime = SimpleNamespace(proposals=proposals, coordinator=coordinator)
    return Application(runtime)


def command(app, op, args, account='kp', identifier=None):
    return app.command(account, {'requestId': identifier or uuid.uuid4().hex,
        'authorityEpoch': app.host.epoch, 'op': op, 'args': args})


def committed(receipt):
    assert receipt['status'] == 'committed', receipt
    return receipt['result']


def delta():
    return loads((Path(__file__).parents[1] / 'examples/bonus-15.json').read_bytes())


def settings(auto=False):
    return {'enabled': True, 'profileId': 'deepseek-main', 'externalSources': {'public': True, 'private': False, 'kp': False},
        'auto': {'enabled': auto, 'channelIds': ['general'], 'prefix': '!ai '}}


def test_requests_are_explicit_idempotent_redacted_and_paged(application):
    app = application
    committed(command(app,'ai.access.update',{'revision':1,'allowPlayerChat':True,'autoApproveBatches':False}))
    one = command(app, 'ai.request.create', {'sourceKind': 'manual', 'text': 'secret request'}, 'player1', 'one')
    assert command(app, 'ai.request.create', {'sourceKind': 'manual', 'text': 'secret request'}, 'player1', 'one') == one
    committed(one)
    with pytest.raises(AiError, match='COMMAND_ID_CONFLICT'):
        command(app, 'ai.request.create', {'sourceKind': 'manual', 'text': 'changed'}, 'player1', 'one')
    assert app.tasks('player2')['items'] == []
    assert app.tasks('player1')['items'][0]['text'] == 'secret request' and not app.tasks('player1')['items'][0].get('response')
    assert app.tasks('kp')['items'][0]['text'] == 'secret request'
    assert not app.repository.state()['tasks']  # A pack without knowledge support cannot dispatch PL.
    denied = command(app, 'ai.request.dispatch', {'requestId':one['result']['requestId']}, 'player1')
    assert denied['code'] == 'PERMISSION_DENIED'
    committed(command(app, 'ai.request.create', {'sourceKind': 'manual', 'text': 'second'}))
    page = app.tasks('kp', limit=1)
    assert page['nextBefore'] and len(app.tasks('kp', page['nextBefore'])['items']) == 1
    assert app.receipt('player2', 'one')['status'] == 'unknown'


def test_chat_forwarding_binds_original_and_policy(application):
    app = application; message = add_message(app.host, 'player1', '!ai make item')
    args = {'sourceKind': 'chat', 'channelId': 'general', 'sourceId': message['messageId'], 'sourceRevision': message['revision'], 'text': message['text']}
    request = committed(command(app, 'ai.request.create', args))
    assert committed(command(app, 'ai.request.create', {**args, 'sourceRevision': str(message['revision'])})) == request
    assert app.tasks('kp')['items'][0]['text'] == message['text']  # review allowed before external consent
    assert command(app, 'ai.request.dispatch', request)['code'] == 'EXTERNAL_SCOPE_DISABLED'
    committed(command(app, 'ai.settings.update', settings()))
    task = committed(command(app, 'ai.request.dispatch', request))
    assert app.repository.state()['requests'][task['taskId']]['initiator'] == 'player1'
    assert committed(command(app, 'ai.request.dispatch', request))['taskId'] == task['taskId']
    committed(command(app, 'ai.request.cancel', request, 'player1'))
    assert app.repository.state()['tasks'][task['taskId']]['status'] == 'cancelled'
    assert command(app, 'ai.request.create', {**args, 'text': 'forged'})['code'] == 'SOURCE_STALE'


def test_player_can_cancel_after_dispatching_kp_loses_role(application):
    from test_known_runtime import install
    install(application)
    app = application
    request = committed(command(app, 'ai.request.create', {'sourceKind': 'manual', 'text': 'my request'}, 'player1'))
    request={'requestId':request['requestId']}
    task = committed(command(app, 'ai.request.dispatch', request))
    assert command(app, 'ai.request.cancel', request, 'player2')['code'] == 'PERMISSION_DENIED'
    state = app.host.state();state['members']['kp']['role'] = 'player';app.host.commit(state)
    committed(command(app, 'ai.request.cancel', request, 'player1'))
    assert app.repository.state()['tasks'][task['taskId']]['status'] == 'cancelled'


def test_plan_without_proposal_rechecks_context_on_read(application):
    import asyncio
    from test_coordinator import Fake, completion, wait_task
    app = application;enable(app.host, public=True)
    add_message(app.host, 'player1', 'context source')
    async def callback(*args):return completion({'kind': 'plan', 'text': 'sensitive generated plan'})
    async def run():
        app.coordinator.provider_factory = lambda p: Fake(callback)
        await app.coordinator.start()
        try:
            request = committed(command(app, 'ai.request.create', {'sourceKind': 'manual', 'text': 'make plan'}))
            task = committed(command(app, 'ai.request.dispatch', request))
            assert (await wait_task(app.coordinator, task['taskId']))['status'] == 'review_ready'
            assert app.tasks('kp')['items'][0]['response'] == 'sensitive generated plan'
            state = app.host.state();state['chat']['messages']['general'][0].update(deleted=True, text='', revision=2);app.host.commit(state)
            assert app.tasks('kp')['items'][0]['status'] == 'stale'
            assert 'response' not in app.tasks('kp')['items'][0]
        finally:await app.coordinator.close()
    asyncio.run(run())


def test_auto_off_prefix_dedup_edits_withdrawal_and_role(application):
    app = application
    add_message(app.host, 'player1', '!ai old')
    app.scan_auto(); assert not app.repository.state()['tasks']
    committed(command(app, 'ai.settings.update', settings(True)))
    app.scan_auto(); assert not app.repository.state()['tasks']
    add_message(app.host, 'player1', 'ordinary chat')
    message = add_message(app.host, 'player1', '!ai new')
    app.scan_auto(); app.scan_auto()
    assert len(app.repository.state()['tasks']) == 1
    state = app.host.state(); target = state['chat']['messages']['general'][-1]
    target['revision'] += 1; target['text'] = '!ai revised'; app.host.commit(state)
    app.scan_auto()
    assert sorted(t['status'] for t in app.repository.state()['tasks'].values()) == ['cancelled', 'queued']
    state = app.host.state(); target = state['chat']['messages']['general'][-1]
    target.update(deleted=True, text='', revision=target['revision'] + 1); app.host.commit(state)
    app.scan_auto(); app.scan_auto()
    assert all(t['status'] == 'cancelled' for t in app.repository.state()['tasks'].values())
    add_message(app.host, 'player1', '!ai after demotion')
    state = app.host.state(); state['members']['kp']['role'] = 'player'; app.host.commit(state)
    app.scan_auto(); assert len(app.repository.state()['tasks']) == 2


def host_command(app, op, args, identifier):
    return app.host.command('kp', {'protocolVersion': 1, 'type': 'command', 'requestId': identifier,
        'roomId': app.host.state()['roomId'], 'payload': {'commandId': identifier,
        'authorityEpoch': app.host.epoch, 'op': op, 'args': args}})


def test_manual_revision_invalidates_approval_and_cancel_revokes(application):
    app = application
    proposal = committed(command(app, 'ai.draft.create', {'text': 'manual', 'changeSet': delta()}, identifier='create'))
    assert app.tasks('kp')['items'][0]['proposalId'] == proposal['proposalId']
    committed(command(app, 'ai.proposal.validate', {'proposalId': proposal['proposalId'], 'revision': 1}))
    args = {'proposalId': proposal['proposalId'], 'proposalRevision': 1,
        'riskDecisions': {'choice-value': 'limited charges preserve choice', 'gameplay-risk': 'accept bounded gain'}}
    approval = committed(host_command(app, 'ai.proposal.approve', args, 'approve'))
    changed = delta(); changed['configurations'][0]['value']['defaults']['bonus'] = 5
    revised = committed(command(app, 'ai.proposal.revise', {'proposalId': proposal['proposalId'], 'revision': 1, 'changeSet': changed}))
    assert revised['revision'] == 2 and revised['reportRefs'] == []
    assert host_command(app, 'publication.apply', {'approvalId': approval['approvalId']}, 'old-load')['status'] == 'rejected'
    committed(command(app, 'ai.proposal.validate', {'proposalId': proposal['proposalId'], 'revision': 2}))
    args['proposalRevision'] = 2
    args['riskDecisions'].pop('gameplay-risk')
    approval = committed(host_command(app, 'ai.proposal.approve', args, 'approve-new'))
    committed(command(app, 'ai.request.cancel', {'requestId': proposal['requestId']}))
    assert host_command(app, 'publication.apply', {'approvalId': approval['approvalId']}, 'cancelled-load')['status'] == 'rejected'
    assert app.host.state()['configurations']['fixture.token']['defaults']['bonus'] == 0


def test_receipt_rechecks_private_sources_and_restart_pending(application):
    app = application; host = app.host
    state = host.state();state['chat']['channels']['group'] = chat.channel('group', 'group', 'private', ['kp', 'player1']);state['chat']['messages']['group'] = [];host.commit(state)
    message = add_message(host, 'player1', 'private evidence', 'group')
    receipt = command(app, 'ai.memory.create', {'content': 'sensitive summary', 'visibility': 'private', 'sourceRefs': [
        {'kind': 'message', 'id': message['messageId'], 'channelId': 'group', 'revision': message['revision'], 'visibility': 'private'}]}, identifier='secret')
    committed(receipt)
    state = host.state();state['chat']['channels']['group']['participants'].remove('kp');host.commit(state)
    assert 'result' not in app.receipt('kp', 'secret')
    app.repository.update(lambda s: s['commands'].update({'api:kp:unfinished': {'receipt': {'requestId': 'unfinished', 'status': 'pending'}}}))
    directory = app.repository.store.path;app.repository.close()
    from onlinecoc_ai.repository import Repository
    app.proposals.repository = app.repository = Repository(directory, host.state()['aiControl']['scopeId'])
    assert app.receipt('kp', 'unfinished')['status'] == 'unknown'
    assert app.receipt('kp', 'unfinished')['code'] == 'PROCESS_RESTARTED'


def test_http_auth_limits_schema_capability_and_disabled_module(application):
    service = application
    committed(command(service,'ai.access.update',{'revision':1,'allowPlayerChat':True,'autoApproveBatches':False}))
    async def idle():pass
    runtime = SimpleNamespace(application=service, start=idle, close=idle)
    app = create_app(service.host, ai_runtime=runtime)
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        assert client.get('/api/v1/ai/settings').status_code == 401
        assert client.get('/api/v1/capabilities').json()['ai']['available']
        assert client.post('/api/v1/ai/commands', json={}).status_code == 403
        client.headers['origin'] = 'http://127.0.0.1:8765'
        csrf = client.post('/api/v1/login', json={'loginName': 'player1', 'password': 'test-password'}).json()['csrf']
        assert client.post('/api/v1/ai/commands', json={}).status_code == 403
        client.headers['x-csrf-token'] = csrf
        assert client.get('/api/v1/ai/settings').status_code == 403
        assert client.post('/api/v1/ai/commands', content='x' * 65537).status_code == 413
        assert client.post('/api/v1/ai/drafts', content='x' * (8 * 1024 * 1024 + 1)).status_code == 413
        assert client.post('/api/v1/ai/drafts', json=[]).status_code == 409
        envelope = {'requestId': 'http', 'authorityEpoch': service.host.epoch, 'op': 'ai.request.create', 'args': {'text': 'HTTP player request', 'sourceKind': 'manual'}}
        receipt = client.post('/api/v1/ai/commands', json=envelope).json();committed(receipt)
        assert client.get('/api/v1/ai/receipts/http').json() == receipt
        envelope['args']['extra'] = True
        assert client.post('/api/v1/ai/commands', json=envelope).json()['code'] == 'INPUT_INVALID'
        assert client.get('/api/v1/ai/tasks?limit=101').status_code == 409
    with TestClient(create_app(service.host), base_url='http://127.0.0.1:8765') as client:
        assert not client.get('/api/v1/capabilities').json()['ai']['available']
        assert client.get('/api/v1/ai/tasks').status_code == 404


def test_cli_uses_same_three_engines(validation_case, tmp_path, capsys):
    from onlinecoc_ai.cli import main
    from onlinecoc_ai.contracts import canonical
    from onlinecoc_ai.validation.base import check_base
    from onlinecoc_ai.validation.rules import check_rules
    from onlinecoc_ai.validation.gameplay import assess
    from onlinecoc_ai.validation.common import static_context
    pack, state, artifact, _, changes = validation_case
    context = static_context(pack, state, artifact)
    changes_file = tmp_path / 'changes.json'; changes_file.write_bytes(canonical(changes))
    state_file = tmp_path / 'state.json'; state_file.write_bytes(canonical(state))
    for name, function in [('check-base', check_base), ('check-rules', check_rules), ('assess', assess)]:
        direct = function(pack, state, artifact, context, changes)
        if isinstance(direct, tuple):direct = direct[0]
        assert main([name, '--pack', str(pack.root), '--changes', str(changes_file), '--state', str(state_file)]) == 0
        output = loads(capsys.readouterr().out)
        for key in ('status', 'risk', 'coverage', 'findings', 'reviewItems', 'evidence'):
            assert output[key] == direct[key], key
