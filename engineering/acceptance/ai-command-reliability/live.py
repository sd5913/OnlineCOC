"""Explicit opt-in, one global durable budget; saves synthetic inputs/outputs."""
import argparse
import asyncio
import copy
import json
import time
from pathlib import Path
from casebook import HERE,ROOT,BASE,build
from evaluate import evaluate
from onlinecoc_ai.coordinator import SYSTEM
from onlinecoc_ai.contracts import canonical,digest
from onlinecoc_ai.profiles import load_profiles
from onlinecoc_ai.providers import create_provider


def save(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temporary.replace(path)


async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',action='store_true');parser.add_argument('--stage',choices=['baseline','improved'],default='baseline');parser.add_argument('--cases',nargs='*');args=parser.parse_args()
    budget=json.loads((HERE/'budget.json').read_text(encoding='utf-8'));ledger_path=HERE/'live-ledger.json'
    ledger=json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else {'budget':budget,'attempts':[],'status':'ready'}
    profile_path=ROOT/'engineering/ai/config/ai-providers.json';config_before=profile_path.read_bytes()
    profile=copy.deepcopy(load_profiles(profile_path)['deepseek-main']);profile['request']['maxOutputTokens']=1600
    profile['request']['totalTimeoutMs']=min(profile['request']['totalTimeoutMs'],180000)
    cases=build();selected=[c for c in cases if not args.cases or c['caseId'] in args.cases]
    provider=create_provider(profile) if args.run else None
    completed={(x['stage'],x['caseId']) for x in ledger['attempts'] if x.get('status')=='completed'}
    try:
        for case in selected:
            if (args.stage,case['caseId']) in completed:continue
            payload={k:case[k] for k in ('request','context','schemas')}
            payload['authority']='Synthetic, fully read authorized facts. Prepare only the requested candidate; do not execute or add unrelated actions.'
            payload.update(sessionAccess={'level':'administrator'},currentActor={'accountId':'kp','role':'kp'},aiPermissions={'allowRuntimeChanges':True,'allowDataQueries':True})
            tools=[case['tool']] if 'tool' in case else []
            system=SYSTEM
            if args.stage=='improved':
                # Product instructions are explicitly snapshotted by the caller;
                # this process continues to use frozen provider/host boundaries.
                system=(HERE/'improved-system.txt').read_text(encoding='utf-8')
            messages=[{'role':'system','content':system},{'role':'user','content':canonical(payload).decode()}]
            reserve=len(canonical({'messages':messages,'tools':tools,'model':profile['model']}))+1600+2048
            charged=sum(x.get('chargedTokens',x['reservedTokens']) for x in ledger['attempts'])
            if len(ledger['attempts'])>=budget['externalAttemptLimit'] or charged+reserve>budget['totalTokenLimit']:
                ledger.update(status='budget-blocked',blockedCase=case['caseId']);save(ledger_path,ledger);break
            if not args.run:
                print(json.dumps({'caseId':case['caseId'],'reservedTokens':reserve,'ready':True}));continue
            entry={'attemptId':len(ledger['attempts'])+1,'stage':args.stage,'caseId':case['caseId'],'category':case['category'],'status':'started','reservedTokens':reserve,'requestedModel':profile['model'],'input':{'messages':messages,'tools':tools},'startedAt':time.time()}
            ledger['attempts'].append(entry);ledger['status']='running';save(ledger_path,ledger);start=time.perf_counter()
            try:
                response=await provider.complete(messages,tools)
                entry.update(status='completed',output=response.message,usage=response.usage,returnedModel=response.model,chargedTokens=response.usage['total_tokens'],responseDigest=response.response_digest,evaluation=evaluate(case,response.message))
            except Exception as exc:
                entry.update(status='service-failed',code=getattr(exc,'code',type(exc).__name__),chargedTokens=reserve)
            finally:
                entry['seconds']=round(time.perf_counter()-start,3);save(ledger_path,ledger)
                print(json.dumps({k:entry.get(k) for k in ('attemptId','stage','caseId','status','seconds','evaluation','usage')},ensure_ascii=False),flush=True)
        if ledger.get('status')=='running':ledger['status']='stage-finished'
    finally:
        if provider:await provider.close()
        ledger['sourceConfigUnchanged']=profile_path.read_bytes()==config_before
        ledger['sourceConfigDigest']=digest(config_before.hex());save(ledger_path,ledger)


if __name__=='__main__':
    from onlinecoc_ai.local_lock import file_lock
    with file_lock(HERE/'live-ledger.json'):asyncio.run(main())
