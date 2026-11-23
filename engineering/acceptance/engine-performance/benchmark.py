"""Local isolated paired engine measurements; no external service or room."""
import copy
import json
import math
from pathlib import Path
import statistics
import sys
import time

OUT = Path(__file__).parent
name = sys.argv[1]
root = OUT / 'work' / name / 'engineering'
sys.path[:0] = [str(root / p) for p in ('backend/src', 'data-management', 'ai/src', 'backend/tests')]
from onlinecoc.host import Host
from onlinecoc.lua_runtime import execute
from onlinecoc.registry import stage
from onlinecoc import contracts, chat
from onlinecoc.model import validate
from onlinecoc_data import canonical
from test_host import message
from test_knowledge import install, observe

results = {'environment': {'python': sys.version, 'samples': 30, 'transport': 'in-process local engine; not WAN'}, 'measurements': {}}
def measure(label, fn, n=30):
    values=[]; output=None
    for _ in range(n):
        start=time.perf_counter(); output=fn();values.append((time.perf_counter()-start)*1000)
    ordered=sorted(values)
    results['measurements'][label]={'n':n,'p50Ms':statistics.median(values),'p95Ms':ordered[math.ceil(n*.95)-1],'samplesMs':values}
    print(label, round(statistics.median(values),3), round(ordered[math.ceil(n*.95)-1],3), flush=True)
    return output

h=Host(OUT/'work'/name/'room',bootstrap='test-password')
try:
    state=h.state();artifact=state['artifacts'][state['activeRuleset']]
    measure('worker.inspect',lambda:execute(artifact['sources'],{'kind':'inspect'}))
    last=measure('worker.run',lambda:execute(artifact['sources'],{'kind':'run','rule':'demo.attack','input':{'actor':'actor-player1'},'mode':'calculation','state':h.snapshot_for_execution(state),'account':'player1','data':artifact['data']}))
    results['workerDetailExample']={k:v for k,v in last.items() if k.startswith('worker')}
    measure('stage.sameArtifact',lambda:stage(artifact['sources'],artifact['data']))
    measure('project.room',lambda:h.project('player1'))
    counter=iter(range(30))
    def action():
        result=h.command('player1',message(h,'player1','action.invoke',{'actionId':'demo.check','input':{'actor':'actor-player1','skill':'skill-player1'}},'bench-'+str(next(counter))))
        assert result['status']=='committed',result
        return result
    measure('command.check',action)
    install(h);observe(h)
    measure('project.knowledge',lambda:h.project('player1'))
    msg=message(h,'player1','chat.message.send',{'channelId':'general','text':'hello'},'schema')
    measure('schema.command100',lambda:[contracts.check('command',msg) for _ in range(100)])
    measure('schema.operation100',lambda:[contracts.validate_operation('chat.message.send',{'channelId':'general','text':'hello'}) for _ in range(100)])
    state=h.state()
    # Remove disclosure policy for independent chat/storage scaling only.
    for count in (100,1000,10000):
        sample=copy.deepcopy(state)
        for i in range(count):chat.apply(sample,'kp','chat.message.send',{'channelId':'general','text':'history '+str(i)},float(i))
        validate(sample)
        measure('validate.history'+str(count),lambda:validate(sample))
        measure('canonical.history'+str(count),lambda:canonical(sample))
        measure('snapshot.history'+str(count),lambda:copy.deepcopy(sample))
        measure('commit.history'+str(count),lambda:h.commit(sample))
        results['measurements']['commit.history'+str(count)]['payloadBytes']=len(canonical(sample))
finally:
    h.close()
(OUT/(name+'-results.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
