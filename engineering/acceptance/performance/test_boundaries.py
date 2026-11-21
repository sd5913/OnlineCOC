"""Semantic guards for optimization: validation, byte format and quota safety."""
import copy
import json
from pathlib import Path
import sys
import pytest
from jsonschema import Draft202012Validator

ENGINEERING=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ENGINEERING/'backend/src'),str(ENGINEERING/'data-management')]
from onlinecoc import chat
from onlinecoc.contracts import MODELS,validate_model
from onlinecoc.errors import DomainError
from onlinecoc.model import demo_state
from onlinecoc_data import FileDataStore,StoreError,canonical
from onlinecoc_data.store import digest

def room():
    state=demo_state([('kp','kp'),('player1','player'),('player2','player')])
    chat.apply(state,'player1','chat.message.send',{'channelId':'general','text':'cached original'},1)
    return state

@pytest.mark.parametrize('mutation',[
    lambda m:m.update(text=123),lambda m:m.update(sequence=0),lambda m:m.update(revision=False),
    lambda m:m.update(assetIds=()),lambda m:m.update(kind='unknown'),lambda m:m.pop('senderAccountId'),
    lambda m:m.update(unknown='extra'),lambda m:m.update(createdAt='bad'),
    lambda m:m.update(card={'accountId':'kp'}),lambda m:m.update(text='x'*4001)])
def test_cached_message_still_matches_original_schema_after_mutation(mutation):
    state=room();validate_model('ChatState',state['chat'])
    mutation(state['chat']['messages']['general'][0])
    assert not Draft202012Validator(MODELS['ChatState']).is_valid(state['chat'])
    with pytest.raises(DomainError) as failure:validate_model('ChatState',state['chat'])
    assert failure.value.code=='INPUT_INVALID'
    assert failure.value.detail['path'].startswith('/messages/general/0')

@pytest.mark.parametrize('change',[
    lambda s:s['members'].pop('player1'),
    lambda s:s['chat']['messages']['general'].append(copy.deepcopy(s['chat']['messages']['general'][0])),
    lambda s:s['chat']['channels']['general'].update(lastSequence=2),
])
def test_pure_schema_cache_never_skips_live_cross_record_constraints(change):
    state=room();chat.validate(state);change(state)
    with pytest.raises(DomainError):chat.validate(state)

def test_storage_encoding_is_byte_identical_and_snapshots_remain_detached(tmp_path):
    with FileDataStore(tmp_path/'store') as store:
        for value in [None,{'z':'中文"\n','a':[1,1.5,True,None]},{'payload':{'nested':[]}}]:
            parent=store.head;number=store.generation+1;data=canonical(value)
            expected=canonical({'format':1,'generation':number,'parent':parent,
                                'digest':digest(data),'length':len(data),'payload':value})
            store.commit(store.generation,value)
            assert (store.generations/f'{number:012d}.json').read_bytes()==expected
        detached=store.snapshot()[1];detached['payload']['nested'].append(1)
        assert store.snapshot()[1]['payload']['nested']==[]
        assert store.inspect()['bytes']==sum(p.stat().st_size for p in store.generations.iterdir())

@pytest.mark.parametrize('name',['0.json','000000000000.json','01.json','broken.json.gz'])
def test_fast_quota_scan_keeps_filename_validation(tmp_path,name):
    with FileDataStore(tmp_path/'store') as store:
        (store.generations/name).write_bytes(b'{}')
        with pytest.raises(StoreError,match='STORE_CORRUPT'):store.inspect()

def test_staging_bytes_and_external_growth_are_recounted(tmp_path):
    with FileDataStore(tmp_path/'store',max_bytes=2000) as store:
        store.commit(0,{'ok':True});first=store.inspect()['bytes']
        (store.staging/'interrupted.tmp').write_bytes(b'x'*1900)
        assert store.inspect()['bytes']==first+1900
        with pytest.raises(StoreError,match='STORE_FULL'):store.commit(1,{'next':True})
        assert store.generation==1
