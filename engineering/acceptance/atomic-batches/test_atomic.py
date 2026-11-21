"""Independent saves only; real Lua workers and durable FileDataStore."""
import copy
import threading
import time
import json
import subprocess
import sys
from pathlib import Path

import pytest
from onlinecoc.host import Host
from onlinecoc.registry import stage
from onlinecoc.errors import DomainError
from onlinecoc.atomic_batches import child_id, SUPPORTED
from onlinecoc_data import canonical


RULES={
    'add.lua': "return rule('atomic.add', {'actor','amount'}, function(r,a,n) r.set(a,'hp',r.number(a,'hp')+n); return r.number(a,'hp') end)",
    'fail.lua': "return rule('atomic.fail', {'actor'}, function(r,a) r.set(a,'hp',1); error('TEST_SLOT_EMPTY') end)",
    'private.lua': "return rule('atomic.private', {'actor'}, function(r,a) error(r.read(a).name) end)",
    'roll.lua': "return rule('atomic.roll', {'actor'}, function(r,a) local n=r.roll(20); r.set(a,'hp',n); return n end)",
    'false.lua': "return rule('atomic.false', {'actor'}, function(r,a) local n=r.roll(20); r.set(a,'hp',n); return false end)",
    'swallow.lua': "return rule('atomic.swallow', {'actor'}, function(r,a) pcall(function() r.set(a,'hp',3) end); return true end)",
    'pre.lua': "return rule('atomic.pre', {'actor','amount'}, function(r,a,n) assert(r.number(a,'hp')==n,'TEST_PRECONDITION'); return true end)",
    'flow.lua': "return flow('atomic.flow', {'actor'}, {ask('q', {role='kp',seconds=10,yes='end',no='end',timeout='end'})})",
    'blocked.lua': "return rule('atomic.blocked', {}, function(r) return {public={outcome='blocked', reason='synthetic'}} end)",
}


@pytest.fixture(scope='module')
def artifact():return stage(RULES)


@pytest.fixture
def host(tmp_path,artifact):
    h=Host(tmp_path/'room',bootstrap='synthetic-password')
    s=h.state();s['artifacts'][artifact['revision']]=copy.deepcopy(artifact);s['activeRuleset']=artifact['revision']
    s['entities']['actor-player1']['numbers']['maxHp']=100
    h.commit(s)
    yield h
    h.close()


def action(op,**args):return {'target':'host','op':op,'args':args}
def rule(name='atomic.add',**inputs):return action('action.invoke',actionId=name,input={'actor':'actor-player1',**inputs})
def patch(name='renamed'):return action('entity.patch',id='actor-player1',name=name)
def business(h):
    s=h.state();s.pop('commands');return s
def run(h,actions,cid='batch',account='kp'):return h.execute_batch(account,actions,command_id=cid)


def test_preflight_no_mutation_and_sequential_dependency(host):
    actions=[action('entity.update',id='actor-player1',numbers={'hp':12}),rule('atomic.pre',amount=12)]
    before=canonical(host.state());g=host.store.generation
    result=host.preflight_batch('kp',actions)
    assert result['status']=='passed',result
    assert [i['status'] for i in result['items']]==['passed','passed']
    assert canonical(host.state())==before and host.store.generation==g


@pytest.mark.parametrize('position',[0,1,2])
def test_failure_discards_first_middle_last(host,position):
    actions=[patch('first'),rule(amount=2),patch('last')];actions[position]=rule('atomic.fail')
    before=business(host);result=run(host,actions)
    assert result['status']=='rejected',result
    ex=result['result'];assert ex['committedCount']==0 and ex['failedCount']==1
    assert ex['rolledBackCount']==position and ex['notExecutedCount']==2-position
    assert ex['items'][position]['ruleCode']=='TEST_SLOT_EMPTY'
    assert business(host)==before
    assert list(host.state()['commands'])==['kp:batch']
    assert run(host,actions)==result


def test_success_dependency_receipt_and_dedupe(host):
    actions=[action('entity.update',id='actor-player1',numbers={'hp':12}),rule('atomic.pre',amount=12)]
    result=run(host,actions)
    assert result['status']=='committed' and result['result']['committedCount']==2,result
    assert host.state()['entities']['actor-player1']['numbers']['hp']==12
    g=host.store.generation;assert run(host,actions)==result and host.store.generation==g
    with pytest.raises(DomainError,match='COMMAND_ID_CONFLICT'):run(host,[patch('other')])
    assert host.receipt('kp',child_id('batch',1))['result'] is True


