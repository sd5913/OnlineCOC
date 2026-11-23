"""Real isolated host: durable drops and local operation cost (no external API)."""
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from datetime import datetime
import hashlib
import json
import statistics
import time
import uuid
from harness import PACK, provision, running
from client import HostError
from playwright.sync_api import sync_playwright, expect


def distribution(values):
    values = sorted(values)
    return {'samples': len(values), 'p50Ms': round(statistics.median(values), 2),
            'p95Ms': round(values[min(len(values)-1, int(len(values)*.95))], 2),
            'maxMs': round(max(values), 2)}


def verify_projection_cache():
    from package import Package
    from unittest.mock import Mock

    package = Package.__new__(Package)
    package.knowledge_pages = {}
    client = Mock()
    def view(account, revision):
        return {'accountId': account, 'roomId': 'room', 'runId': 'run',
                'authorityEpoch': 'auth', 'authorizationEpoch': 1,
                'knowledge': {'scopeId': 'scope', 'viewRevision': revision, 'hasMore': False,
                              'items': [{'facetId': 'scene', 'ref': {'id': account}}]}}
    first = view('one', 'v1')
    client.request.return_value = {'items': [{'data': 'private one'}]}
    assert package.player_records(client, first) == [{'data': 'private one'}]
    package.player_records(client, first)
    assert client.request.call_count == 1
    client.request.return_value = {'items': [{'data': 'private two'}]}
    assert package.player_records(client, view('two', 'v1')) == [{'data': 'private two'}]
    for field in ('runId', 'authorityEpoch', 'authorizationEpoch', 'roomId'):
        old_count = client.request.call_count
        package.player_records(client, {**first, field: 'changed'})
        assert client.request.call_count == old_count + 1
    revoked = view('one', 'v2')
    revoked['knowledge']['items'] = []
    assert not package.player_records(client, revoked)
    overflow = view('one', 'v3')
    overflow['knowledge']['hasMore'] = True
    client.request.return_value = {'items': [], 'nextCursor': None}
    assert not package.player_records(client, overflow)
    assert 'one' not in package.knowledge_pages
    client.request.assert_called_with('/knowledge/search', {'limit': 50})


