"""Explicit data edits preserve authoritative baseline and normal publication checks."""
import asyncio
import copy
import json
from types import SimpleNamespace
import pytest
from jsonschema import Draft202012Validator
from onlinecoc_ai import data_edits
from onlinecoc_ai.contracts import digest
from onlinecoc_ai.errors import AiError,require
from onlinecoc_ai.answers import parse_answer
from onlinecoc_ai.context import Context
from onlinecoc_ai.sandbox import stage
from test_entrypoints import application,command,committed
from test_coordinator import setup,Fake,completion,wait_task
from test_access_batches import session,submit,tool_call
from test_context import enable


def delta():return {'schemaVersion':1,'configurations':[],'sources':{},'data':{},'suggestions':[]}

def game():return {'title':'保留标题','items':[{'id':str(i),'name':'旧物品'+str(i)} for i in range(31)],'rooms':{'unknown-to-model':{'description':'保留全部字段'}},'tuning':{'a':1,'b':2}}

def unit():
    snapshot=({'scopeId':'test','facts':{'sessionAccess':{'level':'administrator'}}},{},{'revision':'r1','data':{'game.json':game(),'other.json':{'unchanged':True}}})
    def kp(account):require(account=='kp','PERMISSION_DENIED')
    app=SimpleNamespace(host=SimpleNamespace(kp=kp,state=lambda:{'aiControl':{'settings':{'externalSources':{'kp':True}}}}),repository=SimpleNamespace(state=lambda:{'settings':{}}))
    return app,snapshot,{}

def ref(app,snapshot,pool,path):return data_edits.read(app,'kp',snapshot,{'file':'game.json','path':path,'limit':1},pool)['editRef']

def test_append_from_partial_array_preserves_all_unread_data_and_is_repeatable():
    app,snapshot,pool=unit();before=copy.deepcopy(snapshot);r=ref(app,snapshot,pool,['items'])
    edits=[{'op':'append','ref':r,'keyField':'id','value':{'id':'flame-needle','name':'火焰针剑'}}]
    value,proof=data_edits.compile_edits(delta(),edits,snapshot[2],pool)
    assert value['data']['game.json']['items'][:-1]==game()['items']
    assert {k:v for k,v in value['data']['game.json'].items() if k!='items'}=={k:v for k,v in game().items() if k!='items'}
    assert snapshot==before and delta()['data']=={} and len(proof)==1
    assert data_edits.compile_edits(delta(),edits,snapshot[2],pool)[0]==value

def test_append_uniqueness_checks_items_outside_returned_page():
    app,snapshot,pool=unit();r=ref(app,snapshot,pool,['items'])
    with pytest.raises(AiError,match='DATA_EDIT_KEY_CONFLICT'):
        data_edits.compile_edits(delta(),[{'op':'append','ref':r,'keyField':'id','value':{'id':'30','name':'duplicate outside page'}}],snapshot[2],pool)

def test_add_replace_remove_are_explicit_and_preserve_siblings():
    app,snapshot,pool=unit();a=ref(app,snapshot,pool,['tuning']);b=ref(app,snapshot,pool,['tuning','a']);c=ref(app,snapshot,pool,['tuning','b'])
    value,_=data_edits.compile_edits(delta(),[{'op':'add','ref':a,'key':'c','value':3},{'op':'replace','ref':b,'value':4},{'op':'remove','ref':c}],snapshot[2],pool)
    assert value['data']['game.json']['tuning']=={'a':4,'c':3}
    assert value['data']['game.json']['items']==game()['items']

@pytest.mark.parametrize('case,code',[('mixed','DATA_EDIT_MIXED_REPLACEMENT'),('stale','DATA_EDIT_BASELINE_STALE'),('forged','DATA_EDIT_REFERENCE_UNVERIFIED'),('incomplete','DATA_EDIT_INCOMPLETE_READ'),('overlap','DATA_EDIT_OVERLAP'),('array-remove','DATA_EDIT_TARGET_INVALID'),('root','DATA_EDIT_INCOMPLETE_READ'),('add-existing','DATA_EDIT_TARGET_INVALID')])
def test_rejects_unsafe_edits_atomically(case,code):
    app,snapshot,pool=unit();r=ref(app,snapshot,pool,['items']);change=delta();edits=[{'op':'append','ref':r,'keyField':'id','value':{'id':'new','name':'x'}}]
    artifact=copy.deepcopy(snapshot[2])
    if case=='mixed':change['data']['game.json']={'items':[]}
    if case=='stale':artifact['data']['game.json']['title']='concurrent change'
    if case=='forged':edits[0]['ref']='0'*64
    if case=='incomplete':edits=[{'op':'replace','ref':r,'value':[]}]
    if case=='overlap':edits.append({'op':'replace','ref':r,'value':[]})
    if case=='array-remove':edits=[{'op':'remove','ref':ref(app,snapshot,pool,['items',0])}]
    if case=='root':edits=[{'op':'replace','ref':ref(app,snapshot,pool,[]),'value':{}}]
    if case=='add-existing':edits=[{'op':'add','ref':ref(app,snapshot,pool,['tuning']),'key':'a','value':100}]
    before=copy.deepcopy(artifact)
    with pytest.raises(AiError,match=code):data_edits.compile_edits(change,edits,artifact,pool)
    assert artifact==before

