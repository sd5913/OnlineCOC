"""Real subprocess probes never widen live Host action permissions."""
import copy
import pytest
from onlinecoc.errors import DomainError
from onlinecoc.model import demo_state
from onlinecoc.registry import stage
from onlinecoc.worker_process import execute_request
from onlinecoc.host import Host
from ai_helpers import ai_message


SOURCE = """return rule('probe.private', {'actor'}, function(r, actor)
  r.set(actor, 'hp', r.number(actor, 'hp') - 1)
  return r.number(actor, 'hp')
end, {public=false})"""


@pytest.fixture(scope='module')
def artifact():return stage({'probe.lua':SOURCE},{})


def request(artifact,account='kp'):
    return {'kind':'sequence','sources':artifact['sources'],'data':artifact['data'],'metadata':artifact['metadata'],
            'state':demo_state([('kp','kp'),('p1','player')]),'account':account,
            'steps':[{'rule':'probe.private','input':{'actor':'actor-p1'}}],
            'policy':{'sides':100},'trials':[[]]}


@pytest.mark.parametrize('account,whitelist,allowed',[
    ('kp',None,False),('kp',[],False),('kp',['probe.private'],True),('p1',['probe.private'],False)])
def test_only_explicit_kp_probe_runs_private_rule_in_isolated_state(artifact,account,whitelist,allowed):
    payload=request(artifact,account)
    if whitelist is not None:payload['privateRuleIds']=whitelist
    before=copy.deepcopy(payload['state'])
    result=execute_request(payload)['trials'][0]['steps'][0]
    assert result['ok'] is allowed,result
    if allowed:
        assert result['result']<before['entities']['actor-p1']['numbers']['hp']
        assert result['effects']
    else:assert result['code']=='PERMISSION_DENIED'
    assert payload['state']==before


@pytest.mark.parametrize('invalid',[True,'probe.private',['unknown'],['probe.private','probe.private']])
def test_probe_whitelist_is_strictly_validated(artifact,invalid):
    payload=request(artifact);payload['privateRuleIds']=invalid
    with pytest.raises(DomainError,match='INPUT_INVALID'):execute_request(payload)


def test_another_whitelisted_rule_does_not_enable_private_target():
    artifact=stage({'probe.lua':SOURCE,'other.lua':"return rule('probe.other', {}, function() return 1 end, {public=false})"},{})
    payload=request(artifact);payload['privateRuleIds']=['probe.other']
    assert execute_request(payload)['trials'][0]['steps'][0]=={'ok':False,'code':'PERMISSION_DENIED'}


@pytest.mark.parametrize('explicit',[False,True])
def test_ai_scenario_wrapper_keeps_private_access_opt_in(artifact,explicit):
    from onlinecoc_ai.sandbox import run_scenario
    payload=request(artifact)
    scenario={'account':'kp','steps':payload['steps'],'randomPolicy':payload['policy']}
    kwargs={'private_rule_ids':('probe.private',)} if explicit else {}
    result=run_scenario(artifact,payload['state'],scenario,[[]],**kwargs)[0]['steps'][0]
    assert result['ok'] is explicit
    if not explicit:assert result['code']=='PERMISSION_DENIED'


def test_live_host_keeps_private_rules_unavailable_even_for_kp(tmp_path):
    host=Host(tmp_path/'host',bootstrap='test-password')
    try:
        state=host.state();sources=copy.deepcopy(state['artifacts'][state['activeRuleset']]['sources']);sources['probe.lua']=SOURCE
        artifact=stage(sources,state['artifacts'][state['activeRuleset']]['data'])
        state['artifacts'][artifact['revision']]=artifact;state['activeRuleset']=artifact['revision'];host.commit(state)
        before=host.state()['entities']
        for account in ('kp','player1'):
            message=ai_message(host,'action.invoke',{'actionId':'probe.private','input':{'actor':'actor-player1'}},'private-'+account,account)
            message['payload'].update(catalogRevision=host.catalog(account)['revision'],rulesetRevision=artifact['revision'],runId=state['runId'])
            with pytest.raises(DomainError,match='PERMISSION_DENIED'):
                host.command(account,message)
        assert host.state()['entities']==before
    finally:host.close()
