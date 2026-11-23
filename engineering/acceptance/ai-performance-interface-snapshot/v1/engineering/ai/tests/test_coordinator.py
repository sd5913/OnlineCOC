import asyncio
import copy
from pathlib import Path

import pytest

from onlinecoc.host import Host
from onlinecoc_ai.contracts import loads,digest
from onlinecoc_ai.coordinator import Coordinator
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.pack import Pack,fixture_state
from onlinecoc_ai.proposals import Proposals
from onlinecoc_ai.providers.base import Completion,ProviderError
from onlinecoc_ai.sandbox import stage


@pytest.fixture
def setup(tmp_path):
    host=Host(tmp_path/'host',bootstrap='test-password')
    pack=Pack(Path(__file__).parent/'fixtures/pack');artifact=stage(pack.sources,pack.data)
    world=fixture_state(pack.json(pack.scenarios[0]['fixtureRef']),pack.configurations);state=host.state()
    for key in ('entities','relations','configurations','members','progress','collectionRevision'):state[key]=world[key]
    state['artifacts'][artifact['revision']]=artifact;state['activeRuleset']=artifact['revision']
    state['aiControl']['settings'].update(enabled=True,profileId='deepseek-main');host.commit(state)
    service=Proposals(host,pack)
    profile=loads((Path(__file__).parents[1]/'examples/ai-providers.json').read_bytes())['profiles'][0]
    profile['enabled']=True
    yield host,service,profile
    service.close();host.close()


def completion(value):
    from onlinecoc_ai.contracts import canonical
    return Completion({'role':'assistant','content':canonical(value).decode()},
        {'prompt_tokens':10,'completion_tokens':10,'total_tokens':20},'stop',digest(value))


class Fake:
    def __init__(self,callback):self.callback=callback;self.calls=0
    async def complete(self,messages,tools):
        self.calls+=1
        return await self.callback(self.calls,messages,tools)
    async def close(self):pass


async def wait_task(coordinator,identifier,timeout=20):
    async with asyncio.timeout(timeout):
        while True:
            task=coordinator.repository.state()['tasks'][identifier]
            if task['status'] not in ('queued','generating','validating'):return task
            await asyncio.sleep(.02)


def test_draft_is_checked_but_never_published(setup):
    host,service,profile=setup
    delta=loads((Path(__file__).parents[1]/'examples/bonus-15.json').read_bytes())
    async def callback(*args):return completion({'kind':'draft','text':'有限次数道具，风险待 KP 审核','changeSet':delta})
    async def run():
        c=Coordinator(service,{profile['profileId']:profile},provider_factory=lambda p:Fake(callback));await c.start()
        try:
            task=c.enqueue('kp','one','制作道具')
            result=await wait_task(c,task['taskId'])
            assert result['status']=='review_ready',result
            assert service.get('kp',result['proposalId'])['model']==profile['model']
            assert host.state()['configurations']['fixture.token']['defaults']['bonus']==0
            assert host.state()['aiControl']['approvals']=={}
        finally:await c.close()
    asyncio.run(run())


def test_blocked_model_does_not_hold_host_lock_and_can_cancel(setup):
    host,service,profile=setup
    async def run():
        entered=asyncio.Event();never=asyncio.Event()
        async def callback(*args):entered.set();await never.wait()
        c=Coordinator(service,{profile['profileId']:profile},provider_factory=lambda p:Fake(callback));await c.start()
        try:
            task=c.enqueue('kp','blocked','test');await entered.wait()
            def ordinary():
                with host.lock:
                    state=host.state();state['entities']['actor-one']['name']='still responsive';host.commit(state)
            await asyncio.wait_for(asyncio.to_thread(ordinary),2)
            c.cancel('kp',task['taskId'])
            assert (await wait_task(c,task['taskId']))['status']=='cancelled'
        finally:await c.close()
    asyncio.run(run())


