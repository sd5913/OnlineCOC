import copy
import types
import pytest

from onlinecoc.errors import DomainError
from onlinecoc.publication import candidate_configurations, is_high_risk
from onlinecoc.room_read import fragments
from onlinecoc.data_queries import query, recheck
from onlinecoc.ai_contracts import digest
from onlinecoc_data import canonical


def configuration(key='item.one', revision='1', kind='item', behavior=None):
    return dict(configurationId=key,revision=revision,typeRef=kind,defaults={},behaviors=behavior or {})


def world():
    artifact={'sources':{'base.lua':'baseline'},'data':{'world.json':{'secret':'private world'}},
              'metadata':{'base.rule':{'dependencies':[]}},'revision':'r1'}
    return {'schemaVersion':4,'roomId':'review','activeRuleset':'r1','artifacts':{'r1':artifact},
            'configurations':{'item.one':configuration()},'entities':{},'relations':{},'progress':{},
            'members':{a:{'memberId':'m-'+a,'accountId':a,'role':'kp' if a=='kp' else 'player','active':True} for a in ('kp','p1','p2')},
            'chat':{'channels':{'private':{'channelId':'private','kind':'direct','participants':['p1','p2'],'name':'private','lastSequence':1,'revision':1}},
                    'messages':{'private':[{'messageId':'message-one','revision':1,'sequence':1,'kind':'text','text':'private testimony','deleted':False,'channelId':'private'}]}},
            'aiControl':{'scopeId':'scope-one','settings':{'externalSources':{'public':True,'kp':True,'private':True}}}}


def changes(state, entries=()):
    old=state['artifacts'][state['activeRuleset']]
    return {'configurations':list(entries),'sources':copy.deepcopy(old['sources']),'data':copy.deepcopy(old['data'])}


def test_add_replace_remove_projection_is_atomic_and_does_not_mutate_input():
    state=world();before=copy.deepcopy(state)
    delta=changes(state,[{'kind':'remove','id':'item.one','expectedRevision':'1','value':None},
                         {'kind':'add','id':'actor.new','expectedRevision':None,'value':configuration('actor.new',kind='actor')}])
    result=candidate_configurations(state,delta,state['artifacts']['r1'])
    assert set(result)=={'actor.new'} and state==before
    replacement=changes(state,[{'kind':'replace','id':'item.one','expectedRevision':'1','value':configuration(revision='2')}])
    assert candidate_configurations(state,replacement,state['artifacts']['r1'])['item.one']['revision']=='2'


@pytest.mark.parametrize('lifecycle',['active','archived'])
def test_delete_referenced_configuration_never_cascades(lifecycle):
    state=world();state['entities']['e']={'configurationId':'item.one','lifecycle':lifecycle,'rules':{}}
    before=copy.deepcopy(state)
    with pytest.raises(DomainError,match='REFERENCE_CONFLICT'):
        candidate_configurations(state,changes(state,[{'kind':'remove','id':'item.one','expectedRevision':'1','value':None}]),state['artifacts']['r1'])
    assert state==before


@pytest.mark.parametrize('location',['configuration','entity'])
def test_new_ruleset_must_preserve_all_existing_behavior_bindings(location):
    state=world()
    if location=='configuration':state['configurations']['item.one']['behaviors']={'use':{'ruleId':'removed.rule'}}
    else:state['entities']['e']={'configurationId':'item.one','rules':{'use':{'ruleId':'removed.rule'}}}
    with pytest.raises(DomainError,match='REFERENCE_CONFLICT'):
        candidate_configurations(state,changes(state),state['artifacts']['r1'])


def test_rule_dependencies_and_stale_configuration_changes_fail():
    state=world();artifact=copy.deepcopy(state['artifacts']['r1']);artifact['metadata']['base.rule']['dependencies']=['missing']
    with pytest.raises(DomainError,match='RULE_CYCLE_OR_MISSING'):candidate_configurations(state,changes(state),artifact)
    with pytest.raises(DomainError,match='VERSION_CONFLICT'):
        candidate_configurations(state,changes(state,[{'kind':'remove','id':'item.one','expectedRevision':'stale','value':None}]),state['artifacts']['r1'])


def test_inflight_flow_keeps_old_artifact_and_does_not_require_old_rule_in_new_catalog():
    state=world();state['flows']={'f':{'ruleset':'r1','rule':'base.rule','status':'waiting'}}
    artifact=copy.deepcopy(state['artifacts']['r1']);artifact['metadata']={'new.rule':{'dependencies':[]}}
    assert candidate_configurations(state,changes(state),artifact)==state['configurations']
    assert 'base.rule' in state['artifacts']['r1']['metadata']


@pytest.mark.parametrize('kind',['item','weapon','bag'])
def test_item_family_configuration_changes_are_high_risk(kind):
    state=world();delta=changes(state,[{'kind':'add','id':'new','value':configuration('new',kind=kind),'expectedRevision':None}])
    assert is_high_risk(state,delta,{})


