import copy
import pytest

from onlinecoc.errors import DomainError
from onlinecoc_ai.errors import AiError
from ai_helpers import ai_message,approve_case,approval_args


def test_approval_stages_evidence_without_loading(ai_case):
    host,service,proposal,_=ai_case
    before=host.state();identifier=approve_case(ai_case);after=host.state()
    assert after['configurations']==before['configurations'] and after['activeRuleset']==before['activeRuleset']
    record=after['aiControl']['approvals'][identifier]
    assert record['status']=='approved' and len(record['reports'])==3
    assert record['changeSet']['configurations'][0]['value']['defaults']['bonus']==15


def test_player_and_forged_pass_are_rejected(ai_case):
    host,service,proposal,_=ai_case
    args={'proposalId':proposal['proposalId'],'proposalRevision':1,'riskDecisions':{}}
    with pytest.raises(DomainError,match='PERMISSION_DENIED'):
        host.command('player1',ai_message(host,'ai.proposal.approve',args,'player',account='player1'))
    args['reports']=[{'status':'pass'}]
    with pytest.raises(DomainError,match='INPUT_INVALID'):
        host.command('kp',ai_message(host,'ai.proposal.approve',args,'forged'))


def test_required_risk_reasons_are_enforced(ai_case):
    host,service,proposal,_=ai_case
    args=approval_args(host,service,proposal);args['riskDecisions']={}
    result=host.command('kp',ai_message(host,'ai.proposal.approve',args,'no-risk'))
    assert result['status']=='rejected' and result['code']=='RISK_REVIEW_REQUIRED'


def test_edit_revokes_old_approval_and_requires_fresh_reports(ai_case):
    host,service,proposal,delta=ai_case
    identifier=approve_case(ai_case)
    edited=copy.deepcopy(delta);edited['configurations'][0]['value']['defaults']['bonus']=5
    new=service.revise('kp',proposal['proposalId'],1,edited)
    assert new['revision']==2 and new['reportRefs']==[]
    assert host.state()['aiControl']['approvals'][identifier]['status']=='revoked'
    result=host.command('kp',ai_message(host,'publication.apply',{'approvalId':identifier},'load-old'))
    assert result['code']=='APPROVAL_REVOKED'
    with pytest.raises(AiError,match='PROPOSAL_STALE'):
        service.prepared('kp',proposal['proposalId'],1)


@pytest.mark.parametrize('mutation,code',[
    (lambda state,approval: state['entities']['actor-one']['numbers'].update(target=42),'BASELINE_STALE'),
    (lambda state,approval: approval['reports'][0]['findings'].append({'code':'fake','severity':'info','path':'','sourceRef':'','message':'tampered','evidence':None,'suggestion':''}),'DIGEST_MISMATCH'),
    (lambda state,approval: state['aiControl']['packBinding'].update(digest='f'*64),'VALIDATOR_STALE'),
    (lambda state,approval: state['members']['kp'].update(authorizationEpoch=2),'PERMISSION_DENIED'),
])
def test_approved_context_and_evidence_cannot_drift(ai_case,mutation,code):
    host,_,_,_=ai_case;identifier=approve_case(ai_case)
    state=host.state();mutation(state,state['aiControl']['approvals'][identifier]);host.commit(state)
    result=host.command('kp',ai_message(host,'publication.apply',{'approvalId':identifier},'changed'))
    assert result['status']=='rejected' and result['code']==code,result
    assert host.state()['configurations']['fixture.token']['defaults']['bonus']==0


def test_expiry_blocks_loading(ai_case):
    host,_,_,_=ai_case;identifier=approve_case(ai_case)
    host.clock=lambda:host.state()['aiControl']['approvals'][identifier]['expiresAt']+1
    result=host.command('kp',ai_message(host,'publication.apply',{'approvalId':identifier},'expired'))
    assert result['code']=='APPROVAL_EXPIRED'


def test_failed_validation_cannot_be_prepared(ai_case):
    host,service,proposal,delta=ai_case
    delta['configurations'][0]['value']['defaults']['bonus']=16
    edited=service.revise('kp',proposal['proposalId'],1,delta)
    result=service.validate('kp',proposal['proposalId'],edited['revision'])
    assert result['proposal']['status']=='blocked'
    with pytest.raises(AiError):service.prepared('kp',proposal['proposalId'],2)
