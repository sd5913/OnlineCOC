import copy
import json
import math
import threading
from collections import OrderedDict
from pathlib import Path
from jsonschema import Draft202012Validator
from onlinecoc_data import canonical
from .errors import DomainError
ROOT=Path(__file__).resolve().parents[3]
SCHEMAS=json.loads((ROOT/"contracts/messages.json").read_text(encoding="utf-8"))
_MESSAGE_VALIDATORS={kind:Draft202012Validator(schema) for kind,schema in SCHEMAS.items()}

def check(kind,data):
    try: _MESSAGE_VALIDATORS[kind].validate(data)
    except Exception as e: raise DomainError("INPUT_INVALID",str(e)) from e

def input_schema(inputs):
    types={"amount":{"type":"integer","minimum":0,"maximum":1000000},"quantity":{"type":"integer","minimum":1,"maximum":1000000},
           "text":{"type":"string","maxLength":1000},"choice":{"type":"boolean"}}
    props={name:types.get(kind,{"type":"string","minLength":1,"maxLength":100}) for name,kind in inputs.items()}
    return {"type":"object","properties":props,"required":list(props),"additionalProperties":False}

MODELS=json.loads((ROOT/'contracts/models.json').read_text(encoding='utf-8'))
OPERATIONS=json.loads((ROOT/'contracts/operations.json').read_text(encoding='utf-8'))
_MODEL_VALIDATORS={kind:Draft202012Validator(schema) for kind,schema in MODELS.items()}
_OPERATION_VALIDATORS={kind:Draft202012Validator(schema) for kind,schema in OPERATIONS.items()}
# Split the exact schema, caching only byte-identical messages. Cross-record
# references and current authority are still checked in chat.validate.
_CHAT_SHELL=copy.deepcopy(MODELS['ChatState'])
_CHAT_MESSAGE_SCHEMA=_CHAT_SHELL['properties']['messages']['additionalProperties'].pop('items')
_CHAT_SHELL_VALIDATOR=Draft202012Validator(_CHAT_SHELL)
_CHAT_MESSAGE_VALIDATOR=Draft202012Validator(_CHAT_MESSAGE_SCHEMA)
_MESSAGE_VALIDATED=OrderedDict()
_MESSAGE_CACHE_BYTES=0
_MESSAGE_CACHE_LOCK=threading.Lock()
_MESSAGE_CACHE_LIMIT=8*1024*1024
_TEXT_FIELDS=tuple(_CHAT_MESSAGE_SCHEMA['properties'])
_TEXT_KEYS=frozenset(_TEXT_FIELDS)

def _message_key(message):
    # Common text messages have only scalar fields plus a string asset list.
    # Capture every field and its exact type, not mutable identity or message ID.
    # Rich cards and non-JSON inputs use the existing full canonical path.
    if type(message) is dict and message.keys()==_TEXT_KEYS and message.get('card') is None:
        parts=[];size=256
        for name in _TEXT_FIELDS:
            value=message[name]
            if name=='assetIds' and type(value) is list and all(type(x) is str for x in value):
                parts.append(tuple(value));size+=sum(len(x)*4+16 for x in value)
            elif type(value) in (str,int,bool,type(None)):
                parts.append((type(value),value));size+=len(value)*4 if type(value) is str else 32
            elif type(value) is float and math.isfinite(value):
                parts.append((float,value));size+=32
            else:break
        else:return tuple(parts),size
    try:key=canonical(message) if _json_tree(message) else None
    except (ValueError,TypeError,RecursionError):key=None
    return key,len(key) if key is not None else 0

# Split, without weakening, the exact persisted approval schema. The model's
# cross-record checks and publication's current authority checks still run.
_AI_SHELL=copy.deepcopy(MODELS['AiControl'])
_APPROVAL_SCHEMA=_AI_SHELL['properties']['approvals'].pop('additionalProperties')
_AI_SHELL_VALIDATOR=Draft202012Validator(_AI_SHELL)
_APPROVAL_VALIDATOR=Draft202012Validator({**_APPROVAL_SCHEMA,'$defs':MODELS['AiControl']['$defs']})
_APPROVAL_VALIDATED=OrderedDict()
_APPROVAL_CACHE_BYTES=0
_APPROVAL_CACHE_LOCK=threading.Lock()
_APPROVAL_CACHE_LIMIT=16*1024*1024

