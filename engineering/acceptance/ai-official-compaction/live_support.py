"""Synthetic Stumpsville fixture helpers reused from the retained ISSUE-023 experiment."""
import copy
from types import SimpleNamespace
from onlinecoc.host import Host
from onlinecoc_ai.pack import Pack,fixture_state
from onlinecoc_ai.sandbox import stage
from onlinecoc_ai.proposals import Proposals
from onlinecoc_ai.api import Application
from onlinecoc_ai.coordinator import Coordinator
from onlinecoc_ai.context import Context
from test_entrypoints import command,committed
from test_known_runtime import observe
def business(app):
    s = app.host.state()
    return {k: copy.deepcopy(s[k]) for k in ('entities', 'relations', 'configurations', 'activeRuleset', 'artifacts', 'progress', 'members', 'chat', 'outbox')}

def setup_case(folder, packpath, case, profile):
    host = Host(folder / 'host', bootstrap='synthetic-test-password')
    pack = Pack(packpath)
    artifact = stage(pack.sources, pack.data)
    slot = case.get('slot', 5)
    items = artifact['data']['game.json']['items']
    ration = next((i + 1 for i, v in enumerate(items) if v['id'] == 'ration' or v['name'] == '口粮'))
    fixture = {'accounts': [{'accountId': 'kp', 'role': 'kp'}, {'accountId': 'player1', 'role': 'player'}, {'accountId': 'player2', 'role': 'player'}], 'instances': [{'instanceId': 'actor-one', 'configurationId': 'sv.character', 'owner': 'player1', 'name': '阿栗', 'visibility': 'public', 'numbers': {'approved': 1, 'ready': 1, 'hp': 1, 'maxHp': 8, 'item' + str(slot): ration, 'uses' + str(slot): 3}}, {'instanceId': 'npc-one', 'configurationId': 'sv.npc', 'owner': 'kp', 'name': '巡林员', 'visibility': 'kp', 'numbers': {}}, {'instanceId': 'session-one', 'configurationId': 'sv.session', 'owner': 'kp', 'name': '合成测试场次', 'visibility': 'public', 'numbers': {'autoResolve': 1, 'started': 1}}]}
    world = fixture_state(fixture, pack.configurations)
    room = host.state()
    for key in ('entities', 'relations', 'configurations', 'members', 'progress', 'collectionRevision'):
        room[key] = world[key]
    room['entities']['npc-one']['metadata']['secret'] = '合成暗号：松鼠桥'
    room['relations']['actor-session'] = {'relationId': 'actor-session', 'revision': 1, 'sourceId': 'actor-one', 'targetId': 'session-one', 'relationType': 'source', 'tags': [], 'metadata': {}}
    if case['id'] == 'config-remove':
        room['configurations']['sv.item.reviewtest'] = {'configurationId': 'sv.item.reviewtest', 'revision': '1', 'typeRef': 'item', 'defaults': {'uses': 3}}
    room['artifacts'][artifact['revision']] = artifact
    room['activeRuleset'] = artifact['revision']
    host.commit(room)
    proposals = Proposals(host, pack)
    coordinator = Coordinator(proposals, {profile['profileId']: copy.deepcopy(profile)}, context=Context(proposals, demand=True))
    app = Application(SimpleNamespace(proposals=proposals, coordinator=coordinator))
    committed(command(app, 'ai.room.initialize', {'scopeId': room['aiControl']['scopeId'], 'profileId': profile['profileId']}))
    if case.get('account') == 'player1':
        from onlinecoc.knowledge import HostStateProvider
        descriptor = {'policyId': 'personal-test', 'namespace': 'witness', 'providerId': 'synthetic-character-names-v1', 'contractVersion': 1, 'mode': 'required-personal', 'selectors': [{'kind': 'entity', 'configurationPrefix': 'sv.character'}], 'facetSchemas': {'identity': {'schema': {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name'], 'additionalProperties': False}, 'modes': ['observed_snapshot'], 'labelField': 'name'}}, 'egress': {key: 'filtered' for key in ('view', 'query', 'rules', 'receipts', 'assets', 'export', 'ai')}}
        installed = app.host.register_knowledge_provider(descriptor, HostStateProvider({'identity': {'name': 'name'}}))
        committed(app.rulings.host_command('kp', 'synthetic-knowledge-bind', 'knowledge.policy.bind', {'policyId': installed['policyId'], 'descriptorDigest': installed['descriptorDigest'], 'expectedRevision': 0}))
        observe(app)
    if case['id'] in ('basis-question', 'c-dynamic-basis'):
        basis = {'revision': 1, 'metricOverrides': {}, 'liveScenarios': [], 'notes': '本轮合成依据'}
        if case['id'] == 'basis-question':
            basis['metricOverrides'] = {'npc-morale-success': {'absoluteDelta': 0.25, 'risk': 'medium'}}
        else:
            basis['liveScenarios'] = [{'configurationId': 'sv.character', 'rule': 'sv.rest', 'actorInput': 'actor', 'input': {'kind': 'short', 'attribute': ''}, 'coversData': [], 'coversRules': ['sv.rest'], 'randomSides': 6}]
        committed(command(app, 'ai.c_basis.update', basis))
    return app

def approve(app, item, key):
    args = {'rulingId': item['rulingId'], 'digest': item['digest'], 'decision': 'approve', 'riskDecisions': {r['id']: '合成场景验收，明确采纳已列出的来源与游戏性风险。' for r in item['risks']}}
    if item.get('highRisk'):
        args['explicitHighRiskDigest'] = item['digest']
    if item.get('cAssessment', {}).get('requiresAcceptance'):
        args['cReview'] = {k: item['cAssessment'][k] for k in ('basisRevision', 'basisDigest', 'reportDigest')}
    if item.get('consultationAssessment', {}).get('requiresAcceptance'):
        args['consultationReview'] = {'sourceDigest': item['consultationAssessment']['sourceDigest']}
    result = command(app, 'ai.ruling.decide', args, identifier=key)
    after = business(app)
    assert command(app, 'ai.ruling.decide', args, identifier=key) == result and business(app) == after
    assert committed(result)['status'] == 'completed', result
    return result

def artifact(app):
    room = app.host.state()
    return room['artifacts'][room['activeRuleset']]
