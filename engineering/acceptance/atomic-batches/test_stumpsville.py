"""Actual package Lua/configuration, synthetic room only, no AI credentials."""
import copy
import json
from pathlib import Path

import pytest
from onlinecoc.registry import stage
from onlinecoc.model import entity
from test_atomic import host, artifact, action, run, business

PACK=Path(__file__).resolve().parents[3]/'rulepacks/stumpsville'


@pytest.fixture(scope='module')
def pack_artifact():
    names=['inventory.lua','inventory-core.lua','automation.lua','layout.lua','rest.lua']
    return stage({n:(PACK/'rules'/n).read_text(encoding='utf-8') for n in names},
        {'game.json':json.loads((PACK/'config/game.json').read_text(encoding='utf-8'))})


@pytest.fixture
def pack_host(host,pack_artifact):
    s=host.state()
    configurations=json.loads((PACK/'config/configurations.json').read_text(encoding='utf-8'))
    for configuration in configurations:s['configurations'][configuration['configurationId']]=configuration
    actor=s['entities']['actor-player1'];config=s['configurations']['sv.character']
    actor.update(configurationId='sv.character',configurationRevision=config['revision'],numbers=copy.deepcopy(config['defaults']))
    actor['numbers'].update(hp=2,maxHp=6,approved=1,ready=1,item3=6,uses3=0,item5=3,uses5=3)
    config=s['configurations']['sv.session'];session=entity('synthetic-session','actor','Synthetic session',None,**config['defaults'])
    session.update(configurationId='sv.session',configurationRevision=config['revision'])
    session['numbers']['phase']=1;s['entities'][session['instanceId']]=session
    s['relations']['synthetic-source']={'relationId':'synthetic-source','sourceId':actor['instanceId'],
        'targetId':session['instanceId'],'relationType':'source','revision':1,'tags':[],'metadata':{}}
    s['artifacts'][pack_artifact['revision']]=pack_artifact;s['activeRuleset']=pack_artifact['revision'];host.commit(s)
    return host


def inventory(slot):
    return action('action.invoke',actionId='sv.inventory',input={'actor':'actor-player1','operation':'use','slot':slot,'value':1})
def short_rest():
    return action('action.invoke',actionId='sv.rest',input={'actor':'actor-player1','kind':'short','attribute':''})
def notify():
    return action('notification.send',recipientAccountIds=['player1'],text='已完成口粮消耗和短休，请查看实际状态。',sourceActionIndex=1)


def test_wrong_definition_number_as_slot_reports_inner_reason(pack_host):
    h=pack_host;before=business(h);actions=[inventory(3),short_rest(),notify()]
    pre=h.preflight_batch('kp',actions)
    assert pre['status']=='blocked' and pre['items'][0]['ruleCode']=='SV_ITEM_NO_USES_OR_MANUAL_SPELL',pre
    result=run(h,actions)
    assert result['result']['failedCount']==1 and result['result']['notExecutedCount']==2,result
    assert result['result']['committedCount']==0 and result['result']['status']=='failed'
    assert business(h)==before and h.state()['commands']['kp:batch']['random']==[]


def test_correct_slot_then_rest_and_notification(pack_host,monkeypatch):
    h=pack_host;calls=[]
    monkeypatch.setattr('onlinecoc.atomic_batches.secrets.randbelow',lambda sides:calls.append(sides) or 1)
    actions=[inventory(5),short_rest(),notify()]
    pre=h.preflight_batch('kp',actions)
    assert [r['status'] for r in pre['items']]==['passed','runtime_required','runtime_required'],pre
    assert not calls and h.state()['entities']['actor-player1']['numbers']['uses5']==3
    result=run(h,actions);assert result['status']=='committed',result
    numbers=h.state()['entities']['actor-player1']['numbers']
    assert numbers['uses5']==2 and numbers['hp']==5 and numbers['uses3']==0
    assert len(h.notifications('player1')['items'])==1 and calls==[6]
    assert run(h,actions)==result and calls==[6]


def test_late_error_discards_use_healing_and_notification(pack_host,monkeypatch):
    h=pack_host;before=business(h)
    monkeypatch.setattr('onlinecoc.atomic_batches.secrets.randbelow',lambda _:1)
    result=run(h,[inventory(5),short_rest(),notify(),inventory(4)])
    assert result['status']=='rejected' and result['result']['rolledBackCount']==3,result
    assert result['result']['items'][3]['ruleCode']=='SV_EMPTY_SLOT'
    assert business(h)==before and len(h.state()['commands']['kp:batch']['random'])==1


def test_ration_moved_to_another_slot_is_not_guessed(pack_host):
    h=pack_host;s=h.state();n=s['entities']['actor-player1']['numbers']
    n.update(item5=0,uses5=0,item6=3,uses6=3);h.commit(s)
    pre=h.preflight_batch('kp',[inventory(5),short_rest(),notify()])
    assert pre['status']=='blocked' and pre['items'][0]['ruleCode']=='SV_EMPTY_SLOT',pre
    assert h.state()['entities']['actor-player1']['numbers']['uses6']==3
