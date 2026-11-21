"""C acceptance through actual Host.command, durable publish and room reopening."""
import copy
from pathlib import Path
from uuid import uuid4
from onlinecoc.host import Host
from onlinecoc_ai.pack import Pack,fixture_state
from onlinecoc_ai.sandbox import stage
from onlinecoc_ai.proposals import Proposals
from onlinecoc_ai.c_review import assessment

ROOT=Path(__file__).resolve().parent/'work/engine/engineering'

def message(h,op,args,command_id):
    return {'protocolVersion':1,'type':'command','requestId':command_id,'roomId':h.state()['roomId'],
        'payload':{'commandId':command_id,'authorityEpoch':h.epoch,'op':op,'args':args}}

def test_manual_c_proof_command_publish_reopen(tmp_path):
    h=Host(tmp_path/'host',bootstrap='synthetic-password')
    pack=Pack(ROOT/'ai/tests/fixtures/pack');artifact=stage(pack.sources,pack.data)
    room=h.state();world=fixture_state(pack.json(pack.scenarios[0]['fixtureRef']),pack.configurations)
    for key in ('entities','relations','members','configurations','progress','collectionRevision'):room[key]=world[key]
    room['artifacts'][artifact['revision']]=artifact;room['activeRuleset']=artifact['revision'];h.commit(room)
    service=Proposals(h,pack)
    config=copy.deepcopy(pack.configurations['fixture.token']);config['revision']='2';config['defaults']['bonus']=15
    delta={'schemaVersion':1,'configurations':[{'kind':'replace','id':config['configurationId'],'expectedRevision':'1','value':config}],
        'sources':{},'data':{},'suggestions':[]}
    proposal=service.create('kp','C人工采纳持久恢复',delta);service.validate('kp',proposal['proposalId'],1)
    bundle=service.prepared('kp',proposal['proposalId'],1)
    c=next(r for r in bundle['reports'] if r['level']=='C')
    c.update(status='unknown',risk='unknown',findings=[{'code':'LIVE_SCENARIO_COVERAGE_MISSING','severity':'error',
        'path':'/changeSet','sourceRef':'fixture','message':'Synthetic boundary report','evidence':{},'suggestion':'KP review'}])
    basis={k:v for k,v in c['evidence']['reviewBasis'].items() if k not in ('basisRevision','basisDigest')}
    bundle['cAssessment']=assessment(bundle['reports'],basis)
    h.ai_prepared_resolver=lambda *args:copy.deepcopy(bundle)
    decisions={item['id']:'Reviewed required item' for item in pack.contract['reviewPolicy']['items'] if item['required']}
    decisions.update({'high-risk':'Explicitly accept item change','gameplay-risk':'Explicitly accept stated coverage limitation'})
    args={'proposalId':proposal['proposalId'],'proposalRevision':1,'riskDecisions':decisions,
        'explicitHighRiskDigest':bundle['candidateDigest'],'cReview':{k:bundle['cAssessment'][k] for k in ('basisRevision','basisDigest','reportDigest')}}
    approve_message=message(h,'ai.proposal.approve',args,str(uuid4()))
    try:
        receipt=h.command('kp',approve_message);assert receipt['status']=='committed',receipt
        identifier=receipt['result']['approvalId']
        publication_message=message(h,'publication.apply',{'approvalId':identifier},str(uuid4()))
        published=h.command('kp',publication_message);assert published['status']=='committed',published
        old_scope=h.state()['aiControl']['scopeId']
        service.close();h.close();h=Host(tmp_path/'host')
        assert h.state()['aiControl']['scopeId']==old_scope
        assert h.command('kp',approve_message)==receipt and h.command('kp',publication_message)==published
        assert len(h.state()['aiControl']['publications'])==1
        stored=h.state()['aiControl']['approvals'][identifier]
        assert stored['cReview']==args['cReview'] and stored['status']=='consumed'
        assert next(r for r in stored['reports'] if r['level']=='C')['status']=='unknown'
    finally:service.close();h.close()
