"""Shared cumulative real-HTTP ledger; caller holds the single-process file lock."""
import copy
import json
import time
from pathlib import Path
from onlinecoc_ai.contracts import canonical
from onlinecoc_ai.providers import create_provider
from onlinecoc_ai.errors import AiError
HERE=Path(__file__).resolve().parent


def save(path,value):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for attempt in range(10):
        try:tmp.replace(path);return
        except PermissionError:
            if attempt==9:raise
            time.sleep(.05)


class BoundedProvider:
    def __init__(self,profile,stage,case_id,category,*,evaluate=None):
        self.profile=copy.deepcopy(profile);self.provider=create_provider(self.profile)
        self.stage,self.case_id,self.category,self.evaluate=stage,case_id,category,evaluate
        self.calls=[]

    async def complete(self,messages,tools):
        path=HERE/'live-ledger.json';ledger=json.loads(path.read_text(encoding='utf-8'));budget=json.loads((HERE/'budget.json').read_text(encoding='utf-8'))
        if ledger.get('status')=='sealed':raise AiError('EXPERIMENT_SEALED')
        reserve=len(canonical({'messages':messages,'tools':tools,'model':self.profile['model']}))+self.profile['request']['maxOutputTokens']+2048
        used=sum(a.get('chargedTokens',a['reservedTokens']) for a in ledger['attempts'])
        if len(ledger['attempts'])>=budget['externalAttemptLimit'] or used+reserve>budget['totalTokenLimit']:
            ledger.update(status='budget-blocked',blockedCase=self.case_id);save(path,ledger);raise AiError('EXPERIMENT_BUDGET_EXCEEDED')
        row={'attemptId':len(ledger['attempts'])+1,'stage':self.stage,'caseId':self.case_id,'category':self.category,'status':'started',
            'requestedModel':self.profile['model'],'reservedTokens':reserve,'input':{'messages':copy.deepcopy(messages),'tools':copy.deepcopy(tools)},'startedAt':time.time()}
        ledger['attempts'].append(row);ledger['status']='running';save(path,ledger);start=time.perf_counter()
        try:
            result=await self.provider.complete(messages,tools)
            row.update(status='completed',output=result.message,usage=result.usage,returnedModel=result.model,chargedTokens=result.usage['total_tokens'],responseDigest=result.response_digest)
            if self.evaluate:row['evaluation']=self.evaluate(result.message)
            return result
        except Exception as exc:
            row.update(status='service-failed',code=getattr(exc,'code',type(exc).__name__),chargedTokens=reserve);raise
        finally:
            row['seconds']=round(time.perf_counter()-start,3);save(path,ledger);self.calls.append(row['attemptId'])
            print(json.dumps({k:row.get(k) for k in ('attemptId','stage','caseId','status','seconds','usage','evaluation')},ensure_ascii=False),flush=True)

    async def close(self):await self.provider.close()
