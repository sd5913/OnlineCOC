"""Author reproducible minimal game-state recipes, never production state."""
import copy
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PACK=ROOT/'rulepacks/stumpsville'


def ent(key,kind='character',owner='player1',**numbers):
    return {'id':key,'configurationId':'sv.'+kind,'owner':owner,'visibility':'public','numbers':numbers}
def char(**numbers):return ent('actor',**numbers)
def session(**numbers):return ent('session','session',None,**numbers)
def source():return {'sourceId':'actor','targetId':'session','relationType':'source'}
def active(**numbers):return char(approved=1,ready=1,**numbers)
def draw(sides,*values):return [{'sides':sides,'value':value} for value in values]


CASES=[]
def add(rule,principal,entities,args,updates,result,*,relations=None,rolls=None,intent='',case_id=None,
        category='positive',preflight=None,code=None,rule_code=None):
    rolls=rolls or []
    case={'caseId':case_id or rule.removeprefix('sv.').replace('.','-')+'-positive',
        'category':category,'actionId':rule,'principal':principal,'intent':intent,
        'stateSpec':{'entities':entities,'relations':relations or []},
        'action':{'target':'host','op':'action.invoke','args':{'actionId':rule,'input':args}},
        'randomPolicy':{'kind':'scripted-only-in-isolated-harness','draws':rolls},
        'oracle':{'receiptStatus':'rejected' if category=='technical_rejection' else 'committed',
            'preflightStatus':preflight or ('runtime_required' if rolls else 'passed'),
            'numberUpdates':updates,'resultSubset':result,'unchangedOtherEntityFields':True,
            'idempotentReplay':True}}
    if code:case['oracle']['itemCode']=code
    if rule_code:case['oracle']['ruleCode']=rule_code
    CASES.append(case)
    return case

add('sv.create','player1',[ent('draft','draft')],{'actor':'draft'},
    {'draft':{'str':7,'dex':7,'wil':7,'hp':4,'pips':2,'generation':1}},
    {'str':7,'dex':7,'wil':7,'hp':4,'pips':2},rolls=draw(6,3,4,1,3,4,1,3,4,1,4,2),
    intent='为我拥有的角色草稿生成初始属性；草稿尚不是已批准角色。')
add('sv.profile','kp',[char()],{'actor':'actor','strength':8,'dexterity':9,'will':10,'hp':5,'pips':3},
    {'actor':{'str':8,'strMax':8,'dex':9,'dexMax':9,'wil':10,'wilMax':10,'maxHp':5,'hp':5,'pips':3,'approved':1}},
    {'character':'actor','approved':True},intent='KP批准尚未批准的角色，使用明确给定的初始数值。')
add('sv.ready','player1',[char(approved=1)],{'actor':'actor','ready':True},
    {'actor':{'ready':1}},{'ready':True},intent='将我已批准的角色设为准备完成。')
add('sv.check','player1',[active(),session(phase=1)],{'actor':'actor','attribute':'str','mode':'normal'},
    {'actor':{'checks':1,'lastRoll':5}},{'attribute':'str','mode':'normal','rolled':5,'target':10,'passed':True},
    relations=[source()],rolls=draw(20,5),intent='已开始的会话中，我已批准且准备好的角色进行普通STR检定。')
add('sv.inventory','player1',[char(item5=3,uses5=3),session()],
    {'actor':'actor','operation':'use','slot':5,'value':1},{'actor':{'uses5':2}},
    {'operation':'use','slot':5,'uses':2},relations=[source()],
    intent='消耗第5槽的口粮一格用量；物品定义编号是3，参数slot应为5。')
add('sv.grant','kp',[char()],{'actor':'actor','item':3,'slot':5,'uses':3},
    {'actor':{'item5':3,'uses5':3,'ticks5':0}},{'item':3,'slot':5},
    intent='KP将定义编号3的口粮放入空的第5槽，带3格用量。')
add('sv.remove','kp',[char(item5=2,uses5=3,ticks5=2,litSlot=5)],{'actor':'actor','slot':5},
    {'actor':{'item5':0,'uses5':0,'ticks5':0,'litSlot':0}},{'removed':2,'slot':5},
    intent='KP移除第5槽正在点燃的火把，并清除该槽计时和点燃标记。')
add('sv.transfer','kp',[char(item5=3,uses5=2,ticks5=1),ent('target',owner='player2')],
    {'actor':'actor','target':'target','slot':5,'destination':6},
    {'actor':{'item5':0,'uses5':0,'ticks5':0},'target':{'item6':3,'uses6':2,'ticks6':1}},
    {'item':3,'recipient':'target','slot':6},intent='KP把角色第5槽口粮转交另一角色的空第6槽，保留剩余用量。')
add('sv.damage','kp',[char()],{'actor':'actor','amount':2,'attribute':'str'},
    {'actor':{'hp':2}},{'damage':2,'hp':2,'overflow':0,'critical':False},intent='KP结算2点伤害；目标无护甲、HP为4，不发生溢出。')
add('sv.rest','kp',[char(hp=1,incapacitated=1)],{'actor':'actor','kind':'short','attribute':''},
    {'actor':{'hp':4,'incapacitated':0}},{'kind':'short','hp':4},rolls=draw(6,2),
    intent='KP令仍存活角色短休，恢复由实际骰子和最大HP决定，清除失能。')
add('sv.morale','kp',[ent('npc','npc',None)],{'actor':'npc'},
    {'npc':{'lastRoll':7}},{'attribute':'wil','rolled':7,'target':10,'passed':True},rolls=draw(20,7),
    intent='KP为真实sv.npc对象进行士气检定。')
