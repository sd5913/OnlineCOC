import copy
import uuid
import pytest
from onlinecoc.host import Host
from onlinecoc.errors import DomainError
from onlinecoc.knowledge import HostStateProvider
from onlinecoc.knowledge.models import digest, validate
from test_host import message


def descriptor():
    return dict(policyId='case-files', namespace='case', providerId='case-provider', contractVersion=1,
                mode='required-personal', selectors=[{'kind':'entity','configurationId':'demo.actor','resourceKind':'witness'}],
                facetSchemas={
                    'identity':{'schema':{'type':'object','properties':{'name':{'type':'string'}},'required':['name'],'additionalProperties':False},'modes':['observed_snapshot'],'labelField':'name'},
                    'health':{'schema':{'type':'object','properties':{'hp':{'type':'number'}},'required':['hp'],'additionalProperties':False},'modes':['live_scope']}},
                egress={k:('filtered' if k=='ai' else 'denied') for k in ('view','query','rules','receipts','assets','export','ai')})

def provider():
    return HostStateProvider({'identity':{'name':'name'},'health':{'hp':'numbers.hp'}},live_facets=['health'])

def command(h,op,args,account='kp',command_id=None):
    return h.command(account,message(h,account,op,args,command_id or uuid.uuid4().hex))

def install(h, p=None):
    d=h.register_knowledge_provider(descriptor(),p or provider())
    result=command(h,'knowledge.policy.bind',{'policyId':d['policyId'],'descriptorDigest':d['descriptorDigest'],'expectedRevision':0})
    assert result['status']=='committed',result
    return d

def observe(h,who='player1',entity='actor-player1',**kw):
    args=dict(policyId='case-files',expectedPolicyRevision=1,subjectMemberId='member-'+who,
              resource={'namespace':'case','kind':'witness','id':entity},facetIds=['identity'],
              expectedSourceRevision=str(h.state()['entities'][entity]['revision']),reason='合成测试披露')
    args.update(kw)
    result=command(h,'knowledge.observe',args)
    assert result['status']=='committed',result
    return result['result']

@pytest.fixture
def host(tmp_path):
    h=Host(tmp_path/'room',bootstrap='test-password')
    yield h
    h.close()

def test_k01_empty_and_k24_no_ai(host):
    assert host.state()['schemaVersion']==4
    assert host.knowledge.capabilities('player1')['status']=='unavailable'
    assert 'actor-player1' in host.project('player1')['entities']
    install(host);observe(host)
    assert host.knowledge.search('player1',{})['items']
    assert host.ai_prepared_resolver is None

def test_k02_k03_subject_and_legacy_exit(host):
    install(host)
    assert 'actor-player1' not in host.project('player1')['entities']
    assert not host.knowledge.search('player1',{})['items']
    observe(host)
    ref=host.knowledge.search('player1',{})['items'][0]['ref']
    assert not host.knowledge.search('player2',{})['items']
    with pytest.raises(DomainError,match='NOT_VISIBLE'):host.knowledge.read('player2',{'refs':[ref]})
    assert host.knowledge.read('player1',{'refs':[ref]})['items'][0]['data']=={'name':'调查员 1'}
    assert 'actor-player1' not in {e['instanceId'] for e in host.query('player1','entities')}

def test_k04_fixed_versions_and_k20_archive(host):
    install(host);observe(host)
    old=host.knowledge.search('player1',{})['items'][0]
    state=host.state();state['entities']['actor-player1'].update(name='尚未披露的新名称',revision=2);host.commit(state)
    assert host.knowledge.read('player1',{'refs':[old['ref']]})['items'][0]['data']=={'name':old['label']}
    assert host.knowledge.search('player1',{})['items'][0]['label']==old['label']
    observe(host)
    assert len(host.knowledge.search('player1',{'includeHistory':True})['items'])==2
    state=host.state();state['entities']['actor-player1']['lifecycle']='archived'
    state['relations']={k:v for k,v in state['relations'].items() if 'actor-player1' not in (v['sourceId'],v['targetId'])};host.commit(state)
    assert host.knowledge.read('player1',{'refs':[old['ref']]})['items']
    state=host.state();state['entities']['actor-player1']['metadata']['knowledgeRevoked']=True;host.commit(state)
    with pytest.raises(DomainError,match='NOT_VISIBLE'):host.knowledge.read('player1',{'refs':[old['ref']]})

