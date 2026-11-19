"""Strict player responses select evidence; model prose never becomes displayed facts.

This module is deliberately independent of the host and its mutable contracts.
The caller must acquire and recheck every evidence item through KnowledgeService.
"""
import base64
import copy
import hashlib
import json
import re

from .errors import AiError, require

SCHEMA = {'type': 'object', 'additionalProperties': False,
    'required': ['kind', 'evidence', 'next'], 'properties': {
        'kind': {'const': 'known'},
        'evidence': {'type': 'array', 'maxItems': 12, 'uniqueItems': True,
            'items': {'type': 'string', 'pattern': '^k[0-9a-f]{64}$'}},
        'next': {'enum': ['none', 'ask_kp']}}}

INSTRUCTIONS = '''You assist one player using only their verified personal knowledge.
Use the supplied knowledge search/read tools to answer the request. A search label is
not a detail: read the selected references before answering. Never call another data
source, infer discoveries, use module lore or invent narrative facts.
Return only a valid JSON object: {"kind":"known","evidence":["issued evidenceId"],"next":"none"}.
Select at most 12 distinct evidenceId values actually issued in a detail read.
The server renders their exact authorized observations; do not return text, titles,
choices, conclusions, suspicions or commands. Select next="ask_kp" to offer the neutral
option to request a KP disclosure; it does not grant access or execute anything.
If there is no relevant readable evidence, return an empty evidence list. Empty search
results say nothing about whether an object exists. Old observations are not current
world state. Provider failures must not be bypassed with previous model text.
'''


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def evidence_id(ref):
    return 'k' + hashlib.sha256(_canonical(ref).encode()).hexdigest()


def reference_token(ref):
    """Version the opaque UI encoding separately from the content revision."""
    require(type(ref) is dict and set(ref) == {'schemaVersion','scopeId','id','revision','digest'}
        and ref['schemaVersion'] == 1, 'KNOWLEDGE_DATA_INVALID')
    require(all(type(ref[k]) is str and 1 <= len(ref[k]) <= 200 for k in ('scopeId','id','revision','digest')),
        'KNOWLEDGE_DATA_INVALID')
    value = base64.urlsafe_b64encode(_canonical(ref).encode()).decode().rstrip('=')
    require(len(value) <= 1500, 'KNOWLEDGE_DATA_INVALID')
    return '[[knowledge:' + value + '@1]]'


def decode_reference(key, revision):
    require(revision == '1' and type(key) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,1500}', key), 'REFERENCE_INVALID')
    try:
        ref = json.loads(base64.urlsafe_b64decode(key + '=' * (-len(key) % 4)).decode())
        require(reference_token(ref) == '[[knowledge:' + key + '@1]]', 'REFERENCE_INVALID')
        return ref
    except (ValueError, UnicodeError, TypeError, KeyError) as exc:
        raise AiError('REFERENCE_INVALID') from exc


def register(pool, items):
    """Only detailed, already-authorized items can be issued to this model turn."""
    issued = []
    for item in items:
        require(type(item) is dict and 'data' in item and item.get('mode') in ('observed_snapshot','live_scope')
            and type(item.get('label')) is str and type(item.get('facetId')) is str, 'KNOWLEDGE_DATA_INVALID')
        reference_token(item.get('ref'))
        require(len(_canonical(item).encode()) <= 64 * 1024, 'KNOWLEDGE_DATA_INVALID')
        key = evidence_id(item['ref'])
        require(key not in pool or pool[key] == item, 'KNOWLEDGE_DATA_INVALID')
        require(key in pool or len(pool) < 128, 'QUERY_LIMIT')
        pool[key] = copy.deepcopy(item)
        issued.append({**copy.deepcopy(item), 'evidenceId': key})
    return issued


def parse(content, pool):
    from jsonschema import Draft202012Validator
    require(type(content) is str and len(content) <= 8000, 'MODEL_JSON_INVALID')
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, 'MODEL_FIELDS_INVALID')
            result[key] = value
        return result
    fenced = re.fullmatch(r'\s*```(?:json)?\s*\n([\s\S]*?)\n```\s*', content)
    try:
        value = json.loads(fenced[1] if fenced else content, object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(AiError('MODEL_JSON_INVALID')))
    except (ValueError, RecursionError):
        raise AiError('MODEL_JSON_INVALID') from None
    require(Draft202012Validator(SCHEMA).is_valid(value), 'MODEL_KNOWN_ANSWER_INVALID')
    require(all(key in pool for key in value['evidence']), 'REFERENCE_UNVERIFIED')
    return value


def _literal(value):
    """Evidence is data, never nested reference markup, HTML or instructions."""
    text = value if type(value) is str else _canonical(value)
    return re.sub(r'([\\`*_{}\[\]()<>#!|])', r'\\\1', text).replace('\r', '')


def render(output, pool):
    # Fixed order avoids a model-provided priority/suspicion ranking.
    selected = sorted((pool[key] for key in output['evidence']), key=lambda v: (v.get('observedAt') or 0, v['ref']['id'], v['facetId']))
    parts = []
    for item in selected:
        heading = '观察记录' if item['mode'] == 'observed_snapshot' else '持续告知资料'
        data = item['data']
        text = data['text'] if type(data) is dict and set(data) == {'text'} else data
        parts.append(heading + ' · ' + reference_token(item['ref']) + '\n\n' + _literal(text))
    text = '\n\n'.join(parts) or '当前可核验的本人已知资料不足，无法据此提供更多信息。'
    require(len(text) <= 8000, 'MODEL_KNOWN_ANSWER_LIMIT')
    choices = None
    if output['next'] == 'ask_kp':
        choices = {'prompt': '需要向 KP 请求说明吗？', 'options': [
            {'id':'ask_kp','label':'请 KP 说明','text':'请 KP 说明本次问题中允许我获知的信息。'},
            {'id':'known_only','label':'仅整理已知资料','text':'只整理当前已经核验的本人已知资料。'}]}
    return {'kind': 'plan', 'text': text, **({'choices': choices} if choices else {})}
