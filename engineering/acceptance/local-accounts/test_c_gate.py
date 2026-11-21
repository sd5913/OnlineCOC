"""Real fixture preparation plus deliberately forged reports for host-boundary checks."""
import copy
from pathlib import Path
from types import SimpleNamespace
import pytest
from onlinecoc.host import Host
from onlinecoc.ai_contracts import digest, validate_bundle, approval_digest
from onlinecoc.errors import DomainError
from onlinecoc.publication import approve, apply
from onlinecoc.model import validate
from onlinecoc_ai.pack import Pack, fixture_state
from onlinecoc_ai.sandbox import stage
from onlinecoc_ai.proposals import Proposals
from onlinecoc_ai.c_review import assessment

ROOT=Path(__file__).resolve().parent/'work/engine/engineering'

@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    h=Host(tmp_path_factory.mktemp('c-gate')/'host',bootstrap='test-password')
    pack=Pack(ROOT/'ai/tests/fixtures/pack')
    artifact=stage(pack.sources,pack.data)
    state=h.state();world=fixture_state(pack.json(pack.scenarios[0]['fixtureRef']),pack.configurations)
    for key in ('entities','relations','members','configurations','progress','collectionRevision'):state[key]=world[key]
    state['artifacts'][artifact['revision']]=artifact;state['activeRuleset']=artifact['revision'];h.commit(state)
    service=Proposals(h,pack)
    config=copy.deepcopy(pack.configurations['fixture.token']);config['revision']='2';config['defaults']['bonus']=15
    delta={'schemaVersion':1,'configurations':[{'kind':'replace','id':config['configurationId'],'expectedRevision':'1','value':config}],
        'sources':{},'data':{},'suggestions':[]}
    proposal=service.create('kp','有限使用提高检定成功率的道具',delta)
    service.validate('kp',proposal['proposalId'],1)
    bundle=service.prepared('kp',proposal['proposalId'],1)
    yield h,bundle
    service.close();h.close()

def changed(bundle,code='EXTENSION_FORBIDDEN',status='unknown'):
    result=copy.deepcopy(bundle)
    c=next(r for r in result['reports'] if r['level']=='C')
    c['status']=status;c['risk']='unknown'
    c['findings']=[{'code':code,'severity':'error','path':'/changeSet','sourceRef':'fixture','message':'synthetic host-boundary case','evidence':{},'suggestion':'KP assessment'}]
    basis={k:v for k,v in c['evidence']['reviewBasis'].items() if k not in ('basisRevision','basisDigest')}
    result['cAssessment']=assessment(result['reports'],basis)
    return result

def arguments(bundle,**extra):
    proof={k:bundle['cAssessment'][k] for k in ('basisRevision','basisDigest','reportDigest')}
    return {'proposalId':bundle['proposalId'],'proposalRevision':bundle['proposalRevision'],
        'explicitHighRiskDigest':bundle['candidateDigest'],
        'riskDecisions':{'resource':'Reviewed resource lifecycle','gameplay-risk':'Accepted bounded gameplay risk'},'cReview':proof,**extra}

def test_real_passed_bundle_approval_and_publication(prepared):
    h,bundle=prepared
    # Discover actual required author review IDs rather than inventing permission.
    args=arguments(bundle)
    args['riskDecisions']={item['id']:'Reviewed required item' for item in h.state()['aiControl']['packBinding']['contract']['reviewPolicy']['items'] if item['required']}
    args['riskDecisions']['gameplay-risk']='Accepted bounded gameplay risk'
    args['riskDecisions']['high-risk']='Explicitly reviewed the item change'
    state=h.state();result=approve(h,state,'kp',args,bundle)
    validate(state)
    out=apply(h,state,'kp',{'approvalId':result['approvalId']},'publication-test')
    assert out['approvalId']==result['approvalId'] and state['aiControl']['approvals'][result['approvalId']]['status']=='consumed'

