"""Same synthetic fixtures, separate processes and trees, no external model."""
import argparse,copy,json,math,sys,time
from pathlib import Path

parser=argparse.ArgumentParser();parser.add_argument('--tree',required=True);parser.add_argument('--label',required=True);args=parser.parse_args()
HERE=Path(__file__).resolve().parent;tree=Path(args.tree);eng=tree/'engineering'
sys.path[:0]=[str(eng/'ai/tests'),str(eng/'ai/src'),str(eng/'backend/src'),str(eng/'data-management')]
from test_coordinator import setup
from test_entrypoints import application,delta,command,committed
from test_access_batches import batch
from onlinecoc_ai.contracts import canonical,digest
try:
    from onlinecoc_ai.segmented_store import state_bytes
except ImportError:
    state_bytes=canonical

def measure(fn,count=30):
    start=time.perf_counter();value=fn();cold=(time.perf_counter()-start)*1000
    values=[]
    for _ in range(count):
        started=time.perf_counter();value=fn();values.append((time.perf_counter()-started)*1000)
    ordered=sorted(values)
    return {'samples':count,'coldMs':round(cold,3),'p50Ms':round(ordered[len(ordered)//2],3),
            'p95Ms':round(ordered[math.ceil(len(ordered)*.95)-1],3),'samplesMs':[round(v,3) for v in values],
            'responseBytes':len(canonical(value)) if value is not None else 0}

result={'label':args.label,'tree':str(tree),'realModelCalls':0,'scales':[]}
for size in (100,1000,10000):
    folder=HERE/'work'/('bench-'+args.label+'-'+str(size)+'-'+str(time.time_ns()));folder.mkdir(parents=True)
    fixture=setup.__wrapped__(folder);app=application.__wrapped__(next(fixture))
    try:
        b=batch(app);repo=app.repository;state=repo.state();original=state['settings']['batches'][b['batchId']]
        clones={}
        for n in range(size):
            v=copy.deepcopy(original);v['batchId']=format(n+1,'032x');v['createdAt']+=n
            v['digest']=digest({k:v[k] for k in ('batchId','sessionId','requestId','creator','actions','context','baseline','authorityEpoch')});clones[v['batchId']]=v
        state['settings']['batches']=clones
        row={'count':size};result['scales'].append(row)
        try:repo.commit(state)
        except Exception as exc:
            row.update(status='capacity-rejected',code=getattr(exc,'code',type(exc).__name__))
            continue
        row['status']='measured';row['stateBytes']=len(state_bytes(state))
        fresh=hasattr(app.rulings,'page')
        row['list']=measure(lambda:app.rulings.page('kp',limit=20) if fresh else app.rulings.list('kp'))
        rid='batch:'+format(size,'032x')
        row['detail']=measure(lambda:app.rulings.detail('kp',rid) if fresh else next(i for i in app.rulings.list('kp')['items'] if i['rulingId']==rid))
        def read():
            with repo.read_scope():return len(repo.read_state()['settings']['batches'])
        row['readSnapshot']=measure(read)
        row['verify']=measure(lambda:repo.verify(state))
        def transaction():
            with repo.transaction():
                for n in range(3):repo.update(lambda s:s['settings'].update(perfCounter=s['settings'].get('perfCounter',0)+1))
        row['transaction3Updates']=measure(transaction)
    finally:
        try:next(fixture)
        except StopIteration:pass
        (HERE/(args.label+'-benchmark.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(row,ensure_ascii=False),flush=True)
print(json.dumps({'report':args.label+'-benchmark.json','scales':len(result['scales'])}),flush=True)
