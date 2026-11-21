import copy
from concurrent.futures import ThreadPoolExecutor
import pytest

from onlinecoc.errors import DomainError
from ai_helpers import ai_message,approve_case,approval_args


def test_load_once_after_ai_store_is_closed_and_restart(ai_case):
    host,service,proposal,_=ai_case;identifier=approve_case(ai_case)
    before=host.state();service.close()
    message=ai_message(host,'publication.apply',{'approvalId':identifier},'load')
    result=host.command('kp',message)
    assert result['status']=='committed',result
    assert host.command('kp',message)==result
    again=host.command('kp',ai_message(host,'publication.apply',{'approvalId':identifier},'other-id'))
    assert again['result']==result['result']
    state=host.state()
    assert state['configurations']['fixture.token']['defaults']['bonus']==15
    assert state['entities']==before['entities'] and len(state['aiControl']['publications'])==1
    scope=state['aiControl']['scopeId'];host.close();host.__init__(host.path)
    assert host.state()['aiControl']['scopeId']==scope
    assert host.command('kp',message)==result


def test_same_command_id_different_payload_conflicts(ai_case):
    host,_,_,_=ai_case;identifier=approve_case(ai_case)
    message=ai_message(host,'publication.apply',{'approvalId':identifier},'conflict');host.command('kp',message)
    bad=copy.deepcopy(message);bad['payload']['args']['approvalId']='different'
    with pytest.raises(DomainError,match='COMMAND_ID_CONFLICT'):host.command('kp',bad)


def test_concurrent_duplicate_publications_have_one_effect(ai_case):
    host,_,_,_=ai_case;identifier=approve_case(ai_case)
    first=ai_message(host,'publication.apply',{'approvalId':identifier},'concurrent-one')
    second=ai_message(host,'publication.apply',{'approvalId':identifier},'concurrent-two')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda m:host.command('kp',m),[first,second]))
    assert results[0]['result']==results[1]['result']
    assert len(host.state()['aiControl']['publications'])==1


def test_publication_reconciliation_never_reapplies_effects(ai_case):
    host,service,proposal,_=ai_case;identifier=approve_case(ai_case)
    host.command('kp',ai_message(host,'publication.apply',{'approvalId':identifier},'publish'))
    service.reconcile();generation=host.store.generation
    service.reconcile()
    assert service.get('kp',proposal['proposalId'])['status']=='published'
    assert host.store.generation==generation


def test_two_kps_cannot_publish_against_the_same_old_baseline(ai_case):
    host,service,_,delta=ai_case
    state=host.state();state['members']['kp2']={'memberId':'member-kp2','accountId':'kp2','role':'kp','active':True,'authorizationEpoch':1,'metadata':{}}
    host.commit(state)
    messages=[]
    for account in ('kp','kp2'):
        proposal=service.create(account,'有限次数道具',delta)
        service.validate(account,proposal['proposalId'],1)
        args=approval_args(host,service,proposal,account)
        approval=host.command(account,ai_message(host,'ai.proposal.approve',args,'approve-'+account,account))
        assert approval['status']=='committed',approval
        messages.append((account,ai_message(host,'publication.apply',{'approvalId':approval['result']['approvalId']},'publish-'+account,account)))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda pair:host.command(*pair),messages))
    assert sorted(r['status'] for r in results)==['committed','rejected']
    assert next(r for r in results if r['status']=='rejected')['code']=='BASELINE_STALE'
    assert len(host.state()['aiControl']['publications'])==1


def test_resolving_prepared_bundle_does_not_hold_room_lock(ai_case):
    import threading
    host,service,proposal,_=ai_case
    entered=threading.Event();release=threading.Event();original=host.ai_prepared_resolver
    def delayed(*args):
        result=original(*args);entered.set();assert release.wait(5);return result
    host.ai_prepared_resolver=delayed
    args=approval_args(host,service,proposal)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending=pool.submit(host.command,'kp',ai_message(host,'ai.proposal.approve',args,'delayed-approval'))
        try:
            assert entered.wait(3)
            ordinary=pool.submit(host.command,'kp',ai_message(host,'entity.patch',{'id':'actor-one','name':'并发修改'},'ordinary'))
            assert ordinary.result(timeout=2)['status']=='committed'
        finally:
            release.set();host.ai_prepared_resolver=original
        result=pending.result(timeout=3)
        assert result['status']=='rejected' and result['code']=='BASELINE_STALE'
