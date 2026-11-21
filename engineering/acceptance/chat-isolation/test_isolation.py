import copy
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from onlinecoc.host import Host
from onlinecoc.errors import DomainError
from onlinecoc.ai_contracts import digest,world_digest
from onlinecoc.data_queries import query,recheck
from onlinecoc.ai_sources import check_sources
from onlinecoc.server import create_app
from fixture import message
from pathlib import Path
from fixture import setup

@pytest.fixture
def h(tmp_path):
 host=Host(tmp_path/'room',bootstrap='synthetic-password');host.ai_room_read_authorizer=lambda a:a=='kp'
 s=host.state();s['aiControl']['settings']['externalSources']={'public':True,'private':True,'kp':True};host.commit(s)
 yield host
 host.close()

def send(h,text='ordinary',id=None):return h.command('player1',message(h,'player1','chat.message.send',{'channelId':'general','text':text},id))
def search(h,mode='state',query_text=''):
 args={'types':['room'],'query':query_text,'limit':2,'roomMode':mode}
 result=query(h,h.state(),'kp','search',args,initiator='kp',external=True,read_scope='kp-room')
 proof={'scopeId':h.state()['aiControl']['scopeId'],'operation':'search','args':args,'initiator':'kp','readScope':'kp-room','digest':digest(result)}
 return result,{'facts':{'dataQueries':[proof]}}

def test_stable_room_query_excludes_traffic_and_audit(h):
 before,proof=search(h);world=world_digest(h.state());send(h)
 assert world_digest(h.state())==world
 assert search(h)[0]==before
 recheck(h,h.state(),'kp',proof)
 assert all(row['ref']['sourceId']=='host-room-state' for row in before['items'])

def test_full_records_preserve_strict_proof(h):
 _,proof=search(h,'records');send(h)
 with pytest.raises(DomainError,match='SOURCE_STALE'):recheck(h,h.state(),'kp',proof)

@pytest.mark.parametrize('field',['entities','members','configurations'])
def test_stable_room_still_invalidates_real_changes(h,field):
 _,proof=search(h)
 s=h.state()
 if field=='entities':s[field]['actor-player1']['name']='changed';s[field]['actor-player1']['revision']+=1
 elif field=='members':s[field]['player1']['authorizationEpoch']+=1
 else:s[field]['demo.actor']['revision']='changed'
 h.commit(s)
 with pytest.raises(DomainError,match='SOURCE_STALE'):recheck(h,h.state(),'kp',proof)

def test_state_refs_read_automatically_and_follow_revision(h):
 result,_=search(h,query_text='/entities/actor-player1');ref=result['items'][0]['ref']
 read=lambda:query(h,h.state(),'kp','read',{'refs':[ref]},read_scope='kp-room')
 before=read();send(h);assert read()==before
 s=h.state();s['entities']['actor-player1']['revision']+=1;h.commit(s)
 with pytest.raises(DomainError,match='SOURCE_STALE'):read()

@pytest.mark.parametrize('operation',['edit','retract'])
def test_explicit_message_keeps_revision_dependency(h,operation):
 result=send(h);msg=h.state()['chat']['messages']['general'][0]
 ref={'kind':'message','id':msg['messageId'],'channelId':'general','revision':'1','visibility':'public','digest':digest(msg)}
 send(h,'unrelated');check_sources(h,h.state(),'kp',[ref])
 args={'channelId':'general','messageId':msg['messageId'],'revision':1}
 if operation=='edit':args['text']='changed'
 assert h.command('player1',message(h,'player1','chat.message.'+operation,args))['status']=='committed'
 with pytest.raises(DomainError,match='SOURCE_STALE'):check_sources(h,h.state(),'kp',[ref])

def test_projection_cache_is_detached_and_invalidated(h,monkeypatch):
 calls=[];original=h.state
 monkeypatch.setattr(h,'state',lambda:(calls.append(1),original())[1])
 first=h.project('player1');count=len(calls);first['entities'].clear()
 assert h.project('player1')['entities'] and len(calls)==count
 s=original();s['members']['player1']['active']=False;h.commit(s)
 with pytest.raises(DomainError):h.project('player1')

