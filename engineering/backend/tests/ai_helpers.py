"""Shared AI acceptance command helpers (not a pytest plugin)."""

def ai_message(host,op,args,identifier,account='kp'):
    view=host.project(account)
    return {'protocolVersion':1,'type':'command','requestId':identifier,'roomId':'demo','payload':{
        'commandId':identifier,'authorityEpoch':view['authorityEpoch'],'op':op,'args':args}}


def approval_args(host,service,proposal,account='kp'):
    from onlinecoc.publication import is_high_risk
    args={'proposalId':proposal['proposalId'],'proposalRevision':proposal['revision'],
          'riskDecisions':{'choice-value':'有限次数保留其他选择的价值','gameplay-risk':'接受成功率提升并限制资源消耗'}}
    prepared=service.prepared(account,proposal['proposalId'],proposal['revision'])
    state=host.state()
    if is_high_risk(state,prepared['changeSet'],state['aiControl']['packBinding']['contract']):
        args['explicitHighRiskDigest']=prepared['candidateDigest']
        args['riskDecisions']['high-risk']='已检查完整候选并接受高危配置影响'
    return args


def approve_case(case,identifier='approve'):
    host,service,proposal,delta=case
    args=approval_args(host,service,proposal)
    result=host.command('kp',ai_message(host,'ai.proposal.approve',args,identifier))
    assert result['status']=='committed',result
    return result['result']['approvalId']