@pytest.mark.parametrize('bad',[
    {'target':'ai','op':'ai.session.create','args':{}},
    action('flow.cancel',flowId='none'),action('flow.respond',waitId='none',revision=1,answer=True),
    action('flow.retry',flowId='none'),action('rule.activate',revision='none'),
    action('publication.apply',approvalId='none'),action('member.add',accountId='player2',role='player'),
    rule('atomic.flow'),action('member.update',accountId='kp',active=False),
])
def test_unsupported_is_rejected_before_any_effect(host,bad):
    before=business(host);actions=[rule('atomic.roll'),bad]
    pre=host.preflight_batch('kp',actions)
    assert pre['status']=='unsupported',pre
    assert pre['items'][0]['status']=='runtime_required' and pre['items'][0]['code']=='BATCH_PRECHECK_FAILED'
    result=run(host,actions)
    assert result['status']=='rejected' and result['result']['committedCount']==0,result
    assert host.state()['commands']['kp:batch']['random']==[]
    assert business(host)==before


def test_runtime_preflight_never_rolls(host,monkeypatch):
    monkeypatch.setattr('onlinecoc.atomic_batches.secrets.randbelow',lambda _:pytest.fail('preflight rolled'))
    before=canonical(host.state());actions=[patch(),rule('atomic.roll'),patch('later')]
    pre=host.preflight_batch('kp',actions)
    assert [r['status'] for r in pre['items']]==['passed','runtime_required','runtime_required'],pre
    assert pre['status']=='runtime_required' and canonical(host.state())==before


def test_false_game_result_is_committed_once(host,monkeypatch):
    calls=[]
    def rng(sides):calls.append(sides);return 18
    monkeypatch.setattr('onlinecoc.atomic_batches.secrets.randbelow',rng)
    actions=[rule('atomic.false'),patch()];result=run(host,actions)
    assert result['status']=='committed' and result['result']['items'][0]['result'] is False,result
    assert host.state()['entities']['actor-player1']['numbers']['hp']==19
    assert run(host,actions)==result and calls==[20]
    host.close();host.__init__(host.path)
    assert run(host,actions)==result and calls==[20]


class Crash(BaseException):pass


@pytest.mark.parametrize('point',['after_batch_intent','after_batch_random','after_batch_item','after_batch_terminal'])
def test_crash_restart_reuses_trace_and_single_effect(host,monkeypatch,point):
    calls=[]
    def rng(sides):calls.append(sides);return 6
    monkeypatch.setattr('onlinecoc.atomic_batches.secrets.randbelow',rng)
    def fault(stage):
        if stage==point:raise Crash()
    actions=[rule('atomic.roll'),patch()];host.fault=fault
    with pytest.raises(Crash):run(host,actions)
    host.fault=None;host.close();host.__init__(host.path)
    result=run(host,actions)
    assert result['status']=='committed',result
    assert host.state()['entities']['actor-player1']['numbers']['hp']==7
    assert calls==[20]
    assert len(host.state()['audit'])==2


def test_recovery_refuses_changed_room_without_overwrite(host,monkeypatch):
    calls=[]
    monkeypatch.setattr('onlinecoc.atomic_batches.secrets.randbelow',lambda sides:calls.append(sides) or 4)
    def fault(stage):
        if stage=='after_batch_random':raise Crash()
    actions=[rule('atomic.roll')];host.fault=fault
    with pytest.raises(Crash):run(host,actions)
    host.fault=None;s=host.state();s['entities']['actor-player2']['name']='concurrent';host.commit(s)
    host.close();host.__init__(host.path)
    result=run(host,actions)
    assert result['status']=='rejected' and result['code']=='BATCH_STATE_CHANGED',result
    assert host.state()['entities']['actor-player1']['numbers']['hp']==9
    assert host.state()['entities']['actor-player2']['name']=='concurrent' and calls==[20]


