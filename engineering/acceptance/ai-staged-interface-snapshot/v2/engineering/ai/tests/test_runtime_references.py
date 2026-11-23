import copy
from types import SimpleNamespace
import pytest
from onlinecoc_ai.runtime_references import attach
from onlinecoc_ai.contracts import digest
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.validation.extensions import configuration_checks


def fixture():
    declaration={'configurationIds':['test.actor'],'dataFile':'game.json','arrayPath':['items'],'indexBase':1,
        'idField':'id','labelField':'name','slots':[{'slot':3,'definitionField':'item3','quantityField':'uses3'},{'slot':7,'definitionField':'item7','quantityField':'uses7'}]}
    pack=SimpleNamespace(contract={'contextMapping':{'gameTerms':'terms.json'},'sources':[{'path':'terms.json','visibility':'kp'}]},json=lambda path:{'runtimeReferences':[declaration]})
    snapshot=({'facts':{}},{},{'revision':'frozen','data':{'game.json':{'items':[{'id':'ration','name':'口粮'},{'id':'cheese','name':'奶酪'}]}}})
    value={'items':[{'authority':'host-state','ref':{'kind':'entity'},'data':{'instanceId':'read-actor','configurationId':'test.actor','numbers':{'item3':2,'uses3':0,'item7':1,'uses7':3}}}]}
    return pack,snapshot,value,declaration


@pytest.mark.parametrize('admin,kp',[(False,True),(True,False),(False,False)])
def test_reference_projection_never_expands_player_or_disabled_kp_egress(admin,kp):
    pack,snapshot,value,_=fixture();before=copy.deepcopy((snapshot,value))
    assert attach(pack,snapshot,value,administrator=admin,kp_external=kp)==value
    assert (snapshot,value)==before


def test_reference_projection_requires_read_entity_and_tracks_frozen_definition_node():
    pack,snapshot,value,_=fixture();original=copy.deepcopy(value)
    output=attach(pack,snapshot,value,administrator=True,kp_external=True)
    projection=output['items'][0]['referenceProjections'][0]
    assert [(s['slot'],s['definitionId'],s['remainingQuantity']) for s in projection['slots']]==[(3,'cheese',0),(7,'ration',3)]
    assert value==original and projection['source']['revision']=='frozen'
    proof=snapshot[0]['facts']['configDataReads'][0]
    assert proof['path']==['items'] and proof['targetDigest']==digest(snapshot[2]['data']['game.json']['items'])
    # Mutation of an unrelated live copy cannot alter this sending-time input.
    live=copy.deepcopy(snapshot[2]);live['data']['game.json']['items'].reverse()
    assert attach(pack,snapshot,value,administrator=True,kp_external=True)==output
    assert len(snapshot[0]['facts']['configDataReads'])==1
    for unread in ({'items':[{'ref':{'kind':'entity'}}]},{'items':[]}):
        fresh=copy.deepcopy(snapshot);fresh[0]['facts']={}
        assert attach(pack,fresh,unread,administrator=True,kp_external=True)==unread and fresh[0]['facts']=={}


def test_invalid_optional_declaration_does_not_expand_or_break_query():
    pack,snapshot,value,declaration=fixture();declaration['arrayPath']=['absent']
    assert attach(pack,snapshot,value,administrator=True,kp_external=True)==value
    assert snapshot[0]['facts']=={}


@pytest.mark.parametrize('index,expected',[(1.0,True),(True,False),(1.5,False),(float('nan'),False),(float('inf'),False)])
def test_numeric_reference_accepts_integral_float_but_not_boolean_fraction_or_nonfinite(index,expected):
    pack,snapshot,value,_=fixture();value['items'][0]['data']['numbers']['item7']=index
    output=attach(pack,snapshot,value,administrator=True,kp_external=True)
    slots=output['items'][0]['referenceProjections'][0]['slots']
    assert any(s['slot']==7 and s['definitionIndex']==1 for s in slots)==expected


@pytest.mark.parametrize('invalid',[None,[],3,'invalid'])
def test_nonobject_terms_and_definition_elements_do_not_break_authorized_query(invalid):
    pack,snapshot,value,_=fixture();pack.json=lambda path:invalid
    assert attach(pack,snapshot,value,administrator=True,kp_external=True)==value
    pack,snapshot,value,_=fixture();snapshot[2]['data']['game.json']['items'][0]=invalid
    output=attach(pack,snapshot,value,administrator=True,kp_external=True)
    assert [s['slot'] for s in output['items'][0]['referenceProjections'][0]['slots']]==[3]


