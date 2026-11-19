"""Trusted, declarative player menu projection. Never infer knowledge from world flags."""
import copy
import hashlib
import json
from pathlib import Path

VERSION = 2
BASELINE = json.loads((Path(__file__).resolve().parents[1] / 'config/scene-actions.json').read_text(encoding='utf-8'))
STOCK_SOURCE = (Path(__file__).resolve().parents[1] / 'rules/scene.lua').read_text(encoding='utf-8')
POLICY_DIGEST = hashlib.sha256(json.dumps(BASELINE, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def plain_definition(action):
    value = copy.deepcopy(action)
    value.pop('player', None)
    for choice in value.get('choices', []):
        choice.pop('player', None)
    return value


def definitions(content):
    """Old stock artifacts can use audited wording; changed/unknown ones fail closed."""
    baseline = {a['id']: a for a in BASELINE['actions']}
    result = []
    for action in content.get('actions', []):
        current = copy.deepcopy(action)
        original = baseline.get(action.get('id'))
        if 'player' not in current and original and plain_definition(current) == plain_definition(original):
            current = copy.deepcopy(original)
        result.append(current)
    return result


def catalog(content):
    values = content.get('playerKnowledge', BASELINE['playerKnowledge'])
    return [copy.deepcopy(v) for v in values if isinstance(v, dict)
            and set(v) == {'id', 'location', 'title', 'text'}
            and type(v['location']) is int and v['location'] >= 1
            and all(isinstance(v[k], str) and 0 < len(v[k]) <= 2000 for k in ('id', 'title', 'text'))]


def visible(player, known, fields):
    if not isinstance(player, dict) or set(player) != set(fields) | {'requiresAny'}:
        return False
    required = player['requiresAny']
    return (all(isinstance(player[k], str) and 0 < len(player[k]) <= 2000 for k in fields)
            and isinstance(required, list) and all(isinstance(k, str) and k for k in required)
            and (not required or bool(known.intersection(required))))


def menu(content, location, clues):
    known = {c['id'] for c in clues if isinstance(c, dict) and isinstance(c.get('id'), str)}
    result = []
    for action in definitions(content):
        player = action.get('player')
        if action.get('location') != location or not visible(player, known, ('label', 'hint')):
            continue
        choices = []
        for choice in action.get('choices', []):
            shown = choice.get('player')
            if visible(shown, known, ('label', 'process')):
                choices.append({'id': choice['id'], 'label': shown['label'], 'process': shown['process']})
        if choices:
            result.append({'id': action['id'], 'location': location, 'label': player['label'],
                           'hint': player['hint'], 'choices': choices})
    return result


def outcome_clues(content, action, choice, result, source):
    """Facts already disclosed by a committed outcome, including stock Lua artifacts."""
    if source != STOCK_SOURCE or result.get('outcome') == 'blocked':
        return []
    key = {('house-pots', 'search'): 'pots-observed', ('house-pots', 'take'): 'pots-observed',
           ('hall-observe', 'inspect'): 'hall-company', ('hall-negotiate', 'talk'): 'hall-company',
           ('hall-negotiate', 'food'): 'hall-company', ('cage-gate', 'inspect'): 'cage-route',
           ('cave-cheese', 'inspect'): 'cave-stock', ('cave-sleeper', 'observe'): 'sleeper-seen',
           ('cave-sleeper', 'talk'): 'sleeper-seen'}.get((action, choice))
    # This compatibility extraction only applies to the audited stock mechanics.
    raw = next((a for a in content.get('actions', []) if a['id'] == action), None)
    baseline = next((a for a in BASELINE['actions'] if a['id'] == action), None)
    if not raw or not baseline or plain_definition(raw) != plain_definition(baseline):
        return []
    return [v for v in catalog(content) if v['id'] == key]


TEXT = {'type': 'string', 'maxLength': 6000}
def object_schema(properties, required=None):
    return {'type': 'object', 'properties': properties, 'required': list(properties) if required is None else required,
            'additionalProperties': False}
CHOICE = object_schema({'id': TEXT, 'label': TEXT, 'process': TEXT})
ACTION = object_schema({'id': TEXT, 'location': {'type': 'integer'}, 'label': TEXT, 'hint': TEXT,
                        'choices': {'type': 'array', 'minItems': 1, 'maxItems': 20, 'items': CHOICE}})
CLUE = object_schema({'id': TEXT, 'title': TEXT, 'text': TEXT, 'location': {'type': 'integer'}}, ['id', 'title', 'text'])
SCENE = object_schema({'index': {'type': 'integer'}, 'name': TEXT, 'description': TEXT,
    'features': {'type': 'array', 'items': TEXT}, 'exits': {'type': 'array', 'items': {'type': 'integer'}},
    'clues': {'type': 'array', 'items': CLUE}, 'actions': {'type': 'array', 'maxItems': 50, 'items': ACTION},
    'entityId': TEXT, 'doors': {'type': 'object', 'additionalProperties': {'enum': ['open', 'closed', 'locked', 'unknown']}},
    'navigation': {'type': 'object', 'additionalProperties': TEXT}})
IDENTITY = object_schema({'name': TEXT, 'location': {'type': ['integer', 'null']}, 'entityId': TEXT})
PLAY = object_schema({'name': TEXT, 'entityId': TEXT, 'numbers': object_schema({
    'phase': {'type': 'number'}, 'round': {'type': 'number'}, 'autoResolve': {'type': 'number'}}, [])})
# entityProjection requires a complete legal Entity; the host validates that shape too.
SHEET = {'type': 'object', 'required': ['instanceId', 'name', 'owner', 'numbers'],
         'properties': {'instanceId': TEXT, 'name': TEXT, 'owner': TEXT,
                        'numbers': {'type': 'object', 'additionalProperties': {'type': 'number'}}}}