def main(comparison=None):
    if comparison == 'after': verify_projection_cache()
    output = PACK/'tests/output'/('drop-performance-'+uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    report = {'checkedAt': datetime.now().astimezone().isoformat(), 'checks': [],
              'measurements': {}, 'externalModelCalls': 0, 'formalSaveChanged': False,
              'evidenceDirectory': output.relative_to(PACK).as_posix()}
    with running('drop-performance', data=output/'room', no_browser=True) as (runtime, password):
        kp, p1, p2 = provision(runtime, password)
        actor = p1.state()['character']['instanceId']
        actor2 = p2.state()['character']['instanceId']
        p1.action('inventory', {'operation': 'light', 'slot': 2, 'value': 0})
        kp.action('world', {'operation': 'round', 'round': 0})
        old = p1.state()['character']['numbers']
        body = {'operation': 'drop', 'slot': 2, 'value': old['item2']}
        drop_id = str(uuid.uuid4())
        outcome = p1.action('inventory', body, drop_id)
        assert outcome['dropped'] == {'item': old['item2'], 'uses': old['uses2'], 'ticks': old['ticks2'], 'location': old['location']}, outcome
        assert p1.action('inventory', body, drop_id) == outcome
        state = p1.state()
        assert all(state['character']['numbers'][k] == 0 for k in ('item2', 'uses2', 'ticks2', 'litSlot'))
        assert len(state['groundItems']) == 1 and len(p2.state()['groundItems']) == 1
        report['checks'].append('drop clears inventory and lit slot; preserves uses/ticks/location; replay creates one drop')
        ground = state['groundItems'][0]
        rejected = p1.action('inventory', body, allow_error=True)
        assert rejected.get('status') == 'rejected'
        assert len(p1.state()['groundItems']) == 1
        # Same-scene guard and PL cannot invoke the KP pickup operation.
        assert p1.action('ground.take', {'id': ground['id'], 'actor': actor, 'slot': 2}, allow_error=True).get('code')
        kp.command('entity.update', {'id': actor2, 'numbers': {'location': 2}})
        assert p2.state()['groundItems'] == []
        bad = kp.action('ground.take', {'id': ground['id'], 'actor': actor2, 'slot': 7}, allow_error=True)
        assert bad.get('status') == 'rejected'
        kp.action('ground.take', {'id': ground['id'], 'actor': actor, 'slot': 2})
        restored = p1.state()['character']['numbers']
        assert all(restored[k] == old[k] for k in ('item2', 'uses2', 'ticks2'))
        assert not p1.state()['groundItems'] and restored['litSlot'] == 0
        report['checks'].append('scene visibility, role/scene guards and pickup preserve item state without relighting')
        # Lose the reply AFTER the host committed. A new Package object models a
        # process restart; the saved command envelope recovers the host receipt.
        from client import Client
        from package import Package
        send = Client.send
        def lose_reply(client, envelope):
            result = send(client, envelope)
            if envelope['payload']['args'].get('input', {}).get('operation') == 'drop':
                raise HostError({'httpStatus': 503, 'status': 'unknown', 'code': 'TEST_LOST_REPLY'})
            return result
        recovery_id = str(uuid.uuid4())
        Client.send = lose_reply
        try:
            failed = p1.action('inventory', body, recovery_id, True)
            assert failed.get('code') == 'TEST_LOST_REPLY', failed
        finally:
            Client.send = send
        runtime.package = Package(runtime.package.path)
        recovered = p1.action('inventory', body, recovery_id)
        assert recovered['dropped']['item'] == old['item2']
        assert len(p1.state()['groundItems']) == 1
        assert p1.action('inventory', body, recovery_id) == recovered
        report['checks'].append('committed host action with lost reply survives package reload and recovers exactly one ground record')
        # Same drop cannot be taken twice; an invalid slot does not consume it.
        ground = kp.state()['groundItems'][0]
        bad = kp.action('ground.take', {'id': ground['id'], 'actor': actor, 'slot': 1}, allow_error=True)
        assert bad.get('status') == 'rejected', bad
        assert not kp.state()['groundItems'][0].get('claim')
        take_id = str(uuid.uuid4())
        args = {'id': ground['id'], 'actor': actor, 'slot': 2}
        taken = kp.action('ground.take', args, take_id)
        assert kp.action('ground.take', args, take_id) == taken
        assert kp.action('ground.take', args, allow_error=True).get('status') == 'rejected'
        report['checks'].append('failed pickup frees claim; duplicate pickup/replay cannot duplicate items')
        # Condition slots cannot be dropped. Stale UI cannot drop a replacement.
        game = kp.state()['items']
        condition = next(int(i) for i, item in game.items() if item['kind'] == 'condition')
        kp.action('grant', {'actor': actor, 'item': condition, 'slot': 20, 'uses': 0})
        assert p1.action('inventory', {'operation': 'drop', 'slot': 20, 'value': condition}, allow_error=True).get('status') == 'rejected'
        assert p1.action('inventory', {'operation': 'drop', 'slot': 2, 'value': 999}, allow_error=True).get('status') == 'rejected'
        report['checks'].append('conditions require rule-based recovery; stale item identity is rejected')
        # Manual ruling mode uses the same drop receipt and queue semantics.
        request = p1.action('request', {'kind': 'inventory', 'input': body, 'manual': True, 'text': '丢弃火把'})
        assert p1.state()['character']['numbers']['item2'] == old['item2']
        kp.action('resolve', {'requestId': request['requestId'], 'approve': True})
        assert len(p1.state()['groundItems']) == 1
        report['checks'].append('manual drop request waits for KP approval then creates one ground item')
        for notice in p1.request('/api/v1/notifications?after=0&limit=50')['items']:
            p1.action('notification.ack', {'notificationId': notice['notificationId']})
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width': 1280, 'height': 900})
            errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(runtime.origin+'/sessions/drop-browser/')
            page.locator('[name=loginName]').fill('player1'); page.locator('[name=password]').fill(password)
            page.get_by_role('button', name='进入冒险', exact=True).click()
            page.locator('.identity').wait_for()
            page.goto(runtime.origin+'/sessions/drop-browser/#/play/scene')
            expect(page.locator('.ground-items')).to_be_visible()
            page.locator('[data-action=item]').first.click()
            page.get_by_role('button', name='丢弃', exact=True).click()
            page.get_by_role('button', name='确认丢弃', exact=True).click()
            expect(page.locator('[data-action=pickup-drop]')).to_have_count(2)
            expect(page.locator('#toast')).to_be_hidden(timeout=15000)
            page.wait_for_timeout(4000)
            expect(page.locator('.effects-popup')).to_be_hidden(timeout=15000)
            page.screenshot(path=str(output/'drop-desktop.png'), full_page=True)
            page.set_viewport_size({'width': 390, 'height': 844})
            page.get_by_role('button', name='地图与行动', exact=True).click()
            expect(page.locator('.ground-items')).to_be_visible()
            page.locator('.ground-items').scroll_into_view_if_needed()
            page.screenshot(path=str(output/'drop-mobile.png'), full_page=True)
            assert not errors, errors
            browser.close()
        report['checks'].append('desktop and 390px player UI: item details → drop confirmation → scene ground list')
        # Count package persistence and internal HTTP calls per measured group.
        saves, calls = [], []
        original_save = runtime.package.save
        original_request = Client.request
        def traced_save():
            start = time.perf_counter()
            try: return original_save()
            finally: saves.append((time.perf_counter()-start)*1000)
        def traced_request(client, path, data=None):
            start = time.perf_counter()
            try: return original_request(client, path, data)
            finally: calls.append((path.split('?')[0], (time.perf_counter()-start)*1000))
        runtime.package.save = traced_save; Client.request = traced_request
        def measured(name, fn, count=12, workers=1):
            if comparison: count = 30
            saves.clear(); calls.clear()
            def one(i):
                start = time.perf_counter(); fn(i); return (time.perf_counter()-start)*1000
            start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=workers) as pool: values = list(pool.map(one, range(count)))
            report['measurements'][name] = {**distribution(values), 'workers': workers,
                'wallSeconds': round(time.perf_counter()-start, 3), 'packageSaves': len(saves),
                'saveMsTotal': round(sum(saves), 2), 'internalHttp': dict(Counter(p for p, _ in calls))}
            print(name, json.dumps(report['measurements'][name]), flush=True)
        try:
            measured('hostViewPL', lambda _: p1.request('/api/v1/view'))
            measured('packageStatePL', lambda _: p1.state())
            measured('packageStateKP', lambda _: kp.state())
            measured('fourReadersState', lambda i: (p1 if i%2 else kp).state(), workers=4)
            measured('note', lambda i: p1.action('note', {'text': '性能记录 '+str(i)}))
            channel = kp.command('chat.direct.open', {'accountId': 'player1'})['result']['channelId']
            measured('directChat', lambda i: kp.command('chat.message.send', {'channelId': channel, 'text': '性能聊天 '+str(i)}))
            measured('check', lambda _: p1.action('check', {'attribute': 'dex', 'mode': 'normal'}))
            def ruling(i):
                req = p1.action('request', {'kind': 'check', 'input': {'attribute': 'dex', 'mode': 'normal'}, 'manual': True, 'text': '性能裁决'})
                kp.action('resolve', {'requestId': req['requestId'], 'approve': True})
            measured('requestAndRuling', ruling, count=6)
            measured('worldRound', lambda i: kp.action('world', {'operation': 'round', 'round': i}), count=6)
            measured('stateAfterHistory', lambda _: p1.state())
            metrics = kp.request('/api/v1/admin')['metrics']
            report['hostMetrics'] = {k: distribution(v) for k, v in metrics.items() if k in ('commits','workers') and v}
            report['hostMetrics']['commandQueue'] = distribution([x['queueMs'] for x in metrics['commands']])
            report['hostMetrics']['commandTotal'] = distribution([x['totalMs'] for x in metrics['commands']])
            report['packageBytes'] = runtime.package.path.stat().st_size
            report['packageJobs'] = len(runtime.package.state['jobs'])
        finally:
            Client.request = original_request; runtime.package.save = original_save
    report['passed'] = True
    paths = ['rules/inventory-core.lua', 'rules/ground-take.lua', 'tools/package.py', 'tools/action_errors.py', 'tools/knowledge_provider.py', 'ui/app.js']
    report['sourceHashes'] = {p: hashlib.sha256((PACK/p).read_bytes()).hexdigest() for p in paths}
    report['comparison'] = comparison
    paths = [output/'report.json']
    if comparison is None: paths.append(PACK/'tests/drop-performance-results.json')
    for path in paths:
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'passed': True, 'checks': len(report['checks']), 'output': str(output)}))


