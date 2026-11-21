"""Separate wire/format validity, exact synthetic intent, and execution evidence."""
import copy
import json
from jsonschema import Draft202012Validator
from casebook import BASE,EMPTY
from onlinecoc_ai.answers import parse_answer,validate_answer
from onlinecoc_ai.contracts import validate
from onlinecoc_ai.data_edits import EDITS_SCHEMA
from onlinecoc_ai.batches import HOST_OPS,AI_OPS

HOST=json.loads((BASE/'engineering/contracts/operations.json').read_text(encoding='utf-8'))
AI=json.loads((BASE/'engineering/contracts/ai-operations.json').read_text(encoding='utf-8'))


def evaluate(case,message):
    result={'formatPassed':False,'semanticPassed':False,'execution':'not_run','errors':[]}
    try:
        if 'tool' in case:
            calls=message.get('tool_calls',[])
            if len(calls)!=1:raise ValueError('exactly one query tool call required')
            function=calls[0]['function'];args=json.loads(function['arguments'])
            Draft202012Validator(case['tool']['function']['parameters']).validate(args)
            result['formatPassed']=True
            result['semanticPassed']=function['name']==case['expected']['tool'] and args==case['expected']['arguments']
            if not result['semanticPassed']:result['errors'].append({'code':'QUERY_INTENT_MISMATCH','path':'/tool_calls/0'})
            return result
        value=parse_answer(message.get('content'));validate_answer(value,set())
        if value['kind']=='batch':
            if not isinstance(value['actions'],list) or not value['actions']:raise ValueError('actions required')
            for i,action in enumerate(value['actions']):
                if set(action)!={'target','op','args'}:raise ValueError('invalid action fields')
                if action['target'] not in ('host','ai') or action['op'] not in (HOST_OPS if action['target']=='host' else AI_OPS):raise ValueError('operation is not available in this target namespace')
                schema=case['schemas'].get(action['op'],(HOST if action['target']=='host' else AI).get(action['op']))
                if schema is None:raise ValueError('operation not available')
                Draft202012Validator(schema).validate(action['args'])
                if action['op']=='action.invoke' and 'input:'+action['args']['actionId'] in case['schemas']:
                    Draft202012Validator(case['schemas']['input:'+action['args']['actionId']]).validate(action['args']['input'])
        elif value['kind']=='draft':
            validate('ChangeSet',value['changeSet'])
            if 'dataEdits' in value:Draft202012Validator(EDITS_SCHEMA).validate(value['dataEdits'])
        result['formatPassed']=True
        expected=case['expected']
        if case['caseId']=='lua:forbidden':
            good=value['kind'] in ('plan','clarification') and not any(k in value for k in ('actions','changeSet'))
        elif case['caseId']=='lua:valid':
            change=value.get('changeSet',{});sources=change.get('sources',{})
            good=value['kind']=='draft' and set(sources)=={'extra.lua'} and not change.get('configurations') and not change.get('data') and not change.get('suggestions')
            if good:
                from onlinecoc.registry import stage
                artifact=stage(sources,{})
                definitions=artifact.get('metadata',{})
                # Parsing and inspecting the real Lua sandbox is an additional
                # execution check, not a claim that the game command committed.
                good='fixture.ext.inspect' in json.dumps(definitions)
                result['luaStaging']='passed' if good else 'failed'
        else:
            candidate=copy.deepcopy(value)
            if case.get('allowNotifications') and value['kind']=='batch':
                # Optional policy-required notifications may follow the exact
                # requested action; no other operation or argument is relaxed.
                actual=value['actions'];required=expected['actions'];extra=actual[len(required):]
                allowed=set()
                entities=case.get('context',{}).get('state',{}).get('entities',{})
                for action in required:
                    args=action['args'];ids=[args.get('id'),args.get('entityId'),args.get('input',{}).get('actor'),args.get('input',{}).get('target')]
                    allowed.update(entities[key]['owner'] for key in ids if key in entities and entities[key].get('owner'))
                    if args.get('owner'):allowed.add(args['owner'])
                if all(a['target']=='host' and a['op']=='notification.send' and
                       0<=a['args'].get('sourceActionIndex',-1)<len(required) and
                       set(a['args'].get('recipientAccountIds',[]))<=allowed and bool(a['args'].get('recipientAccountIds')) and
                       isinstance(a['args'].get('text'),str) and bool(a['args']['text'].strip()) for a in extra):candidate['actions']=actual[:len(required)]
            good=all(candidate.get(key)==expected_value for key,expected_value in expected.items())
        result['semanticPassed']=bool(good)
        if not good:result['errors'].append({'code':'INTENT_MISMATCH','path':'/'})
    except Exception as exc:
        result['errors'].append({'code':getattr(exc,'code',type(exc).__name__),'path':'/'+ '/'.join(map(str,getattr(exc,'absolute_path',[]))),'reason':str(exc)[:600]})
    return result


def expected_message(case):
    if 'tool' in case:
        return {'role':'assistant','content':None,'tool_calls':[{'id':'synthetic-call','type':'function','function':{'name':case['expected']['tool'],'arguments':json.dumps(case['expected']['arguments'])}}]}
    value=copy.deepcopy(case['expected']);value['text']='合成契约与语义判定器自检，不代表真实模型输出。'
    if case['caseId']=='lua:valid':value['changeSet']={**EMPTY,'sources':{'extra.lua':"return rule('fixture.ext.inspect', {'actor'}, function(r, actor) return {ok=true} end)"}}
    return {'role':'assistant','content':json.dumps(value,ensure_ascii=False)}
