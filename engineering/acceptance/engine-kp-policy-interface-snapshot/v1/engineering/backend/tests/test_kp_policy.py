import copy
import pytest
from ai_helpers import ai_message,approval_args
from onlinecoc.ai_contracts import digest,approval_digest
from onlinecoc.publication import consultation_source_digest,consultation_assessment
from onlinecoc.errors import DomainError

def prepare(case,flags=None):
 host,service,proposal,_=case
 args=approval_args(host,service,proposal)
 bundle=service.prepared('kp',proposal['proposalId'],proposal['revision'])
 bundle['context']['facts'].update({'consultationOnly':True,**(flags or {})})
 for report in bundle['reports']:report['contextDigest']=digest(bundle['context'])
 bundle['cAssessment']['reportDigest']=digest(bundle['reports'])
 host.ai_prepared_resolver=lambda *a:copy.deepcopy(bundle)
 args['riskDecisions']['consultation-source']='接受咨询来源的不确定性'
 args['consultationReview']={'sourceDigest':consultation_source_digest(bundle['context'])}
 return host,args,bundle

def approve(host,args):return host.command('kp',ai_message(host,'ai.proposal.approve',args,'approve-consultation'))

@pytest.mark.parametrize('bad',['missing-reason','short-reason','missing-digest','old-digest'])
def test_consultation_requires_exact_acceptance(ai_case,bad):
 host,args,_=prepare(ai_case)
 if bad=='missing-reason':del args['riskDecisions']['consultation-source']
 elif bad=='short-reason':args['riskDecisions']['consultation-source']='x'
 elif bad=='missing-digest':del args['consultationReview']
 else:args['consultationReview']['sourceDigest']='0'*64
 if bad=='short-reason':
  with pytest.raises(DomainError,match='INPUT_INVALID'):approve(host,args)
  assert not host.state()['aiControl']['approvals'];return
 result=approve(host,args)
 assert result['status']=='rejected' and result['code'] in ('RISK_REVIEW_REQUIRED','CONSULTATION_REVIEW_REQUIRED'),result
 assert not host.state()['aiControl']['approvals']

def test_kp_consultation_supported_candidate_publishes_once(ai_case):
 host,args,bundle=prepare(ai_case);before=host.state()
 result=approve(host,args);assert result['status']=='committed',result
 identifier=result['result']['approvalId'];record=host.state()['aiControl']['approvals'][identifier]
 assert record['context']['facts']['consultationOnly'] is True
 assert record['consultationReview']['sourceDigest']==consultation_source_digest(bundle['context'])
 assert record['consultationAssessment']['requiresAcceptance'] is True
 command=ai_message(host,'publication.apply',{'approvalId':identifier},'publish-consultation')
 receipt=host.command('kp',command);assert receipt['status']=='committed',receipt
 assert host.command('kp',command)==receipt
 state=host.state();assert state['configurations']['fixture.token']['defaults']['bonus']==15
 assert state['entities']==before['entities'] and len(state['aiControl']['publications'])==1

@pytest.mark.parametrize('flags',[{'strictPlayer':True},{'sessionAccess':{'level':'player'}}])
def test_player_context_never_elevated_by_kp_acceptance(ai_case,flags):
 host,args,_=prepare(ai_case,flags);r=approve(host,args)
 assert r['status']=='rejected' and r['code']=='CONSULTATION_ONLY',r

def test_pl_cannot_approve_kp_consultation(ai_case):
 host,args,_=prepare(ai_case)
 with pytest.raises(DomainError,match='PERMISSION_DENIED'):
  host.command('player1',ai_message(host,'ai.proposal.approve',args,'player-approve','player1'))

@pytest.mark.parametrize('change',['reason','digest','authority','world'])
def test_publication_rechecks_acceptance_and_current_conditions(ai_case,change):
 host,args,_=prepare(ai_case);r=approve(host,args);assert r['status']=='committed',r
 identifier=r['result']['approvalId'];state=host.state();approval=state['aiControl']['approvals'][identifier]
 if change in ('reason','digest'):
  if change=='reason':approval['riskDecisions'].pop('consultation-source')
  else:approval.pop('consultationReview')
  approval['approvalDigest']=approval_digest(approval)
 elif change=='authority':state['members']['kp']['authorizationEpoch']+=1
 else:state['collectionRevision']+=1
 host.commit(state)
 r=host.command('kp',ai_message(host,'publication.apply',{'approvalId':identifier},'apply-invalid'))
 assert r['status']=='rejected',r
 assert r['code']=={'reason':'RISK_REVIEW_REQUIRED','digest':'CONSULTATION_REVIEW_REQUIRED','authority':'PERMISSION_DENIED','world':'BASELINE_STALE'}[change]
 assert not host.state()['aiControl']['publications']

def test_technical_failure_is_not_accepted_as_risk(ai_case):
 host,args,bundle=prepare(ai_case)
 bundle['reports'][0]['status']='fail';bundle['cAssessment']['reportDigest']=digest(bundle['reports'])
 result=approve(host,args)
 assert result['status']=='rejected' and result['code']=='CHECKS_INCOMPLETE',result

def test_unsupported_storage_change_is_not_success(ai_case):
 host,args,bundle=prepare(ai_case)
 bundle['changeSet']['packageStorage']={'path':'unsupported','value':'not written'}
 result=approve(host,args)
 assert result['status']=='rejected' and result['code']=='AI_INPUT_INVALID',result
 assert not host.state()['aiControl']['approvals']

def test_source_digest_binds_scope_sources_and_queries():
 context={'scopeId':'scope','sourceRefs':[{'kind':'manual','id':'one'}],'memoryRefs':[{'id':'m1'}],'facts':{'dataQueries':[{'digest':'one'}]}}
 old=consultation_source_digest(context)
 for part in ('scope','source','memory','query'):
  changed=copy.deepcopy(context)
  if part=='scope':changed['scopeId']='other'
  elif part=='source':changed['sourceRefs'][0]['id']='other'
  elif part=='memory':changed['memoryRefs'][0]['id']='other'
  else:changed['facts']['dataQueries'][0]['digest']='other'
  assert consultation_source_digest(changed)!=old

def test_host_independently_detects_foreign_refs_without_legacy_flag():
 context={'scopeId':'scope','sourceRefs':[],'memoryRefs':[],'facts':{'dataQueries':[{'readRefs':[
  {'ref':{'sourceId':'host'}},{'ref':{'sourceId':'host-room-state'}},{'ref':{'sourceId':'package.world'}}]}]}}
 result=consultation_assessment(context)
 assert result['requiresAcceptance'] is True and result['sourceCount']==1
 assert result['sourceDigest']==digest(context)

def test_host_assessment_matches_frozen_ai_contract():
 from onlinecoc_ai.consultation import assessment
 context={'scopeId':'scope','sourceRefs':[],'memoryRefs':[],'facts':{'dataQueries':[{'readRefs':[
  {'ref':{'sourceId':'host'}},{'ref':{'sourceId':'package.world'}},{'ref':{'sourceId':'package.world'}}]}]}}
 assert consultation_assessment(context)==assessment(context)
 assert consultation_assessment(context)['sourceCount']==1
