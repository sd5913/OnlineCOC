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
        storm('commission','start')
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
                storm('pump','wedge')
                storm('pump','service')
            else:
                storm('pump','gear')
            move(12)
            storm('roads12','survey')
            move(8)
            act('factory-equipment','inspect')
            storm('mill','run')
            move(3)
            storm('commission','deliver')
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
                storm('ferry','wait')
                storm('ferry','wait')
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


if __name__=='__main__':
    play(sys.argv[1], '--alternate' in sys.argv[2:])
