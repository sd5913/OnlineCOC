"""Compare fresh sandbox worker startup with/without automatic site hooks."""
import json
from pathlib import Path
import sys
import time
HERE=Path(__file__).resolve().parent;ENGINEERING=HERE.parents[1]
sys.path[:0]=[str(ENGINEERING/'backend/src'),str(ENGINEERING/'data-management')]
from onlinecoc.lua_runtime import execute
from onlinecoc import worker_process
original=worker_process.subprocess.Popen
results={}
try:
    for mode in ('original','no-site'):
        def launch(args,**kwargs):
            if mode=='no-site':args=[args[0],'-S',*args[1:]]
            return original(args,**kwargs)
        worker_process.subprocess.Popen=launch
        values=[]
        for _ in range(8):
            start=time.perf_counter()
            result=execute({'probe.lua':"return rule('probe',{},function()return 1 end)"},{'kind':'inspect'})
            assert 'probe' in result['metadata'];values.append((time.perf_counter()-start)*1000)
        results[mode]=values
finally:worker_process.subprocess.Popen=original
(HERE/'worker-probe.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
print(json.dumps({key:sorted(values)[len(values)//2] for key,values in results.items()}))
