"""Focused real-API feedback probe, not a repeat of the full production prompt."""
import asyncio
import importlib.util
import json
import sys
import time
from pathlib import Path
HERE=Path(__file__).resolve().parent
tree=json.loads((HERE/'core-v3-final-source.json').read_text())['tree']
sys.argv=[str(HERE/'coordinator_live.py'),'--tree',tree]
spec=importlib.util.spec_from_file_location('natural_test',HERE/'coordinator_live.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
from onlinecoc_ai.coordinator import repair_feedback
from onlinecoc_ai.reliability import require_search_evidence,tool_arguments
from onlinecoc_ai.data_queries import DataQueryService,NAMES
from onlinecoc_ai.contracts import canonical


async def main():
    config=h.ROOT/'engineering/ai/config/ai-providers.json';original=config.read_bytes()
    profile=h.load_profiles(config)['deepseek-main'];profile['request']['maxOutputTokens']=900
    failed=json.loads((HERE/'live-ledger.json').read_text(encoding='utf-8'))['attempts'][13]
    original_payload=json.loads(failed['input']['messages'][1]['content'])
    payload={k:original_payload[k] for k in ('request','currentActor','dataAccess','sessionAccess','externalSources','effectiveAccess')}
    tools=[t for t in failed['input']['tools'] if t['function']['name'] in ('room_search_data','room_read_data')]
    case=next(c for c in h.CASES if c['id']=='kp-all-read');pack=Path(json.loads((HERE/'strict-pack-source.json').read_text())['path'])
    app=h.setup_case(HERE/'work'/('evidence-repair-'+str(time.time_ns())),pack,case,profile)
    provider=h.BoundedProvider(profile,'focused-evidence-repair','kp-all-read-repair','question')
    report={'tree':tree,'originalAttemptId':14,'fullProductionPrompt':False,'scope':'Same synthetic room and actual authorized DataQueryService; reduced prompt and two read tools, no mutation tools.', 'status':'running'}
    try:
        request_id=h.submit(app,h.session(app),case['text'])['requestId'];request=app.repository.state()['requests'][request_id]
        snapshot,_=app.coordinator.context.capture('kp',request);before=h.business(app)
        try:require_search_evidence(case['text'],payload,snapshot[0],h.parse_answer(failed['output']['content']))
        except h.AiError as exc:feedback=repair_feedback(exc,failed['output']['content'])
        else:raise AssertionError('Original false absence was not detected')
        messages=[{'role':'system','content':'Answer the authorized user with a JSON object {"kind":"plan","text":"..."}. Room placeholders are unloaded. Use exact read tools and actual evidence. Do not modify data or infer absence from unloaded context.'},
            {'role':'user','content':canonical(payload).decode()},failed['output'],{'role':'user','content':canonical(feedback).decode()}]
        report['feedback']=feedback
        for turn in range(4):
            result=await provider.complete(messages,tools if turn<3 else []);message=result.message;messages.append(message)
            if not message.get('tool_calls'):
                output=h.parse_answer(message['content']);require_search_evidence(case['text'],payload,snapshot[0],output)
                assert h.semantic(case,output),output
                report['output']=output;report['status']='passed';break
            for call in message['tool_calls']:
                name=call['function']['name'];schema=next(t['function']['parameters'] for t in tools if t['function']['name']==name)
                args=tool_arguments(call['function']['arguments'],schema)
                value=DataQueryService(app.host).attach('kp',NAMES[name],args,snapshot,'kp')
                messages.append({'role':'tool','tool_call_id':call['id'],'content':canonical(value).decode()})
        assert report['status']=='passed','No final answer within bounded tool turns'
        assert h.business(app)==before;report['businessUnchanged']=True
    except Exception as exc:report.update(status='failed',code=getattr(exc,'code',type(exc).__name__),reason=str(exc)[:500])
    finally:
        report['attemptIds']=provider.calls;report['sourceConfigUnchanged']=config.read_bytes()==original
        await provider.close();app.proposals.close();app.host.close()
        h.save(HERE/('evidence-repair-'+str(time.time_ns())+'.json'),report);print(json.dumps(report,ensure_ascii=False),flush=True)
    assert report['status']=='passed',report.get('reason')


if __name__=='__main__':
    from onlinecoc_ai.errors import AiError
    h.AiError=AiError
    with h.file_lock(HERE/'work/external-single-writer'):asyncio.run(main())