def verify_scale():
    import tracemalloc
    from unittest.mock import Mock, patch
    from package import Job, Package
    from launch import projection_delta
    from chat import ScopedChat
    output = PACK/'tests/output'/('package-scale-' + uuid.uuid4().hex[:8])
    output.mkdir()
    report = {'fixture': 'synthetic completed jobs, 30 synchronous saves per size', 'measurements': {}}
    for size in (100, 1000, 10000):
        folder = output/str(size)
        package = Package(folder/'package.json')
        rows = package.state['receipts']['pl'] = []
        for i in range(size):
            key = str(i)
            value = {'value': i, 'text': '样本' * 40}
            package.state['jobs']['pl:'+key] = {'done': True, 'result': value, 'fingerprint': key,
                                                'steps': {'test': {'result': value}}}
            rows.append({'id': key, 'result': value})
        package.state['events']['pl'] = [{'receiptId': '0'}]
        pending = 'pl:'+str(size-1)
        package.state['autoSceneQueue'][pending] = {'status': 'queued'}
        # Pending origins cannot be sealed, even if the submission has a receipt.
        package.save()
        assert pending not in package.archived_jobs
        package.state['autoSceneQueue'][pending]['status'] = 'completed'
        values, flat = [], []
        for _ in range(30):
            start = time.perf_counter()
            package.save()
            values.append((time.perf_counter()-start)*1000)
            start = time.perf_counter()
            Package.atomic_bytes(folder/'flat.json', json.dumps(package.state, ensure_ascii=False).encode())
            flat.append((time.perf_counter()-start)*1000)
        tracemalloc.start()
        restored = Package(package.path)
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert restored.state == package.state
        if size >= 1000:
            disk = json.loads(package.path.read_bytes())
            assert disk['eventReceipts']['pl'] == [rows[0]] and len(disk['receipts']['pl']) < 384
        report['measurements'][str(size)] = {'save': distribution(values), 'flatSave': distribution(flat),
                'liveBytes': package.path.stat().st_size, 'flatBytes': (folder/'flat.json').stat().st_size,
                'jobSegments': len(package.job_segments), 'reloadPeakPythonBytes': peak_bytes}
    # A failed envelope checkpoint must never be sent on a live retry without
    # successfully establishing the checkpoint first.
    storage, client = Mock(), Mock()
    client.envelope.return_value = {'payload': {'commandId': 'id'}}
    client.send.return_value = {'status': 'committed', 'result': 1}
    journal = {'steps': {}}
    job = Job(storage, client, journal)
    storage.save.side_effect = OSError('checkpoint failed')
    for _ in range(2):
        try: job.command('step', 'test', {})
        except OSError: pass
        else: raise AssertionError('missing failed checkpoint')
    assert not journal['steps'] and not client.send.called
    storage.save.side_effect = None
    assert job.command('step', 'test', {}) == 1 and client.send.call_count == 1
    # Simulate interruption between publishing the immutable segment and the root index.
    package = Package(output/'fault'/'package.json')
    package.save()
    for i in range(512):
        key = str(i)
        package.state['jobs']['pl:'+key] = {'done': True, 'result': i}
        package.state['receipts'].setdefault('pl', []).append({'id': key, 'result': i})
    write = package.atomic_bytes
    def fail_root(path, raw):
        if path == package.path: raise OSError('injected before root publication')
        write(path,raw)
    with patch.object(package,'atomic_bytes',fail_root):
        try: package.save()
        except OSError: pass
        else: raise AssertionError('missing injected fault')
    assert not Package(package.path).state['jobs'] and not package.job_segments
    package.save()
    assert package.archived_receipts.get('pl',0) > 0 and Package(package.path).state == package.state
    archive = package.path.with_suffix('.jobs')/(package.job_segments[0]+'.json')
    archive.write_bytes(b'{}')
    try: Package(package.path)
    except ValueError: pass
    else: raise AssertionError('corrupt archive accepted')
    base = {'accountId':'kp','rooms':['private'],'events':[{'id':'event'}],'items':{},'channels':{}}
    initial = projection_delta(base,'initial')
    assert not projection_delta(base,','.join(initial['versions']))['domains']
    changed = projection_delta({'accountId':'pl','items':{},'channels':{}},','.join(initial['versions']))
    assert changed['domains'] == {'0':{'accountId':'pl'},'2':{}}
    package = Package(output/'chat.json')
    chat = ScopedChat(package)
    rows = [{'messageId':str(i),'senderAccountId':'pl' if i%2 else 'kp','revision':1,
             'deleted':False,'sequence':i,'text':'text'} for i in range(1,10001)]
    chat.data['messages']['sv-party']=rows
    view={'role':'kp','accountId':'kp','entities':{},'status':'active'}
    assert chat.channels(view)['sv-party']['unreadCount']==5000
    chat.action(view,'chat.message.retract',{'channelId':'sv-party','messageId':'1','revision':1},'none')
    chat.action(view,'chat.read',{'channelId':'sv-party','sequence':5000},'none')
    assert chat.channels(view)['sv-party']['unreadCount']==2500
    assert chat.scoped_history(view,{'channelId':'sv-party','before':9000,'limit':2})['nextBefore']==8998
    import os
    from knowledge_provider import Provider
    source = output/'knowledge.json'
    original = {'format': 2, 'sceneId': 'scene', 'doors': {'1-2': 'open'}, 'notes': {}}
    source.write_text(json.dumps(original), 'utf8')
    provider = Provider(source)
    version = provider.projection_revision()
    source.write_text(json.dumps({**original, 'notes': {'pl': 'unrelated'}}), 'utf8')
    assert provider.projection_revision() == version
    stamp = source.stat()
    raw = source.read_bytes().replace(b'open', b'shut')
    source.write_bytes(raw)
    os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert provider.projection_revision() != version
    source.write_bytes(b'!' * len(raw))
    os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    try: provider.projection_revision()
    except ValueError: pass
    else: raise AssertionError('corrupt knowledge file retained its token')
    source.unlink()
    try: provider.projection_revision()
    except FileNotFoundError: pass
    else: raise AssertionError('missing knowledge file retained its token')
    report['checks']=['archive reload equality at three sizes','pending scene kept live','orphan segment retry', 'failed command checkpoint retry',
                      'receipt order after recovery','corrupt segment rejected','delta removal on identity change',
                      '10000-message unread/retract and history cursor',
                      'knowledge token: unrelated write, same-stat change, corruption, deletion']
    report['passed']=True
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(output, report['measurements'])


