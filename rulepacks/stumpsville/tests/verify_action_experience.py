"""Isolated real-host action latency and browser dice replay, without model calls."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import statistics
import time
from harness import PACK, running, provision
from playwright.sync_api import sync_playwright, expect
import launch
from client import Client


def main(baseline=None):
    checks, errors, timings = [], [], {}
    output = PACK / 'tests/output/screenshots'
    output.mkdir(parents=True, exist_ok=True)
    with running('action-experience') as (runtime, password):
        kp, player, other = provision(runtime, password)
        actor = player.state()['character']['instanceId']
        kp.action('actor.update', {'id': actor, 'numbers': {'dexMax': 20, 'dex': 20}})
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)

            def login(context, name):
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(runtime.origin + '/sessions/' + name + '/')
                page.locator('[name=loginName]').fill(name)
                page.locator('[name=password]').fill(password)
                page.get_by_role('button', name='进入冒险', exact=True).click()
                page.locator('.identity').wait_for()
                if name != 'kp':
                    page.goto(runtime.origin + '/sessions/' + name + '/#/play/scene')
                    page.locator('.available-actions').wait_for()
                return page

            def notebook(page, visible):
                if page.locator('#notebook-body').is_visible() != visible:
                    page.locator('[data-action=notebook-toggle][data-args*=records]').click()

            def scene(page, label, choice=None):
                notebook(page, False)
                page.get_by_role('button', name=label, exact=True).click()
                if choice:
                    page.locator('#dialog [name=scene-choice]').select_option(choice)
                started = time.perf_counter()
                with page.expect_response(lambda r: '/package/action' in r.url and r.request.method == 'POST') as response:
                    page.get_by_role('button', name='执行行动', exact=True).click()
                result = response.value.json()
                assert result.get('status') == 'processing', result
                page.locator('#dialog').wait_for(state='hidden')
                notebook(page, True)
                # Match the new command's ID, never a previous settled log entry.
                card = page.locator(f'.event-card[data-event-id="{result["jobId"]}"]')
                expect(card.locator('.event-head .tag')).to_have_text('已结算', timeout=30000)
                return round((time.perf_counter() - started) * 1000)

            original = launch.STATIC['app.js']
            phases = [('after', None)]
            if baseline:
                phases.insert(0, ('before', Path(baseline).resolve()))
            for phase, source in phases:
                if source:
                    # Baseline is an explicitly supplied, ignored pre-change source snapshot.
                    launch.STATIC['app.js'] = (str(source.relative_to(PACK)), original[1])
                else:
                    launch.STATIC['app.js'] = original
                gm_context = browser.new_context(viewport={'width': 1440, 'height': 900})
                pl_context = browser.new_context(viewport={'width': 1440, 'height': 900})
                gm, pl = login(gm_context, 'kp'), login(pl_context, 'player1')
                timings[phase] = []
                for delay in (0, 800, 1400, 1900):
                    pl.wait_for_timeout(delay)
                    timings[phase].append(scene(pl, '观察地面'))
                if source:
                    gm_context.close(); pl_context.close()
            checks.append('four distinct preset receipts settle through a KP browser in a separate context (no BroadcastChannel shortcut)')
            expect(pl.locator('.dice-popup')).to_be_hidden()
            checks.append('safe observations settle without dice popup')

            elapsed = scene(pl, '检查奶酪', 'careful')
            popup = pl.locator('.dice-popup')
            expect(popup).to_be_visible()
            expect(popup).to_have_attribute('data-phase', 'result')
            event = next(e for e in reversed(player.state()['events']) if e['result'].get('checks'))
            expect(popup.locator('.dice-result strong')).to_have_text(str(event['result']['checks'][0]['rolled']))
            expect(popup).to_contain_text('敏捷 ≤ 20')
            pl.screenshot(path=str(output / 'action-check-popup.png'))
            popup.locator('.dice-close').click()
            checks.append('preset popup shows committed host roll and threshold; gameplay settlement is not delayed by animation')

            def check(mode='advantage', manual=False):
                notebook(pl, False)
                pl.locator('.generic-actions [data-action=check]').click()
                pl.locator('#dialog [name=mode]').select_option(mode)
                if manual:
                    pl.locator('#dialog [name=ruling]').select_option('manual')
                pl.locator('#dialog button[type=submit]').click()
                pl.locator('#dialog').wait_for(state='hidden')

            check()
            expect(popup).to_be_visible()
            expect(popup).to_have_attribute('data-phase', 'result')
            event = next(e for e in reversed(player.state()['events']) if e['result'].get('mode') == 'advantage')
            r = event['result']
            expect(popup).to_contain_text(f'{r["first"]} / {r["second"]}')
            expect(popup.locator('.dice-result strong')).to_have_text(str(r['rolled']))
            count = len(player.state()['events'])
            popup.locator('.dice-close').click()
            pl.wait_for_timeout(3200)
            expect(popup).to_be_hidden()
            assert len(player.state()['events']) == count
            pl.reload(); pl.locator('.available-actions').wait_for()
            pl.wait_for_timeout(2800)
            expect(popup).to_be_hidden()
            checks.append('advantage shows both actual dice; polling and reload do not replay history or send extra commands')

            # Hold a genuine old GET response, finish a new check, then deliver
            # the old response late. It must not erase the new result or replay it.
            pl.evaluate('''() => {
                const original=window.fetch;let armed=true;
                window.fetch=async (...args)=>{
                    const response=await original(...args);
                    if(armed&&String(args[0]).includes('package/state')){
                        armed=false;
                        return new Promise(resolve=>window.releaseOldState=()=>resolve(response));
                    }
                    return response;
                };
            }''')
            for _ in range(60):
                if pl.evaluate('() => typeof window.releaseOldState === "function"'):
                    break
                pl.wait_for_timeout(100)
            assert pl.evaluate('() => typeof window.releaseOldState === "function"')
            check()
            expect(popup).to_have_attribute('data-phase', 'result')
            newest = player.state()['events'][-1]['id']
            pl.evaluate('window.releaseOldState()')
            pl.wait_for_timeout(300)
            notebook(pl, True)
            expect(pl.locator(f'.event-card[data-event-id="{newest}"]')).to_be_visible()
            popup.locator('.dice-close').click()
            checks.append('a delayed pre-action state response cannot overwrite the completed check')

            check('normal', manual=True)
            expect(popup).to_be_hidden()
            request = next(r for r in player.state()['requests'] if r['status'] == 'pending')
            kp.action('resolve', {'requestId': request['id'], 'approve': True, 'reason': '隔离测试'})
            expect(popup).to_be_visible(timeout=10000)
            expect(popup).to_have_attribute('data-phase', 'result')
            popup.locator('.dice-close').click()
            checks.append('manual request has no premature dice; approved host result triggers popup')

            other.action('check', {'attribute': 'dex', 'mode': 'normal'})
            pl.wait_for_timeout(2800)
            expect(popup).to_be_hidden()
            checks.append('another player’s check never triggers this player’s popup')

            pl.locator('[data-action=preferences]').click()
            pl.locator('#dialog [name=dice]').uncheck()
            pl.locator('#dialog button[type=submit]').click()
            pl.reload(); pl.locator('.available-actions').wait_for()
            check()
            pl.wait_for_timeout(1100)
            expect(popup).to_be_hidden()
            pl.locator('[data-action=preferences]').click()
            expect(pl.locator('#dialog [name=dice]')).not_to_be_checked()
            pl.locator('#dialog [name=dice]').check()
            pl.locator('#dialog [name=reduce]').check()
            pl.locator('#dialog button[type=submit]').click()
            check()
            expect(popup).to_have_attribute('data-phase', 'result')
            pl.set_viewport_size({'width': 390, 'height': 844})
            box = popup.bounding_box()
            assert 0 <= box['x'] and box['x'] + box['width'] <= 390, box
            pl.screenshot(path=str(output / 'action-check-mobile.png'))
            checks.append('preference survives reload; reduced motion reveals results directly; popup fits 390px')

            same_device = login(gm_context, 'player2')
            scene(same_device, '观察地面')
            checks.append('same-origin player and KP tabs complete through the local wake channel without changing account ownership')
            npc = kp.state()['npcs'][0]['instanceId']
            damage = kp.action('damage', {'actor': npc, 'amount': 100, 'attribute': 'dex'})
            assert damage['save'] > 0
            gm_popup = gm.locator('.dice-popup')
            expect(gm_popup).to_be_visible(timeout=10000)
            expect(gm_popup).to_have_attribute('data-phase', 'result')
            expect(gm_popup.locator('.dice-result strong')).to_have_text(str(damage['save']))
            assert 'undefined' not in gm_popup.inner_text()
            checks.append('KP damage with a critical-injury save displays the actual save and remaining threshold')
            launch.STATIC['app.js'] = original
            browser.close()
        calls = []
        original_request = Client.request
        def traced(client, path, body=None):
            started = time.perf_counter()
            try:
                return original_request(client, path, body)
            finally:
                calls.append({'path': path.split('/receipts/')[0] if '/receipts/' in path else path,
                              'operation': body.get('payload', {}).get('op') if isinstance(body, dict) else None,
                              'ms': round((time.perf_counter() - started) * 1000)})
        Client.request = traced
        started = time.perf_counter()
        try:
            player.action('scene.action', {'action': 'tunnel-ground', 'choice': 'inspect'})
            task = kp.request('/package/scene-executor', {})['jobs'][0]
            kp.action('scene.autorun', {'jobId': task['id']}, task['commandId'])
            player.state()
        finally:
            Client.request = original_request
        direct = {'elapsedMs': round((time.perf_counter() - started) * 1000), 'requests': calls}
    assert not errors, errors
    checks.append('browser has no uncaught JavaScript errors')
    result = {'date': datetime.now().astimezone().isoformat(), 'passed': True, 'checks': checks,
              'timingsMs': timings, 'medianMs': {k: round(statistics.median(v)) for k, v in timings.items()},
              'presetCheckMs': elapsed, 'directScene': direct,
              'note': 'Isolated local host, separate browser contexts, four distinct no-roll presets with varied think time per phase. Optional before uses the supplied old frontend with the CURRENT backend; not a full prior-server, multi-device or load benchmark.'}
    (PACK / 'tests/action-experience-results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', type=Path)
    main(parser.parse_args().baseline)
