"""Lossless history compression: original bytes, complete chain and failure recovery."""
import gzip
import hashlib
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'data-management'))
from onlinecoc_data import FileDataStore, StoreError


def seed(directory,count=10,**options):
    store=FileDataStore(directory,**options)
    for i in range(count):store.commit(store.generation,{'counter':i,'payload':'repeatable fixture '*600,'commands':{'kp:one':{'status':'committed','result':1}}})
    return store


def originals(directory):
    result={}
    for p in (directory/'generations').iterdir():
        if p.name.endswith('.json.gz'):raw=gzip.decompress(p.read_bytes());name=p.name[:-3]
        elif p.name.endswith('.json'):raw=p.read_bytes();name=p.name
        else:continue
        if name in result:assert result[name]==raw
        result[name]=raw
    return result


def test_opt_in_preserves_every_original_byte_head_cas_lock_and_export(tmp_path):
    root=tmp_path/'store';store=seed(root);expected=originals(root)
    assert not list(store.generations.glob('*.gz'))
    generation,payload=store.snapshot();head=store.head
    result=store.compress_history(generation)
    assert result['historyPreserved'] and result['archivedGenerations']==8 and result['freedBytes']>0
    assert originals(root)==expected and store.head==head and store.snapshot()==(generation,payload)
    assert len(list(store.generations.glob('*.json')))==2
    with pytest.raises(StoreError,match='VERSION_CONFLICT'):store.commit(generation-1,{})
    with pytest.raises(StoreError,match='STORE_LOCKED'):FileDataStore(root)
    store.export_snapshot(tmp_path/'export.json');store.close()
    with FileDataStore(root) as reopened:
        assert reopened.snapshot()==(generation,payload) and reopened.head==head
        assert reopened.get_receipt('kp','one')['status']=='committed'
        reopened.commit(generation,payload)
    FileDataStore.restore(tmp_path/'export.json',tmp_path/'restored')
    with FileDataStore(tmp_path/'restored') as restored:assert restored.snapshot()[1]==payload


def test_auto_compression_allows_many_updates_beyond_original_quota(tmp_path):
    root=tmp_path/'store';hashes={};max_bytes=160000
    with FileDataStore(root,max_bytes=max_bytes,auto_compress=True) as store:
        for i in range(60):
            payload={'data':'compressible state '*500,'counter':i,'commands':{f'kp:{j}':{'status':'committed','result':j} for j in range(i+1)}}
            generation=store.commit(store.generation,payload)
            hashes[generation]=hashlib.sha256((store.generations/f'{generation:012d}.json').read_bytes()).hexdigest()
        assert store.inspect()['bytes']<=max_bytes and list(store.generations.glob('*.gz'))
        current=store.snapshot()
    assert len(originals(root))==60
    assert sum(len(raw) for raw in originals(root).values())>max_bytes*3
    for name,raw in originals(root).items():assert hashlib.sha256(raw).hexdigest()==hashes[int(name[:-5])]
    with FileDataStore(root,max_bytes=max_bytes) as store:
        assert store.snapshot()==current and store.get_receipt('kp','10')['result']==10


@pytest.mark.parametrize('stage',['compression_before_write','compression_half_write','compression_before_sync','compression_before_publish','compression_after_publish','compression_before_unlink','compression_after_unlink'])
def test_archive_fault_never_loses_any_generation_or_confirmed_state(tmp_path,stage):
    root=tmp_path/'store';store=seed(root);before=originals(root);snapshot=store.snapshot()
    def fault(point):
        if point==stage:raise RuntimeError('isolated injected failure')
    store.fault=fault
    with pytest.raises(RuntimeError,match='isolated injected failure'):store.compress_history()
    store.close()
    with FileDataStore(root) as reopened:
        assert reopened.snapshot()==snapshot and originals(root)==before
        reopened.compress_history(snapshot[0])
        assert originals(root)==before
        reopened.commit(snapshot[0],snapshot[1])
    with FileDataStore(root) as reopened:assert reopened.generation==snapshot[0]+1


def test_corrupt_archive_or_conflicting_duplicate_is_never_ignored(tmp_path):
    root=tmp_path/'store'
    with seed(root) as store:store.compress_history()
    path=next((root/'generations').glob('*.gz'));raw=gzip.decompress(path.read_bytes())
    path.with_name(path.name[:-3]).write_bytes(raw+b' ')
    with pytest.raises(StoreError,match='STORE_CORRUPT_OR_UNSUPPORTED'):FileDataStore(root)
    path.with_name(path.name[:-3]).write_bytes(raw)
    path.write_bytes(path.read_bytes()[:20])
    with pytest.raises(StoreError,match='STORE_CORRUPT_OR_UNSUPPORTED'):FileDataStore(root)


def test_corruption_before_archive_does_not_replace_originals(tmp_path):
    root=tmp_path/'store';store=seed(root)
    path=next(store.generations.glob('*.json'));path.write_bytes(b'corrupt')
    with pytest.raises(Exception):store.compress_history()
    assert path.read_bytes()==b'corrupt' and not list(store.generations.glob('*.gz'))
    store.close()


def test_true_capacity_limit_still_fails_without_losing_confirmed_generation(tmp_path):
    root=tmp_path/'store'
    with FileDataStore(root,max_bytes=8000,auto_compress=True) as store:
        store.commit(0,{'confirmed':'yes'})
        with pytest.raises(StoreError,match='STORE_FULL'):store.commit(1,{'huge':'x'*10000})
        assert store.snapshot()==(1,{'confirmed':'yes'})
    with FileDataStore(root,max_bytes=8000) as store:assert store.snapshot()==(1,{'confirmed':'yes'})


@pytest.mark.parametrize('options',[{'auto_compress':1},{'retain_generations':0},{'retain_generations':True}])
def test_invalid_archive_options_are_rejected_without_creating_store(tmp_path,options):
    path=tmp_path/'invalid'
    with pytest.raises(StoreError,match='INVALID_RETENTION'):FileDataStore(path,**options)
    assert not path.exists()
