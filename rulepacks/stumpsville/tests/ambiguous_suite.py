"""Stumpsville KP requests, fixed before the live comparison. Use fresh rooms."""
import re

# Each entry contains the original request, the scripted next human reply and the
# expected number of genuine decisions beyond the original intent.
EXTRA = {
    'rope': ('豆叶要攀爬，给她发一捆现成的绳索吧，放哪合适你安排，发好告诉她。','用现有绳索，挑能放下的空位就好。',0),
    'heal': ('让受了点伤的豆叶恢复到满生命，别动上限，顺便告诉她已经好了。','就按她当前生命上限处理。',0),
    'rations': ('这趟出门给两位玩家各带一份现成口粮，别新建物品，背包位置你看着放。','木栗、豆叶各领一份现有口粮。',0),
    'newtool': ('做一种叫「蜡布罩」的普通占槽物品，给雨天赶路用，细节照类似工具。先只加定义。','采用你推荐的尺寸和用量，不要发给角色。',0),
    'fork': ('我想让庭院的银铃成为剧情伏笔，公开给玩家还是只记在主持真相里我还没定。先讲讲两种做法，等我选再改。','选主持私密真相。在庭院原有真相末尾追加一句银铃线索，其他先照旧。',1),
    'map': ('从庭院边上开个叫「避雨棚」的小支路吧。要能从庭院进、原路回，别放宝物也先别公开。文案你定。','作为新地点双向连庭院，沿用现有地点和通路默认值。',0),
    'npc': ('给我备一个独立的巡桥学徒 NPC 模板，体力参照普通小鼠，护甲 1 就行。只要模板，暂不让他出场。','按普通 NPC 模板推荐其余默认值，取一个合适的扩展 ID。',0),
    'calculation': ('主持想多一条只读的侦察评分规则，输入角色，返回敏捷和意志之和。单独新增，不动角色数值。名字你定。','使用独立的计算规则，输入 actor，按当前 dex 和 wil 相加。',0),
    'bandage': ('把物品表里的干净绷带写得更有现场感，提到亚麻和草药即可，照料伤者的原用途和数值都留着。','只润色干净绷带的描述，不需要新增物品。',0),
    'light': ('木栗现在带着什么能照明的东西，还能用几格？帮我查一下，先别点。','请按当前角色的槽位和物品表直接回答。',0),
    'options': ('豆叶嫌背包紧，我在考虑丢东西或扩容。先给我比较两种办法在这局的后果，先别执行。','只比较丢弃和扩容，尤其说明扩容是否要改规则。',0),
    'dinner': ('今晚的饭钱算木栗一枚，帮我把账结了，给他留句话。','从木栗现有钱币扣 1，定向通知他。',0),
    'stock': ('在庭院里留一份现有口粮当可发现的物资吧。加到这个地点的库存里就行，别先发给谁。','庭院库存新增一份普通口粮，保留原来的物资。',0),
}
TITLES={'shield':'制作、发放并通知','travel':'选择路费接收者与金额','courtyard':'庭院雨景','rope':'给豆叶发绳索','heal':'治疗与通知','rations':'两人各领口粮','newtool':'新增蜡布罩定义','fork':'公开或私密的剧情伏笔','map':'新增双向避雨棚','npc':'新增 NPC 模板','calculation':'新增只读计算规则','bandage':'润色绷带描述','light':'查询照明与剩余用量','options':'比较丢弃与扩容','dinner':'扣饭钱并通知','stock':'庭院补充库存'}
READ_ONLY={'light','options'}
DECISIONS={'travel','fork'}

def appended_rain(original, edited):
    if not isinstance(original,str) or not isinstance(edited,str) or not edited.startswith(original):
        return False
    addition=edited[len(original):]
    return any(word in addition for word in ('雨','檐还在滴水','檐下滴水','檐上滴水'))

def describes_drop(reply):
    location=any(word in reply for word in ('地面','原地','当前位置','地点','所在场景','当前场景','现场','地上','原处','落在','掉落'))
    recover=any(word in reply for word in ('取回','捡回','拿回','拾回','拾取','拿取','捡起','捡取','再拿','再取','重新获得','重新捡','重新拾'))
    denies_drop=re.search(r'(?:丢弃后.{0,6})?(?:不会|不能|无法)(?:留在|落在|掉在)(?:原地|现场|地点|地面)|(?:任何人|自己都).{0,6}(?:无法|不能)(?:再|重新)?(?:捡回|取回|拿回)',reply)
    return bool(location and recover and not denies_drop)

def count_item(numbers, ordinal):
    return sum(numbers.get('item'+str(i))==ordinal for i in range(1,21))

