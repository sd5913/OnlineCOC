"""Real host transactions; deterministic trusted resolver, no model/AI store.

Only validator-code fingerprint is fixed while the independent AI module is
under concurrent development. All DTO/digest/permission/commit checks are real.
"""
import copy
import pytest
from onlinecoc.host import Host
from onlinecoc.registry import stage
from onlinecoc.ai_contracts import digest, baseline_digest, candidate_digest, approval_digest, world_digest
from onlinecoc import publication
from ai_helpers import ai_message


@pytest.fixture
def host(tmp_path, monkeypatch):
    monkeypatch.setattr(publication,'validator_digest',lambda:'a'*64)
    h=Host(tmp_path/'room',bootstrap='test-password')
    s=h.state();s['configurations']['review.unused']={'configurationId':'review.unused','revision':'1','typeRef':'status','defaults':{}}
    h.commit(s)
    yield h
    h.close()


def prepared(host, entries=(), artifact=None):
    contract={'schemaVersion':1,'packId':'host-review','packVersion':'1','hostProtocolRange':{'min':1,'max':1},
              'sources':[],'schemas':{},'checks':'checks.json','scenarios':[],'metrics':'metrics.json','reviewChecklist':'review.json',
              'extensionPoints':[],'requiredChecks':[],'requiredMetrics':[],
              'reviewPolicy':{'approvalTtlSeconds':600,'items':[],'allowUnmeasuredOptional':False},
              'contextMapping':{},'highRisk':{'configurationIds':[],'configurationPrefixes':[],'ruleFiles':[],'dataFiles':[],'allowRemove':True}}
    s=host.state();s['aiControl']['packBinding']={'contract':contract,'digest':digest(contract),'validatorSetDigest':'a'*64}
    s['aiControl']['proposalHeads']['proposal']=1;host.commit(s)
    artifact=copy.deepcopy(artifact or s['artifacts'][s['activeRuleset']])
    delta={'schemaVersion':1,'configurations':list(entries),'sources':artifact['sources'],'data':artifact['data'],'suggestions':[]}
    ctx={'schemaVersion':1,'scopeId':s['aiControl']['scopeId'],'initiator':'kp','reviewPrincipal':'kp','authorityEpoch':host.epoch,
         'authorizationEpoch':s['members']['kp']['authorizationEpoch'],'baseRuleset':s['activeRuleset'],'configDigest':digest(s['configurations']),
         'contractDigest':digest(contract),'validatorSetDigest':'a'*64,'worldDigest':world_digest(s),'sourceRefs':[],'memoryRefs':[],
         'includedSources':[],'omittedSources':[],'facts':{},'createdAt':host.clock()}
    result={'schemaVersion':1,'proposalId':'proposal','proposalRevision':1,'scopeId':ctx['scopeId'],'context':ctx,'changeSet':delta,
            'artifact':artifact,'reports':[],'candidateDigest':candidate_digest(ctx,delta),'baselineDigest':baseline_digest(ctx),'createdAt':host.clock()}
    for level in 'ABC':
        result['reports'].append({'schemaVersion':1,'reportId':'fixture-'+level,'level':level,'status':'pass',
            'candidateDigest':result['candidateDigest'],'baselineDigest':result['baselineDigest'],'contextDigest':digest(ctx),
            'contractDigest':ctx['contractDigest'],'validatorSetDigest':'a'*64,'coverage':['trusted-host-fixture'],
            'findings':[],'evidence':{},'risk':'low','reviewItems':[],'createdAt':host.clock()})
    host.ai_prepared_resolver=lambda *args:copy.deepcopy(result)
    return result


def approval_args(bundle):
    return {'proposalId':'proposal','proposalRevision':1,'explicitHighRiskDigest':bundle['candidateDigest'],
            'riskDecisions':{'high-risk':'Confirm exact high-risk candidate'}}


def approve(host,bundle):
    response=host.command('kp',ai_message(host,'ai.proposal.approve',approval_args(bundle),'approve'))
    assert response['status']=='committed',response
    return response['result']['approvalId']


def remove():return {'kind':'remove','id':'review.unused','expectedRevision':'1','value':None}


