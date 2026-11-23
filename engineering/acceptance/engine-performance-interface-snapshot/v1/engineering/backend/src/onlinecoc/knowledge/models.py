"""Versioned schemas and invariants for the durable knowledge ledger."""
import hashlib
import json
import uuid
import copy
import threading
from collections import OrderedDict
from pathlib import Path
from jsonschema import Draft202012Validator
from onlinecoc_data import canonical
from ..errors import DomainError, require

CONTRACT = json.loads((Path(__file__).resolve().parents[4] / 'contracts/knowledge.json').read_text(encoding='utf-8'))
VALIDATORS = {group: {name: Draft202012Validator(schema) for name, schema in values.items()}
              for group, values in CONTRACT.items() if group in ('models', 'commands', 'queries')}
_header = copy.deepcopy(CONTRACT['models']['KnowledgeState'])
for _field in ('policies', 'observations', 'grants'):
    _header['properties'][_field]['additionalProperties'] = {'type': 'object'}
_header_validator = Draft202012Validator(_header)
# Cache only successful structural/content validation of identical canonical
# records. Never cache visibility, grants, provider guards or relationships.
_checked = OrderedDict()
_checked_lock = threading.RLock()

def _record(kind, value):
    raw = canonical(value)
    key = (kind, hashlib.sha256(raw).digest())
    with _checked_lock:
        if key in _checked:
            _checked.move_to_end(key)
            return
    check('models', kind, value)
    if kind == 'PolicyBinding':
        require(value['descriptorDigest'] == descriptor_digest(value), 'INPUT_INVALID')
    elif kind == 'Observation':
        require(len(raw) <= 32768, 'KNOWLEDGE_LIMIT')
        for facet in value['facets'].values():
            require(facet['digest'] == digest(facet['data']), 'INPUT_INVALID')
            require(len(canonical(facet['data'])) <= 8192, 'KNOWLEDGE_LIMIT')
    with _checked_lock:
        _checked[key] = True
        if len(_checked) > 16384:
            _checked.popitem(last=False)

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def check(group, name, value):
    if next(VALIDATORS[group][name].iter_errors(value), None):
        raise DomainError('INPUT_INVALID')

def initial():
    return dict(schemaVersion=1, scopeId=str(uuid.uuid4()), revision=1,
                policies={}, observations={}, grants={}, subjectEpochs={})

def descriptor_digest(value):
    return digest({k: v for k, v in value.items() if k not in ('descriptorDigest', 'revision')})

def validate(value):
    if next(_header_validator.iter_errors(value), None):
        raise DomainError('INPUT_INVALID')
    require(len(canonical(value)) <= 16 * 1024 * 1024, 'KNOWLEDGE_LIMIT')
    for key, policy in value['policies'].items():
        _record('PolicyBinding', policy)
        require(key == policy['policyId'], 'INPUT_INVALID')
    for key, obs in value['observations'].items():
        _record('Observation', obs)
        require(key == obs['observationId'] and obs['policyId'] in value['policies'], 'INPUT_INVALID')
    for key, grant in value['grants'].items():
        _record('Grant', grant)
        require(key == grant['grantId'] and grant['policyId'] in value['policies'], 'INPUT_INVALID')
        if grant['mode'] == 'observed_snapshot':
            obs = value['observations'].get(grant['observationId'])
            require(obs and obs['resource'] == grant['resource'] and obs['policyId'] == grant['policyId']
                    and set(grant['facetIds']) <= set(obs['facets']), 'INPUT_INVALID')
        else:
            require(grant['observationId'] is None, 'INPUT_INVALID')