add('sv.travel','kp',[char(approved=1)],{'actor':'actor','location':2},
    {'actor':{'location':2}},{'location':2},intent='KP将已批准角色移动到配置中确实存在的地点编号2。')
add('sv.travel.auto','player1',[active(),session(phase=1,door1_2=1),ent('destination','location',None,index=2)],
    {'actor':'actor','destination':'destination'},{'actor':{'location':2}},{'location':2,'automatic':True},
    relations=[source()],intent='从地点1沿已开放通路前往相邻的公开地点对象destination（其index为2）。')
add('sv.world','kp',[session()],{'actor':'session','operation':'start','value':0},
    {'session':{'phase':1}},{'phase':1,'round':0},intent='KP启动sv.session会话；actor应指向会话对象。')
add('sv.generate','kp',[ent('world','world',None)],{'actor':'world','kind':'pots'},
    {'world':{'pots':4,'generated4':1}},{'count':4},rolls=draw(6,4),
    intent='KP为尚未生成锅具库存的sv.world对象生成锅具数量。')
add('sv.adjudicate','kp',[active(),session(phase=1,autoResolve=0)],
    {'actor':'actor','kind':'check','attribute':'dex','mode':'normal','operation':'','slot':0,'value':0},
    {'actor':{'checks':1,'lastRoll':6}},{'attribute':'dex','mode':'normal','rolled':6,'passed':True},
    relations=[source()],rolls=draw(20,6),intent='自动结算关闭时，由KP裁定角色普通DEX检定，保留全部必填占位字段。')
scene_entities=[active(),session(phase=1),ent('scene','scene',None),ent('world','world',None)]
scene_args={'actor':'actor','scene':'scene','world':'world','action':'tunnel-ground','choice':'inspect'}
add('sv.scene.resolve','kp',scene_entities,scene_args,{'scene':{'trapKnown':1}},
    {'public':{'sceneAction':'tunnel-ground','choice':'inspect','outcome':'success','cost':0},'reveals':[2]},
    relations=[source()],intent='KP在入口地点观察地面，记录实际场景发现；无需投骰。')

# Distinguish valid failed/blocked outcomes from rejected transactions.
add('sv.check','player1',[active(),session(phase=1)],{'actor':'actor','attribute':'str','mode':'normal'},
    {'actor':{'checks':1,'lastRoll':20}},{'rolled':20,'target':10,'passed':False},relations=[source()],rolls=draw(20,20),
    case_id='check-gameplay-failure',category='gameplay_failure',intent='正常检定未过仍应提交一次，重放原ID不得重掷。')
blocked_args={**scene_args,'action':'tunnel-cheese','choice':'careful'}
add('sv.scene.resolve','kp',copy.deepcopy(scene_entities),blocked_args,{},
    {'public':{'outcome':'blocked','cost':0}},relations=[source()],case_id='scene-business-blocked',
    category='business_blocked',intent='尚未发现机关连接时尝试谨慎取奶酪：规则返回blocked，未达目标，不是技术拒绝。')
failure_entities=copy.deepcopy(scene_entities);failure_entities[2]['numbers']['trapKnown']=1
add('sv.scene.resolve','kp',failure_entities,blocked_args,
    {'actor':{'checks':1,'lastRoll':20,'hp':3},'scene':{'trapState':2},'session':{'round':1}},
    {'public':{'outcome':'failure','cost':1,'round':1}},relations=[source()],rolls=draw(20,20)+draw(12,1),
    case_id='scene-gameplay-failure',category='gameplay_failure',intent='机关已知但解除检定失败，伤害和轮次应保留；不能当执行错误回滚重掷。')
add('sv.inventory','kp',[char(item3=6,uses3=0,item5=3,uses5=3),session()],
    {'actor':'actor','operation':'use','slot':3,'value':1},{},{},relations=[source()],
    case_id='inventory-wrong-slot',category='technical_rejection',preflight='blocked',code='RULE_FAILED',
    rule_code='SV_ITEM_NO_USES_OR_MANUAL_SPELL',intent='误将物品定义编号3当槽位；槽3是奶酪，口粮在槽5，必须拒绝且不扣物品。')
add('sv.grant','player1',[char()],{'actor':'actor','item':3,'slot':5,'uses':3},{},{},
    case_id='grant-permission-denied',category='technical_rejection',preflight='blocked',code='PERMISSION_DENIED',
    intent='玩家不得通过公开目录绕过sv.grant的KP权限。')
add('sv.inventory','kp',[char(item5=3,uses5=3),session()],
    {'actor':'actor','operation':'use','slot':'5','value':1},{},{},relations=[source()],
    case_id='inventory-schema-invalid',category='technical_rejection',preflight='blocked',code='INPUT_INVALID',
    intent='slot错误地提供为字符串，参数检查必须阻止执行。')
add('sv.travel.auto','kp',[active(),session(phase=1),ent('destination','location',None,index=2)],
    {'actor':'actor','destination':'destination'},{},{},relations=[source()],
    case_id='travel-door-closed',category='technical_rejection',preflight='blocked',code='RULE_FAILED',
    rule_code='SV_DOOR_CLOSED',intent='地点相邻但门未开放，不应把Schema通过当成旅行可执行。')


if __name__=='__main__':
    configurations=json.loads((PACK/'config/configurations.json').read_text(encoding='utf-8'))
    doc={'schemaVersion':1,'fixtureSemantics':'Only listed game entities/relations; configuration defaults plus explicit numeric overrides. Fresh Host supplies ordinary empty room collections and synthetic identities.',
        'configurations':configurations,'cases':CASES}
    (HERE/'cases.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'cases':len(CASES),'positiveActionIds':len({c['actionId'] for c in CASES if c['category']=='positive'})}))
