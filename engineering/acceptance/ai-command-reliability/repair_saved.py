"""Production Coordinator repairing a replayed, genuine failed model response.

The first response is verbatim historical API output (zero new HTTP). Further
responses come from DeepSeek and see only production validation feedback.
"""
import argparse
import asyncio
import copy
import json
import shutil
import time
import traceback
from pathlib import Path
from valid_cases import HERE,ROOT,application,close,session,submit,command,committed,Context,digest
from bounded_provider import BoundedProvider,save
from coordinator_live import setup_case,approve,business
from onlinecoc_ai.local_lock import file_lock
from onlinecoc_ai.profiles import load_profiles
from onlinecoc_ai.providers.base import Completion
from test_coordinator import wait_task


class ReplayFirst:
    def __init__(self,profile,case,seed):
        self.inner=BoundedProvider(profile,'saved-failure-repair',case,'repair');self.seed=seed;self.used=False
    async def complete(self,messages,tools):
        if not self.used:
            self.used=True
            return Completion(copy.deepcopy(self.seed),{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0},'stop',digest(self.seed),'historical-response-replay')
        return await self.inner.complete(messages,tools)
    async def close(self):await self.inner.close()


async def main():
    parser=argparse.ArgumentParser();parser.add_argument('cases',nargs='+');args=parser.parse_args()
    ledger=json.loads((HERE/'live-ledger.json').read_text(encoding='utf-8'));cases={c['caseId']:c for c in json.loads((HERE/'valid-cases.json').read_text(encoding='utf-8'))}
    profile=copy.deepcopy(load_profiles(ROOT/'engineering/ai/config/ai-providers.json')['deepseek-main']);profile['limits'].update(maxRepairAttempts=2,maxTransportRetries=2,maxToolRounds=3);profile['request']['maxOutputTokens']=2000
    run=str(time.time_ns());work=HERE/'work'/('saved-repair-'+run);work.mkdir(parents=True);rows=[]
    for name in args.cases:
        row={'caseId':name,'historicalFirstResponse':True};app=None
        try:
            if name=='npc-marker':
                seed=next(a for a in ledger['attempts'] if a['attemptId']==169);pack=HERE/'work/strict-real-pack-v2/integrations/ai-pack-6e53556afda3b5f63824'
                request='新增NPC配置sv.ext.npc.reliability，沿用sv.npc全部默认值，仅hp和maxHp改成5，修订1，遵守包的新NPC固定标记，不改实例。'
                app=setup_case(work/name,pack,{'id':name,'kind':'configuration'})
            else:
                case=cases[name];seed=next(a for a in ledger['attempts'] if a['stage']=='valid-v3' and a['caseId']==name)
                path=work/name.replace(':','-');shutil.copytree(HERE/case['fixturePath'],path);app=application(path,HERE/case['packPath'],fresh=False);request=case['request']
            row['seedAttemptId']=seed['attemptId'];row['initialOutput']=seed['output'];before=business(app.host)
            app.coordinator.context=Context(app.proposals,demand=True);app.coordinator.profiles={profile['profileId']:profile}
            provider=ReplayFirst(profile,name,seed['output']);app.coordinator.provider_factory=lambda _:provider
            await app.coordinator.start();s=session(app);r=submit(app,s,request);dispatched=committed(command(app,'ai.request.dispatch',{'requestId':r['requestId']}));task=await wait_task(app.coordinator,dispatched['taskId'],timeout=270)
            row.update(task=task,attemptIds=provider.inner.calls,beforeApprovalUnchanged=business(app.host)==before)
            assert row['beforeApprovalUnchanged']
            if task['status']=='review_ready':
                if task.get('batchId'):
                    candidate=app.repository.state()['settings']['batches'][task['batchId']];rid='batch:'+task['batchId'];row['candidate']=candidate
                elif task.get('proposalId'):
                    candidate=app.proposals.get('kp',task['proposalId']);rid='proposal:'+task['proposalId'];row['candidate']=candidate;row['reports']=[app.repository.state()['reports'][r] for r in candidate['reportRefs']]
                else:raise AssertionError('No repaired candidate')
                item=next(i for i in app.rulings.list('kp')['items'] if i['rulingId']==rid);row['receipt']=approve(app,item,'repair:'+name)
                row['status']='committed' if committed(row['receipt'])['status']=='completed' else 'failed';row['after']=business(app.host)
            else:row['status']=task['status']
        except Exception as exc:row.update(status='error',code=getattr(exc,'code',type(exc).__name__),reason=str(exc),traceback=traceback.format_exc())
        finally:
            if app:await app.coordinator.close();close(app)
        rows.append(row);save(HERE/('saved-repair-'+run+'.json'),{'runId':run,'cases':rows});print(json.dumps({k:row.get(k) for k in ('caseId','status','code','reason','attemptIds')},ensure_ascii=False),flush=True)


if __name__=='__main__':
    with file_lock(HERE/'live-ledger.json'):asyncio.run(main())
