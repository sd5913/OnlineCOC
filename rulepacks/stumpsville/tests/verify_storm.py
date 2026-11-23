"""Play a complete storm route through two authenticated player and keeper sessions."""
import sys
import uuid
from harness import running, provision, Account


def browser_finish(runtime, password):
    from playwright.sync_api import sync_playwright, expect
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page()
        page.goto(runtime.origin+'/sessions/storm-review/')
        page.locator('input[name=loginName]').fill('kp')
        page.locator('input[name=password]').fill(password)
        page.get_by_role('button',name='进入冒险',exact=True).click()
        page.get_by_role('button',name='确认结局 · 溪岸撤离').click()
        page.locator('textarea[name=roster]').fill('木栗护送居民，豆叶在入口接应。')
        page.get_by_role('button',name='记录结局',exact=True).click()
        expect(page.locator('#room-overview')).to_contain_text('已结局',timeout=20000)
        browser.close()


def play(route, alternate=False):
    with running('storm-' + route) as (runtime, password):
        data_dir = runtime.args.data_dir
        keeper, player, observer = provision(runtime, password)
        def act(action, choice):
            key = str(uuid.uuid4())
            args = {'action': action, 'choice': choice}
            result = player.action('scene.action', args, key)
            for attempt in range(8):
                if result.get('status') != 'processing':
                    break
                for task in keeper.request('/package/scene-executor', {})['jobs']:
                    keeper.action('scene.autorun', {'jobId':task['id']}, task['commandId'])
                result = player.action('scene.action', args, key)
            assert result.get('outcome') == 'success', (action, choice, result)
            return result
        def move(index):
            result = player.action('request', {'kind':'travel','destination':index})
            assert result.get('location') == index, result
        def storm(action, choice):
            return act('storm-' + action, choice)
        if route == 'home':
            previous = next(x for x in observer.state()['locations'] if x['index']==1)['description']
            assert '一轮奶酪' in previous
            actor = player.state()['character']['instanceId']
            keeper.action('stock.take',{'index':1,'item':6,'actor':actor,'slot':7})
            assert '只剩一圈压痕' in next(x for x in observer.state()['locations'] if x['index']==1)['description']
            assert '一轮奶酪' in previous
            player, observer = observer, player
            act('tunnel-ground','inspect')
            current = next(x for x in player.state()['locations'] if x['index']==1)
            assert '只剩一圈压痕' in current['description']
            assert all(c['id']!='take' for a in current['actions'] if a['id']=='tunnel-cheese' for c in a['choices'])
            move(2)
            move(1)
            assert '只剩一圈压痕' in next(x for x in player.state()['locations'] if x['index']==1)['description']
            player, observer = observer, player
        act('tunnel-ground','inspect')
        move(2)
        storm('brace','slow')
        move(3)
        def current_choices(action):
            return {c['id'] for a in player.state()['sceneActions'] if a['id']==action for c in a['choices']}
        assert current_choices('storm-commission') == {'start'}
        delayed = player.action('scene.action', {'action':'storm-commission','choice':'start','manual':True})
        storm('commission','start')
        turn = keeper.state()['session']['numbers']['round']
        stale = keeper.action('resolve', {'requestId':delayed['requestId'],'approve':True}, allow_error=True)
        assert '等候搜救' in str(stale), stale
        assert keeper.state()['session']['numbers']['round'] == turn
        assert not current_choices('storm-commission')
        place = next(p for p in player.state()['locations'] if p['index']==3)
        assert '等候搜救和补给' in place['description']
        assert player.action('scene.action', {'action':'storm-commission','choice':'start'}, allow_error=True).get('code')
        if route == 'evacuated':
            premature = keeper.action('storm.finish', {'route':route, 'roster':'仍在搜救'}, allow_error=True)
            assert premature.get('code') == '所选结局尚未满足', premature
            assert keeper.state()['session']['numbers']['phase']==1
        act('courtyard-ladders','inspect')
        move(6)
        act('web-inspect','inspect')
        storm('decoy','lead')
        move(3)
        if route == 'home':
            storm('roads3','survey')
            move(11)
            storm('roads11','survey')
            move(12)
            storm('supplies12','inspect')
            if alternate:
                storm('supplies12','27')
            else:
                storm('supplies12','17')
                storm('supplies12','18')
            move(11)
            if alternate:
                start = runtime.package.state['sceneState']['stormStart']
                turn = keeper.state()['session']['numbers']['round']
                while turn-start+1 < 18:
                    turn = keeper.action('world',{'operation':'round','round':turn})['round']
                storm('pump','dredge')
                wedge = player.action('scene.action', {'action':'storm-pump','choice':'wedge','manual':True})
                storm('pump','wedge')
                before = player.state()
                duplicate = keeper.action('resolve', {'requestId':wedge['requestId'],'approve':True}, allow_error=True)
                assert '木楔已经撑住' in str(duplicate), duplicate
                after = player.state()
                assert before['character']['numbers'] == after['character']['numbers']
                assert before['session']['numbers']['round'] == after['session']['numbers']['round']
                assert 'wedge' not in current_choices('storm-pump') and 'service' in current_choices('storm-pump')
                storm('pump','service')
            else:
                storm('pump','gear')
            move(12)
            storm('roads12','survey')
            move(8)
            act('factory-equipment','inspect')
            storm('mill','run')
            move(3)
            assert current_choices('storm-commission') == {'deliver'}
            storm('commission','deliver')
            assert current_choices('storm-commission') == {'shelter'}
            storm('commission','shelter')
        else:
            storm('roads3','survey')
            move(11)
            storm('roads11','survey')
            move(14)
            if route == 'allied':
                if not alternate:
                    storm('ferry','labour')
                move(11)
                move(3)
                move(7)
                act('hall-observe','inspect')
                if alternate:
                    act('hall-negotiate','food')
                    move(8)
                    act('factory-exits','survey')
                    act('factory-exits','iron')
                    move(9)
                    act('cage-listen','listen')
                    act('cage-listen','flute')
                    act('cage-gate','open')
                    move(10)
                    act('cave-sleeper','observe')
                    act('cave-sleeper','talk')
                    act('cave-cheese','inspect')
                    act('cave-cheese','take')
                    act('cave-cheese','take')
                    move(9)
                    move(8)
                    move(7)
                    storm('pact','food')
                    pocket = player.state()['character']['numbers']
                    assert not any(pocket['item'+str(slot)]==6 for slot in range(1,21))
                else:
                    storm('pact','work')
                move(3)
                move(11)
                move(14)
                if alternate:
                    move(11)
                    storm('supplies11','inspect')
                    storm('supplies11','21')
                    move(3)
                    move(8)
                    storm('roads8','survey')
                    move(13)
                    storm('signal','light')
                    storm('roads13','survey')
                    move(14)
                else:
                    storm('ferry','runner')
                for _ in range(2):
                    if 'wait' in current_choices('storm-ferry'):
                        storm('ferry','wait')
                assert 'wait' not in current_choices('storm-ferry')
                storm('ferry','meet')
            else:
                if alternate:
                    move(11)
                    move(12)
                    storm('supplies12','inspect')
                    storm('supplies12','18')
                    move(11)
                    move(14)
                    storm('escape','boat')
                else:
                    storm('escape','path')
                storm('escape','credit')
                storm('escape','brace')
                storm('escape','leave')
        assert route in keeper.state()['storm']['routes']
        assert 'storm' not in observer.state()
        if route=='evacuated' and not alternate:
            browser_finish(runtime, password)
            result = keeper.state()['storm']['ending']
            assert result['route']==route
            args = key = None
        else:
            args = {'route':route,'roster':'木栗与豆叶去向均已核对。'}
            key = str(uuid.uuid4())
            result = keeper.action('storm.finish',args,key)
            assert result.get('route') == route, result
            assert keeper.action('storm.finish',args,key) == result
        assert keeper.state()['session']['numbers']['phase']==2
    with running('storm-recovery', data=data_dir) as (recovered, _):
        keeper = Account(recovered.origin, 'kp', password, 'kp')
        assert keeper.state()['storm']['ending']['route'] == route
        if key:
            assert keeper.action('storm.finish',args,key) == result
    print('PASS',route,'alternate' if alternate else 'primary','incl. restart',flush=True)


