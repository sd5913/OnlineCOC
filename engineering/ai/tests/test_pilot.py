"""AI-6 uses the actual maintained host demo; no copied Lua or provider calls."""
import copy
from pathlib import Path

import pytest
from onlinecoc.host import Host
from onlinecoc.assets import Assets, restore_host
from onlinecoc_ai.pack import Pack, merge_changes
from onlinecoc_ai.proposals import Proposals
from onlinecoc_ai.contracts import loads, canonical, digest
from onlinecoc_ai.validation.base import check_base
from onlinecoc_ai.validation.rules import check_rules
from onlinecoc_ai.validation.gameplay import assess

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / 'rulepacks/demo'


@pytest.fixture
def pilot(tmp_path):
    host = Host(tmp_path / 'host', bootstrap='test-password')
    service = Proposals(host, Pack(PACK))
    try:yield host, service
    finally:service.close();host.close()


def delta(amount=15):return loads((PACK / f'ai/examples/skill-{amount}.json').read_bytes())


def command(host, op, args, identifier):
    view = host.project('kp')
    return host.command('kp', {'protocolVersion': 1, 'type': 'command', 'requestId': identifier, 'roomId': 'demo',
        'payload': {'commandId': identifier, 'authorityEpoch': host.epoch, 'op': op, 'args': args,
            'runId': view['runId'], 'catalogRevision': view['catalog']['revision'], 'rulesetRevision': view['catalog']['rulesetRevision'],
            'expectedViews': {key: value['viewToken'] for key, value in view['entities'].items()}}})


def approve(host, proposal, identifier):
    decisions = {'newcomer-value': '为新技能保留有限初值，旧技能投入仍有价值'}
    if proposal['changeSet']['configurations'][0]['value']['defaults']['value'] > 10:decisions['gameplay-risk'] = '接受已测量的新建技能成功率变化'
    receipt = command(host, 'ai.proposal.approve', {'proposalId': proposal['proposalId'], 'proposalRevision': proposal['revision'], 'riskDecisions': decisions}, identifier)
    assert receipt['status'] == 'committed', receipt
    return receipt['result']['approvalId']


def test_actual_pack_baseline_metrics_and_no_live_effects(pilot):
    host, service = pilot
    context, state, artifact = service.snapshot('kp');before = copy.deepcopy(host.state())
    assert artifact['sources'] == service.pack.sources
    assert artifact['data'] == service.pack.data
    assert state['configurations'] == service.pack.configurations
    proposal = service.create('kp', '增加新技能初始值', delta())
    result = service.validate('kp', proposal['proposalId'], 1)
    assert [report['status'] for report in result['reports']] == ['pass'] * 3, result
    comparisons = result['reports'][2]['evidence']['comparisons']
    new = next(c for c in comparisons if c['metricId'] == 'new-skill-success')
    existing = next(c for c in comparisons if c['metricId'] == 'existing-skill-success')
    assert new['baseline'] == 0 and new['candidate'] == .15 and new['relativeDelta'] is None and new['exact']
    assert existing['baseline'] == existing['candidate'] == .6
    for key in ('entities', 'relations', 'configurations', 'activeRuleset'):
        assert host.state()[key] == before[key]
    (ROOT / 'acceptance/ai-runtime/ai-6-demo-report.json').write_bytes(canonical({
        'packId': service.pack.contract['packId'], 'packDigest': service.pack.digest,
        'baselineRuleset': artifact['revision'], 'candidateDigest': proposal['candidateDigest'],
        'sourceDigests': {key: digest(value) for key, value in service.pack.sources.items()},
        'reports': result['reports'], 'realProviderTested': False, 'humanPlaytestCompleted': False}))


def test_demo_edit_stale_reject_publish_and_restore(pilot, tmp_path):
    host, service = pilot
    proposal = service.create('kp', '新技能初值 15', delta())
    service.validate('kp', proposal['proposalId'], 1);original = approve(host, proposal, 'first-approval')
    proposal = service.revise('kp', proposal['proposalId'], 1, delta(10), summary='降低新技能初值为 10')
    assert command(host, 'publication.apply', {'approvalId': original}, 'superseded')['code'] == 'APPROVAL_REVOKED'
    service.validate('kp', proposal['proposalId'], 2);approval = approve(host, proposal, 'second-approval')
    assert command(host, 'entity.patch', {'id': 'actor-player1', 'name': '审核期间的实际变化'}, 'concurrent')['status'] == 'committed'
    assert command(host, 'publication.apply', {'approvalId': approval}, 'stale-load')['code'] == 'BASELINE_STALE'
    proposal = service.revise('kp', proposal['proposalId'], 2, delta(10))
    service.validate('kp', proposal['proposalId'], 3);approval = approve(host, proposal, 'third-approval')
    assert command(host, 'ai.proposal.revoke', {'approvalId': approval}, 'reject')['status'] == 'committed'
    assert command(host, 'publication.apply', {'approvalId': approval}, 'rejected-load')['code'] == 'APPROVAL_REVOKED'
    approval = approve(host, proposal, 'fourth-approval')
    def lost_reply(point):
        if point == 'after_publish':raise OSError('acceptance reply loss')
    host.store.fault = lost_reply
    try:receipt = command(host, 'publication.apply', {'approvalId': approval}, 'published')
    finally:host.store.fault = None
    assert receipt['status'] == 'committed' and host.receipt('kp', 'published') == receipt
    assert command(host, 'publication.apply', {'approvalId': approval}, 'duplicate')['result'] == receipt['result']
    assert host.state()['configurations']['demo.skill']['defaults']['value'] == 10
    assert host.state()['entities']['skill-player1']['numbers']['value'] == 60
    assert len(host.state()['aiControl']['publications']) == 1
    service.reconcile()
    scope = host.state()['aiControl']['scopeId']
    Assets(host).backup('kp', tmp_path / 'backup', True)
    restore_host(tmp_path / 'backup', tmp_path / 'restored')
    recovered = Host(tmp_path / 'restored')
    try:
        assert recovered.state()['aiControl']['scopeId'] != scope
        assert recovered.state()['configurations']['demo.skill']['defaults']['value'] == 10
        assert recovered.state()['entities']['skill-player1']['numbers']['value'] == 60
        assert recovered.receipt('kp', 'published') == receipt
        assert not (recovered.path / 'ai').exists()
    finally:recovered.close()


def test_demo_pack_author_constraints_and_existing_flow_block(pilot):
    host, service = pilot
    context, state, artifact = service.snapshot('kp')
    invalid = delta();invalid['configurations'][0]['value']['defaults']['value'] = 31
    report = check_rules(service.pack, state, artifact, context, merge_changes(artifact, invalid))
    assert report['status'] == 'fail' and any(f['code'] == 'PACK_RULE_VIOLATION' for f in report['findings'])
    altered = delta();altered['data']['environment.json'] = {'attackBonus': 3}
    report, _ = check_base(service.pack, state, artifact, context, merge_changes(artifact, altered))
    assert report['status'] == 'fail'
    receipt = command(host, 'action.invoke', {'actionId': 'demo.timed', 'input': {'actor': 'actor-player1', 'amount': 1}}, 'waiting-flow')
    assert receipt['status'] == 'committed', receipt
    proposal = service.create('kp', '等待流程期间的配置变更', delta())
    report = service.validate('kp', proposal['proposalId'], 1)['reports'][1]
    assert report['status'] == 'unknown' and any(f['code'] == 'FLOW_DEPENDENCY_UNMEASURED' for f in report['findings'])
