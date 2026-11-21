import copy,time,uuid
from onlinecoc.host import Host
from onlinecoc.ai_contracts import digest
from onlinecoc_ai.pack import Pack,fixture_state
from onlinecoc_ai.sandbox import stage
from onlinecoc_ai.proposals import Proposals
from onlinecoc import data_queries

def setup(root,directory,stable=False,attach_query=True):
 h=Host(directory,bootstrap='synthetic-password');pack=Pack(root/'ai/tests/fixtures/pack')
 art=stage(pack.sources,pack.data);s=h.state();world=fixture_state(pack.json(pack.scenarios[0]['fixtureRef']),pack.configurations)
 for key in ('entities','relations','members','configurations','progress','collectionRevision'):s[key]=world[key]
 actor=next(v for v in s['entities'].values() if v['typeRef']=='actor')
 for i in range(120):
  e=copy.deepcopy(actor);e['instanceId']='load-'+str(i);e['name']='Synthetic actor '+str(i);s['entities'][e['instanceId']]=e
 for i in range(1200):
  s['chat']['messages']['general'].append({'messageId':'seed-'+str(i),'channelId':'general','sequence':i+1,'senderAccountId':['kp','player1','player2'][i%3],
   'createdAt':1.,'updatedAt':1.,'revision':1,'deleted':False,'kind':'text','text':'Synthetic history '+str(i)+' x'*80,'replyTo':None,'assetIds':[],'speakerId':None,'speakerName':None,'card':None})
 s['chat']['channels']['general'].update(lastSequence=1200,revision=1201)
 s['artifacts'][art['revision']]=art;s['activeRuleset']=art['revision'];h.commit(s)
 service=Proposals(h,pack);h.ai_room_read_authorizer=lambda account:account=='kp'
 s=h.state();s['aiControl']['settings']['externalSources']={'public':True,'kp':True,'private':True};h.commit(s)
 config=copy.deepcopy(pack.configurations['fixture.token']);config['revision']='2';config['defaults']['bonus']=15
 delta={'schemaVersion':1,'configurations':[{'kind':'replace','id':config['configurationId'],'expectedRevision':'1','value':config}],'sources':{},'data':{},'suggestions':[]}
 p=service.create('kp','Concurrent fixture item update',delta);service.validate('kp',p['proposalId'],1)
 b=service.prepared('kp',p['proposalId'],1)
 args={'types':['room'],'query':'','limit':2}
 if stable:args['roomMode']='state'
 if attach_query:
  result=data_queries.query(h,h.state(),'kp','search',args,initiator='kp',external=True,read_scope='kp-room')
  b['context']['facts']['dataQueries']=[{'scopeId':h.state()['aiControl']['scopeId'],'operation':'search','args':args,'initiator':'kp','readScope':'kp-room','digest':digest(result)}]
  for report in b['reports']:report['contextDigest']=digest(b['context'])
  b['cAssessment']['reportDigest']=digest(b['reports'])
 h.validate_ai_sources(h.state(),'kp',b['context'])
 h.ai_prepared_resolver=lambda *a:copy.deepcopy(b)
 decisions={item['id']:'Reviewed required fixture item' for item in pack.contract['reviewPolicy']['items'] if item['required']}
 decisions.update({'high-risk':'Reviewed high risk item change','gameplay-risk':'Reviewed gameplay fixture outcome'})
 approval={'proposalId':p['proposalId'],'proposalRevision':1,'explicitHighRiskDigest':b['candidateDigest'],'riskDecisions':decisions}
 return h,service,approval

def message(h,account,op,args,identifier=None):
 return {'protocolVersion':1,'type':'command','requestId':identifier or uuid.uuid4().hex,'roomId':h.state()['roomId'],
  'payload':{'commandId':identifier or uuid.uuid4().hex,'authorityEpoch':h.epoch,'op':op,'args':args}}
