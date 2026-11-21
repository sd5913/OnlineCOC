"""KP candidate labels aid discovery; identity/evidence and PL knowledge stay strict."""
import copy
from types import SimpleNamespace
import pytest
from onlinecoc.ai_contracts import digest
from onlinecoc.data_queries import query,recheck
from onlinecoc.errors import DomainError
from onlinecoc.model import demo_state,entity


@pytest.fixture
def case():
    state=demo_state([('kp','kp'),('player1','player'),('player2','player')])
    state['entities']['actual-character']=entity('actual-character','actor','木栗','player1',hp=10,maxHp=10)
    state['entities']['actual-character']['configurationId']='sv.character'
    state['configurations']['sv.character']={**state['configurations']['demo.actor'],'configurationId':'sv.character'}
    state['aiControl']['settings']['externalSources']={'public':True,'kp':True,'private':True}
    calls=[]
    class Adapter:
        kinds=()
        def reference_label(self,kind,key,fallback):
            calls.append((kind,key,fallback))
            return '木栗（player1 的树桩镇角色）' if key=='actual-character' else fallback
    knowledge=SimpleNamespace(managed=lambda *args:False)
    host=SimpleNamespace(ai_data_adapter=Adapter(),knowledge=knowledge)
    return host,state,calls


def search(host,state,text='',**kwargs):
    return query(host,state,'kp','search',{'types':['entity'],'query':text,'limit':50},**kwargs)


def test_kp_finds_bound_character_without_rewriting_entity_or_six_field_ref(case):
    host,state,calls=case;before=copy.deepcopy(state)
    result=search(host,state,'player1 的树桩镇角色')
    assert len(result['items'])==1
    found=result['items'][0];ref=found['ref']
    assert set(ref)=={'sourceId','kind','id','revision','digest','scopeId'}
    read=query(host,state,'kp','read',{'refs':[ref]})['items'][0]
    assert read['label']==found['label'] and read['data']==state['entities']['actual-character']
    assert read['data']['name']=='木栗' and read['data']['owner']=='player1' and read['data']['configurationId']=='sv.character'
    host.ai_data_adapter=None
    ordinary=query(host,state,'kp','read',{'refs':[ref]})['items'][0]
    assert ordinary['ref']==ref and ordinary['label']=='木栗' and state==before


@pytest.mark.parametrize('result',[None,42,{},'', '   ', 'x'*161, '\ud800'])
def test_invalid_labels_fall_back_to_original_name(case,result):
    host,state,calls=case
    host.ai_data_adapter.reference_label=lambda *args:result
    found=search(host,state,'木栗')['items']
    assert len(found)==1 and found[0]['label']=='木栗'


def test_exception_or_missing_hook_falls_back_without_failing_room(case):
    host,state,calls=case
    def broken(*args):raise RuntimeError('adapter problem')
    for adapter in (SimpleNamespace(kinds=(),reference_label=broken),SimpleNamespace(kinds=()),None):
        host.ai_data_adapter=adapter
        assert search(host,state,'木栗')['items'][0]['label']=='木栗'


def test_valid_160_character_label_is_retained_after_trimming(case):
    host,state,calls=case;label='归属'+('x'*158)
    host.ai_data_adapter.reference_label=lambda kind,key,name:(' '+label+' ') if key=='actual-character' else name
    assert search(host,state,'归属')['items'][0]['label']==label


def test_label_hook_never_receives_external_policy_filtered_entity(case):
    host,state,calls=case
    state['entities']['actual-character']['visibility']='owner'
    state['aiControl']['settings']['externalSources']['private']=False
    assert search(host,state,'树桩镇角色',external=True)['items']==[]
    assert all(key!='actual-character' for _,key,_ in calls)


def test_mixed_principals_keep_filtered_original_labels(case):
    host,state,calls=case
    assert search(host,state,'树桩镇角色',initiator='player1')['items']==[]
    assert search(host,state,'木栗',initiator='player1')['items']
    assert search(host,state,'隐藏线索',initiator='player1')['items']==[]
    assert calls==[]


@pytest.mark.parametrize('account,player',[('player1',None),('kp','player1')])
def test_strict_player_queries_never_call_entity_label_hook(case,account,player):
    host,state,calls=case
    host.knowledge.capture=lambda *args,**kwargs:None
    host.knowledge.require_egress=lambda *args,**kwargs:None
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):
        query(host,state,account,'search',{'types':['entity'],'query':'player1'},player=player)
    assert calls==[]


def test_enriched_search_pagination_and_proof_bind_label_changes(case):
    host,state,calls=case
    host.ai_data_adapter.reference_label=lambda kind,key,name:'归属 player1 / '+key
    args={'types':['entity'],'query':'归属 player1','limit':2}
    kwargs={'initiator':'kp','external':True}
    first=query(host,state,'kp','search',args,**kwargs)
    second=query(host,state,'kp','search',dict(args,cursor=first['page']['nextCursor']),**kwargs)
    assert {v['ref']['id'] for v in first['items']}.isdisjoint(v['ref']['id'] for v in second['items'])
    proof={'scopeId':state['aiControl']['scopeId'],'operation':'search','args':args,'initiator':'kp','digest':digest(first)}
    context={'facts':{'dataQueries':[proof]}}
    recheck(host,state,'kp',context)
    host.ai_data_adapter.reference_label=lambda kind,key,name:'归属 player2 / '+key
    with pytest.raises(DomainError,match='SOURCE_STALE'):recheck(host,state,'kp',context)
    with pytest.raises(DomainError,match='SOURCE_STALE'):
        query(host,state,'kp','search',dict(args,cursor=first['page']['nextCursor']),**kwargs)