def test_k05_live_revisions_and_eligibility(host):
    install(host)
    args=dict(policyId='case-files',expectedPolicyRevision=1,subjectMemberId='member-player1',resource={'namespace':'case','kind':'witness','id':'actor-player1'},facetIds=['health'],reason='持续本人状态')
    assert command(host,'knowledge.subscribe',args)['status']=='committed'
    ref=host.knowledge.search('player1',{})['items'][0]['ref']
    state=host.state();state['entities']['actor-player1']['numbers']['hp']=3;state['entities']['actor-player1']['revision']+=1;host.commit(state)
    with pytest.raises(DomainError,match='NOT_VISIBLE'):host.knowledge.read('player1',{'refs':[ref]})
    ref=host.knowledge.search('player1',{})['items'][0]['ref']
    assert host.knowledge.read('player1',{'refs':[ref]})['items'][0]['data']['hp']==3
    state=host.state();state['entities']['actor-player1']['owner']='player2';host.commit(state)
    assert not host.knowledge.search('player1',{})['items']
    args['facetIds']=['identity']
    assert command(host,'knowledge.subscribe',args)['code']=='KNOWLEDGE_MODE_UNSUPPORTED'

def test_k06_equivalent_grant_and_k14_unrelated_change(host):
    install(host);grant=observe(host)
    ref=host.knowledge.search('player1',{})['items'][0]['ref'];proof=host.knowledge.evidence('player1',[ref])
    state=host.state();duplicate=copy.deepcopy(state['knowledge']['grants'][grant['grantId']]);duplicate['grantId']='duplicate';state['knowledge']['grants']['duplicate']=duplicate
    state['entities']['actor-player2']['numbers']['hp']=5;state['entities']['actor-player2']['revision']+=1;host.commit(state)
    assert host.knowledge.recheck('player1',proof)
    command(host,'knowledge.revoke',{'grantId':grant['grantId'],'expectedRevision':1,'reason':'撤第一份'})
    assert host.knowledge.recheck('player1',proof)
    command(host,'knowledge.revoke',{'grantId':'duplicate','expectedRevision':1,'reason':'撤最后一份'})
    with pytest.raises(DomainError,match='NOT_VISIBLE'):host.knowledge.recheck('player1',proof)

def test_k07_forgery_and_k08_dedupe(host):
    install(host)
    args={'policyId':'case-files','resource':{'namespace':'case','kind':'witness','id':'actor-player1'},'facetIds':['identity'],'expectedPolicyRevision':1,'expectedSourceRevision':'1','subjectMemberId':'member-player1','reason':'request'}
    assert command(host,'knowledge.observe',args,account='player1')['code']=='PERMISSION_DENIED'
    with pytest.raises(DomainError,match='INPUT_INVALID'):command(host,'knowledge.observe',{**args,'observedAt':0})
    m=message(host,'kp','knowledge.observe',args,'repeat');a=host.command('kp',m);b=host.command('kp',m)
    assert a==b and len(host.state()['knowledge']['observations'])==1
    m['payload']['args']['reason']='changed'
    with pytest.raises(DomainError,match='COMMAND_ID_CONFLICT'):host.command('kp',m)
    assert command(host,'knowledge.observe',{**args,'expectedPolicyRevision':2})['code']=='VERSION_CONFLICT'

@pytest.mark.parametrize('point',['before_knowledge_commit','after_knowledge_commit'])
def test_k09_crash_atomicity(host,point):
    install(host)
    def fault(stage):
        if stage==point:raise RuntimeError('power loss')
    host.fault=fault
    try:observe(host)
    except RuntimeError:pass
    host.fault=None
    state=host.state();expected=0 if point.startswith('before') else 1
    assert len(state['knowledge']['observations'])==len(state['knowledge']['grants'])==expected
    host.close();host.__init__(host.path)
    assert len(host.state()['knowledge']['grants'])==expected