def _json_tree(value,max_nodes=4096):
    # JSON encoding normalizes tuples and non-string dict keys; those must not
    # collide with a previously validated JSON-native value in the cache.
    pending=[(value,False)];active=set();checked=set()
    while pending:
        item,leaving=pending.pop();kind=type(item)
        if kind in (str,int,float,bool,type(None)):continue
        if kind not in (dict,list):return False
        identifier=id(item)
        if leaving:
            active.remove(identifier);checked.add(identifier);continue
        if identifier in active or len(active)+len(checked)>max_nodes:return False
        if identifier in checked:continue
        active.add(identifier);pending.append((item,True))
        if kind is dict:
            if any(type(key) is not str for key in item):return False
            pending.extend((child,False) for child in item.values())
        else:pending.extend((child,False) for child in item)
    return True

def _model_error(kind,error,prefix=()):
    path=list(prefix)+list(error.absolute_path)
    if error.validator=='required' and isinstance(error.instance,dict):
        path.append(next(k for k in error.validator_value if k not in error.instance))
    pointer='/'+'/'.join(str(k).replace('~','~0').replace('/','~1') for k in path)
    raise DomainError('INPUT_INVALID',{'model':kind,'path':pointer[:512],'constraint':error.validator})

def _chat_schema(value):
    global _MESSAGE_CACHE_BYTES
    error=next(_CHAT_SHELL_VALIDATOR.iter_errors(value),None)
    if error is not None:_model_error('ChatState',error)
    for channel,messages in value['messages'].items():
        for index,message in enumerate(messages):
            key,size=_message_key(message)
            if key is not None:
                with _MESSAGE_CACHE_LOCK:
                    if key in _MESSAGE_VALIDATED:
                        _MESSAGE_VALIDATED.move_to_end(key);continue
            error=next(_CHAT_MESSAGE_VALIDATOR.iter_errors(message),None)
            if error is not None:_model_error('ChatState',error,('messages',channel,index))
            if key is not None and size<=16384:
                with _MESSAGE_CACHE_LOCK:
                    if key not in _MESSAGE_VALIDATED:
                        _MESSAGE_VALIDATED[key]=size;_MESSAGE_CACHE_BYTES+=size
                    while _MESSAGE_CACHE_BYTES>_MESSAGE_CACHE_LIMIT or len(_MESSAGE_VALIDATED)>10000:
                        _,weight=_MESSAGE_VALIDATED.popitem(last=False);_MESSAGE_CACHE_BYTES-=weight

def _ai_schema(value):
    global _APPROVAL_CACHE_BYTES
    error=next(_AI_SHELL_VALIDATOR.iter_errors(value),None)
    if error is not None:_model_error('AiControl',error)
    for identifier,approval in value['approvals'].items():
        try:key=canonical(approval) if _json_tree(approval,65536) else None
        except (ValueError,TypeError,RecursionError):key=None
        if key is not None:
            with _APPROVAL_CACHE_LOCK:
                if key in _APPROVAL_VALIDATED:
                    _APPROVAL_VALIDATED.move_to_end(key);continue
        error=next(_APPROVAL_VALIDATOR.iter_errors(approval),None)
        if error is not None:_model_error('AiControl',error,('approvals',identifier))
        if key is not None and len(key)<=2*1024*1024:
            with _APPROVAL_CACHE_LOCK:
                if key not in _APPROVAL_VALIDATED:
                    _APPROVAL_VALIDATED[key]=None;_APPROVAL_CACHE_BYTES+=len(key)
                while _APPROVAL_CACHE_BYTES>_APPROVAL_CACHE_LIMIT or len(_APPROVAL_VALIDATED)>1000:
                    old,_=_APPROVAL_VALIDATED.popitem(last=False);_APPROVAL_CACHE_BYTES-=len(old)


def validate_model(kind,value):
    if kind=='ChatState':return _chat_schema(value)
    if kind=='AiControl':return _ai_schema(value)
    error=next(_MODEL_VALIDATORS[kind].iter_errors(value),None)
    if error is not None:_model_error(kind,error)
def validate_operation(op,args):
    if op not in OPERATIONS:raise DomainError('UNKNOWN_OPERATION')
    error=next(_OPERATION_VALIDATORS[op].iter_errors(args),None)
    if error is not None:_model_error(op,error)