def test_high_risk_requires_explicit_candidate_digest_and_reason(host):
    bundle=prepared(host,[remove()]);args=approval_args(bundle)
    for number,value in enumerate((None,'b'*64)):
        attempt=copy.deepcopy(args)
        if value is None:attempt.pop('explicitHighRiskDigest')
        else:attempt['explicitHighRiskDigest']=value
        response=host.command('kp',ai_message(host,'ai.proposal.approve',attempt,'missing-'+str(number)))
        assert response['code']=='HIGH_RISK_REVIEW_REQUIRED'
    attempt=copy.deepcopy(args);attempt['riskDecisions']={}
    assert host.command('kp',ai_message(host,'ai.proposal.approve',attempt,'no-reason'))['code']=='RISK_REVIEW_REQUIRED'
    identifier=approve(host,bundle)
    assert host.state()['aiControl']['approvals'][identifier]['explicitHighRiskDigest']==bundle['candidateDigest']
    assert 'review.unused' in host.state()['configurations']


def test_remove_apply_returns_null_and_is_exactly_once(host):
    bundle=prepared(host,[remove()]);identifier=approve(host,bundle)
    message=ai_message(host,'publication.apply',{'approvalId':identifier},'apply')
    response=host.command('kp',message);assert response['status']=='committed',response
    assert response['result']['configurationRevisions']=={'review.unused':None}
    assert 'review.unused' not in host.state()['configurations']
    assert host.command('kp',message)==response
    assert host.command('kp',ai_message(host,'publication.apply',{'approvalId':identifier},'again'))['result']==response['result']
    assert len(host.state()['aiControl']['publications'])==1


@pytest.mark.parametrize('lifecycle',['active','archived'])
def test_referenced_remove_rejected_before_approval(host,lifecycle):
    s=host.state();entity=copy.deepcopy(s['entities']['actor-player1']);entity.update(instanceId='review-reference',lifecycle=lifecycle)
    s['entities']['review-reference']=entity;host.commit(s)
    bundle=prepared(host,[{'kind':'remove','id':'demo.actor','expectedRevision':'1','value':None}])
    result=host.command('kp',ai_message(host,'ai.proposal.approve',approval_args(bundle),'deny'))
    assert result['code']=='REFERENCE_CONFLICT' and not host.state()['aiControl']['approvals']


def test_core_rule_and_data_replacement_waits_for_explicit_publish(host):
    old=host.state()['activeRuleset'];artifact=stage({'replacement.lua':"return rule('replacement', {}, function(r) return 7 end)"},{'game.json':{'map':['new-room'],'items':['new-item']}})
    bundle=prepared(host,artifact=artifact);identifier=approve(host,bundle)
    assert host.state()['activeRuleset']==old
    result=host.command('kp',ai_message(host,'publication.apply',{'approvalId':identifier},'replace'))
    assert result['status']=='committed',result
    s=host.state();assert s['activeRuleset']==artifact['revision'] and old in s['artifacts']


def test_old_approval_without_manual_fingerprint_cannot_be_loaded(host):
    bundle=prepared(host,[remove()]);identifier=approve(host,bundle)
    s=host.state();approval=s['aiControl']['approvals'][identifier];approval.pop('explicitHighRiskDigest');approval['approvalDigest']=approval_digest(approval);host.commit(s)
    result=host.command('kp',ai_message(host,'publication.apply',{'approvalId':identifier},'legacy'))
    assert result['code']=='HIGH_RISK_REVIEW_REQUIRED'
    assert 'review.unused' in host.state()['configurations']


def test_partial_configuration_failure_leaves_no_commit_and_can_reconcile_receipt(host):
    bundle=prepared(host,[remove()]);identifier=approve(host,bundle)
    message=ai_message(host,'publication.apply',{'approvalId':identifier},'interrupted')
    def fault(point):
        if point=='after_publication_configuration':raise RuntimeError('isolated failure')
    host.fault=fault
    with pytest.raises(RuntimeError,match='isolated failure'):host.command('kp',message)
    assert host.receipt('kp','interrupted')['status']=='unknown'
    s=host.state();assert 'review.unused' in s['configurations'] and s['aiControl']['approvals'][identifier]['status']=='approved'
    host.fault=None
    assert host.command('kp',message)['status']=='committed'


def test_player_cannot_approve_or_publish_high_risk(host):
    from onlinecoc.errors import DomainError
    bundle=prepared(host,[remove()])
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):
        host.command('player1',ai_message(host,'ai.proposal.approve',approval_args(bundle),'pl',account='player1'))
    identifier=approve(host,bundle)
    response=host.command('player1',ai_message(host,'publication.apply',{'approvalId':identifier},'pl-apply',account='player1'))
    assert response['code']=='PERMISSION_DENIED'
