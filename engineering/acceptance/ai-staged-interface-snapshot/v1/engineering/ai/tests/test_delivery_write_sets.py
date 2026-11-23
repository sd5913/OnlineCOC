"""Narrow durable receipt writes share verified history, never grant authority."""
import copy
import pytest
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.repository import Repository
from onlinecoc_ai.segmented_store import SegmentedStore,state_bytes
from test_entrypoints import application
from test_coordinator import setup
from test_access_batches import batch


def receipt(text='original'):
    return {'a'*64:{'text':text,'scopeId':'b'*32}}


def test_delivery_merge_reuses_unchanged_history_and_matches_full_validation(application,monkeypatch):
    app=application;batch(app);repo=app.repository
    with repo.read_scope():before=repo.read_state()
    stored=repo.store._decoded;generation=repo.store.generation;calls=[];verify=repo.verify
    monkeypatch.setattr(repo,'verify',lambda state:(calls.append(1),verify(state))[1])
    changes={'rulingDeliveries':receipt(),'messageDeliveries':receipt('response')}
    repo.update_delivery_receipts(changes)
    assert not calls and repo.store.generation==generation+1
    with repo.read_scope():after=repo.read_state()
    assert after['settings']['batches'] is before['settings']['batches']
    assert repo.store._decoded['settings']['batches'] is stored['settings']['batches']
    expected=copy.deepcopy(before)
    for name,rows in changes.items():expected['settings'][name]=rows
    assert repo.state()==expected
    verify(expected)
    assert repo.store._logical_bytes==len(state_bytes(expected))
    changes['rulingDeliveries']['a'*64]['text']='caller mutation'
    assert repo.state()['settings']['rulingDeliveries']['a'*64]['text']=='original'
    repo.update_delivery_receipts({'rulingDeliveries':receipt()})
    assert repo.store.generation==generation+1


@pytest.mark.parametrize('stage',['segment_before_write','segment_before_sync','segment_before_publish','segment_after_publish','before_publish','after_publish'])
def test_delivery_write_failure_and_lost_reply_match_atomic_head(tmp_path,stage):
    path=tmp_path/'ai';repo=Repository(path,'b'*32);before=repo.state();generation=repo.store.generation
    def fail(point):
        if point==stage:raise RuntimeError(stage)
    repo.store.fault=fail
    with pytest.raises(RuntimeError):repo.update_delivery_receipts({'rulingDeliveries':receipt()})
    after=repo.state()
    assert ('rulingDeliveries' in after['settings'])==(stage=='after_publish')
    repo.close();repo=Repository(path,'b'*32)
    try:
        assert repo.state()==after
        repo.update_delivery_receipts({'rulingDeliveries':receipt()})
        assert repo.store.generation==generation+1
        assert repo.state()['settings']['rulingDeliveries']==receipt()
    finally:repo.close()


def test_delivery_merges_inside_general_transaction_rollback_and_validate(application):
    repo=application.repository;before=repo.state();generation=repo.store.generation
    with pytest.raises(RuntimeError):
        with repo.transaction():
            repo.update_delivery_receipts({'messageDeliveries':receipt()})
            assert 'messageDeliveries' in repo.state()['settings']
            raise RuntimeError('rollback')
    assert repo.state()==before and repo.store.generation==generation
    with repo.transaction():
        repo.update_delivery_receipts({'messageDeliveries':receipt()})
        repo.update_delivery_receipts({'rulingDeliveries':receipt()})
    assert repo.store.generation==generation+1
    repo.verify(repo.state())


def test_fast_write_cannot_bypass_other_business_changes(application):
    app=application;b=batch(app);repo=app.repository
    with pytest.raises(AiError):repo.update_delivery_receipts({'batches':{}})
    bad=repo.state();bad['settings']['batches'][b['batchId']]['actions'][0]['args']['name']='invalid digest'
    repo.store.commit(repo.store.generation,bad)  # Simulate an unverified external store generation.
    generation=repo.store.generation
    with pytest.raises(AiError,match='BATCH_STATE_INVALID'):repo.update_delivery_receipts({'rulingDeliveries':receipt()})
    assert repo.store.generation==generation


def test_depth_and_size_limits_are_identical_to_aggregate(tmp_path,monkeypatch):
    from onlinecoc_ai import segmented_store
    repo=Repository(tmp_path/'ai','b'*32)
    try:
        nested={}
        for _ in range(62):nested={'next':nested}
        before=repo.state()
        with pytest.raises(AiError):repo.update_delivery_receipts({'rulingDeliveries':{'a'*64:nested}})
        full=copy.deepcopy(before);full['settings']['rulingDeliveries']={'a'*64:nested}
        with pytest.raises(AiError):repo.verify(full)
        monkeypatch.setattr(segmented_store,'STATE_BYTES',len(state_bytes(before))+5)
        with pytest.raises(AiError):repo.update_delivery_receipts({'rulingDeliveries':receipt()})
        assert repo.state()==before
    finally:repo.close()


def test_delivery_patch_reopens_old_segment_layout_and_exports_logical_backup(tmp_path):
    folder=tmp_path/'ai';repo=Repository(folder,'b'*32)
    repo.update(lambda state:state['settings'].update(padding=['original'*90]*500))
    expected=repo.state()
    # Version 2 originally packed small top-level fields into shared chunks.
    physical={'aiStorageFormat':2,'state':repo.store._encode(expected)}
    from onlinecoc_data import FileDataStore
    FileDataStore.commit(repo.store,repo.store.generation,physical);repo.close()
    repo=Repository(folder,'b'*32)
    try:
        repo.update_delivery_receipts({'rulingDeliveries':receipt()})
        expected['settings']['rulingDeliveries']=receipt()
        assert repo.state()==expected
        bundle=tmp_path/'backup.json';repo.store.export_snapshot(bundle)
    finally:repo.close()
    SegmentedStore.restore(bundle,tmp_path/'restored')
    with SegmentedStore(tmp_path/'restored') as store:assert store.snapshot()[1]==expected


@pytest.mark.parametrize('stage',['segment_after_publish','after_publish'])
def test_delivery_process_exit_recovers_without_replaying_proof(tmp_path,stage):
    import subprocess,sys
    folder=tmp_path/'ai';repo=Repository(folder,'b'*32);generation=repo.store.generation;repo.close()
    script="""
import os,sys
sys.path[:0]=PATHS
from onlinecoc_ai.repository import Repository
repo=Repository(FOLDER,'b'*32)
def crash(point):
    if point==STAGE:os._exit(73)
repo.store.fault=crash
repo.update_delivery_receipts({'rulingDeliveries':{'a'*64:{'text':'durable original'}}})
""".replace('PATHS',repr(sys.path)).replace('FOLDER',repr(str(folder))).replace('STAGE',repr(stage))
    result=subprocess.run([sys.executable,'-X','utf8','-B','-c',script],capture_output=True,timeout=30)
    assert result.returncode==73,result.stderr.decode(errors='replace')
    repo=Repository(folder,'b'*32)
    try:
        assert ('rulingDeliveries' in repo.state()['settings'])==(stage=='after_publish')
        repo.update_delivery_receipts({'rulingDeliveries':{'a'*64:{'text':'durable original'}}})
        assert repo.store.generation==generation+1
    finally:repo.close()
