"""Reproducible isolated medium-size disclosure benchmark (no model calls)."""
import copy
import json
import platform
import statistics
import sys
import tempfile
import time
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'backend/src'),str(ROOT/'backend/tests'),str(ROOT/'data-management')]
from onlinecoc.host import Host
from onlinecoc.model import entity, visible
from onlinecoc_data import canonical
from test_knowledge import install,observe,provider,descriptor

def main():
    with tempfile.TemporaryDirectory(prefix='onlinecoc-knowledge-bench-') as tmp:
        h=Host(tmp,bootstrap='test-password')
        try:
            install(h);observe(h);s=h.state();k=s['knowledge']
            template_o=next(iter(k['observations'].values()));template_g=next(iter(k['grants'].values()))
            k['observations']={};k['grants']={}
            for n in range(1,21):
                account='player'+str(n)
                s['members'][account]={'memberId':'member-'+account,'accountId':account,'active':True,'role':'player','authorizationEpoch':1,'metadata':{}}
            for n in range(1000):
                key='benchmark-'+str(n);e=entity(key,'actor','Evidence '+str(n),None,hp=10,maxHp=10,armor=0,attack=0);s['entities'][key]=e
                obs=copy.deepcopy(template_o);obs.update(observationId='observation-'+str(n),resource={'namespace':'case','kind':'witness','id':key},
                    sourceGuard={'entityId':key,'configurationId':'demo.actor'},sequence=n+1,facets={'identity':{'data':{'name':e['name']},'digest':''}})
                from onlinecoc.knowledge.models import digest
                obs['facets']['identity']['digest']=digest(obs['facets']['identity']['data']);k['observations'][obs['observationId']]=obs
                for j in range(5):
                    account='player'+str((n+j)%20+1);grant=copy.deepcopy(template_g)
                    grant.update(grantId=f'grant-{n}-{j}',subject={'kind':'account','accountId':account,'memberId':'member-'+account},resource=obs['resource'],observationId=obs['observationId'])
                    k['grants'][grant['grantId']]=grant
            k['revision']=1001;h.commit(s)
            commit_ms=h.metrics['commits'][-1]
            h.close()
            process=subprocess.run([sys.executable,'-B',str(Path(__file__)),'--open-only',tmp],capture_output=True,text=True,check=True)
            cold_open_ms=json.loads(process.stdout)['openMs']
            h=Host(tmp)
            h.register_knowledge_provider(descriptor(),provider())
            start=time.perf_counter();cold_page=h.knowledge.search('player1',{'limit':50})
            cold_search_ms=(time.perf_counter()-start)*1000
            if '--cold-only' in sys.argv:
                path=Path(__file__).with_name('performance.json');result=json.loads(path.read_text(encoding='utf-8'))
                started=time.perf_counter();observe(h,entity='benchmark-0');command_ms=(time.perf_counter()-started)*1000
                result['cold']={'openMs':cold_open_ms,'firstSearchMs':cold_search_ms,'initialFullCommitMs':commit_ms,'items':len(cold_page['items']),
                                'warmObserveCommandMs':command_ms,'warmCommitMs':h.metrics['commits'][-1],
                                'note':'cold open uses a fresh process; warmObserve adds one observation/grant after the 5000-grant fixture'}
                path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                print(json.dumps(result['cold']),flush=True);return
            refs=[i['ref'] for i in h.knowledge.search('player1',{'limit':50})['items'][:12]]
            proof=h.knowledge.evidence('player1',refs,player=True)
            counts={'storeSnapshots':0,'guard':0,'pin':0,'live':0}
            original=h.store.snapshot
            def snapshot():counts['storeSnapshots']+=1;return original()
            h.store.snapshot=snapshot
            p=h.knowledge.providers['case-provider'];guard=p.check_guard
            def check_guard(*args):counts['guard']+=1;return guard(*args)
            p.check_guard=check_guard
            def legacy():
                state=h.state()
                return {key:e for key,e in state['entities'].items() if e['lifecycle']=='active' and visible(state,'player1',e)}
            operations={'legacy_entities':legacy,'search_50':lambda:h.knowledge.search('player1',{'limit':50}),
                        'read_12':lambda:h.knowledge.read('player1',{'refs':refs}),'recheck_12':lambda:h.knowledge.recheck('player1',proof)}
            measurements={}
            for name,fn in operations.items():
                for key in counts:counts[key]=0
                times=[]
                for _ in range(100):
                    start=time.perf_counter();fn();times.append((time.perf_counter()-start)*1000)
                measurements[name]={'p50Ms':statistics.median(times),'p95Ms':sorted(times)[94],'maxMs':max(times),'repetitions':100,'counts':dict(counts)}
                print(name,round(measurements[name]['p95Ms'],2),'ms',flush=True)
            threshold=2*measurements['legacy_entities']['p95Ms']+20
            result={'python':platform.python_version(),'platform':platform.platform(),'processor':platform.processor(),
                    'subjects':20,'resources':1000,'grants':5000,'knowledgeBytes':len(canonical(k)),
                    'roomCommitBytes':len(canonical(s)),'wsProjectionBytes':len(canonical(h.project('player1'))),
                    'measurements':measurements,'thresholdMs':threshold,
                    'passed':all(measurements[n]['p95Ms']<=threshold for n in ('search_50','read_12','recheck_12')),
                    'baseline':'same ledger and host snapshot, legacy visible-entity scan; no knowledge filtering',
                    'storage':'FileDataStore warm in-memory snapshot; 1 snapshot capture per request, no repeated disk/package loads'}
            result['cold']={'openMs':cold_open_ms,'firstSearchMs':cold_search_ms,'lastFullCommitMs':commit_ms,'items':len(cold_page['items'])}
            Path(__file__).with_name('performance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({'passed':result['passed'],'thresholdMs':threshold,'knowledgeBytes':result['knowledgeBytes']}),flush=True)
        finally:h.close()

if __name__=='__main__':
    if '--open-only' in sys.argv:
        start=time.perf_counter();h=Host(sys.argv[-1]);elapsed=(time.perf_counter()-start)*1000;h.close();print(json.dumps({'openMs':elapsed}))
    else:main()