@pytest.mark.parametrize('point',['after_batch_item','before_batch_terminal'])
def test_reentrant_change_never_overwritten(host,point):
    done=False
    def fault(stage):
        nonlocal done
        if stage==point and not done:
            done=True;s=host.state();s['entities']['actor-player2']['name']='concurrent';host.commit(s)
    host.fault=fault;result=run(host,[patch()]);host.fault=None
    assert result['status']=='rejected',result
    assert result['code']=='BATCH_STATE_CHANGED',result
    assert host.state()['entities']['actor-player2']['name']=='concurrent'
    assert host.state()['entities']['actor-player1']['name']!='renamed'


def test_notification_commit_only_and_deduplicated(host):
    actions=[patch(),action('notification.send',recipientAccountIds=['player1'],text='Done',sourceActionIndex=0)]
    observed=[]
    def fault(stage):
        if stage=='after_batch_item':observed.append(host.notifications('player1')['items'])
    host.fault=fault;result=run(host,actions);host.fault=None
    assert result['status']=='committed',result
    assert observed==[[],[]]
    assert len(host.notifications('player1')['items'])==1
    assert run(host,actions)==result and len(host.notifications('player1')['items'])==1


def test_notification_failure_discards_business(host):
    before=business(host)
    result=run(host,[patch(),action('notification.send',recipientAccountIds=['missing'],text='Done',sourceActionIndex=0)])
    assert result['status']=='rejected' and business(host)==before,result


@pytest.mark.parametrize('source',[True,-1,1,100])
def test_bad_notification_index_blocks_before_effect(host,source):
    before=business(host)
    result=run(host,[patch(),action('notification.send',recipientAccountIds=['player1'],text='Done',sourceActionIndex=source)])
    assert result['status']=='rejected' and business(host)==before,result


def test_schema_diagnostic_and_no_private_exception(host):
    pre=host.preflight_batch('kp',[rule(amount='wrong')])
    assert pre['status']=='blocked' and pre['items'][0]['path']=='/actions/0/args/input/amount',pre
    result=run(host,[rule('atomic.private')])
    assert '调查员' not in str(result) and 'stack traceback' not in str(result)
    assert 'ruleCode' not in result['result']['items'][0]


def test_player_permission_and_receipt_redaction(host):
    result=run(host,[rule('atomic.fail')],account='player1')
    assert result['status']=='rejected' and 'TEST_SLOT_EMPTY' not in str(result),result
    pre=host.preflight_batch('player1',[rule('atomic.fail')])
    assert 'TEST_SLOT_EMPTY' not in str(pre)
    result=run(host,[rule('atomic.swallow',actor='actor-player2')],cid='denied',account='player1')
    assert result['status']=='rejected' and result['result']['items'][0]['code']=='PERMISSION_DENIED',result


def test_no_autonomous_flow_tick(host):
    before=business(host);result=run(host,[patch()])
    after=business(host)
    assert result['status']=='committed' and before['flows']==after['flows'] and before['waits']==after['waits']


def test_publish_reply_loss_is_success(host):
    calls=0
    def fault(stage):
        nonlocal calls
        if stage=='after_publish':
            calls+=1
            if calls==2:raise RuntimeError('reply lost')
    host.store.fault=fault;result=run(host,[patch()]);host.store.fault=None
    assert result['status']=='committed' and host.state()['entities']['actor-player1']['name']=='renamed',result


def test_two_threads_serialize_without_lost_update(host):
    outputs=[]
    def worker(cid):outputs.append(run(host,[rule(amount=1)],cid=cid))
    threads=[threading.Thread(target=worker,args=(str(i),)) for i in range(2)]
    for t in threads:t.start()
    for t in threads:t.join(15)
    assert len(outputs)==2 and all(r['status']=='committed' for r in outputs)
    assert host.state()['entities']['actor-player1']['numbers']['hp']==11


def test_scope_list_is_explicit():
    assert len(SUPPORTED)==21 and 'flow.respond' not in SUPPORTED and 'member.add' not in SUPPORTED


