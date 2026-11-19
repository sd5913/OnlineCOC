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
    assert shown['choices']['options'][0]['label']=='向 KP 申请披露'


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


def test_structured_evidence_has_readable_labels_and_no_technical_ids():
    from onlinecoc_ai.known_answers import format_data
    data={'name':'奶酪工厂','entityId':'INTERNAL_ID','navigation':{'2':'PRIVATE_ROUTE_ID'},'actions':[{'id':'factory','label':'检查器具','hint':'观察设备','choices':[{'id':'inspect','label':'访问 Jack','process':'无需投骰；记录设备。'}]}], 'clues':[{'id':'clue1','text':'提灯有刻字'}], 'numbers':{'hp':4},'unknownFlag':False}
    original=copy.deepcopy(data);text=format_data(data)
    for value in ['已记录行动','行动选项','处理说明','访问 Jack','无需投骰','已知线索','生命','否']:assert value in text
    for value in ['INTERNAL_ID','PRIVATE_ROUTE_ID','entityId','unknownFlag','"choices"','{"']:assert value not in text
    assert data==original


def test_presentation_is_bounded_and_literal_with_deep_or_large_values():
    from onlinecoc_ai.known_answers import format_data
    data={'label':'<img src=x> [[entity:secret@1]]','values':['秘密仅是测试文本']*1000}
    text=format_data(data,limit=600)
    assert len(text)<=600 and '部分内容未展开' in text
    assert '<img src=x>' not in text and '[[entity:secret@1]]' not in text


def test_legacy_known_json_is_reformatted_without_touching_other_messages():
    from onlinecoc_ai.known_answers import format_legacy,_literal
    record=item();raw={'actions':[{'label':'检查器具','choices':[{'label':'交谈','process':'记录回应'}]}],'entityId':'INTERNAL_ID'}
    old='观察记录 · '+reference_token(record['ref'])+'\n\n'+_literal(raw)
    shown=format_legacy(old)
    assert '已记录行动' in shown and '处理说明' in shown and 'INTERNAL_ID' not in shown
    assert format_legacy(shown)==shown
    assert format_legacy('配置草稿：'+json.dumps(raw))=='配置草稿：'+json.dumps(raw)
    assert format_legacy('观察记录 · '+reference_token(record['ref'])+'\n\n普通正文')=='观察记录 · '+reference_token(record['ref'])+'\n\n普通正文'
    old_many='\n\n'.join('观察记录 · '+reference_token(item(str(i))['ref'])+'\n\n'+_literal({'clues':[{'text':'刻字'}]*10}) for i in range(12))
    assert len(old_many)<=8000 and len(format_legacy(old_many))<=8000