def verify_event_catalog():
    import json
    from harness import PACK
    import scene_knowledge as knowledge
    content = json.loads((PACK/'config/scene-actions.json').read_bytes())
    game = json.loads((PACK/'config/game.json').read_bytes())
    checked = 0
    for a in content['actions']:
        ix = a['location']
        clues = [c for c in content['playerKnowledge'] if c['location']==ix]
        def offered(flags, remaining=1):
            place = {'index':ix,'description':'','exits':[],'clues':clues,'actions':knowledge.menu(content,ix,clues)}
            knowledge.describe_events(place,content,flags,1)
            knowledge.describe_stock(place,{i:remaining for i in range(1,len(game['items'])+1)},remaining,game)
            return {c['id'] for action in place['actions'] if action['id']==a['id'] for c in action['choices']}
        for c in a['choices']:
            step = c.get('storm', {})
            flags = dict.fromkeys(step.get('need',[]),1)
            if (a['id'],c['id'])==('cage-gate','open'): flags['snakeCalmed']=1
            if step.get('evac'): flags.update(foot=1,fed=1)
            assert c['id'] in offered(flags), (a['id'],c['id'],'cannot reach eligible stage')
            done = step.get('set') or ('sent' if step.get('send') else 'stormStart' if step.get('start') else None)
            if done:
                assert c['id'] not in offered({**flags,done:1}), (a['id'],c['id'],'completed')
            if step.get('take'):
                assert c['id'] not in offered(flags,0), (a['id'],c['id'],'empty stock')
            for needed in step.get('need',[]):
                assert c['id'] not in offered({**flags,needed:0}), (a['id'],c['id'],needed)
            for excluded in step.get('absent',[]):
                assert c['id'] not in offered({**flags,excluded:1})
            checked += 1
    print('PASS catalog:',len(content['actions']),'actions,',checked,'choices')


