"""A0 consumer handshake against a trusted stub, independent of host changes."""
from contextlib import nullcontext
from types import SimpleNamespace
import copy
import pytest
from onlinecoc_ai import knowledge
from onlinecoc_ai.errors import AiError
from test_known_answers import item


class Port:
    def __init__(self):self.calls=[];self.status='ready';self.egress=True
    def capabilities(self,account,**kwargs):return {'status':self.status}
    def require_egress(self,account,channel,**kwargs):
        assert channel=='ai'
        knowledge.require(self.egress,'KNOWLEDGE_EGRESS_DENIED')
    def search(self,account,args,**kwargs):
        self.calls.append((account,args,kwargs));v=item();del v['data']
        return {'items':[v],'nextCursor':None}
    def read(self,account,args,**kwargs):
        self.calls.append((account,args,kwargs));return {'items':[item()],'nextCursor':None}
    def evidence(self,account,refs,**kwargs):return {'accountId':account,'player':True,'refs':refs}
    def recheck_many(self,account,proofs,**kwargs):self.calls.append((account,proofs,kwargs))


def fixture():
    port=Port();room={'aiControl':{'settings':{'externalSources':{'private':True}}}}
    host=SimpleNamespace(knowledge=port,lock=nullcontext(),state=lambda:copy.deepcopy(room))
    context={'facts':{'sessionAccess':{'level':'player','owner':'pl'},'knowledgeProofs':[{'accountId':'pl','player':True,'refs':[]}]}}
    return host,context,room,port


def test_only_details_issue_evidence_and_principal_is_server_bound():
    host,context,room,port=fixture();pool={}
    knowledge.attach(host,context,'room_search_knowledge',{},pool)
    assert not pool and len(context['facts']['knowledgeProofs'])==2
    value=knowledge.attach(host,context,'room_read_knowledge',{'refs':[{**item()['ref'],'digest':'f'*64}]},pool)
    assert len(pool)==1 and value['items'][0]['evidenceId'] in pool
    assert all(c[0]=='pl' and c[2]['player'] is True for c in port.calls)
    with pytest.raises(AiError):knowledge.attach(host,context,'room_search_knowledge',{'accountId':'kp'},pool)


@pytest.mark.parametrize('status',['blocked','unavailable'])
def test_failure_cannot_fall_back_to_public_entities(status):
    host,context,_,port=fixture();port.status=status
    with pytest.raises(AiError,match='KNOWLEDGE_UNAVAILABLE'):knowledge.attach(host,context,'room_search_knowledge',{}, {})
    assert port.calls==[]


def test_private_export_and_proof_owner_are_checked():
    host,context,room,port=fixture();room['aiControl']['settings']['externalSources']['private']=False
    with pytest.raises(AiError,match='EXTERNAL_SCOPE_DISABLED'):knowledge.attach(host,context,'room_search_knowledge',{}, {})
    context['facts']['knowledgeProofs'][0]['accountId']='kp'
    with pytest.raises(AiError,match='SOURCE_STALE'):knowledge.recheck(host,room,context)
    assert port.calls==[]


def test_ai_egress_is_checked_and_proofs_share_one_capture():
    host,context,room,port=fixture()
    context['facts']['knowledgeProofs'].append({'accountId':'pl','player':True,'refs':[item()['ref']]})
    knowledge.recheck(host,room,context)
    assert len(port.calls)==1 and len(port.calls[0][1])==2
    port.egress=False
    with pytest.raises(AiError,match='KNOWLEDGE_EGRESS_DENIED'):
        knowledge.attach(host,context,'room_search_knowledge',{}, {})