def test_multiple_appends_and_large_object_index_do_not_require_reconstruction():
    app,snapshot,pool=unit();snapshot[2]['data']['game.json']['large']={str(i):'x'*4000 for i in range(20)}
    index=data_edits.read(app,'kp',snapshot,{'file':'game.json'},pool)
    assert not index['complete'] and 'value' not in index and 'items' in [x['key'] for x in index['keys']]
    r=ref(app,snapshot,pool,['items'])
    value,_=data_edits.compile_edits(delta(),[{'op':'append','ref':r,'keyField':'id','value':{'id':i,'name':i}} for i in ('a','b')],snapshot[2],pool)
    assert [x['id'] for x in value['data']['game.json']['items'][-2:]]==['a','b']
    assert value['data']['game.json']['large']==snapshot[2]['data']['game.json']['large']

@pytest.mark.parametrize('args',[{'file':'../absent.json'},{'file':'game.json','path':['missing']},{'file':'game.json','path':['items',True]},{'file':'game.json','path':['items'],'offset':50}])
def test_read_does_not_issue_ref_on_invalid_path_or_page(args):
    app,snapshot,pool=unit()
    with pytest.raises(AiError):data_edits.read(app,'kp',snapshot,args,pool)
    assert not pool

def install_game(app):
    room=app.host.state();old=room['artifacts'][room['activeRuleset']]
    artifact=stage(old['sources'],{**old['data'],'game.json':game()})
    room['artifacts'][artifact['revision']]=artifact;room['activeRuleset']=artifact['revision'];app.host.commit(room)
    app.proposals.pack.schemas['game.json']=Draft202012Validator({'type':'object','required':['title','items','rooms','tuning'],
        'properties':{'title':{'type':'string'},'items':{'type':'array','items':{'type':'object','required':['id','name']}}}})
    enable(app.host,kp=True,public=True,private=True)

@pytest.mark.parametrize('blocked,code',[('kp','EXTERNAL_SCOPE_DISABLED'),('queries','DATA_QUERIES_DISABLED'),('player','TOOL_FORBIDDEN')])
def test_real_application_egress_and_session_ceiling(application,blocked,code):
    app=application;install_game(app);s=session(app);r=submit(app,s);snapshot,_=Context(app.proposals).capture('kp',app.repository.state()['requests'][r['requestId']])
    if blocked=='kp':enable(app.host,kp=False)
    if blocked=='queries':committed(command(app,'ai.access.update',{'revision':1,'allowDataQueries':False,'allowPlayerChat':False,'autoApproveBatches':False}))
    if blocked=='player':snapshot[0]['facts']['sessionAccess']['level']='player'
    with pytest.raises(AiError,match=code):data_edits.read(app,'kp',snapshot,{'file':'game.json','path':['items']},{})