def verify_archive_backup():
    from pathlib import Path
    import subprocess
    from harness import Account

    with running('perf-paired') as (runtime, password):
        keeper, player, _ = provision(runtime, password)
        places = player.state()['locations']
        assert sum(bool(place['known']) for place in places) == 1
        key = '0123-original-note'
        args = {'text': 'archive recovery'}
        first = player.action('note', args, key)
        with runtime.package.lock:
            for i in range(1100):
                action_id = 'synthetic-' + str(i)
                runtime.package.state['jobs']['kp:' + action_id] = {'done': True, 'result': i}
                runtime.package.state['receipts']['kp'].append({
                    'id': action_id, 'result': i, 'operation': 'note', 'commandIds': [], 'time': i})
            runtime.package.save()
        backup = keeper.action('backup')
        snapshot = json.loads(Path(backup['packageFile']).read_text('utf8'))['package']
        assert snapshot['format'] == 2 and 'jobSegments' not in snapshot and 'player1:' + key in snapshot['jobs']
        target = runtime.data.with_name(runtime.data.name + '-restored')
        target.mkdir()
        runtime.process.terminate()
        runtime.process.wait(timeout=15)
        subprocess.run(runtime.command[:-1] + [str(target/'host'), 'restore', '--bundle',
                       str(runtime.host_data/'backups'/backup['host']['backupId']), '--identity-dir',
                       str(runtime.host_data/'identity')], env=runtime.env, check=True, timeout=60)
        (target/'package.json').write_text(json.dumps(snapshot, ensure_ascii=False), 'utf8')
        with running('paired', target) as (restored, _):
            pl = Account(restored.origin, 'player1', password, 'player1')
            assert pl.state()['note'] == args['text']
            assert pl.action('note', args, key) == first
            assert sum(r['id'] == key for r in restored.package.state['receipts']['player1']) == 1
        print('backup and old receipt recovery verified', runtime.data.name, len(snapshot['jobs']))


