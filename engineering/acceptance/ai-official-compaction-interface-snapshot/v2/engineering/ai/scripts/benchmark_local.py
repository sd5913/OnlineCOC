"""Offline, isolated room benchmark; never opens an existing game save."""
import sys, time, json, uuid, copy, statistics, cProfile, pstats, io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'ai/src'), str(ROOT/'backend/src'), str(ROOT/'data-management')]
from onlinecoc.host import Host
from onlinecoc_ai.runtime import Runtime

def main():
    target=Path(sys.argv[1]);target.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter();host=Host(target/'host',bootstrap='offline-test-password')
    runtime=Runtime(host,ROOT/'ai/examples/ai-providers.json',ROOT/'rulepacks/demo');app=runtime.application
    report={'startupMs':round((time.perf_counter()-started)*1000,2),'historyRequests':250,'samples':{}}
    def command(op,args):
        result=app.command('kp',{'requestId':uuid.uuid4().hex,'authorityEpoch':host.epoch,'op':op,'args':args})
        assert result['status']=='committed',result
        return result['result']
    try:
        sid=command('ai.session.create',{'title':'性能夹具'})['sessionId']
        rid=command('ai.session.submit',{'sessionId':sid,'text':'公开离线测试'})['requestId']
        state=app.repository.state();sample=state['requests'][rid]
        for i in range(250):
            key=uuid.uuid4().hex;r=copy.deepcopy(sample);r.update(requestId=key,sourceId='benchmark:'+key,dedupKey=key*2,status='cancelled');state['requests'][key]=r
        app.repository.commit(state)
        for name,fn in [('create',lambda:command('ai.session.create',{'title':'新会话'})),('detail',lambda:app.sessions.get('kp',sid)),('list',lambda:app.sessions.list('kp'))]:
            values=[]
            for _ in range(7):
                start=time.perf_counter();fn();values.append(round((time.perf_counter()-start)*1000,2))
            report['samples'][name]={'medianMs':statistics.median(values),'maxMs':max(values),'allMs':values}
        profile=cProfile.Profile();profile.enable();command('ai.session.create',{'title':'分析'});profile.disable()
        stream=io.StringIO();pstats.Stats(profile,stream=stream).sort_stats('cumulative').print_stats(12)
        report['profile']=stream.getvalue();print(json.dumps(report,ensure_ascii=False,indent=2))
    finally:runtime.proposals.close();host.close()
if __name__=='__main__':main()
