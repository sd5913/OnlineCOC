"""Real direct generation against validated synthetic records; not Coordinator E2E."""
import argparse
import asyncio
import copy
import json
from valid_cases import HERE,ROOT,SYSTEM,canonical
from onlinecoc_ai.profiles import load_profiles
from onlinecoc_ai.local_lock import file_lock
from evaluate import evaluate
from bounded_provider import BoundedProvider,save


async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',action='store_true');parser.add_argument('--cases',nargs='*');args=parser.parse_args()
    cases=json.loads((HERE/'valid-cases.json').read_text(encoding='utf-8'))
    profilepath=ROOT/'engineering/ai/config/ai-providers.json';before=profilepath.read_bytes();profile=copy.deepcopy(load_profiles(profilepath)['deepseek-main'])
    profile['request']['maxOutputTokens']=2000;profile['request']['totalTimeoutMs']=min(profile['request']['totalTimeoutMs'],180000)
    ledger=json.loads((HERE/'live-ledger.json').read_text(encoding='utf-8'));done={a['caseId'] for a in ledger['attempts'] if a['stage']=='valid-v3' and a['status']=='completed'}
    for case in cases:
        if case['caseId'] in done or args.cases and case['caseId'] not in args.cases:continue
        payload={k:case[k] for k in ('request','context','schemas','catalog') if k in case}
        payload.update(authority='Synthetic isolated records. Prepare the requested candidate only. All listed records are currently authorized; expected output and dice are not supplied.',
            sessionAccess={'level':'administrator'},currentActor={'accountId':'kp','role':'kp'},aiPermissions={'allowRuntimeChanges':True,'allowDataQueries':True})
        tools=[case['tool']] if 'tool' in case else []
        if case.get('principal')=='player1':payload.update(sessionAccess={'level':'player'},currentActor={'accountId':'player1','role':'player'})
        messages=[{'role':'system','content':SYSTEM},{'role':'user','content':canonical(payload).decode()}]
        if not args.run:
            print(json.dumps({'caseId':case['caseId'],'inputBytes':len(canonical(messages)),'ready':True}));continue
        provider=BoundedProvider(profile,'valid-v3',case['caseId'],case['category'],evaluate=lambda m:evaluate(case,m))
        try:await provider.complete(messages,tools)
        except Exception as exc:
            failure_path=HERE/'valid-transport-failures.json'
            failures=json.loads(failure_path.read_text(encoding='utf-8')) if failure_path.exists() else []
            failures.append({'stage':'valid-v3','caseId':case['caseId'],'code':getattr(exc,'code',type(exc).__name__),'detail':str(exc)[:1000],'attempts':provider.calls})
            save(failure_path,failures)
            if getattr(exc,'code','')=='EXPERIMENT_BUDGET_EXCEEDED':break
        finally:await provider.close()
    assert profilepath.read_bytes()==before
    ledger=json.loads((HERE/'live-ledger.json').read_text(encoding='utf-8'))
    if ledger['status']=='running':ledger['status']='stage-finished'
    ledger['sourceConfigUnchanged']=True;save(HERE/'live-ledger.json',ledger)


if __name__=='__main__':
    with file_lock(HERE/'live-ledger.json'):asyncio.run(main())
