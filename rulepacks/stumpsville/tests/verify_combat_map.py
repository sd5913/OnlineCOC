"""Exercise the normal package API and Edge against an isolated room."""
from concurrent.futures import ThreadPoolExecutor
import uuid
from harness import running, provision
from playwright.sync_api import sync_playwright, expect


def main():
    with running('combat-map',no_browser=True) as (runtime,password):
        kp,one,two=provision(runtime,password)
        state=kp.state()
        assert state['combatReady']
        snake=next(n['instanceId'] for n in state['npcs'] if n['name']=='守卫蛇')
        actors=[p.state()['character']['instanceId'] for p in (one,two)]
        def stats(actor,**numbers):
            kp.command('entity.update',{'id':actor,'numbers':numbers})
        def command(player,move,enemy=snake):
            return {'move':move,'enemy':enemy,'turn':player.state()['character']['numbers'].get('combatTurn',0)}
        def drain():
            for task in kp.request('/package/scene-executor',{})['jobs']:
                kp.action('scene.autorun',{'jobId':task['id']},task['commandId'])
        def play(player,move):
            args=command(player,move)
            key=str(uuid.uuid4())
            assert player.action('combat',args,key)['status']=='processing'
            drain()
            result=player.action('combat',args,key)
            assert result['sceneAction']=='combat',result
            assert player.action('combat',args,key)==result
            return result['combat']
        def engage(actor):
            who=one if actor==actors[0] else two
            result=kp.action('combat',dict(command(who,'engage'),actor=actor))
            assert result.get('combat',{}).get('outcome')=='active',result
        for index in (6,9):
            kp.action('location.publish',{'index':index,'clues':[]})
        for actor in actors:stats(actor,location=9)
        assert 'code' in one.action('combat',command(one,'engage'),allow_error=True)
        kp.action('location.reveal',{'index':9,'accounts':['player1','player2']})
        def scene(player, action, choice):
            args={'action':action,'choice':choice}
            key=str(uuid.uuid4())
            queued=player.action('scene.action',args,key)
            assert queued.get('status')=='processing',queued
            drain()
            return player.action('scene.action',args,key)
        assert scene(one,'cage-listen','listen')['outcome']=='success'
        # A positive target below the die minimum forces failure in this fixture.
        stats(actors[0],dex=0.5)
        opening=scene(one,'cage-listen','sneak')
        assert opening.get('hostile')=='snake' and opening['outcome']=='failure',opening
        engage(actors[1])
        assert one.state()['battle']['enemy']==snake==two.state()['battle']['enemy']
        assert 'code' in two.action('request',{'kind':'travel','destination':8},allow_error=True)
        assert 'code' in one.action('scene.action',{'action':'cage-listen','choice':'listen'},allow_error=True)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            page=browser.new_page(viewport={'width':1366,'height':768})
            page.goto(runtime.origin+'/sessions/combat-map-test/')
            page.locator('[name=loginName]').fill('player1')
            page.locator('[name=password]').fill(password)
            page.get_by_role('button',name='进入冒险',exact=True).click()
            link=page.locator('a[href="#/play/scene"]').first
            expect(link).to_be_visible()
            link.evaluate('(link) => link.click()')
            expect(page.locator('.scene-column')).to_be_visible()
            expect(page.locator('.battle-window')).to_contain_text('守卫蛇')
            page.locator('.battle-window [data-action=battle-hide]').click()
            page.locator('.battle-window [data-action=battle-open]').click()
            expect(page.locator('.battle-window')).to_contain_text('逃跑')
            page.locator('.battle-window [data-action=battle-hide]').click()
            svg=page.locator('.node-map svg:visible').first
            def map_check():
                if not svg.count():
                    raise AssertionError((page.url,page.locator('body').inner_text()[:1800],page.locator('.node-map').count()))
                rect=svg.bounding_box()
                orig=svg.get_attribute('viewBox')
                panel=svg.locator('..')
                panel.locator('[data-map-scale]').first.click()
                after=svg.bounding_box()
                assert svg.get_attribute('viewBox')!=orig and all(after[k]==rect[k] for k in ('width','height'))
                panel.locator('[data-map-scale]').last.click()
                assert svg.get_attribute('viewBox')==orig
                svg.hover()
                page.mouse.wheel(0,-120)
                expect(svg).not_to_have_attribute('viewBox',orig)
                before_pan=svg.get_attribute('viewBox')
                svg.focus()
                page.keyboard.press('ArrowRight')
                expect(svg).not_to_have_attribute('viewBox',before_pan)
                panel.locator('[data-map-scale]').last.click()
            map_check()
            page.set_viewport_size({'width':390,'height':844})
            page.locator('[data-action=workspace-column][data-args*=scene]').click()
            map_check()
            browser.close()
        stats(actors[0],armor=8)
        failed_escape=play(one,'flee')
        assert failed_escape['outcome']=='active' and not failed_escape['check']['passed'] and 'counter' in failed_escape
        stats(actors[0],dex=20)
        assert play(one,'flee')['outcome']=='escaped'
        assert not one.state()['battle'] and two.state()['battle']
        stats(snake,hp=0,str=1,armor=0)
        assert play(one,'engage')['outcome']=='active'
        round_before=kp.state()['session']['numbers']['round']
        args=[command(p,'attack') for p in (one,two)]
        keys=[str(uuid.uuid4()) for _ in args]
        with ThreadPoolExecutor(2) as pool:
            queued=list(pool.map(lambda t:t[0].action('combat',t[1],t[2]),zip((one,two),args,keys)))
        assert all(r['status']=='processing' for r in queued)
        drain();drain()
        results=[p.action('combat',a,k) for p,a,k in zip((one,two),args,keys)]
        assert sorted(r.get('combat',{}).get('outcome','blocked') for r in results)==['blocked','victory'],results
        assert not one.state()['battle'] and not two.state()['battle']
        assert kp.state()['session']['numbers']['round']==round_before
        assert 'code' in kp.action('combat',dict(command(one,'engage'),actor=actors[0]),allow_error=True)
        spider=next(n['instanceId'] for n in state['npcs'] if n['name']=='蜘蛛一')
        assert scene(one,'cage-gate','inspect')['outcome']=='success'
        assert scene(one,'cage-gate','open')['outcome']=='success'
        stats(actors[0],location=6,hp=0,dex=0.5,str=1,armor=0)
        stats(spider,armor=100)
        kp.action('location.reveal',{'index':6,'accounts':['player1']})
        assert scene(one,'web-inspect','inspect')['outcome']=='success'
        assert scene(one,'web-call','rescue')['hostile']=='spider'
        assert one.state()['battle']['enemy']==spider
        failed=one.action('combat',dict(command(one,'attack'),enemy=snake),allow_error=True)
        assert 'code' in failed
        args=command(one,'attack',spider);key=str(uuid.uuid4());one.action('combat',args,key);drain()
        assert one.action('combat',args,key)['combat']['outcome']=='incapacitated' and not one.state()['battle']
        print('PASS map extent desktop/mobile, private targets, battle panel, movement lock, flee, shared victory, stale action, incapacitation')


if __name__=='__main__':
    import sys
    if '--legacy-fields' in sys.argv:
        from unittest.mock import patch
        import package
        current_bundle=package.bundle
        def legacy_fields():
            data=current_bundle()
            for config in data['configurations']:
                for field in ('combatKey','combatTurn'):
                    config['defaults'].pop(field,None)
            return data
        with patch.object(package,'bundle',legacy_fields):
            main()
    else:
        main()