def test_core_source_data_remove_and_declared_maps_are_high_risk():
    state=world()
    for key in ('sources','data'):
        delta=changes(state);delta[key]['extra']='changed';assert is_high_risk(state,delta,{})
    assert is_high_risk(state,changes(state,[{'kind':'remove','id':'item.one','value':None}]),{})
    delta=changes(state,[{'kind':'add','id':'map.room','value':configuration('map.room',kind='status')}])
    assert is_high_risk(state,delta,{'highRisk':{'configurationPrefixes':['map.']}})
    assert not is_high_risk(state,delta,{})


def test_full_room_requires_actual_kp_explicit_scope_and_authorizer():
    state=world();host=types.SimpleNamespace()
    args={'types':['room'],'limit':1}
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):query(host,state,'kp','search',args,read_scope='kp-room')
    host.ai_room_read_authorizer=lambda account:True
    for kwargs in ({'player':'p1'},{'initiator':'p1'}):
        with pytest.raises(DomainError,match='PERMISSION_DENIED'):query(host,state,'kp','search',args,read_scope='kp-room',**kwargs)
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):query(host,state,'p1','search',args,read_scope='kp-room')
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):query(host,state,'kp','search',args)
    assert query(host,state,'kp','search',args,read_scope='kp-room')['items']


def test_kp_room_private_chat_is_explicit_and_external_policy_still_applies():
    state=world();host=types.SimpleNamespace(ai_room_read_authorizer=lambda account:True)
    args={'types':['chat'],'query':'private testimony'}
    assert query(host,state,'kp','search',args)['items']==[]
    assert query(host,state,'kp','search',args,read_scope='kp-room')['items']
    state['aiControl']['settings']['externalSources']['private']=False
    assert query(host,state,'kp','search',args,read_scope='kp-room',external=True)['items']==[]
    assert query(host,state,'kp','search',{'types':['room']},read_scope='kp-room',external=True)['items']==[]


def test_room_read_proof_rechecks_grant_and_original_content():
    state=world();host=types.SimpleNamespace(ai_room_read_authorizer=lambda account:True)
    args={'types':['room'],'query':'chat','limit':1}
    page=query(host,state,'kp','search',args,read_scope='kp-room',external=True)
    assert page['items']
    reference=page['items'][0]['ref']
    result=query(host,state,'kp','read',{'refs':[reference]},read_scope='kp-room',external=True,initiator='kp')
    proof={'scopeId':'scope-one','operation':'read','args':{'refs':[reference]},'initiator':'kp','readScope':'kp-room','digest':digest(result)}
    context={'facts':{'dataQueries':[proof]}}
    recheck(host,state,'kp',context)
    host.ai_room_read_authorizer=lambda account:False
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):recheck(host,state,'kp',context)
    host.ai_room_read_authorizer=lambda account:True
    state['chat']['channels']['private']['name']='changed'
    with pytest.raises(DomainError,match='SOURCE_STALE'):recheck(host,state,'kp',context)


def test_large_room_source_splits_without_omission_or_local_identity_access():
    state=world();large='line-秘密\n'*3000
    state['artifacts']['r1']['sources']['large.lua']=large
    state['identity']={'passwordHash':'must-not-appear'}
    values=list(fragments(state));assert all(len(canonical(v))<=4096 for v in values)
    pieces=[v for v in values if v['path']==['artifacts','r1','sources','large.lua']]
    assert ''.join(v['value'] for v in sorted(pieces,key=lambda v:v['textOffset']))==large
    assert all(v['path'][0]!='identity' for v in values)


@pytest.mark.parametrize('scope',[None,'kp-room'])
def test_package_scoped_reader_only_receives_host_authorized_scope(scope):
    state=world();calls=[]
    class Adapter:
        kinds=('ruling',)
        def read(self,state,account):raise AssertionError('scoped adapter must use scoped entry')
        def read_scoped(self,state,account,*,read_scope=None):
            calls.append((account,read_scope))
            return ([{'sourceId':'package-state','kind':'ruling','id':'private-scene','revision':'1',
                      'label':'hidden package record','data':{'secret':'KP-only'},'visibility':'private'}]
                    if read_scope=='kp-room' else [])
    host=types.SimpleNamespace(ai_room_read_authorizer=lambda account:True,ai_data_adapter=Adapter())
    result=query(host,state,'kp','search',{'types':['ruling']},read_scope=scope,external=True)
    assert calls==[('kp',scope)]
    assert bool(result['items'])==(scope=='kp-room')
    calls.clear();host.ai_room_read_authorizer=lambda account:False
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):
        query(host,state,'kp','search',{'types':['ruling']},read_scope='kp-room')
    assert calls==[]


def test_legacy_package_reader_remains_compatible():
    state=world();calls=[]
    class Adapter:
        kinds=('ruling',)
        def read(self,state,account):calls.append(account);return []
    host=types.SimpleNamespace(ai_room_read_authorizer=lambda account:True,ai_data_adapter=Adapter())
    for scope in (None,'kp-room'):
        assert query(host,state,'kp','search',{'types':['ruling']},read_scope=scope)['items']==[]
    assert calls==['kp','kp']