def test_k10_persistent_policy_and_k11_future_objects(host):
    install(host);observe(host)
    ref=host.knowledge.search('player1',{})['items'][0]['ref']
    host.close();host.__init__(host.path)
    assert host.knowledge.capabilities('player1')['status']=='blocked'
    assert 'actor-player1' not in host.project('player1')['entities']
    with pytest.raises(DomainError,match='KNOWLEDGE_UNAVAILABLE'):host.knowledge.read('player1',{'refs':[ref]})
    host.register_knowledge_provider(descriptor(),provider())
    assert host.knowledge.read('player1',{'refs':[ref]})['items']
    state=host.state();new=copy.deepcopy(state['entities']['actor-player1']);new['instanceId']='future';state['entities']['future']=new;host.commit(state)
    assert 'future' not in host.project('player1')['entities']

def test_k12_member_recreated_and_k22_scope_fork(host):
    from onlinecoc.room_lifecycle import fork_scope
    install(host);observe(host);ref=host.knowledge.search('player1',{})['items'][0]['ref']
    state=host.state();state['members']['player1']['memberId']='fresh-member';host.commit(state)
    assert not host.knowledge.search('player1',{})['items']
    state['members']['player1']['memberId']='member-player1';state=fork_scope(state);host.commit(state)
    with pytest.raises(DomainError,match='NOT_VISIBLE'):host.knowledge.read('player1',{'refs':[ref]})
    assert host.knowledge.search('player1',{})['items']

def test_k15_k18_operations_and_old_receipts(host):
    from test_host import invoke
    result=invoke(host,'player1','demo.damage',{'actor':'actor-player1','amount':1},'old')
    assert result['status']=='committed'
    token=host.project('player1')['entities']['actor-player1']['viewToken']
    install(host);observe(host)
    assert not host.project('player1')['catalog']['actions']
    assert not host.project('player1')['relations']
    assert 'result' not in host.receipt('player1','old')
    assert command(host,'entity.patch',{'id':'actor-player1','name':'tamper'},account='player1')['code']=='NOT_VISIBLE'
    m=message(host,'player1','entity.patch',{'id':'actor-player1','name':'tamper'},'old-token');m['payload']['expectedViews']={'actor-player1':token}
    with pytest.raises(DomainError,match='VERSION_CONFLICT'):host.command('player1',m)
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):host.calculate('player1','demo.attack',{'actor':'actor-player1'})

def test_k19_protected_asset_url(host):
    from onlinecoc.assets import Assets
    assets=Assets(host);asset=assets.upload('kp','fixture.txt',b'secret')
    state=host.state();state['entities']['actor-player1']['components']['core.assets']=[asset];host.commit(state)
    install(host)
    with pytest.raises(DomainError,match='NOT_VISIBLE'):assets.read('player1',asset)
    assert assets.read('kp',asset)[0]==b'secret'

def test_k21_oversized_snapshot_and_query(host):
    install(host)
    # Existing entity name is bounded, so a trusted provider can expose a large facet.
    class Big(HostStateProvider):
        def pin(self,r,f,c):
            value=super().pin(r,f,c);value['facets']['identity']['name']='X'*9000;return value
    host.register_knowledge_provider(descriptor(),Big({'identity':{'name':'name'}}))
    args=dict(policyId='case-files',expectedPolicyRevision=1,subjectMemberId='member-player1',resource={'namespace':'case','kind':'witness','id':'actor-player1'},facetIds=['identity'],expectedSourceRevision='1',reason='size')
    assert command(host,'knowledge.observe',args)['code']=='KNOWLEDGE_LIMIT'
    assert not host.state()['knowledge']['grants']
    with pytest.raises(DomainError,match='INPUT_INVALID'):host.knowledge.search('player1',{'limit':51})

