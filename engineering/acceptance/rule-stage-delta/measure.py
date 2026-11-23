"""Actual HTTP envelope bytes and untouched 64KiB boundary, isolated Demo."""
import copy,json,sys,time
from pathlib import Path
OUT=Path(__file__).parent;root=OUT/'work'/sys.argv[1]/'engineering'
sys.path[:0]=[str(root/p) for p in ('backend/src','data-management','ai/src','backend/tests')]
import httpx
from fastapi.testclient import TestClient
from onlinecoc.host import Host
from onlinecoc.server import create_app
from onlinecoc.registry import stage
from onlinecoc_data import canonical
from test_host import message

h=Host(OUT/'work'/sys.argv[1]/('measure-'+str(time.time_ns())),bootstrap='test-password')
results={'maxCommandBytes':65536,'externalCalls':0,'cases':[]}
def body(envelope):return httpx.Request('POST','http://local/',json=envelope).content
try:
    with TestClient(create_app(h,8765),base_url='http://127.0.0.1:8765') as client:
        client.headers['origin']='http://127.0.0.1:8765'
        client.headers['x-csrf-token']=client.post('/api/v1/login',json={'loginName':'kp','password':'test-password'}).json()['csrf']
        initial=h.state();original=initial['artifacts'][initial['activeRuleset']]
        for padding in (30000,60000,96000):
            sources={**original['sources'],'padding.lua':'--'+('x'*padding)+"\nreturn rule('padding',{},function() return 1 end)"}
            data={**original['data'],'padding.json':'y'*padding}
            artifact=stage(sources,data);state=h.state();state['artifacts'][artifact['revision']]=artifact;state['activeRuleset']=artifact['revision'];h.commit(state)
            changed={**data,'small.json':{'value':2}}
            full=message(h,'kp','rule.stage',{'sources':sources,'data':changed},'full-'+str(padding))
            delta=message(h,'kp','rule.stage.delta',{'baseRevision':artifact['revision'],'data':{'small.json':{'value':2}}},'delta-'+str(padding))
            old=client.post('/api/v1/commands',content=body(full));new=client.post('/api/v1/commands',content=body(delta))
            assert new.status_code==200 and new.json()['status']=='committed',new.text
            actual=h.state()['artifacts'][new.json()['result']]
            assert actual==stage(sources,changed) and h.state()['activeRuleset']==artifact['revision']
            expected=413 if len(body(full))>65536 else 200;assert old.status_code==expected
            results['cases'].append({'paddingPerCollection':padding,'fullEnvelopeBytes':len(body(full)),
                'deltaEnvelopeBytes':len(body(delta)),'fullHttpStatus':old.status_code,'deltaHttpStatus':new.status_code,
                'sameAsFullArtifact':True,'activeUnchanged':True,'sourceBytes':len(canonical(sources)),'dataBytes':len(canonical(changed))})
        # A streamed body still has the identical cap, independent of delta mode.
        envelope=message(h,'kp','rule.stage.delta',{'baseRevision':h.state()['activeRuleset'],'data':{'boundary.json':1}},'boundary')
        raw=body(envelope);padded=raw+b' '*(65536-len(raw))
        exact=client.post('/api/v1/commands',content=iter((padded[:32000],padded[32000:])))
        over=client.post('/api/v1/commands',content=iter((padded,b' ')))
        assert exact.status_code==200 and exact.json()['status']=='committed'
        assert over.status_code==413
        results['streamedBoundary']={'at65536':exact.status_code,'at65537':over.status_code}
finally:h.close()
(OUT/'measurements.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False,indent=2))