@pytest.mark.parametrize('code',['EXTENSION_FORBIDDEN','LIVE_SCENARIO_COVERAGE_MISSING','EXISTING_INSTANCE_COVERAGE_MISSING'])
def test_only_allowlisted_unknown_can_be_explicitly_adopted(prepared,code):
    h,base=prepared;bundle=changed(base,code)
    args=arguments(bundle)
    args['riskDecisions']={item['id']:'Reviewed required item' for item in h.state()['aiControl']['packBinding']['contract']['reviewPolicy']['items'] if item['required']}
    args['riskDecisions']['gameplay-risk']='Accepted explicitly observed limitation'
    args['riskDecisions']['high-risk']='Explicitly reviewed the item change'
    validate_bundle(bundle)
    state=h.state();approved=approve(h,state,'kp',args,bundle)
    validate(state)
    stored=state['aiControl']['approvals'][approved['approvalId']]
    assert stored['reports'][-1]['status']=='unknown' and stored['cReview']==args['cReview']
    apply(h,state,'kp',{'approvalId':approved['approvalId']},'publish-adopted')

@pytest.mark.parametrize('code,status',[('RULE_TIMEOUT','unknown'),('SCENARIO_EXECUTION_FAILED','unknown'),('EXTENSION_EFFECT_FORBIDDEN','unknown'),('EXTENSION_FORBIDDEN','fail'),('EXTENSION_FORBIDDEN','error'),('EXTENSION_FORBIDDEN','pass')])
def test_technical_failure_never_bypassed(prepared,code,status):
    bundle=changed(prepared[1],code,status)
    bundle['cAssessment']['adoptable']=True
    with pytest.raises(DomainError,match='CHECKS_INCOMPLETE'):validate_bundle(bundle)

@pytest.mark.parametrize('key',['basisDigest','reportDigest','basisRevision'])
def test_forged_proof_rejected(prepared,key):
    bundle=changed(prepared[1]);bundle['cAssessment'][key]='0'*64 if key.endswith('Digest') else 999
    with pytest.raises(DomainError,match='DIGEST_MISMATCH'):validate_bundle(bundle)

def test_missing_or_stale_acceptance_rejected(prepared):
    h,base=prepared;bundle=changed(base);args=arguments(bundle)
    with pytest.raises(DomainError,match='C_REVIEW_REQUIRED'):approve(h,h.state(),'kp',{**args,'cReview':None},bundle)
    with pytest.raises(DomainError,match='C_REVIEW_REQUIRED'):approve(h,h.state(),'kp',{**args,'cReview':{**args['cReview'],'basisRevision':99}},bundle)

def test_basis_update_invalidates_approval_and_apply(prepared):
    h,bundle=prepared;args=arguments(bundle)
    args['riskDecisions']={item['id']:'Reviewed required item' for item in h.state()['aiControl']['packBinding']['contract']['reviewPolicy']['items'] if item['required']}
    args['riskDecisions']['gameplay-risk']='Accepted bounded gameplay risk'
    args['riskDecisions']['high-risk']='Explicitly reviewed the item change'
    state=h.state();approved=approve(h,state,'kp',args,bundle)
    resolver=h.ai_c_basis_resolver
    h.ai_c_basis_resolver=lambda:{'basisRevision':99,'basisDigest':'0'*64}
    try:
        with pytest.raises(DomainError,match='C_BASIS_STALE'):approve(h,h.state(),'kp',args,bundle)
        with pytest.raises(DomainError,match='C_BASIS_STALE'):apply(h,state,'kp',{'approvalId':approved['approvalId']},'stale-test')
    finally:h.ai_c_basis_resolver=resolver

def test_approval_proof_is_in_digest(prepared):
    h,bundle=prepared;args=arguments(bundle)
    args['riskDecisions']={item['id']:'Reviewed required item' for item in h.state()['aiControl']['packBinding']['contract']['reviewPolicy']['items'] if item['required']}
    args['riskDecisions']['gameplay-risk']='Accepted bounded gameplay risk'
    args['riskDecisions']['high-risk']='Explicitly reviewed the item change'
    state=h.state();result=approve(h,state,'kp',args,bundle)
    state['aiControl']['approvals'][result['approvalId']]['cReview']['basisRevision']=999
    with pytest.raises(DomainError,match='DIGEST_MISMATCH'):apply(h,state,'kp',{'approvalId':result['approvalId']},'tampered')