def verify_polling():
    with running('perf-tabs') as (runtime, password):
        keeper, player, _ = provision(runtime, password)
        route = '/sessions/player1/package/state'
        initial = player.http.get(route, headers={'X-Projection-Versions': 'initial'})
        header = {'X-Projection-Versions': ','.join(initial.json()['versions'])}
        unchanged = player.http.get(route, headers=header)
        unchanged.raise_for_status()
        assert not unchanged.json()['domains']
        player.action('note', {'text': 'changed in own session'})
        updated = player.http.get(route, headers=header).json()
        assert updated['domains']['0']['note'] == 'changed in own session'
        assert '1' not in updated['domains']
        asset = player.http.get('/app.js')
        cached = player.http.get('/app.js', headers={'If-None-Match': asset.headers['etag']})
        assert cached.status_code == 304 and not cached.content
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            context = browser.new_context()
            polls = [[], []]
            group = runtime.origin + '/sessions/shared-tabs/'
            tabs = []
            for number in range(2):
                page = context.new_page()
                page.on('request', lambda req, n=number: polls[n].append(time.monotonic())
                        if '/package/chat/state' in req.url and 'x-chat-version' in req.headers else None)
                page.goto(group)
                if number == 0:
                    page.locator('[name=loginName]').fill('player1')
                    page.locator('[name=password]').fill(password)
                    page.get_by_role('button', name='进入冒险', exact=True).click()
                page.locator('.identity').first.wait_for()
                page.goto(group+'#/play/scene')
                page.locator('.chat-history').first.wait_for()
                tabs.append(page)
            tabs[1].wait_for_timeout(7500)
            # Only visible leaders request the long-wait mode. Close whoever
            # most recently performed that duty and verify the survivor takes over.
            leader = max(range(2), key=lambda n: polls[n][-1] if polls[n] else 0)
            assert polls[leader]
            tabs[leader].close()
            survivor = tabs[1-leader]
            survivor.bring_to_front()
            start = time.monotonic()
            while time.monotonic()-start < 8 and not any(t>start for t in polls[1-leader]):
                survivor.wait_for_timeout(100)
            takeover = next(t-start for t in polls[1-leader] if t>start)
            keeper.action('chat', {'operation': 'chat.message.send',
                          'input': {'channelId': 'general', 'text': 'leader closed'}})
            expect(survivor.locator('.chat-history').first).to_contain_text('leader closed')
            browser.close()
        print(json.dumps({'fullBytes': len(initial.content), 'idleBytes': len(unchanged.content),
                          'takeoverSeconds': round(takeover, 3), 'output': runtime.data.name}))