def test_lightweight_channels_does_not_call_full_projection(h,monkeypatch):
 monkeypatch.setattr(h,'project',lambda *a:(_ for _ in ()).throw(AssertionError('full view used')))
 with TestClient(create_app(h,8765),base_url='http://127.0.0.1:8765') as c:
  c.headers['Origin']='http://127.0.0.1:8765';assert c.post('/api/v1/login',json={'loginName':'player1','password':'synthetic-password'}).status_code==200
  r=c.get('/api/v1/chat/channels');assert r.status_code==200 and r.json()['accountId']=='player1'
  assert set(r.json()['channels'])=={'general'}

def test_private_channels_and_revocation(h):
 result=h.command('player1',message(h,'player1','chat.direct.open',{'accountId':'player2'}));cid=result['result']['channelId']
 assert cid in h.chat_channels('player1')['channels'] and cid not in h.chat_channels('kp')['channels']
 s=h.state();s['members']['player1']['active']=False;h.commit(s)
 with pytest.raises(DomainError):h.chat_channels('player1')

def test_concurrent_duplicates_and_lost_reply_are_exactly_once(h):
 jobs=[message(h,'player1','chat.message.send',{'channelId':'general','text':str(i)},'duplicate-'+str(i)) for i in range(12)]
 with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda m:h.command('player1',m),jobs+jobs))
 assert all(r['status']=='committed' for r in results) and results[:12]==results[12:]
 assert len(h.state()['chat']['messages']['general'])==12
 h.fault=lambda stage:(_ for _ in ()).throw(DomainError('LOST_REPLY')) if stage=='after_chat_commit' else None
 one=send(h,'lost','lost');assert one['status']=='committed'
 assert send(h,'lost','lost')==one and len(h.state()['chat']['messages']['general'])==13

def test_state_read_requires_current_kp_full_read_authority(h):
 _,proof=search(h);h.ai_room_read_authorizer=lambda a:False
 with pytest.raises(DomainError,match='PERMISSION_DENIED'):recheck(h,h.state(),'kp',proof)
 with pytest.raises(DomainError):query(h,h.state(),'player1','search',{'types':['room'],'roomMode':'state'},read_scope='kp-room')


def test_cached_approval_still_checks_mutation_references_and_publication(tmp_path):
 from onlinecoc.contracts import validate_model
 from onlinecoc.model import validate
 root=Path(__file__).resolve().parent/'work/after/engineering'
 host,service,args=setup(root,tmp_path/'populated',stable=True)
 try:
  send(host)
  receipt=host.command('kp',message(host,'kp','ai.proposal.approve',args))
  assert receipt['status']=='committed',receipt
  identifier=receipt['result']['approvalId'];state=host.state()
  validate_model('AiControl',state['aiControl'])
  bad=copy.deepcopy(state['aiControl']);bad['approvals'][identifier]['reports']=tuple(bad['approvals'][identifier]['reports'])
  with pytest.raises(DomainError,match='INPUT_INVALID'):validate_model('AiControl',bad)
  bad=copy.deepcopy(state['aiControl']);bad['approvals'][identifier]['status']='forged'
  with pytest.raises(DomainError,match='INPUT_INVALID'):validate_model('AiControl',bad)
  bad=copy.deepcopy(state);bad['artifacts'].pop(bad['aiControl']['approvals'][identifier]['artifactRevision'])
  with pytest.raises(DomainError,match='ARTIFACT_MISSING'):validate(bad)
  for _ in range(3):assert send(host)['status']=='committed'
  publish=message(host,'kp','publication.apply',{'approvalId':identifier},'publish-after-chat')
  result=host.command('kp',publish);assert result['status']=='committed',result
  assert host.command('kp',publish)==result
  assert len(host.state()['aiControl']['publications'])==1
  assert host.state()['configurations']['fixture.token']['defaults']['bonus']==15
 finally:service.close();host.close()