def solve(case,before,now,turn,kp,p1):
    game=before['data']['game.json']
    updated=now['data']['game.json']
    changes=turn['overallPaths']
    players=now['players'];old=before['players']
    if case in READ_ONLY:
        reply=turn['reply']
        if not isinstance(reply,str) or changes or not turn.get('deliveredAnswer') or turn.get('status') not in ('review_ready','completed'):return False
        if case=='options':return ('丢' in reply or '弃' in reply) and ('扩容' in reply or '容量' in reply or '背包' in reply) and len(reply)>48 and describes_drop(reply)
        torch=next(i for i,v in enumerate(game['items'],1) if v['id']=='torch')
        slot=next(i for i in range(1,21) if old['player1'].get('item'+str(i))==torch)
        uses=old['player1']['uses'+str(slot)]
        return '火把' in reply and (str(uses) in reply or (uses==3 and '三' in reply))
    def scoped(*prefixes):return bool(changes) and all(any(p==v or p.startswith(v) for v in prefixes) for p in changes)
    def notices(who):return len(now['notices'][who])-len(before['notices'][who])
    if case in ('rope','rations'):
        ident='rope' if case=='rope' else 'ration'
        ordinal=next(i for i,v in enumerate(game['items'],1) if v['id']==ident)
        targets=['player2'] if case=='rope' else list(players)
        for who in targets:
            if count_item(players[who],ordinal)!=count_item(old[who],ordinal)+1:return False
            if any(old[who].get('item'+str(i),0)>0 and old[who]['item'+str(i)]!=players[who].get('item'+str(i)) for i in range(1,21)):return False
        return scoped(*(p for who in targets for p in ('/players/'+who+'/item','/players/'+who+'/uses','/notices/'+who+'/'))) and (case=='rations' or notices('player2')==1)
    if case=='heal':
        return players['player2']['hp']==old['player2']['maxHp'] and notices('player2')==1 and scoped('/players/player2/hp','/notices/player2/')
    if case=='dinner':
        return players['player1']['pips']==old['player1']['pips']-1 and notices('player1')==1 and scoped('/players/player1/pips','/notices/player1/')
    where=next(i for i,p in enumerate(game['locations']) if p['name']=='庭院')
    loc=updated['locations'][where];initial=game['locations'][where]
    prefix=f'/data/game.json/locations/{where}/'
    if case=='fork':
        return changes==[prefix+'truth'] and '银铃' in loc['truth'] and initial['truth'] in loc['truth'] and turn['humanRound']>=2
    if case=='stock':
        ordinal=next(i for i,v in enumerate(game['items'],1) if v['id']=='ration')
        return scoped(prefix+'stock/') and loc['stock']==initial['stock']+[{'item':ordinal,'count':1}]
    if case=='bandage':
        i=next(i for i,v in enumerate(game['items']) if v['id']=='bandage')
        desc=updated['items'][i]['description']
        return changes==[f'/data/game.json/items/{i}/description'] and '亚麻' in desc and '草药' in desc and any(x in desc for x in ('照料','包扎','伤'))
    if case=='newtool':
        items=updated['items']
        return len(items)==len(game['items'])+1 and changes==[f'/data/game.json/items/{len(items)-1}'] and items[-1]['name']=='蜡布罩' and items[-1]['kind']=='item'
    if case=='map':
        n=len(game['locations'])
        if len(updated['locations'])!=n+1:return False
        extra=updated['locations'][-1]
        return (scoped(prefix+'exits/',f'/data/game.json/locations/{n}') and extra['name']=='避雨棚' and extra['index']==n+1 and extra['exits']==[initial['index']] and loc['exits']==initial['exits']+[n+1] and not extra['stock'] and str(n+1) not in kp.state()['published'])
    if case=='npc':
        new=now['configurations'].keys()-before['configurations'].keys()
        if len(new)!=1:return False
        key=next(iter(new));c=now['configurations'][key]
        return changes==['/configurations/'+key] and key.startswith('sv.ext.npc.') and c['defaults'].get('armor')==1 and c['defaults'].get('isNpc')==1 and c.get('typeRef')=='actor'
    if case=='calculation':
        new=now['sources'].keys()-before['sources'].keys()
        if len(new)!=1:return False
        name=next(iter(new));m=re.search(r"""rule\s*\(\s*['"]([^'"]+)""",now['sources'][name])
        if not m or changes!=['/sources/'+name]:return False
        result=kp.request('/api/v1/preview',{'rule':m.group(1),'input':{'actor':p1.state()['character']['instanceId']}},allow_error=True)
        turn['ruleProbe']={'rule':m.group(1),'result':result.get('result'),'expected':old['player1']['dex']+old['player1']['wil']}
        return result.get('result')==turn['ruleProbe']['expected']
    raise ValueError(case)
