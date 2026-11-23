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

def install_game(app,document=None):
    room=app.host.state();old=room['artifacts'][room['activeRuleset']]
    artifact=stage(old['sources'],{**old['data'],'game.json':game() if document is None else document})
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
    assert page['positions']==[{'zeroBasedIndex':i,'path':['items',i],'recordFields':{'id':str(i),'name':'旧物品'+str(i)}} for i in (20,21)]
    assert [v['id'] for v in page['value']]==['20','21']


@pytest.mark.parametrize('scenario',['private-text','two-way-map','repeating-stock'])
def test_multi_goal_data_edits_reach_real_publication(application,scenario):
    from test_ambiguity_recovery import run_model
    app=application;document=game()
    document['locations']=[{'id':'courtyard','exits':[]}]
    document['stock']=[{'item':7,'count':1},{'item':7,'count':1}]
    install_game(app,document);before=copy.deepcopy(app.host.state())
    paths={'private-text':[['rooms','unknown-to-model','description']],
        'two-way-map':[['locations'],['locations',0,'exits']], 'repeating-stock':[['stock']]}[scenario]
    refs=[]
    async def callback(n,messages,tools):
        if n>1:refs.append(json.loads(messages[-1]['content'])['editRef'])
        if n<=len(paths):return tool_call(data_edits.NAME,{'file':'game.json','path':paths[n-1]})
        if scenario=='private-text':edits=[{'op':'append','ref':refs[0],'value':'\n仅KP：已经确认保密的真相。'}]
        elif scenario=='two-way-map':edits=[{'op':'append','ref':refs[0],'keyField':'id','value':{'id':'shelter','exits':['courtyard']}},
            {'op':'append_value','ref':refs[1],'value':'shelter'}]
        else:edits=[{'op':'append_value','ref':refs[0],'value':{'item':3,'count':2}}]
        return completion({'kind':'draft','text':'准备已确认的增量，等待审批。','changeSet':delta(),'dataEdits':edits})
    task,provider=run_model(app,callback,'按已确认设计准备配置，保留其他数据')
    assert task['status']=='review_ready',task
    assert provider.calls==len(paths)+1
    assert app.host.state()['activeRuleset']==before['activeRuleset']
    item=app.rulings.detail('kp','proposal:'+task['proposalId'])
    args={'rulingId':item['rulingId'],'digest':item['digest'],'decision':'approve','explicitHighRiskDigest':item['digest'],
        'riskDecisions':{r['id']:'测试确认该项风险' for r in item['risks']}}
    if item.get('cAssessment',{}).get('requiresAcceptance'):
        args['cReview']={k:item['cAssessment'][k] for k in ('basisRevision','basisDigest','reportDigest')}
    result=committed(command(app,'ai.ruling.decide',args))
    assert result['status']=='completed',result
    after=app.host.state();actual=after['artifacts'][after['activeRuleset']]['data']['game.json']
    expected=copy.deepcopy(document)
    if scenario=='private-text':expected['rooms']['unknown-to-model']['description']+='\n仅KP：已经确认保密的真相。'
    elif scenario=='two-way-map':expected['locations'][0]['exits'].append('shelter');expected['locations'].append({'id':'shelter','exits':['courtyard']})
    else:expected['stock'].append({'item':3,'count':2})
    assert actual==expected and after['entities']==before['entities']
    assert app.rulings.detail('kp',item['rulingId'])['status']=='completed'


@pytest.mark.parametrize('correct',[True,False])
def test_data_reference_failure_repairs_same_proposal_and_rechecks_all_layers(application,correct):
    from test_ambiguity_recovery import run_model
    app=application;document=game();document['locations']=[{'index':1,'exits':[]}];install_game(app,document)
    pack=app.proposals.pack;original=pack.json
    pack.contract['contextMapping']['dataReferences']='synthetic-map-refs'
    pack.json=lambda name:([{'dataRef':'game.json','pointer':'/locations','idKey':'index','referencesKey':'exits','allowSelf':False}]
        if name=='synthetic-map-refs' else original(name))
    refs=[]
    async def callback(n,messages,tools):
        if n==1:return tool_call(data_edits.NAME,{'file':'game.json','path':['locations']})
        if n==2:
            refs.append(json.loads(messages[-1]['content'])['editRef'])
            return tool_call(data_edits.NAME,{'file':'game.json','path':['locations',0,'exits']})
        if n==3:refs.append(json.loads(messages[-1]['content'])['editRef'])
        if n==4:
            error=json.loads(messages[-1]['content'])['errors'][0]
            assert error['code']=='DATA_REFERENCE_CONFLICT' and error['path']=='/data/game.json/locations/0/exits'
            return tool_call(data_edits.NAME,{'file':'game.json','path':['locations',0,'exits']})
        value=2 if correct and n>3 else 1
        return completion({'kind':'draft','text':'准备双向连接','changeSet':delta(),'dataEdits':[
            {'op':'append','ref':refs[0],'keyField':'index','value':{'index':2,'exits':[1]}},
            {'op':'append_value','ref':refs[1],'value':value}]})
    before=app.host.state()['activeRuleset'];task,provider=run_model(app,callback,'追加地点并与原地点双向连接')
    assert len(app.repository.state()['proposals'])==1 and app.host.state()['activeRuleset']==before
    proposal=app.proposals.get('kp',task['proposalId'])
    if correct:
        assert task['status']=='review_ready' and proposal['revision']==2 and provider.calls==5,task
        assert all(app.repository.state()['reports'][key]['status']=='pass' for key in proposal['reportRefs'])
    else:
        assert task['status']=='failed' and task['error']=='MODEL_OUTPUT_INVALID' and provider.calls==6,task
        assert app.repository.state()['reports'][proposal['reportRefs'][1]]['status']=='fail'
    assert not app.host.state()['aiControl']['publications']