def test_request_dedup_queue_and_budget(setup):
    _,service,profile=setup;profile['limits']['maxQueuedPerRoom']=1
    c=Coordinator(service,{profile['profileId']:profile})
    first=c.enqueue('kp','same','text')
    assert c.enqueue('kp','same','text')['taskId']==first['taskId']
    with pytest.raises(AiError,match='COMMAND_ID_CONFLICT'):c.enqueue('kp','same','changed')
    with pytest.raises(AiError,match='QUEUE_FULL'):c.enqueue('kp','second','text')
    c.cancel('kp',first['taskId'])
    profile['limits']['dailyTokenBudget']=1
    with pytest.raises(AiError,match='BUDGET_EXCEEDED'):c._reserve(first['taskId'],profile,[{'role':'user','content':'text'}],[])


@pytest.mark.parametrize('mode,expected', [('forged','TOOL_FORBIDDEN'),('loop','TOOL_ROUND_LIMIT'),('retry','PROVIDER_UNAVAILABLE'),('repair','MODEL_OUTPUT_INVALID')])
def test_untrusted_model_and_retry_limits(setup,mode,expected):
    _,service,profile=setup
    profile['limits'].update(maxToolRounds=3,maxRepairAttempts=1,maxTransportRetries=1)
    async def callback(*args):
        if mode=='retry':raise ProviderError('PROVIDER_UNAVAILABLE',retryable=True)
        if mode=='repair':return completion({'invented':'bad'})
        return Completion({'role':'assistant','content':None,'tool_calls':[{'id':'one','type':'function','function':{
            'name':'publication_apply' if mode=='forged' else 'room_read_context','arguments':'{}'}}]},
            {'prompt_tokens':10,'completion_tokens':10,'total_tokens':20},'tool_calls','f'*64)
    provider=Fake(callback)
    async def run():
        c=Coordinator(service,{profile['profileId']:profile},provider_factory=lambda p:provider);await c.start()
        try:
            task=c.enqueue('kp',mode,'text');result=await wait_task(c,task['taskId'])
            assert result['status']=='failed' and result['error']==expected,result
            assert provider.calls<=4
        finally:await c.close()
    asyncio.run(run())


def test_expired_task_and_authority_change_fail_closed(setup):
    host,service,profile=setup;profile['limits']['taskTimeoutMs']=50
    async def callback(*args):await asyncio.sleep(.2);return completion({'kind':'plan','text':'ok'})
    async def run():
        c=Coordinator(service,{profile['profileId']:profile},provider_factory=lambda p:Fake(callback));await c.start()
        try:
            task=c.enqueue('kp','timeout','text');result=await wait_task(c,task['taskId'])
            assert result['error']=='TASK_TIMEOUT'
        finally:await c.close()
    asyncio.run(run())


def test_disabled_service_makes_no_provider_calls(setup):
    host,service,profile=setup;state=host.state();state['aiControl']['settings']['enabled']=False;host.commit(state)
    c=Coordinator(service,{profile['profileId']:profile})
    with pytest.raises(AiError,match='AI_DISABLED'):c.enqueue('kp','off','text')
    assert service.repository.state()['tasks']=={}


def test_retry_budget_records_each_attempt_once(setup):
    _,service,profile=setup
    async def callback(count,*args):
        if count==1:raise ProviderError('PROVIDER_RATE_LIMITED',retryable=True)
        return completion({'kind':'plan','text':'方案待 KP 审核'})
    async def run():
        c=Coordinator(service,{profile['profileId']:profile},provider_factory=lambda p:Fake(callback));await c.start()
        try:
            task=c.enqueue('kp','budget','text');result=await wait_task(c,task['taskId'])
            assert result['status']=='review_ready' and len(result['calls'])==2
            budget=next(iter(service.repository.state()['budgets'].values()))
            assert len(budget['calls'])==2 and budget['charged']==sum(v['charged'] for v in budget['calls'].values())
            assert sorted(v['status'] for v in budget['calls'].values())==['reserved','settled']
        finally:await c.close()
    asyncio.run(run())


