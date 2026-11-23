"""CPU/worker/storage profiles and safe write-set candidate rejection evidence."""
import copy
import cProfile
import io
import json
import math
from pathlib import Path
import pstats
import statistics
import sys
import time

OUT=Path(__file__).parent;name=sys.argv[1];root=OUT/'work'/name/'engineering'
sys.path[:0]=[str(root/p) for p in ('backend/src','data-management','ai/src','backend/tests')]
from onlinecoc.host import Host
from onlinecoc import chat, contracts
from onlinecoc.model import validate
from onlinecoc.worker_process import execute_request
from onlinecoc.server import runtime_info
from onlinecoc_data import canonical
results={'environment':'isolated local Demo; no external provider','samples':30}
def measure(label,fn):
    samples=[];last=None
    for _ in range(30):
        start=time.perf_counter();last=fn();samples.append((time.perf_counter()-start)*1000)
    results[label]={'p50Ms':statistics.median(samples),'p95Ms':sorted(samples)[28],'samplesMs':samples}
    print(label,round(results[label]['p50Ms'],2),round(results[label]['p95Ms'],2),flush=True)
    return last
h=Host(OUT/'work'/name/('profile-room-'+str(time.time_ns())),bootstrap='test-password')
try:
    s=h.state();a=s['artifacts'][s['activeRuleset']]
    request={'sources':a['sources'],'job':{'kind':'run','rule':'demo.attack','mode':'calculation','account':'player1',
        'input':{'actor':'actor-player1'},'state':h.snapshot_for_execution(s),'data':a['data']}}
    results['warmWorkerExample']=measure('worker.warm',lambda:execute_request(request))['workerTimings']
    results['coldWorkerExample']=measure('worker.cold',lambda:execute_request(request,reuse=False))['workerTimings']
    for i in range(10000):chat.apply(s,'kp','chat.message.send',{'channelId':'general','text':'history '+str(i)},float(i))
    validate(s);raw=canonical(s)
    measure('snapshot.deepcopy',lambda:copy.deepcopy(s))
    measure('snapshot.jsonDecodeCandidate',lambda:json.loads(raw))
    measure('validation.full',lambda:validate(s))
    old=contracts._message_key
    def canonical_key(m):
        key=canonical(m) if contracts._json_tree(m) else None
        return key,len(key) if key is not None else 0
    contracts._message_key=canonical_key;validate(s)
    measure('validation.previousCanonicalKey',lambda:validate(s))
    contracts._message_key=old;validate(s)
    measure('commit.full',lambda:h.commit(s))
    results['commitPhases']=h.metrics['commitPhases'][-30:]
    results['storePhaseExample']=h.store.last_commit_metrics
    profiler=cProfile.Profile();profiler.enable();validate(s);profiler.disable()
    stream=io.StringIO();pstats.Stats(profiler,stream=stream).sort_stats('cumulative').print_stats(18)
    results['validationProfile']=stream.getvalue()
    results['memory']=runtime_info()
    results['payloadBytes']=len(raw)
    # A generic changed-object-only validator misses unchanged-row cross-references.
    corrupt=copy.deepcopy(s);corrupt['members'].pop('player1')
    try:validate(corrupt);results['writeSetOnlyRejected']=False
    except Exception as e:results['writeSetOnlyRejected']=getattr(e,'code',type(e).__name__)
    results['decisions']={
      'compiledLuaReuse':'Not adopted: compare fresh VM loadMs with cold importMs; fresh VM retained for every request.',
      'writeSetOnly':'Not adopted: current mutable snapshot API has no immutable ownership/version contract; cross-record and full graph checks still run.',
      'jsonDecodeSnapshot':'Measured only: generic store currently preserves Python value types until reopen; changing that contract requires separate migration.'}
finally:h.close()
(OUT/(name+'-profile.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