@pytest.mark.parametrize('repair',[False,True])
def test_model_increment_compiles_to_checked_manual_candidate(application,repair):
    app=application;install_game(app);before=copy.deepcopy(app.host.state());captured=[]
    committed(command(app,'ai.access.update',{'revision':1,'allowPlayerChat':False,'autoApproveBatches':True,'autoApproveConfigurations':True}))
    async def callback(count,messages,tools):
        if count==1:
            assert data_edits.NAME in [t['function']['name'] for t in tools]
            return tool_call(data_edits.NAME,{'file':'game.json','path':['items'],'limit':1})
        read_result=next(json.loads(m['content']) for m in messages if m.get('role')=='tool' and 'editRef' in json.loads(m['content']))
        item={'id':'flame-needle'}
        if not repair or count>2:item['name']='火焰针剑'
        output={'kind':'draft','text':'只追加物品定义，等待高危审批。','changeSet':delta(),'dataEdits':[{'op':'append','ref':read_result['editRef'],'keyField':'id','value':item}]}
        captured.append(output);return completion(output)
    async def run():
        app.coordinator.provider_factory=lambda _:Fake(callback);await app.coordinator.start()
        try:
            r=submit(app,session(app));dispatched=committed(command(app,'ai.request.dispatch',{'requestId':r['requestId']}))
            task=await wait_task(app.coordinator,dispatched['taskId'],timeout=40);assert task['status']=='review_ready',task
            proposal=app.proposals.get('kp',task['proposalId']);full=proposal['changeSet']['data']['game.json']
            assert full['items'][:-1]==game()['items'] and full['title']==game()['title'] and full['rooms']==game()['rooms']
            assert all(app.repository.state()['reports'][key]['status']=='pass' for key in proposal['reportRefs'])
            ruling=next(i for i in app.rulings.list('kp')['items'] if i['kind']=='configuration')
            assert ruling['highRisk'] and ruling['status']=='pending' and not app.host.state()['aiControl']['publications']
            assert app.host.state()['activeRuleset']==before['activeRuleset'] and app.host.state()['entities']==before['entities']
            assert proposal['revision']==(2 if repair else 1) and len(captured)==(2 if repair else 1)
            facts=app.repository.state()['contexts'][proposal['contextRef']]['facts'];assert facts['configDataEdits'][0]['op']=='append'
        finally:await app.coordinator.close()
    asyncio.run(run())

def test_data_edits_are_only_valid_on_draft():
    for kind in ('plan','clarification','batch'):
        out={'kind':kind,'text':'x','dataEdits':[]}
        if kind=='batch':out['actions']=[]
        with pytest.raises(AiError,match='MODEL_FIELDS_INVALID'):parse_answer(json.dumps(out))


@pytest.mark.parametrize('reverse',[False,True])
def test_parent_append_and_existing_child_edit_are_disjoint_in_either_order(reverse):
    app,snapshot,pool=unit();array=ref(app,snapshot,pool,['items']);child=ref(app,snapshot,pool,['items',0,'name'])
    edits=[{'op':'append','ref':array,'keyField':'id','value':{'id':'new','name':'新地点'}}, {'op':'replace','ref':child,'value':'旧地点补通路'}]
    if reverse:edits.reverse()
    result,_=data_edits.compile_edits(delta(),edits,snapshot[2],pool)
    assert result['data']['game.json']['items'][0]['name']=='旧地点补通路'
    assert result['data']['game.json']['items'][-1]=={'id':'new','name':'新地点'}
    assert result['data']['game.json']['items'][1:-1]==game()['items'][1:]


@pytest.mark.parametrize('reverse',[False,True])
def test_combined_append_and_existing_key_replacement_cannot_hide_duplicate(reverse):
    app,snapshot,pool=unit();array=ref(app,snapshot,pool,['items']);child=ref(app,snapshot,pool,['items',0,'id'])
    edits=[{'op':'append','ref':array,'keyField':'id','value':{'id':'new','name':'x'}},{'op':'replace','ref':child,'value':'new'}]
    if reverse:edits.reverse()
    with pytest.raises(AiError,match='DATA_EDIT_KEY_CONFLICT'):data_edits.compile_edits(delta(),edits,snapshot[2],pool)


def test_string_append_and_ordinary_repeating_array_use_explicit_forms():
    app,snapshot,pool=unit();snapshot[2]['data']['game.json']['stock']=[{'item':7,'count':1},{'item':7,'count':1}]
    text=ref(app,snapshot,pool,['title']);stock=ref(app,snapshot,pool,['stock'])
    result,_=data_edits.compile_edits(delta(),[{'op':'append','ref':text,'value':'，雨滴落在屋檐'},
        {'op':'append_value','ref':stock,'value':{'item':3,'count':1}}],snapshot[2],pool)
    assert result['data']['game.json']['title']=='保留标题，雨滴落在屋檐'
    assert result['data']['game.json']['stock']==[{'item':7,'count':1},{'item':7,'count':1},{'item':3,'count':1}]
    with pytest.raises(AiError,match='DATA_EDIT_OVERLAP'):
        data_edits.compile_edits(delta(),[{'op':'append','ref':text,'value':'new'},{'op':'replace','ref':text,'value':'overwrite'}],snapshot[2],pool)


def test_array_pages_expose_actual_zero_based_positions():
    app,snapshot,pool=unit()
    page=data_edits.read(app,'kp',snapshot,{'file':'game.json','path':['items'],'offset':20,'limit':2},pool)
    assert page['positions']==[{'zeroBasedIndex':20,'path':['items',20]},{'zeroBasedIndex':21,'path':['items',21]}]
    assert [v['id'] for v in page['value']]==['20','21']
