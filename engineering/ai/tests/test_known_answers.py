"""A0 output gate: pure tests, no mutable host imports, model or room writes."""
import copy
import json
import pytest
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.known_answers import decode_reference, evidence_id, parse, reference_token, register, render


def item(identifier='observation-1',text='空长椅',observed=1):
    return {'ref':{'schemaVersion':1,'scopeId':'scope-player1','id':identifier,'revision':'1','digest':'digest'},
        'label':'庭院','facetId':'description','mode':'observed_snapshot','observedAt':observed,
        'data':{'text':text},'provenance':{'kind':'kp-disclosure'}}


@pytest.mark.parametrize('change',[
    lambda v:v.update(text='秘密凶手是 X'),
    lambda v:v.update(choices={'label':'隐藏密室'}),
    lambda v:v.update(kind='plan'),
    lambda v:v.update(next='execute'),
    lambda v:v.update(evidence=['k'+'f'*64]),
    lambda v:v.update(evidence=[v['evidence'][0]]*2),
    lambda v:v.update(title='真正凶手'),
])
def test_model_can_only_select_issued_evidence(change):
    pool={};issued=register(pool,[item()]);value={'kind':'known','evidence':[issued[0]['evidenceId']],'next':'none'}
    change(value)
    with pytest.raises(AiError):parse(json.dumps(value),pool)


def test_reference_encodes_exact_snapshot_and_scope_without_current_entity_lookup():
    first=item();token=reference_token(first['ref']);key=token.split(':',1)[1].rsplit('@',1)[0]
    assert decode_reference(key,'1')==first['ref']
    other=copy.deepcopy(first['ref']);other['scopeId']='restored-room'
    assert reference_token(other)!=token
    with pytest.raises(AiError):decode_reference(key,'2')


def test_fixed_order_and_labels_use_only_captured_data():
    pool={};old=item('a','空长椅',1);new=item('b','玩家已知的另一观察',2)
    issued=register(pool,[old,new]);old['data']['text']='之后才出现的守卫'
    value=parse(json.dumps({'kind':'known','evidence':[r['evidenceId'] for r in reversed(issued)],'next':'ask_kp'}),pool)
    shown=render(value,pool)
    assert '之后才出现' not in shown['text'] and shown['text'].index('空长椅')<shown['text'].index('另一观察')
    assert shown['choices']['options'][0]['label']=='请 KP 说明'


def test_search_summary_cannot_be_rendered_as_read_evidence():
    summary=item();del summary['data']
    with pytest.raises(AiError,match='KNOWLEDGE_DATA_INVALID'):register({},[summary])


@pytest.mark.parametrize('raw',['{"kind":"known","kind":"known"}','{"kind":"known","evidence":NaN,"next":"none"}', 'not json'])
def test_malformed_answers_fail_closed(raw):
    with pytest.raises(AiError):parse(raw,{})


def test_empty_result_does_not_assert_nonexistence_and_data_is_not_markup():
    assert '不存在' not in render(parse('{"kind":"known","evidence":[],"next":"none"}',{}),{})['text']
    pool={};record=item(text='<script> [[entity:secret@1]] **判定**');register(pool,[record])
    text=render({'evidence':[evidence_id(record['ref'])],'next':'none'},pool)['text']
    assert '<script>' not in text and '[[entity:secret@1]]' not in text