@pytest.mark.parametrize('op',sorted(SUPPORTED))
def test_every_declared_operation_has_executed_positive_case(host,op):
    from onlinecoc.assets import Assets
    s=host.state();relation_id=next(iter(s['relations']))
    s['entities']['actor-player1']['rules']={'probe':{'ruleId':'atomic.add'}};host.commit(s)
    args={
        'entity.create':{'configurationId':'demo.item','name':'Synthetic item'},
        'entity.patch':{'id':'actor-player1','name':'Changed'},
        'entity.update':{'id':'actor-player1','numbers':{'hp':8}},
        'entity.archive':{'id':'secret-clue'},
        'relation.set':{'sourceId':'actor-player1','targetId':'actor-player2','relationType':'references'},
        'relation.remove':{'id':relation_id},
        'progress.set':{'ownerKind':'entity','ownerId':'actor-player1','eventKey':'test','value':True},
        'room.status':{'status':'paused'},
        'member.update':{'accountId':'player2','active':False},
        'action.invoke':{'actionId':'atomic.add','input':{'actor':'actor-player1','amount':1}},
        'behavior.invoke':{'entityId':'actor-player1','event':'probe','input':{'actor':'actor-player1','amount':1}},
        'chat.direct.open':{'accountId':'player1'},
        'chat.channel.create':{'kind':'group','name':'Test group','participants':['kp','player1']},
        'chat.channel.update':{'channelId':'general','revision':1,'name':'Renamed'},
        'chat.message.send':{'channelId':'general','text':'Synthetic message'},
    }
    if op in ('asset.attach','asset.remove'):
        aid=Assets(host).upload('kp','synthetic.txt',b'synthetic')
        args[op]={'assetId':aid,**({'entityId':'actor-player1'} if op=='asset.attach' else {})}
    if op in ('chat.message.edit','chat.message.retract'):
        sent=run(host,[action('chat.message.send',channelId='general',text='before')],cid='seed')
        mid=sent['result']['items'][0]['result']['messageId']
        args[op]={'channelId':'general','messageId':mid,'revision':1,
            **({'text':'after'} if op=='chat.message.edit' else {})}
    if op=='chat.message.share':
        run(host,[rule(amount=1)],cid='seed')
        args[op]={'channelId':'general','commandId':child_id('seed',0)}
    if op=='notification.send':
        run(host,[patch()],cid='seed')
        args[op]={'sourceCommandId':child_id('seed',0),'sourceOp':'entity.patch',
            'recipientAccountIds':['player1'],'text':'Synthetic notice'}
    pre=host.preflight_batch('kp',[action(op,**args[op])])
    assert pre['status']=='passed',pre
    result=run(host,[action(op,**args[op])])
    assert result['status']=='committed' and result['result']['committedCount']==1,result


