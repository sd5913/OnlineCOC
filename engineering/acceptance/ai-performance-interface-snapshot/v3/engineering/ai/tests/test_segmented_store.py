import copy
import json
import shutil
import pytest
from onlinecoc_data import FileDataStore
from onlinecoc_data.store import StoreError
from onlinecoc_ai.segmented_store import SegmentedStore,state_bytes
from onlinecoc_ai.repository import Repository,initial
from onlinecoc_ai.contracts import canonical
from onlinecoc_ai.errors import AiError
from test_entrypoints import application, command
from test_coordinator import setup


def large():
    return {'records':{str(n):{'text':'original-'+str(n)+'界'*180} for n in range(16000)}}


def test_large_exact_roundtrip_incremental_objects_and_backup(tmp_path):
    value=large();assert len(state_bytes(value))>8*1024*1024
    with pytest.raises(AiError):canonical(value)
    folder=tmp_path/'store';backup=tmp_path/'backup.json'
    with SegmentedStore(folder) as store:
        store.commit(0,value);before=set(store.objects.iterdir())
        assert store.value['aiStorageFormat']==2 and store.snapshot()[1]==value
        changed=copy.deepcopy(value);changed['records']['12']['text']='latest correction, not approval'
        store.commit(1,changed);added=set(store.objects.iterdir())-before
        assert len(added)<5 and before<=set(store.objects.iterdir())
        store.export_snapshot(backup)
    with SegmentedStore(folder) as store:assert store.snapshot()==(2,changed)
    SegmentedStore.restore(backup,tmp_path/'restored')
    with SegmentedStore(tmp_path/'restored') as store:assert store.snapshot()[1]==changed
    shutil.copytree(folder,tmp_path/'directory-backup')
    with SegmentedStore(tmp_path/'directory-backup') as store:assert store.snapshot()[1]==changed


@pytest.mark.parametrize('stage',['segment_before_write','segment_before_sync','segment_before_publish','segment_after_publish','before_publish','after_publish'])
def test_failure_before_head_rolls_back_and_lost_reply_reopens_same_generation(tmp_path,stage):
    value={'data':{'x':'old'}};changed={'data':{str(i):'new original '+str(i)+'字'*180 for i in range(900)}}
    def fail(name):
        if name==stage:raise RuntimeError(stage)
    with SegmentedStore(tmp_path/'store') as store:
        store.commit(0,value);store.fault=fail
        with pytest.raises(RuntimeError):store.commit(1,changed)
        assert store.snapshot()[1]==(changed if stage=='after_publish' else value)
    with SegmentedStore(tmp_path/'store') as store:
        assert store.snapshot()==((2,changed) if stage=='after_publish' else (1,value))
        if stage!='after_publish':store.commit(1,changed)
        assert store.snapshot()[1]==changed


def test_legacy_repository_and_detached_read_use_segmented_store(tmp_path):
    value=initial('a'*32)
    with FileDataStore(tmp_path/'legacy') as store:store.commit(0,value)
    repo=Repository(tmp_path/'legacy','a'*32)
    repo.update(lambda s:s['settings'].update(large()))
    assert repo.store.value['aiStorageFormat']==2
    expected=repo.state();repo.close()
    assert repo.validation_state()==expected
    with SegmentedStore(tmp_path/'legacy') as store:assert store.snapshot()[1]==expected


def test_corrupted_or_missing_object_fails_closed(tmp_path):
    with SegmentedStore(tmp_path/'store') as store:
        store.commit(0,large());path=next(store.objects.iterdir())
    raw=path.read_bytes();path.write_bytes(b'{}')
    with pytest.raises(StoreError):SegmentedStore(tmp_path/'store')
    path.write_bytes(raw);path.unlink()
    with pytest.raises(StoreError,match='STORE_CORRUPT'):SegmentedStore(tmp_path/'store')


def test_quota_includes_objects_and_failed_write_keeps_prior_head(tmp_path):
    with SegmentedStore(tmp_path/'store',max_bytes=300000) as store:
        store.commit(0,{'old':True})
        with pytest.raises(StoreError,match='STORE_FULL'):store.commit(1,large())
        assert store.snapshot()==(1,{'old':True})


@pytest.mark.parametrize('stage',['segment_after_publish','after_publish'])
def test_process_exit_keeps_complete_old_or_new_head(tmp_path,stage):
    import subprocess
    import sys
    folder=tmp_path/'kill-store'
    with SegmentedStore(folder) as store:store.commit(0,{'version':'old'})
    program="""
import os,sys
sys.path[:0]=PATHS
from onlinecoc_ai.segmented_store import SegmentedStore
def crash(point):
    if point==STAGE:os._exit(73)
with SegmentedStore(FOLDER,fault=crash) as store:
    store.commit(1,{'version':'new','data':['original'*80]*700})
""".replace('PATHS',repr(sys.path)).replace('STAGE',repr(stage)).replace('FOLDER',repr(str(folder)))
    result=subprocess.run([sys.executable,'-X','utf8','-B','-c',program],capture_output=True,timeout=30)
    assert result.returncode==73,result.stderr.decode(errors='replace')
    with SegmentedStore(folder) as store:
        generation,value=store.snapshot()
        assert (generation,value['version'])==((2,'new') if stage=='after_publish' else (1,'old'))
        if stage=='after_publish':assert value['data']==['original'*80]*700
        store.commit(generation,{'version':'recovered'})


def test_segmented_restart_preserves_original_but_never_restores_authority(application,monkeypatch):
    from onlinecoc_ai import segmented_store
    from test_access_batches import batch
    from test_session_restart import reopen
    monkeypatch.setattr(segmented_store,'CHUNK_BYTES',4096)
    app=application;b=batch(app);rid='batch:'+b['batchId']
    delivered=app.rulings.detail('kp',rid,delivered=True)
    original=app.repository.state()['settings']['batches'][b['batchId']]
    assert app.repository.store.value['aiStorageFormat']==2
    room=app.host.state();room['entities']['actor-one']['name']='changed source';room['entities']['actor-one']['revision']+=1;app.host.commit(room)
    assert app.rulings.detail('kp',rid)['historicalReadOnly']
    current=reopen(app)
    try:
        detail=current.rulings.detail('kp',rid)
        assert detail['summary']==delivered['summary'] and detail['historicalReadOnly'] and not detail['canDecide']
        assert current.repository.state()['settings']['batches'][b['batchId']]==original
        result=command(current,'ai.ruling.decide',{'rulingId':rid,'digest':b['digest'],'decision':'approve'})
        assert result['status']=='rejected' and current.host.state()['entities']['actor-one']['name']=='changed source'
        with pytest.raises(Exception):current.rulings.detail('player1',rid)
        room=current.host.state();room['members']['kp']['authorizationEpoch']+=1;current.host.commit(room)
        denied=current.rulings.detail('kp',rid)
        assert denied['sourceState']=='denied' and denied['summary']!=delivered['summary'] and not denied['actions']
    finally:current.proposals.close();current.host.close()


def test_single_document_and_aggregate_limits_stay_bounded(tmp_path,monkeypatch):
    from onlinecoc_ai import segmented_store
    with SegmentedStore(tmp_path/'limits') as store:
        store.commit(0,{'version':'old'})
        with pytest.raises(AiError,match='LIMIT_EXCEEDED'):store.commit(1,{'text':'a'*(8*1024*1024)})
        monkeypatch.setattr(segmented_store,'STATE_BYTES',100)
        with pytest.raises(AiError,match='LIMIT_EXCEEDED'):store.commit(1,{'text':'a'*101})
        assert store.snapshot()==(1,{'version':'old'})