def verify_pickups():
    from scenes import pickup_options
    from scene_knowledge import menu
    game = json.loads((PACK/'config/game.json').read_bytes())
    content = json.loads((PACK/'config/scene-actions.json').read_bytes())
    flags = {'pact': 1, 'ernieSpoken': 1, 'trapState': 1, 'ratsDeal': 1, 'potsKnown': 1, 'factoryKnown': 1}
    model = {'locations': {str(p['index']):p for p in game['locations']}, 'sceneState':flags}
    public_stock = set()
    for index in range(1, len(game['locations'])+1):
        clues = [c for c in content['playerKnowledge'] if c['location']==index]
        place = {'known':True, 'index':index, 'actions':menu(content,index,clues)}
        options = pickup_options(model,place,content['actions'],game['items'])
        public_stock.update((index, int(x['choice'])) for x in options if x['choice'].isdigit())
        for option in options:
            assert (option['action'], option['choice']) == ('house-pots','take') or (
                option['action'].startswith('storm-supplies') and option['choice'] != '24'), option
    assert public_stock == {(r['location'], r['item']) for r in game['stormStocks'] if r['item'] != 24}
    with running('personal-pickups', no_browser=True) as (runtime, password):
        kp, first, second = provision(runtime, password)
        def settle():
            job, = kp.request('/package/scene-executor', {})['jobs']
            return kp.action('scene.autorun', {'jobId': job['id']}, job['commandId'])

        assert all(x['action'] != 'tunnel-cheese' for x in first.state()['pickupOptions'])
        assert first.action('pickup', {'action':'tunnel-cheese','choice':'take'}, allow_error=True).get('code')
        item = first.state()['character']['numbers']['item2']
        first.action('inventory', {'operation': 'drop', 'slot': 2, 'value': item})
        drop, = first.state()['groundItems']
        kp.action('automation.configure', {'enabled': False})
        key = str(uuid.uuid4())
        take = {'id': drop['id'], 'slot': 2}
        assert first.action('pickup', take, key)['status'] == 'processing'
        second.action('pickup', {'id': drop['id'], 'slot': 7})
        assert settle()['outcome'] == 'success'
        assert settle()['outcome'] == 'blocked'
        assert first.action('pickup', take, key)['outcome'] == 'success'
        assert first.state()['character']['numbers']['item2'] == item
        assert not second.state()['groundItems']
        kp.action('automation.configure', {'enabled': True})

        def scene(action, choice):
            first.action('scene.action', {'action': action, 'choice': choice})
            assert settle()['outcome'] == 'success'
        def move(index):
            assert first.action('request', {'kind': 'travel', 'destination': index})['location'] == index

        scene('tunnel-ground', 'inspect')
        move(2)
        scene('storm-brace', 'slow')
        move(3)
        scene('storm-roads3', 'survey')
        move(11)
        scene('storm-roads11', 'survey')
        move(12)
        args = {'action': 'storm-supplies12', 'choice': '17'}
        assert not first.state()['pickupOptions']
        assert first.action('pickup', args, allow_error=True).get('code')
        scene('storm-supplies12', 'inspect')
        available = first.state()['pickupOptions']
        assert {x['choice'] for x in available} == {'17', '18', '19', '20', '27'}
        assert second.action('pickup', args, allow_error=True).get('code')
        kp.action('automation.configure', {'enabled': False})
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width':390, 'height':844})
            page.goto(runtime.origin + '/sessions/pickup-browser/')
            page.locator('[name=loginName]').fill('player1')
            page.locator('[name=password]').fill(password)
            page.get_by_role('button', name='进入冒险', exact=True).click()
            page.locator('.identity').wait_for(state='attached')
            page.goto(runtime.origin + '/sessions/pickup-browser/#/play/scene')
            panel = page.locator('.ground-items')
            expect(panel.get_by_role('heading', name='可拿取物品')).to_be_visible()
            name = next(x['name'] for x in available if x['choice'] == '17')
            row = panel.locator('.row').filter(has_text=name)
            with page.expect_response(lambda r: '/package/action' in r.url and r.request.method == 'POST'
                                      and r.request.post_data_json.get('operation') == 'pickup') as pending:
                row.get_by_role('button', name='拿取', exact=True).click()
            assert pending.value.json().get('status') == 'processing', pending.value.json()
            assert settle()['outcome'] == 'success'
            page.reload()
            expect(panel.locator('.row').filter(has_text=name)).to_have_count(0)
            browser.close()
        assert args['choice'] not in {x['choice'] for x in first.state()['pickupOptions']}
        assert not kp.request('/package/scene-executor', {})['jobs']
        print('PASS: discovery, remaining stock, personal pickup, competing players, manual mode and replay')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', choices=['before', 'after'])
    parser.add_argument('--scale', action='store_true')
    parser.add_argument('--archive-backup', action='store_true')
    parser.add_argument('--polling', action='store_true')
    parser.add_argument('--pickups', action='store_true')
    args=parser.parse_args()
    if args.pickups: verify_pickups()
    elif args.scale: verify_scale()
    elif args.archive_backup: verify_archive_backup()
    elif args.polling: verify_polling()
    else: main(args.comparison)