def test_restart_interrupts_queued_tasks_and_preserves_budget(setup):
    host,service,profile=setup
    c=Coordinator(service,{profile['profileId']:profile})
    task=c.enqueue('kp','restart','text')
    c._reserve(task['taskId'],profile,[{'role':'user','content':'text'}],[])
    budgets=service.repository.state()['budgets'];path=service.repository.store.path
    service.close()
    from onlinecoc_ai.repository import Repository
    repo=Repository(path,host.state()['aiControl']['scopeId'])
    try:
        assert repo.state()['tasks'][task['taskId']]['status']=='interrupted'
        assert repo.state()['budgets']==budgets
    finally:repo.close()


def test_permissions_changed_during_generation_discard_output(setup):
    host,service,profile=setup
    async def callback(*args):
        with host.lock:
            state=host.state();state['members']['kp']['authorizationEpoch']+=1;host.commit(state)
        return completion({'kind':'plan','text':'stale output'})
    async def run():
        c=Coordinator(service,{profile['profileId']:profile},provider_factory=lambda p:Fake(callback));await c.start()
        try:
            task=c.enqueue('kp','revoked','text');result=await wait_task(c,task['taskId'])
            assert result['status']=='failed' and result['error']=='PERMISSION_DENIED'
            assert result['text'] is None
        finally:await c.close()
    asyncio.run(run())


def test_profile_changed_during_generation_discards_output_and_runner_survives(setup):
    _, service, profile = setup
    async def run():
        async def callback(*args):
            c.profiles[profile['profileId']]['revision'] += 1
            return completion({'kind': 'plan', 'text': 'stale provider output'})
        c = Coordinator(service, {profile['profileId']: profile}, provider_factory=lambda p: Fake(callback))
        await c.start()
        try:
            task = c.enqueue('kp', 'changed-profile', 'text')
            result = await wait_task(c, task['taskId'])
            assert result['status'] == 'failed' and result['error'] == 'PROFILE_CHANGED' and result['text'] is None
            async def good(*args):return completion({'kind': 'plan', 'text': 'current profile'})
            c.provider_factory = lambda p: Fake(good)
            task = c.enqueue('kp', 'current-profile', 'new text')
            assert (await wait_task(c, task['taskId']))['text'] == 'current profile'
        finally:await c.close()
    asyncio.run(run())


def test_real_contract_is_exposed_and_repair_names_invalid_field(setup):
    from onlinecoc_ai.coordinator import generation_contract
    from jsonschema import Draft202012Validator
    _, service, profile = setup
    delta = loads((Path(__file__).parents[1] / 'examples/bonus-15.json').read_bytes())
    schema = generation_contract()
    assert Draft202012Validator(schema).is_valid(delta)
    assert 'ConfigurationChange' in schema['$defs'] and 'Approval' not in schema['$defs']
    invalid = copy.deepcopy(delta)
    invalid['configurations'][0]['expectedRevision'] = 1  # string required
    async def callback(count, messages, tools):
        assert 'ConfigurationChange' in messages[0]['content'] and 'expectedRevision' in messages[0]['content']
        if count == 1:return completion({'kind': 'draft', 'text': 'draft', 'changeSet': invalid})
        feedback = loads(messages[-1]['content'])
        assert feedback['error']['path'] == '/configurations/0/expectedRevision'
        assert feedback['error']['code'] == 'INPUT_INVALID'
        return completion({'kind': 'draft', 'text': 'corrected draft', 'changeSet': delta})
    async def run():
        c = Coordinator(service, {profile['profileId']: profile}, provider_factory=lambda p: Fake(callback))
        await c.start()
        try:
            task = c.enqueue('kp', 'schema-repair', 'make an item')
            result = await wait_task(c, task['taskId'])
            assert result['status'] == 'review_ready' and len(result['calls']) == 2
            assert not service.host.state()['aiControl']['approvals']
        finally:await c.close()
    asyncio.run(run())
