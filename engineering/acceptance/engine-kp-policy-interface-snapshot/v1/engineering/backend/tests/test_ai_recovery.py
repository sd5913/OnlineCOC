import pytest

from onlinecoc.errors import DomainError
from ai_helpers import ai_message,approve_case


@pytest.mark.parametrize('exception',[DomainError('INJECTED_AFTER_COMMIT'),OSError('lost reply')])
def test_post_commit_error_keeps_committed_publication(ai_case,exception):
    host,_,_,_=ai_case;identifier=approve_case(ai_case)
    def fault(point):
        if point=='after_publish':raise exception
    host.store.fault=fault
    try:
        result=host.command('kp',ai_message(host,'publication.apply',{'approvalId':identifier},'fault-after'))
        assert result['status']=='committed',result
        assert host.receipt('kp','fault-after')==result
        assert host.state()['aiControl']['approvals'][identifier]['status']=='consumed'
    finally:host.store.fault=None


def test_pre_commit_failure_has_no_partial_configuration(ai_case):
    host,_,_,_=ai_case;identifier=approve_case(ai_case);before=host.state()
    def fault(point):
        if point=='before_publish':raise OSError('injected failure')
    host.store.fault=fault;message=ai_message(host,'publication.apply',{'approvalId':identifier},'fault-before')
    try:
        with pytest.raises(OSError):host.command('kp',message)
        assert host.state()==before
    finally:host.store.fault=None
    assert host.command('kp',message)['status']=='committed'


def test_approval_reply_loss_can_be_queried_without_ai_repository(ai_case):
    host,service,proposal,_=ai_case
    def fault(point):
        if point=='after_ai.proposal.approve_commit':raise DomainError('LOST_REPLY')
    host.fault=fault
    identifier=approve_case(ai_case,'approval-lost')
    service.close();host.fault=None
    assert host.receipt('kp','approval-lost')['result']['approvalId']==identifier


def test_failure_after_local_configuration_edit_rolls_back_everything(ai_case):
    host,_,_,_=ai_case;identifier=approve_case(ai_case);before=host.state()
    def fault(point):
        if point=='after_publication_configuration':raise DomainError('INJECTED_MID_APPLY')
    host.fault=fault
    try:
        result=host.command('kp',ai_message(host,'publication.apply',{'approvalId':identifier},'mid-apply'))
        assert result['code']=='INJECTED_MID_APPLY'
        after=host.state()
        assert after['configurations']==before['configurations'] and after['activeRuleset']==before['activeRuleset']
        assert after['aiControl']==before['aiControl']
    finally:host.fault=None