def test_extension_discriminator_has_exact_technical_feedback_without_changing_defaults():
    pack=SimpleNamespace(extension_validation={'defaultsSchema':'schema','baseConfiguration':'test.base','namespace':'test.new.'},
        json=lambda path:{'type':'object','properties':{'hp':{'type':'number','minimum':0}},'required':['hp']})
    state={'configurations':{'test.new.actor':{'configurationId':'test.new.actor','typeRef':'actor','defaults':{'hp':5}}}}
    with pytest.raises(AiError) as failed:configuration_checks(pack,state,{'sources':{}},{},{'sources':{}})
    assert failed.value.code=='EXTENSION_MARKER_REQUIRED' and failed.value.path=='/configurations/test.new.actor/defaults/isNpc'
    assert 'isNpc=1' in failed.value.detail and state['configurations']['test.new.actor']['defaults']=={'hp':5}
    state['configurations']['test.new.actor']['defaults']['isNpc']=1
    configuration_checks(pack,state,{'sources':{}},{},{'sources':{}})
    state['configurations']['test.new.actor']['defaults']['hp']=-1
    with pytest.raises(AiError,match='EXTENSION_DEFAULTS_INVALID'):configuration_checks(pack,state,{'sources':{}},{},{'sources':{}})


@pytest.mark.parametrize('after,touched,allowed',[
    ({'hp':7,'location':15},{'hp'},True),
    ({'hp':99,'location':15},{'hp'},False),
    ({'hp':7,'location':16},{'hp','location'},False),
    ({'hp':7,'location':15},{'hp','location'},False),
    ({'hp':7,'location':10},{'hp','location'},True)])
def test_existing_effect_ranges_only_ignore_unchanged_unwritten_fields(after,touched,allowed):
    from onlinecoc_ai.pack import local_schema
    from onlinecoc_ai.validation.extensions import validate_effect_numbers
    validator=local_schema({'type':'object','properties':{'hp':{'type':'number','maximum':10},'location':{'type':'integer','maximum':14}}})
    before={'hp':5,'location':15}
    if allowed:
        notes=validate_effect_numbers(validator,before,after,touched,existing=True)
        assert notes==([{'path':['location'],'constraint':'maximum'}] if after['location']==15 else [])
    else:
        with pytest.raises(AiError,match='EXTENSION_EFFECT_RANGE'):validate_effect_numbers(validator,before,after,touched,existing=True)
    if after['location']==15:
        with pytest.raises(AiError,match='EXTENSION_EFFECT_RANGE'):validate_effect_numbers(validator,before,after,touched)


def test_existing_root_constraint_is_not_assumed_unrelated():
    from onlinecoc_ai.pack import local_schema
    from onlinecoc_ai.validation.extensions import validate_effect_numbers
    validator=local_schema({'not':{'properties':{'location':{'const':15}},'required':['location']}})
    with pytest.raises(AiError,match='EXTENSION_EFFECT_RANGE'):
        validate_effect_numbers(validator,{'hp':5,'location':15},{'hp':6,'location':15},{'hp'},existing=True)


@pytest.mark.parametrize('write_location',[False,True])
def test_real_healing_probe_retains_old_location_but_never_writes_out_of_range(validation_case,write_location):
    from onlinecoc_ai.sandbox import stage
    from onlinecoc_ai.validation.extensions import assess_extensions
    pack,state,baseline,context,_=validation_case
    original_json=pack.json
    schema={'type':'object','properties':{'hp':{'type':'number','maximum':10},'location':{'type':'integer','maximum':14}}}
    pack.json=lambda name:schema if name=='effect-schema' else original_json(name)
    pack.extension_validation={'defaultsSchema':'effect-schema','fixtureRef':pack.scenarios[0]['fixtureRef'],
        'baseConfiguration':'fixture.actor','namespace':'fixture.ext.','rulePrefix':'fixture.'}
    state['entities']['actor-one']['numbers'].update(hp=5,location=15)
    state['configurations']['fixture.actor']['defaults']['location']=1
    source="return rule('fixture.heal', {'actor'}, function(r, actor) r.set(actor, 'hp', math.min(10, r.number(actor, 'hp') + 3)) "
    if write_location:source+="r.set(actor, 'location', 15) "
    source+='return {healed=true} end, {kp=true})'
    candidate=stage({**baseline['sources'],'heal.lua':source},baseline['data'])
    changes={'configurations':[],'sources':candidate['sources'],'data':candidate['data']}
    before=copy.deepcopy(state)
    if write_location:
        with pytest.raises(AiError,match='EXTENSION_EFFECT_RANGE'):
            assess_extensions(pack,state,baseline,candidate,changes,'kp')
    else:
        evidence=assess_extensions(pack,state,baseline,candidate,changes,'kp')
        row=next(r for r in evidence['ruleProbes'] if r['target']=='existing:actor-one')
        assert row['inheritedValidationFindings']==[{'path':['location'],'constraint':'maximum'}]
        assert all(t['steps'][0]['ok'] for t in row['trials'])
    assert state==before