def multiplayer_events():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    with running('event-races', no_browser=True) as (runtime, password):
        kp, one, two = provision(runtime, password)
        keepers = [kp, Account(runtime.origin,'kp',password,'second-executor')]
        players = [one,two]
        actors = [p.state()['character']['instanceId'] for p in players]

        def simultaneous(fn):
            gate = Barrier(2)
            def run(i):
                gate.wait(timeout=10)
                return fn(i)
            with ThreadPoolExecutor(2) as pool:
                return list(pool.map(run,range(2)))

        evidence = []
        def visit(index, clues=()):
            kp.action('location.publish', {'index':index})
            for actor in actors:
                kp.command('entity.update', {'id':actor,'numbers':{'location':index}})
            kp.action('location.reveal', {'index':index,'accounts':['player1','player2'],'knowledge':list(clues)})

        def race(action, choice):
            ids = [str(uuid.uuid4()) for _ in players]
            args = {'action':action,'choice':choice}
            queued = simultaneous(lambda i: players[i].action('scene.action',args,ids[i]))
            jobs = [runtime.package.state['autoSceneQueue'][row['jobId']] for row in queued]
            outcomes = simultaneous(lambda i: keepers[i].action('scene.autorun',{'jobId':jobs[i]['id']},jobs[i]['commandId']))
            for i, player in enumerate(players):
                assert player.action('scene.action',args,ids[i]) == outcomes[i]
            evidence.append({'action':action, 'choice':choice, 'outcomes':[r['outcome'] for r in outcomes],
                             'costs':[r.get('cost',0) for r in outcomes], 'sameReceiptOnRetry':True})
            return outcomes

        def turn():
            return kp.state()['session']['numbers']['round']
        def held(item, uses=False):
            total = 0
            for player in players:
                n = player.state()['character']['numbers']
                for slot in range(1,21):
                    if n['item'+str(slot)] == item:
                        total += n['uses'+str(slot)] if uses else 1
            return total
        def one_wins(action, choice):
            outcomes = race(action,choice)
            assert sorted(x['outcome'] for x in outcomes)==['blocked','success'], outcomes

        visit(4)
        start=turn()
        found=race('house-pots','search')
        assert all(x['outcome']=='success' for x in found)
        assert sum(len(x['rolls']) for x in found)==1 and turn()==start+1
        assert all(any(c['id']=='pots-observed' for loc in p.state()['locations'] for c in loc['clues']) for p in players)
        visit(3,['pool-treasure'])
        # Even a failed dive spends its turn; the other queued dive must not roll again.
        round_before = turn()
        kp.command('entity.update', {'id':runtime.package.state['sceneId'],'numbers':{'poolKnown':1}})
        dives = race('courtyard-pool','money')
        assert sum(len(r['checks'])>0 for r in dives)==1 and sum(r['outcome']=='blocked' for r in dives)==1, dives
        assert turn()==round_before+1
        visit(7,['hall-company'])
        for actor in actors:
            kp.action('grant',{'actor':actor,'item':3,'uses':3,'slot':18})
        start,food,flutes=turn(),held(3,True),held(9)
        one_wins('hall-negotiate','food')
        assert turn()==start+1 and held(3,True)==food-1 and held(9)==flutes+1
        visit(9,['snake-rhythm'])
        for actor in actors:
            kp.action('grant',{'actor':actor,'item':9,'uses':0,'slot':19})
        start=turn()
        one_wins('cage-listen','flute')
        assert turn()==start+1
        # Both players make a new observation of the now calm snake.
        visit(9,['snake-rhythm'])
        one_wins('cage-gate','open')
        assert turn()==start+1
        visit(12,['supplies12'])
        start,before=turn(),held(18)
        wax=race('storm-supplies12','18')
        assert all(x['outcome']=='success' for x in wax) and held(18)==before+2 and turn()==start
        kp.command('entity.update',{'id':runtime.package.state['sceneId'],'numbers':{'stormStart':1,'sent':start,'aid':0}})
        visit(14)
        old = next(c['eventVersion'] for a in two.state()['sceneActions'] if a['id']=='storm-ferry' for c in a['choices'] if c['id']=='wait')
        one_wins('storm-ferry','wait')
        assert turn()==start+1
        late = two.action('scene.action', {'action':'storm-ferry','choice':'wait','eventVersion':old,'manual':True}, allow_error=True)
        assert '刷新选项' in str(late) and turn()==start+1
        one_wins('storm-ferry','wait')
        assert turn()==start+2 and runtime.package.state['sceneState']['aid']==1
        visit(1)
        kp.action('door', {'edge':'1-14','status':'locked'})
        observed = race('storm-roads1','survey')
        assert all('仍关闭' in ''.join(o['narrative']) for o in observed)
        assert kp.state()['doors']['1-14']=='locked' and turn()==start+2
        visit(11)
        for actor in actors:
            kp.action('grant', {'actor':actor,'item':17,'slot':15,'uses':0})
            kp.action('grant', {'actor':actor,'item':18,'slot':16,'uses':1})
        # Two independently approved requests race for a single shared repair.
        before = (held(17), held(18,True), turn())
        queued = simultaneous(lambda i: players[i].action('scene.action',{'action':'storm-pump','choice':'gear','manual':True}))
        approval_ids = [str(uuid.uuid4()) for _ in queued]
        approvals = [{'requestId':q['requestId'],'approve':True} for q in queued]
        results = simultaneous(lambda i: keepers[i].action('resolve',approvals[i],approval_ids[i],allow_error=True))
        assert sum('泵轮已经转动' in str(r.get('code','')) for r in results)==1, results
        assert (held(17), held(18,True), turn()) == (before[0]-1, before[1]-1, before[2]+1)
        winner = next(i for i,r in enumerate(results) if not r.get('code'))
        assert keepers[winner].action('resolve',approvals[winner],approval_ids[winner])==results[winner]
        evidence.append({'action':'storm-pump','choice':'gear','manualApprovals':2,'repairs':1,'gearsUsed':1,'waxUsesSpent':1,'roundsAdvanced':1})
        import json
        (runtime.data/'event-races.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf8')
        print('PASS multiplayer generation, payment, reward, finite stock, doors, shared waits and replay')

if __name__=='__main__':
    if sys.argv[1]=='--races': multiplayer_events()
    elif sys.argv[1]=='--catalog': verify_event_catalog()
    else: play(sys.argv[1], '--alternate' in sys.argv[2:])
