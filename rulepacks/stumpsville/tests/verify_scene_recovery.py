"""Current scene format, interrupted execution and finite inventory over real HTTP."""
import copy
import json
import uuid
from datetime import datetime
from unittest.mock import patch
from harness import PACK, running, provision
from package import Package, Job
from client import Client


def main():
    checks = []
    with running('scene-recovery') as (runtime, password):
        kp, p1, _ = provision(runtime, password)
        host = Client(runtime.backend, 'kp', password)
        session = next(e for e in host.request('/view')['entities'].values() if e['configurationId'] == 'sv.session')
        record = {'steps': {}}
        job = Job(runtime.package, host, record)
        before_session = copy.deepcopy(session)
        job.sync_numbers('unchanged', session, {'autoResolve': 1})
        assert host.request('/view')['entities'][session['instanceId']] == before_session
        job.sync_numbers('changed', session, {'autoResolve': 0})
        changed = host.request('/view')['entities'][session['instanceId']]
        assert changed['numbers']['autoResolve'] == 0
        # Simulate committed host effects with the local step result missing.
        record['steps']['changed'].pop('result')
        job.sync_numbers('changed', changed, {'autoResolve': 0})
        assert 'result' in record['steps']['changed']
        assert host.request('/view')['entities'][session['instanceId']] == changed
        job.sync_numbers('restore', changed, {'autoResolve': 1})
        checks.append('unchanged numeric sync creates no revision; changes commit; lost step result recovers the same receipt without another write')
        actor = p1.state()['character']['instanceId']
        identity_files = sorted(str(p.relative_to(runtime.data)) for p in (runtime.data/'host/identity').rglob('*') if p.is_file())
        before = p1.state()['character']['numbers']
        assert p1.state()['sceneAutomation']['ready']
        assert kp.action('scene.install',allow_error=True)['code']=='未知行动'
        assert p1.state()['character']['numbers']==before
        assert identity_files == sorted(str(p.relative_to(runtime.data)) for p in (runtime.data/'host/identity').rglob('*') if p.is_file())
        checks.append('current rooms include scene rules; removed upgrade operation has no effects')

        def submit(action, choice):
            key = str(uuid.uuid4())
            args = {'action': action, 'choice': choice}
            queued = p1.action('scene.action', args, key)
            assert queued['status'] == 'processing'
            task = kp.request('/package/scene-executor', {})['jobs'][0]
            return key, args, task

        def finish(task):
            return kp.action('scene.autorun', {'jobId': task['id']}, task['commandId'])

        key, args, task = submit('tunnel-ground', 'inspect')
        # Host effects committed, but event publication fails before completion.
        with patch.object(runtime.package, 'record_feedback', side_effect=ConnectionError('scene feedback interrupted')):
            response = kp.http.post(kp.prefix+'/package/action', json={'id':task['commandId'], 'operation':'scene.autorun', 'args':{'jobId':task['id']}})
            assert response.status_code == 503, response.text
        assert runtime.package.state['autoSceneQueue'][task['id']]['status'] == 'finishing'
        # An already committed pre-upgrade request must finish, not rerun or vanish.
        runtime.package.state['autoSceneQueue'][task['id']].pop('menuVersion')
        runtime.package.save()
        assert '恢复' in p1.action('check', {'attribute':'dex','mode':'normal'}, allow_error=True)['code']
        runtime.package = Package(runtime.package.path)
        assert kp.request('/package/scene-executor', {})['jobs'][0] == task
        result = finish(task)
        assert p1.action('scene.action', args, key) == result
        assert not runtime.package.state.get('scenePending')
        events = [e for e in p1.state()['events'] if e['id'] == 'player1:'+key]
        assert len(events) == 1 and events[0]['status'] == 'completed'
        assert not kp.request('/package/scene-executor', {})['jobs']
        assert finish(task) == result
        checks.append('interrupted feedback resumes after reload; the original waiting card becomes one completed result; duplicate executor delivery is idempotent')

        kp.action('actor.update', {'id':actor,'numbers':{'dexMax':20,'dex':20}})
        old_checks = p1.state()['character']['numbers']['checks']
        key, args, task = submit('tunnel-cheese', 'careful')
        # Interrupt package publication immediately after the atomic Lua transaction.
        with patch('scenes.apply_numbers', side_effect=ConnectionError('scene publication interrupted')):
            response = kp.http.post(kp.prefix+'/package/action', json={'id':task['commandId'], 'operation':'scene.autorun', 'args':{'jobId':task['id']}})
            assert response.status_code == 503, response.text
        committed = p1.state()['character']['numbers']
        assert committed['checks'] == old_checks+1
        runtime.package.state['autoSceneQueue'][task['id']].pop('menuVersion')
        runtime.package.state['jobs']['kp:'+task['commandId']]['steps']['scene-act'].pop('result')
        runtime.package.save()
        runtime.package = Package(runtime.package.path)
        result = finish(task)
        assert result['checks'][0]['passed']
        assert p1.state()['character']['numbers'] == committed
        assert runtime.package.state['sceneState']['cheese1'] == 0
        assert p1.action('scene.action', args, key) == result
        checks.append('pre-upgrade committed request with lost local result recovers the original host receipt without reroll, duplicate cheese or lost stock decrement')

        # Fill all normal and overflow cells; preflight must leave finite stock alone.
        full = {'location':10}
        full.update({'item'+str(i):6 for i in range(1,21)})
        full.update({'uses'+str(i):0 for i in range(1,21)})
        kp.command('entity.update', {'id':actor,'numbers':full})
        # Discovery is personal even when another player already knows the stock.
        _, _, discovery_task = submit('cave-cheese','inspect')
        finish(discovery_task)
        key, args, task = submit('cave-cheese','take')
        result = finish(task)
        assert result['outcome'] == 'blocked' and result['checks'] == []
        assert runtime.package.state['sceneState']['cheese10'] == 8
        assert p1.state()['character']['numbers']['checks'] == committed['checks']
        checks.append('full inventory blocks before rolling or reducing shared stock')

        kp.action('automation.configure', {'enabled':False})
        pending = p1.action('scene.action', {'action':'cave-cheese','choice':'inspect'})
        assert pending['status'] == 'pending'
        assert not kp.request('/package/scene-executor', {})['jobs']
        kp.action('automation.configure', {'enabled':True})
        assert not kp.request('/package/scene-executor', {})['jobs']
        assert any(r['id'] == pending['requestId'] and r['status'] == 'pending' for r in kp.state()['requests'])
        checks.append('deliberate global manual mode remains manual when automation is re-enabled')
    report = {'passed':True, 'checkedAt':datetime.now().astimezone().isoformat(), 'checks':checks}
    (PACK/'tests/scene-recovery-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__':
    main()
