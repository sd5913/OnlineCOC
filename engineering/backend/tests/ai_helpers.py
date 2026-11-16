"""Shared AI acceptance command helpers (not a pytest plugin)."""

def ai_message(host,op,args,identifier,account='kp'):
    view=host.project(account)
    return {'protocolVersion':1,'type':'command','requestId':identifier,'roomId':'demo','payload':{
        'commandId':identifier,'authorityEpoch':view['authorityEpoch'],'op':op,'args':args}}


def approve_case(case,identifier='approve'):
    host,service,proposal,delta=case
    args={'proposalId':proposal['proposalId'],'proposalRevision':proposal['revision'],
          'riskDecisions':{'choice-value':'有限次数保留其他选择的价值','gameplay-risk':'接受成功率提升并限制资源消耗'}}
    result=host.command('kp',ai_message(host,'ai.proposal.approve',args,identifier))
    assert result['status']=='committed',result
    return result['result']['approvalId']
