"""10,000 actual ruling records, logical/host backups, restart and authority."""
import argparse,copy,hashlib,json,math,sys,time
from pathlib import Path

parser=argparse.ArgumentParser();parser.add_argument('--tree',required=True);parser.add_argument('--label',default='large-history');args=parser.parse_args()
HERE=Path(__file__).resolve().parent;tree=Path(args.tree);eng=tree/'engineering'
sys.path[:0]=[str(eng/'ai/tests'),str(eng/'ai/src'),str(eng/'backend/src'),str(eng/'data-management')]
from test_coordinator import setup
from test_entrypoints import application,command
from test_access_batches import batch
from test_session_restart import reopen
from onlinecoc_ai.contracts import digest
from onlinecoc_ai.segmented_store import SegmentedStore,state_bytes
from onlinecoc.assets import Assets,verify_bundle,restore_host
from onlinecoc.host import Host

folder=HERE/'work'/('large-history-'+str(time.time_ns()));folder.mkdir(parents=True)
fixture=setup.__wrapped__(folder);app=application.__wrapped__(next(fixture));checks=[];current=None
report={'tree':str(tree),'work':str(folder),'realModelCalls':0,'count':10000,'checks':checks,
        'measurement':'Each delivered first call starts with empty repository read cache and ruling index; storage is already open. Then 30 repeated calls. Not process startup or HTTP latency.'}
def ok(name):checks.append({'name':name,'status':'passed'});print(name,flush=True)
def stamp(value):return hashlib.sha256(state_bytes(value)).hexdigest()
def samples(fn):
    start=time.perf_counter();fn();cold=(time.perf_counter()-start)*1000;values=[]
    for _ in range(30):
        start=time.perf_counter();fn();values.append((time.perf_counter()-start)*1000)
    ordered=sorted(values)
    return {'coldMs':cold,'p50Ms':ordered[15],'p95Ms':ordered[28],'samplesMs':values,'samples':30}
try:
    b=batch(app);state=app.repository.state();original=state['settings']['batches'][b['batchId']];clones={}
    for n in range(10000):
        row=copy.deepcopy(original);row['batchId']=format(n+1,'032x');row['createdAt']+=n
        row['status']='rejected' if n%2 else 'pending'
        row['digest']=digest({k:row[k] for k in ('batchId','sessionId','requestId','creator','actions','context','baseline','authorityEpoch')})
        clones[row['batchId']]=row
    state['settings']['batches']=clones;app.repository.commit(state)
    report['stateBytes']=len(state_bytes(state));assert report['stateBytes']>8*1024*1024
    assert app.repository.store.value['aiStorageFormat']==2;ok('over_8mib_commit')
    all_ids=[];cursor=None
    while True:
        page=app.rulings.page('kp',queue='all',limit=100,before=cursor)
        assert page['activeCount']==5000
        all_ids.extend(i['rulingId'] for i in page['items']);cursor=page['nextBefore']
        if cursor is None:break
    assert len(all_ids)==len(set(all_ids))==10000;ok('all_100_pages_no_missing_or_duplicate')
    for queue,status in [('active','pending'),('archived','rejected')]:
        page=app.rulings.page('kp',queue=queue,limit=100)
        assert len(page['items'])==100 and all(i['status']==status for i in page['items']) and page['activeCount']==5000
    ok('active_archived_count_and_status')
    app.repository._read_cache=None;app.rulings._page_index=None
    report['deliveredList']=samples(lambda:app.rulings.page('kp',queue='active',limit=30,delivered=True))
    app.repository._read_cache=None;app.rulings._page_index=None
    report['archivedList']=samples(lambda:app.rulings.page('kp',queue='archived',limit=30,delivered=True))
    rid=app.rulings.page('kp')['items'][0]['rulingId'];detail=app.rulings.detail('kp',rid,delivered=True)
    try:app.rulings.detail('player1',rid)
    except Exception:pass
    else:raise AssertionError('player_read_allowed')
    ok('delivery_reuse_and_player_denial')
    logical=app.repository.state();originals=stamp(logical['settings']['batches'])
    bundle=folder/'logical.json';app.repository.store.export_snapshot(bundle)
    SegmentedStore.restore(bundle,folder/'ai-restored')
    with SegmentedStore(folder/'ai-restored') as store:assert stamp(store.snapshot()[1])==stamp(logical)
    ok('logical_backup_exact_restore')
    host_backup=folder/'host-backup';Assets(app.host).backup('kp',host_backup,True,ai_snapshot=logical);verify_bundle(host_backup)
    restore_host(host_backup,folder/'host-restored')
    attachment=json.loads((folder/'host-restored/ai-history-before-restore.json').read_bytes())
    assert stamp(attachment)==stamp(logical)
    with_host=Host(folder/'host-restored')
    try:
        assert with_host.state()['aiControl']['scopeId']!=logical['scopeId']
        assert not (folder/'host-restored/ai').exists()
    finally:with_host.close()
    ok('paired_host_backup_inert_original_and_new_scope')
    room=app.host.state();room['entities']['actor-one']['name']='Changed after delivery';room['entities']['actor-one']['revision']+=1;app.host.commit(room)
    assert app.rulings.detail('kp',rid)['historicalReadOnly']
    current=reopen(app);fresh=current.rulings.detail('kp',rid)
    assert fresh['summary']==detail['summary'] and fresh['historicalReadOnly'] and not fresh['canDecide']
    assert stamp(current.repository.state()['settings']['batches'])==originals
    assert command(current,'ai.ruling.decide',{'rulingId':rid,'digest':detail['digest'],'decision':'approve'})['status']=='rejected'
    assert current.host.state()['entities']['actor-one']['name']=='Changed after delivery'
    ok('restart_stale_originals_and_approval_recheck')
    room=current.host.state();room['members']['kp']['authorizationEpoch']+=1;current.host.commit(room)
    denied=current.rulings.detail('kp',rid);assert denied['sourceState']=='denied' and denied['summary']!=detail['summary'] and not denied['actions']
    ok('revocation_never_restores_authority_or_body')
    report['status']='passed'
except Exception as exc:
    report.update(status='failed',error=type(exc).__name__,message=str(exc));raise
finally:
    if current:current.proposals.close();current.host.close()
    try:next(fixture)
    except StopIteration:pass
    (HERE/(args.label+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
