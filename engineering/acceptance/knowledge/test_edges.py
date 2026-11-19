"""Negative egress and capacity cases, using independent synthetic rooms."""
import copy
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'backend/src'),str(ROOT/'backend/tests'),str(ROOT/'data-management')]
import pytest
from onlinecoc.errors import DomainError
from onlinecoc.knowledge import HostStateProvider
from test_knowledge import host, install, observe, command, descriptor, provider


def test_cursor_copy_and_policy_rebind_invalidate_old_evidence(host):
    install(host);observe(host);observe(host)
    page=host.knowledge.search('player1',{'includeHistory':True,'limit':1});ref=page['items'][0]['ref']
    assert page['nextCursor']
    with pytest.raises(DomainError,match='SOURCE_STALE'):
        host.knowledge.search('player2',{'includeHistory':True,'limit':1,'cursor':page['nextCursor']})
    updated=descriptor();updated['facetSchemas']['identity']['schema']['maxProperties']=1
    d=host.register_knowledge_provider(updated,provider())
    with pytest.raises(DomainError,match='KNOWLEDGE_UNAVAILABLE'):host.knowledge.read('player1',{'refs':[ref]})
    assert command(host,'knowledge.policy.bind',{'policyId':'case-files','descriptorDigest':d['descriptorDigest'],'expectedRevision':1})['status']=='committed'
    with pytest.raises(DomainError,match='NOT_VISIBLE'):host.knowledge.read('player1',{'refs':[ref]})
    with pytest.raises(DomainError,match='SOURCE_STALE'):
        host.knowledge.search('player1',{'includeHistory':True,'limit':1,'cursor':page['nextCursor']})

def test_query_response_and_observation_limit_are_atomic(host):
    d=descriptor();d['facetSchemas']={str(n):{'schema':{'type':'string'},'modes':['observed_snapshot']} for n in range(8)}
    class Large(HostStateProvider):
        def pin(self,r,f,c):return {'sourceRevision':'1','sourceGuard':{},'facets':{key:'X'*7000 for key in f}}
        def check_guard(self,g,c):return True
    registered=host.register_knowledge_provider(d,Large({}))
    assert command(host,'knowledge.policy.bind',{'policyId':'case-files','descriptorDigest':registered['descriptorDigest'],'expectedRevision':0})['status']=='committed'
    args={'policyId':'case-files','expectedPolicyRevision':1,'subjectMemberId':'member-player1','resource':{'namespace':'case','kind':'witness','id':'actor-player1'},'facetIds':['0','1','2','3','4'],'expectedSourceRevision':'1','reason':'capacity'}
    assert command(host,'knowledge.observe',args)['code']=='KNOWLEDGE_LIMIT'
    assert not host.state()['knowledge']['grants']
    for _ in range(4):
        assert command(host,'knowledge.observe',{**args,'facetIds':['0','1','2']})['status']=='committed'
    refs=[row['ref'] for row in host.knowledge.search('player1',{'includeHistory':True})['items']]
    assert len(refs)==12
    with pytest.raises(DomainError,match='KNOWLEDGE_LIMIT'):host.knowledge.read('player1',{'refs':refs})
    assert len(host.knowledge.read('player1',{'refs':refs[:1]})['items'])==1

def test_old_chat_result_and_speaker_do_not_bypass_policy(host):
    from test_host import invoke
    result=invoke(host,'player1','demo.damage',{'actor':'actor-player1','amount':1},'before-policy')
    assert result['status']=='committed'
    assert command(host,'chat.message.share',{'channelId':'general','commandId':'before-policy'},account='player1')['status']=='committed'
    assert command(host,'chat.message.send',{'channelId':'general','speakerId':'actor-player1','text':'hello'},account='player1')['status']=='committed'
    install(host)
    history=host.chat_history('player2','general')['items']
    assert history[0]['card'] is None and history[1]['speakerName'] is None
    assert command(host,'chat.message.share',{'channelId':'general','commandId':'before-policy'},account='player1')['code']=='PERMISSION_DENIED'

def test_schema_unknown_fields_and_bool_revisions(host):
    d=host.register_knowledge_provider(descriptor(),provider())
    with pytest.raises(DomainError,match='INPUT_INVALID'):
        command(host,'knowledge.policy.bind',{'policyId':'case-files','descriptorDigest':d['descriptorDigest'],'expectedRevision':False})
    with pytest.raises(DomainError,match='INPUT_INVALID'):
        host.knowledge.search('player1',{'asAccount':'kp'})

def test_machine_dtos_match_actual_host_responses(host):
    from onlinecoc.knowledge.models import check
    install(host);observe(host)
    capability=host.knowledge.capabilities('kp')
    for d in capability['descriptors']:check('models','Descriptor',d)
    for p in capability['policies']:check('models','PolicyBinding',p)
    page=host.knowledge.search('player1',{});check('models','KnowledgePage',page)
    refs=[row['ref'] for row in page['items']]
    check('models','KnowledgePage',host.knowledge.read('player1',{'refs':refs}))
    check('models','ReadProof',host.knowledge.evidence('player1',refs,player=True))
    check('models','Preview',host.knowledge.preview('kp',{'policyId':'case-files','resource':{'namespace':'case','kind':'witness','id':'actor-player1'},'facetIds':['identity']}))