def test_k26_strict_data_query(host):
    from onlinecoc.data_queries import query
    with pytest.raises(DomainError,match='KNOWLEDGE_UNAVAILABLE'):query(host,host.state(),'player1','search',{})
    install(host);observe(host)
    page=query(host,host.state(),'kp','search',{'types':['knowledge']},player='player1')
    assert page['items'][0]['ref']['kind']=='knowledge'
    assert query(host,host.state(),'kp','read',{'refs':[page['items'][0]['ref']]},player='player1')['items'][0]['data']=={'name':'调查员 1'}
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):query(host,host.state(),'player1','chat',{'channelId':'room'})

def test_k09_host_effect_and_automatic_observation_same_commit(host):
    from test_host import invoke
    class Auto(HostStateProvider):
        def derive_observations(self,outcome,context):
            return [{'subjectMemberId':'member-player1','resource':{'namespace':'case','kind':'witness','id':'actor-player1'},'facetIds':['identity']}]
    install(host,Auto({'identity':{'name':'name'}}))
    result=invoke(host,'kp','demo.damage',{'actor':'actor-player1','amount':2},'native')
    assert result['status']=='committed'
    state=host.state();assert state['entities']['actor-player1']['numbers']['hp']==9
    assert len(state['knowledge']['observations'])==1
    obs=next(iter(state['knowledge']['observations'].values()))
    assert obs['provenance']['eventKey']=='native:case-provider:0'
    assert invoke(host,'kp','demo.damage',{'actor':'actor-player1','amount':2},'native')==result
    assert len(host.state()['knowledge']['observations'])==1

def test_policy_overlap_and_provider_exception_fail_closed(host):
    install(host);observe(host)
    other=descriptor();other['policyId']='other';d=host.register_knowledge_provider(other,provider())
    assert command(host,'knowledge.policy.bind',{'policyId':'other','descriptorDigest':d['descriptorDigest'],'expectedRevision':0})['code']=='KNOWLEDGE_POLICY_CONFLICT'
    class Broken(HostStateProvider):
        def check_guard(self,guard,context):raise OSError('private provider path')
    host.register_knowledge_provider(descriptor(),Broken({'identity':{'name':'name'}}))
    with pytest.raises(DomainError,match='KNOWLEDGE_UNAVAILABLE'):host.knowledge.search('player1',{})
    assert host.project('player1')['knowledge']['status']=='blocked'

def test_explicit_live_entity_compatibility_and_revoke(host):
    from onlinecoc.contracts import MODELS
    d=descriptor();d['facetSchemas']={'character':{'schema':MODELS['Entity'],'modes':['live_scope'],'labelField':'name','entityProjection':True}}
    d['egress'].update(view='filtered',query='filtered')
    class Full(HostStateProvider):
        def pin(self,r,f,c):
            e=copy.deepcopy(c['state']['entities'][r['id']])
            return {'sourceRevision':str(e['revision']),'facets':{'character':e},'sourceGuard':{'entityId':e['instanceId'],'configurationId':e['configurationId']}}
    installed=host.register_knowledge_provider(d,Full({},live_facets=['character']))
    assert command(host,'knowledge.policy.bind',{'policyId':d['policyId'],'descriptorDigest':installed['descriptorDigest'],'expectedRevision':0})['status']=='committed'
    args={'policyId':'case-files','expectedPolicyRevision':1,'subjectMemberId':'member-player1','resource':{'namespace':'case','kind':'witness','id':'actor-player1'},'facetIds':['character'],'reason':'本人完整状态'}
    grant=command(host,'knowledge.subscribe',args)['result']
    view=host.project('player1');entity=view['entities']['actor-player1']
    assert entity['numbers']['hp']==9 and entity['viewToken']
    assert 'actor-player1' not in host.project('player2')['entities']
    assert any(e['instanceId']=='actor-player1' for e in host.query('player1','entities'))
    command(host,'knowledge.revoke',{'grantId':grant['grantId'],'expectedRevision':1,'reason':'撤销'})
    assert 'actor-player1' not in host.project('player1')['entities']
    m=message(host,'player1','entity.patch',{'id':'actor-player1','name':'x'});m['payload']['expectedViews']={'actor-player1':entity['viewToken']}
    with pytest.raises(DomainError,match='VERSION_CONFLICT'):host.command('player1',m)
    d['facetSchemas']['character']['modes']=['observed_snapshot']
    with pytest.raises(DomainError,match='KNOWLEDGE_MODE_UNSUPPORTED'):host.register_knowledge_provider(d,Full({}))

