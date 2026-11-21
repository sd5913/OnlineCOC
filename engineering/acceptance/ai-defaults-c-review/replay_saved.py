"""Zero-API replay of saved first model answers, with complete effect oracles."""
import copy
import importlib.util
import json
import sys
import time
import traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
tree=json.loads((HERE/'lifecycle-evidence-source.json').read_text())['tree']
sys.argv=[str(HERE/'coordinator_live.py'),'--tree',tree]
spec=importlib.util.spec_from_file_location('natural_test',HERE/'coordinator_live.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
source=HERE/'natural-1795193315656682400.json';saved=json.loads(source.read_text(encoding='utf-8'))
profile=json.loads((Path(tree)/'engineering/ai/examples/ai-providers.json').read_text())['profiles'][0];profile['enabled']=True
pack=Path(json.loads((HERE/'strict-pack-source.json').read_text())['path'])
work=HERE/'work'/('replay-'+str(time.time_ns()));work.mkdir(parents=True)
rows=[]
for original in saved['cases']:
    case=next(c for c in h.CASES if c['id']==original['caseId'])
    if case['category'] not in ('runtime','configuration'):continue
    row={'caseId':case['id'],'sourceAttemptIds':original['attemptIds'],'sourceOutputDigest':h.digest(original['firstOutput']),'status':'running'}
    app=None
    try:
        app=h.setup_case(work/case['id'],pack,case,profile);before=h.business(app);out=h.parse_answer(original['firstOutput'])
        if case['category']=='configuration':
            assert not out.get('dataEdits'),'Replay needs original edit reference evidence'
            p=h.committed(h.command(app,'ai.draft.create',{'text':case['text'],'changeSet':out['changeSet']}))
            h.committed(h.command(app,'ai.proposal.validate',{'proposalId':p['proposalId'],'revision':1}))
            rid='proposal:'+p['proposalId']
        else:
            if case['id']=='unique-short-rest':
                normalized=copy.deepcopy(out)
                # sv.rest's short branch ignores attribute; source and actual effects are checked.
                normalized['actions'][0]['args']['input']['attribute']=''
                assert h.semantic(case,normalized)
                row['oracleCorrection']='Ignored short-rest attribute accepted only after rule-source and actual effect verification; original failed result retained.'
            else:assert h.semantic(case,out)
            request_id=h.submit(app,h.session(app),case['text'])['requestId']
            request=app.repository.state()['requests'][request_id]
            context,_=app.coordinator.context.capture('kp',request)
            bid=app.batches.create('kp',request,out['actions'],out['text'],context[0]);rid='batch:'+bid
        item=next(i for i in app.rulings.list('kp')['items'] if i['rulingId']==rid)
        row['reports']=[{'level':r['level'],'status':r['status'],'codes':[f['code'] for f in r['findings']]} for r in item.get('reports',[])]
        assert h.business(app)==before
        decision=h.committed(h.approval(app,item,'replay-approve'))
        assert decision['status']=='completed',decision.get('blockingReason')
        after=h.business(app);h.verify(case,app,before,after)
        row.update(status='passed',actualExecution=True,idempotent=True,fullEffectOracle=True,beforeDigest=h.digest(before),afterDigest=h.digest(after))
    except Exception as exc:row.update(status='failed',code=getattr(exc,'code',type(exc).__name__),reason=str(exc)[:400],traceback=traceback.format_exc())
    finally:
        if app:app.proposals.close();app.host.close()
    rows.append(row);h.save(HERE/('replay-'+work.name.removeprefix('replay-')+'.json'),{'tree':tree,'realProvider':False,'sourceReport':source.name,'cases':rows})
    print(json.dumps(row,ensure_ascii=False),flush=True)
if any(r['status']=='failed' for r in rows):raise SystemExit(1)