@pytest.mark.parametrize('point',['after_batch_intent','after_batch_random','after_batch_item','after_batch_terminal'])
def test_real_process_exit_and_restart(host,tmp_path,point):
    actions=[rule('atomic.roll'),patch()]
    path=tmp_path/'actions.json';path.write_text(json.dumps(actions),encoding='utf-8')
    data_dir=host.path;host.close()
    worker=Path(__file__).with_name('crash_worker.py')
    outcome=subprocess.run([sys.executable,'-B',str(worker),str(data_dir),str(path),point],
        capture_output=True,timeout=25,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    assert outcome.returncode==70,outcome.stderr.decode(errors='replace')
    from onlinecoc_data import FileDataStore
    with FileDataStore(data_dir/'rooms/demo') as store:prior=store.snapshot()[1]
    host.__init__(data_dir)
    rec=run(host,actions)
    assert rec['status']=='committed',rec
    draws=host.state()['commands']['kp:batch']['random']
    assert len(draws)==1 and host.state()['entities']['actor-player1']['numbers']['hp']==draws[0]['value']
    if prior['commands']['kp:batch']['random']:assert draws==prior['commands']['kp:batch']['random']
    assert len(host.state()['audit'])==2


def test_budget_and_child_id_conflict_fail_closed(host,monkeypatch):
    before=business(host)
    monkeypatch.setattr('onlinecoc.atomic_batches.EXECUTION_SECONDS',0)
    result=run(host,[patch()]);assert result['status']=='rejected' and business(host)==before,result
    monkeypatch.setattr('onlinecoc.atomic_batches.EXECUTION_SECONDS',30)
    cid=child_id('next',0)
    run(host,[patch('first')],cid=cid)
    result=run(host,[patch('blocked')],cid='next')
    assert result['status']=='rejected' and result['result']['items'][0]['code']=='COMMAND_ID_CONFLICT',result


def test_notification_discarded_when_later_item_fails(host):
    before=business(host)
    result=run(host,[patch(),action('notification.send',recipientAccountIds=['player1'],text='Done',sourceActionIndex=0),rule('atomic.fail')])
    assert result['status']=='rejected' and business(host)==before and not host.notifications('player1')['items'],result


def test_current_permission_rechecked_for_committed_child_result(host):
    actions=[rule(amount=1)]
    result=run(host,actions,account='player1')
    assert result['status']=='committed' and result['result']['items'][0]['result']==10
    s=host.state();s['entities']['actor-player1'].update(owner='player2',visibility='owner');host.commit(s)
    assert 'result' not in host.receipt('player1','batch')['result']['items'][0]


def test_business_blocked_is_preserved_not_interpreted_as_goal_completed(host):
    actions=[action('action.invoke',actionId='atomic.blocked',input={})]
    pre=host.preflight_batch('kp',actions)
    assert pre['status']=='passed' and pre['items'][0]['preview'] is True
    assert pre['items'][0]['result']['public']['outcome']=='blocked'
    result=run(host,actions)
    assert result['status']=='committed' and result['result']['items'][0]['result']['public']['outcome']=='blocked'


def memory(host,status='confirmed',revision=2):
    return {'schemaVersion':1,'memoryId':'synthetic-memory','scopeId':host.state()['aiControl']['scopeId'],
        'kind':'event','content':'Synthetic fact','sourceRefs':[],'visibility':'kp','owner':'kp',
        'status':status,'validUntil':None,'supersedes':None,'revision':revision,'createdAt':1}


def test_memory_fact_authoritative_receipt_and_mirror_recovery(host):
    fact=memory(host)
    first=host.commit_memory_fact('kp',fact,command_id='memory-confirm',expected_revision=0)
    assert first['result']['memory']==fact
    generation=host.store.generation
    assert host.commit_memory_fact('kp',fact,command_id='memory-confirm',expected_revision=0)==first
    assert host.store.generation==generation
    host.close();host.__init__(host.path)
    assert host.receipt('kp','memory-confirm')['result']['memory']==fact
    revoked=memory(host,'revoked',3)
    second=host.commit_memory_fact('kp',revoked,command_id='memory-revoke',expected_revision=2)
    assert second['result']['memory']==revoked
    assert host.state()['aiControl']['memoryFacts'][fact['memoryId']]==revoked


@pytest.mark.parametrize('kind',['role','scope','revision','id-conflict','schema'])
def test_memory_fact_guards(host,kind):
    fact=memory(host);account='kp';expected=0;cid='memory'
    if kind=='role':account='player1'
    elif kind=='scope':fact['scopeId']='other'
    elif kind=='revision':expected=1
    elif kind=='schema':fact['unexpected']='bad'
    else:
        host.commit_memory_fact('kp',fact,command_id=cid,expected_revision=0);fact['content']='changed'
    before=canonical(host.state())
    with pytest.raises(DomainError):host.commit_memory_fact(account,fact,command_id=cid,expected_revision=expected)
    assert canonical(host.state())==before


def test_memory_fact_publish_reply_loss(host):
    def fault(stage):
        if stage=='after_publish':raise RuntimeError('lost reply')
    host.store.fault=fault
    result=host.commit_memory_fact('kp',memory(host),command_id='memory',expected_revision=0)
    host.store.fault=None
    assert result['status']=='committed' and host.receipt('kp','memory')==result


def test_thirty_three_small_actions_have_no_business_count_limit(host):
    actions=[patch(str(i)) for i in range(33)]
    pre=host.preflight_batch('kp',actions)
    assert pre['status']=='passed' and len(pre['items'])==33,pre
    result=run(host,actions)
    assert result['status']=='committed' and result['result']['committedCount']==33,result
    assert host.state()['entities']['actor-player1']['name']=='32'
    assert run(host,actions)==result


def test_over_byte_limit_is_rejected_without_intent_or_effects(host):
    actions=[action('chat.message.send',channelId='general',text='x'*4000) for _ in range(9)]
    before=canonical(host.state());generation=host.store.generation
    for operation in (lambda:host.preflight_batch('kp',actions),lambda:run(host,actions)):
        with pytest.raises(DomainError,match='LIMIT_EXCEEDED'):operation()
        assert canonical(host.state())==before and host.store.generation==generation