def test_manage_observation_uses_previous_state_atomically(host):
    class Native(HostStateProvider):
        def derive_observations(self,outcome,context):
            assert outcome['operation']=='entity.patch'
            assert context['previousState']['entities']['actor-player1']['name']=='调查员 1'
            return [{'subjectMemberId':'member-player1','resource':{'namespace':'case','kind':'witness','id':'actor-player1'},'facetIds':['identity']}]
    install(host,Native({'identity':{'name':'name'}}))
    assert command(host,'entity.patch',{'id':'actor-player1','name':'新观察'})['status']=='committed'
    assert host.knowledge.search('player1',{})['items'][0]['label']=='新观察'

def test_structural_cache_never_bypasses_mutation_or_references(host):
    install(host);observe(host);ledger=host.state()['knowledge'];validate(ledger);validate(ledger)
    altered=copy.deepcopy(ledger);next(iter(altered['observations'].values()))['facets']['identity']['data']['name']='tampered'
    with pytest.raises(DomainError,match='INPUT_INVALID'):validate(altered)
    altered=copy.deepcopy(ledger);altered['observations']={}
    with pytest.raises(DomainError,match='INPUT_INVALID'):validate(altered)
    altered=copy.deepcopy(ledger);next(iter(altered['grants'].values()))['revision']=False
    with pytest.raises(DomainError,match='INPUT_INVALID'):validate(altered)
    validate(ledger)

def test_batch_read_proofs_capture_provider_once(host):
    class Cached(HostStateProvider):
        captures=0
        def check_guard(self,guard,context):
            if 'source-version' not in context['cache']:
                self.captures+=1;context['cache']['source-version']='one'
            return super().check_guard(guard,context)
    p=Cached({'identity':{'name':'name'}});install(host,p)
    for _ in range(14):observe(host)
    refs=[r['ref'] for r in host.knowledge.search('player1',{'includeHistory':True})['items']]
    p.captures=0;proof=host.knowledge.evidence('player1',refs,player=True)
    assert p.captures==1
    proofs=[dict(proof,refs=refs[:12]),dict(proof,refs=refs[12:])]
    p.captures=0;assert host.knowledge.recheck_many('player1',proofs)
    assert p.captures==1
    g=next(iter(host.state()['knowledge']['grants'].values()))
    command(host,'knowledge.revoke',{'grantId':g['grantId'],'expectedRevision':1,'reason':'withdraw'})
    with pytest.raises(DomainError,match='NOT_VISIBLE'):host.knowledge.recheck_many('player1',proofs)

def test_explicit_denied_egress_wins_over_provider_hooks(host):
    class Permissive(HostStateProvider):
        def authorize_operation(self,*args):return True
        def project_operation(self,op,result,reads,ctx):return result
        def project_catalog(self,actions,ctx):return actions
    p=Permissive({'identity':{'name':'name'}});install(host,p);observe(host)
    assert host.knowledge.search('player1',{})['items']
    assert host.project('player1')['catalog']['actions']==[]
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):host.calculate('player1','demo.attack',{'actor':'actor-player1'})
    assert host.knowledge.project_result(host.state(),'player1','demo.attack',{'secret':1},{}) is None
    d=descriptor();d['egress']['ai']='denied';registered=host.register_knowledge_provider(d,p)
    command(host,'knowledge.policy.bind',{'policyId':d['policyId'],'descriptorDigest':registered['descriptorDigest'],'expectedRevision':1})
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):host.knowledge.require_egress('player1','ai')
