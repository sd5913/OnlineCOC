"""Combine frozen owners' interfaces; run package regressions without live edits."""
import argparse,hashlib,json,secrets,shutil,sys
from datetime import datetime
from pathlib import Path
import harness,launch,build_web,verify_integrations
from processes import run_owned
PACK=harness.PACK;ROOT=PACK.parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--engine',type=Path,default=ROOT/'engineering/acceptance/engine-chat-interface-snapshot/v2');p.add_argument('--ai',type=Path,default=ROOT/'engineering/acceptance/ai-chat-interface-snapshot/v2');p.add_argument('--skip-delivery',action='store_true');p.add_argument('--batch-workflow',action='store_true');args=p.parse_args()
    output=PACK/'tests/output'/('chat-combined-'+secrets.token_hex(4));output.mkdir(parents=True);source=output/'source'
    report={'at':datetime.now().astimezone().isoformat(),'output':str(output),'source':str(source),'externalApiCalls':0,'checks':[]}
    original_runtime=harness.Runtime;original_launch=launch.ROOT;original_build=build_web.ROOT;original_provider=verify_integrations.ROOT
    try:
        manifests={}
        for label,snapshot in [('engine',args.engine),('ai',args.ai)]:
            metadata=json.loads((snapshot/'source.json').read_text(encoding='utf-8'));manifests[label]=metadata
            for relative,expected in metadata['files'].items():
                file=snapshot/relative
                if not file.exists():file=snapshot/'engineering'/relative
                assert hashlib.sha256(file.read_bytes()).hexdigest()==expected,(label,relative)
        shutil.copytree(args.engine/'engineering',source/'engineering',ignore=lambda directory,names:{'ai'} if Path(directory)==args.engine/'engineering' else {'__pycache__'})
        shutil.copytree(args.ai/'engineering',source/'engineering',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
        (output/'source-manifests.json').write_text(json.dumps(manifests,ensure_ascii=False,indent=2),encoding='utf-8')
        report['checks'].append('engine and AI frozen file hashes verified; separate combined runtime created')
        if not args.skip_delivery:
            delivery=run_owned([sys.executable,'-B','-X','utf8',str(PACK/'tests/verify_chat_delivery.py'),'--label','combined','--source',str(source)],capture_output=True,text=True,timeout=240)
            (output/'chat-delivery.log').write_text(delivery.stdout+'\n'+delivery.stderr,encoding='utf-8')
            assert delivery.returncode==0,delivery.stdout[-3000:]+delivery.stderr[-1200:]
            report['checks'].append('combined four-page latency, concurrent ruling, unknown receipt recovery and channel permissions passed')
        else:report['deliverySkipped']=True
        def runtime(options):
            options.host_control_dir=output/'host-control';r=original_runtime(options);r.command[2]=str(source/'engineering/backend/scripts/run.py');return r
        harness.Runtime=runtime;launch.ROOT=source;build_web.ROOT=source;verify_integrations.ROOT=source
        import verify_ai_data
        verify_ai_data.main();report['checks'].append('real package explicit message -> request -> ruling evidence preserved; message edit invalidates selected old evidence')
        import verify_ai_recovery_ui
        assert verify_ai_recovery_ui.main()==0
        if args.batch_workflow:
            import verify_batch_workflow
            assert verify_batch_workflow.main()==0
            report['checks'].append('current frozen host/AI atomic batch: automatic slot repair, consumption/rest/notification, idempotent replay and result UI passed')
        # Validate the actual current export independently of previous test outputs.
        exported=build_web.build(output/'web-build');descriptor=json.loads((exported/'web.json').read_text(encoding='utf-8'))
        assert {'method':'GET','path':'package/chat/state','query':{}} in descriptor['bridge']['service']
        assert 'stumpsville.pending.*' in descriptor['bridge']['storage']
        report['checks'].append('real AI component embedding, 1440/390px dialogs, reload, exported module graph and chat service/storage whitelist passed')
        report['passed']=True
    except Exception as e:report.update(passed=False,error=repr(e))
    finally:harness.Runtime=original_runtime;launch.ROOT=original_launch;build_web.ROOT=original_build;verify_integrations.ROOT=original_provider
    report['passedCount']=len(report['checks']);canonical=PACK/'tests/chat-combined-results.json'
    if canonical.exists():
        old=json.loads(canonical.read_text(encoding='utf-8'));report['previousRuns']=old.get('previousRuns',[])+[{k:v for k,v in old.items() if k!='previousRuns'}]
    for file in [canonical,output/'results.json']:file.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False));return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
