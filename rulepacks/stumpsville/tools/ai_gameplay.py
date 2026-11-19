"""Author declarations for high-risk gameplay changes; no runtime save is exported."""


def shape(value):
    if isinstance(value, bool):
        return {'type': 'boolean'}
    if isinstance(value, str):
        return {'type': 'string'}
    if isinstance(value, (int, float)):
        return {'type': 'integer' if isinstance(value, int) else 'number'}
    if isinstance(value, list):
        variants = []
        for item in value:
            candidate = shape(item)
            if candidate not in variants:
                variants.append(candidate)
        return {'type': 'array', 'items': {'anyOf': variants} if variants else {}}
    if isinstance(value, dict):
        return {'type': 'object', 'required': list(value),
                'properties': {k: shape(v) for k, v in value.items()}, 'additionalProperties': False}
    return {'type': 'null'}


def materials(contract, configurations, data, rule_files):
    contract['highRisk'] = {
        'configurationIds': [c['configurationId'] for c in configurations if c['configurationId'] != 'sv.npc'],
        'configurationPrefixes': ['sv.item.', 'sv.weapon.', 'sv.bag.', 'sv.location.'],
        'ruleFiles': list(rule_files), 'dataFiles': list(data), 'allowRemove': True}
    contract['contextMapping'].update(gameTerms='ai/game-terms.json', stableArrays='ai/stable-arrays.json', dataReferences='ai/data-references.json', liveScenarios='ai/live-scenarios.json')
    contract['sources'].extend([
        {'id': 'stumpsville-game-terms', 'path': 'ai/game-terms.json', 'visibility': 'kp'},
        {'id': 'stumpsville-stable-arrays', 'path': 'ai/stable-arrays.json', 'visibility': 'kp'},
        {'id': 'stumpsville-data-references', 'path': 'ai/data-references.json', 'visibility': 'kp'},
        {'id': 'stumpsville-live-scenarios', 'path': 'ai/live-scenarios.json', 'visibility': 'kp'}])
    files = {'ai/stable-arrays.json': [
        {'dataRef': 'game.json', 'pointer': '/items', 'idKey': 'id', 'appendOnly': True},
        {'dataRef': 'game.json', 'pointer': '/locations', 'idKey': 'index', 'appendOnly': True}],
        'ai/data-references.json': [{'dataRef': 'game.json', 'pointer': '/locations', 'idKey': 'index', 'referencesKey': 'exits', 'contiguousFrom': 1, 'allowSelf': False}],
        'ai/live-scenarios.json': [
            {'configurationId':'sv.character','rule':'sv.layout','actorInput':'actor','input':{},'coversData':['game.json'],'coversRules':['sv.layout']},
            {'configurationId':'sv.character','rule':'sv.check.core','actorInput':'actor','input':{'attribute':'str','mode':'normal'},'coversData':[],'coversRules':['sv.check.core'],
             'expectedErrors':['SV_NOT_APPROVED','SV_NOT_READY','SV_CANNOT_ACT','SV_SESSION_NOT_STARTED']},
            {'configurationId':'sv.character','rule':'sv.travel','actorInput':'actor','input':{'location':1},'coversData':[],'coversRules':['sv.travel'],
             'expectedErrors':['SV_NOT_APPROVED']}]}
    files['ai/gameplay-world.json'] = {'accounts':[{'accountId':'kp','role':'kp'},{'accountId':'player1','role':'player'}],
        'instances':[{'instanceId':'ai-player','configurationId':'sv.character','owner':'player1','name':'配置兼容验收角色','visibility':'public','numbers':{'approved':1}}]}
    for name, rule, inputs in [('inventory','sv.layout',{}),('travel','sv.travel',{'location':2})]:
        path='ai/gameplay-'+name+'.json'
        files[path]={'schemaVersion':1,'scenarioId':'gameplay-'+name,'fixtureRef':'ai/gameplay-world.json','account':'kp',
            'steps':[{'rule':rule,'input':{'actor':'ai-player',**inputs}}],
            'randomPolicy':{'mode':'fixed','sides':20,'samples':1,'seed':1,'values':[10]},'maxSteps':1,'metricIds':[]}
        contract['scenarios'].append(path)
    for name, value in data.items():
        files['ai/' + name + '.schema.json'] = shape(value)
    game = files['ai/game.json.schema.json']
    game['properties']['items']['items'] = {
        'type': 'object', 'required': ['id', 'name', 'kind', 'slots', 'uses', 'description'],
        'properties': {'id': {'type': 'string', 'minLength': 1}, 'name': {'type': 'string', 'minLength': 1},
            'kind': {'enum': sorted({v['kind'] for v in data['game.json']['items']})},
            'slots': {'enum': [1, 2, 4]}, 'uses': {'type': 'integer', 'minimum': 0},
            'description': {'type': 'string'}, 'damage': {'type': 'string'}, 'useDie': {'type': 'boolean'},
            'light': {'type': 'boolean'}, 'armor': {'type': 'integer', 'minimum': 0},
            'shape': {'type': 'string'}, 'price': {'type': 'number', 'minimum': 0}},
        'additionalProperties': False}
    locations = game['properties']['locations']
    locations['items'] = shape(data['game.json']['locations'][0])
    for place in data['game.json']['locations']:
        for key, value in place.items():
            locations['items']['properties'].setdefault(key, shape(value))
    locations['items']['properties']['index'] = {'type': 'integer', 'minimum': 1}
    locations['items']['properties']['exits'] = {'type': 'array', 'uniqueItems': True,
                                               'items': {'type': 'integer', 'minimum': 1}}
    locations['items']['properties']['stock'] = {'type': 'array', 'items': {
        'type': 'object', 'required': ['item', 'count'], 'additionalProperties': False,
        'properties': {'item': {'type': 'integer', 'minimum': 1}, 'count': {'type': 'integer', 'minimum': 0}}}}
    # Empty stock/clue arrays in the first room must not erase the authored shapes.
    clues = [v for place in data['game.json']['locations'] for v in place.get('clues', [])]
    if clues:
        locations['items']['properties']['clues'] = shape(clues)
    return files
