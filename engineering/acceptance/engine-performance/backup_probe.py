"""Measure total backup latency and outer room-lock hold time separately."""
import json
from pathlib import Path
import statistics
import sys
import threading
import time

OUT=Path(__file__).parent;name=sys.argv[1];root=OUT/'work'/name/'engineering'
sys.path[:0]=[str(root/p) for p in ('backend/src','data-management','ai/src')]
from onlinecoc.host import Host
from onlinecoc.assets import Assets,verify_bundle
from onlinecoc.server import runtime_info
class Monitor:
    def __init__(self,lock):self.lock=lock;self.local=threading.local();self.holds=[]
    def __enter__(self):
        self.lock.acquire();depth=getattr(self.local,'depth',0)
        if depth==0:self.local.started=time.perf_counter()
        self.local.depth=depth+1;return self
    def __exit__(self,*args):
        self.local.depth-=1
        if not self.local.depth:self.holds.append((time.perf_counter()-self.local.started)*1000)
        self.lock.release()
folder=OUT/'work'/name/('backups-'+str(time.time_ns()))
h=Host(folder/'host',bootstrap='test-password');assets=Assets(h)
try:
    for index in range(3):assets.upload('kp','blob'+str(index),bytes([index])*1024*1024)
    monitor=Monitor(h.lock);h.lock=monitor;rows=[]
    for i in range(30):
        count=len(monitor.holds);started=time.perf_counter();target=folder/str(i)
        assets.backup('kp',target,include_identity=True)
        rows.append({'totalMs':(time.perf_counter()-started)*1000,'lockMs':sum(monitor.holds[count:])})
        verify_bundle(target)
    results={'samples':rows,'assetBytes':3*1024*1024,'n':30,'failures':0,'memory':runtime_info()}
    for key in ('totalMs','lockMs'):
        values=sorted(r[key] for r in rows);results[key]={'p50':statistics.median(values),'p95':values[28]}
    (OUT/(name+'-backup.json')).write_text(json.dumps(results,indent=2),encoding='utf-8')
    print({key:results[key] for key in ('totalMs','lockMs')})
finally:h.close()
