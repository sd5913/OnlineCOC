"""Isolated native defaults/account tab; --live-host adds the real local CLI."""
from datetime import datetime
import argparse
import copy
import json
import os
from pathlib import Path
import secrets
import sys
import time
import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch

PACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK/'tools'))
from panel import PanelWindow, arguments
from accounts import AccountError
from processes import run_owned


def pump(root, condition, timeout=10):
    end = time.monotonic()+timeout
    while time.monotonic() < end:
        root.update()
        if condition():return
        time.sleep(.02)
    raise AssertionError('Timed out waiting for native UI')


def snapshot(root, path):
    from verify_lan import screenshot
    screenshot(root, path)


def synthetic(output, checks):
    completed=run_owned([sys.executable,'-B','-c','import sys,json;print(json.dumps({"value":sys.stdin.read()},ensure_ascii=True))'],
        input='中文 stdin',capture_output=True,text=True,timeout=10,env={**os.environ,'PYTHONUTF8':'1'})
    assert json.loads(completed.stdout)=={'value':'中文 stdin'}
    checks.append('owned child stdin carries UTF-8 privately and exits cleanly')
    assert arguments([]).ai and arguments(['--ai']).ai and not arguments(['--no-ai']).ai
    root=tk.Tk(); window=PanelWindow(root,output/'slots',False)
    try:
        pump(root,lambda:not window.scanning)
        assert window.ai.get() and [window.notebook.tab(x,'text') for x in window.notebook.tabs()]==['房间启动','账号管理']
        window.slot_name.set('默认账号验收');window.create_slot()
        assert window.password.get()==window.confirm.get()=='12345678'
        checks.append('AI defaults on; explicit disable works; two tabs and default bootstrap password are visible')
        snapshot(root,output/'default-panel.png')
        records={x:{'accountId':x,'nickname':x,'role':'kp' if x=='kp' else 'player','disabled':False} for x in ['kp','player1','player2']}
        seen=[]; committed=set(); uncertain={'once':True}
        def request(runtime,body):
            seen.append(copy.deepcopy(body))
            if body['operation']=='list':return {'accounts':list(records.values())}
            if body['accountId']=='kp' and body['operation']=='delete':raise AccountError('LAST_ACTIVE_KP')
            if body['operation']=='create':
                if body['requestId'] not in committed:
                    assert body['accountId'] not in records
                    records[body['accountId']]={'accountId':body['accountId'],'role':body['role'],'disabled':False}
                    committed.add(body['requestId'])
                if uncertain['once']:
                    uncertain['once']=False;raise AccountError('HOST_CONTROL_TIMEOUT',uncertain=True)
            elif body['operation']=='delete':records[body['accountId']]['disabled']=True
            return {**{k:body[k] for k in ['requestId','operation','accountId']},'status':'committed'}
        tab=window.accounts_tab;tab.request=request
        window.service.runtime=SimpleNamespace(host_data=window.data/'host')
        window.url='http://127.0.0.1:1/'
        pump(root,lambda:len(tab.records)==3 and not tab.busy)
        tab.login.set('新增玩家');tab.password.set('test-password');tab.create_button.invoke()
        pump(root,lambda:bool(tab.pending) and not tab.busy)
        first=tab.pending['body']['requestId'];assert '待核对' in tab.status.get()
        assert str(tab.create_button['state'])=='disabled'
        tab.retry_button.invoke();pump(root,lambda:not tab.pending and not tab.busy and len(tab.records)==4)
        assert len(committed)==1 and [x['requestId'] for x in seen if x.get('operation')=='create']==[first,first]
        assert first in tab.status.get()
        checks.append('unknown account creation keeps original request; retry commits once, status retains locator and refreshes actual list')
        import accounts
        original=accounts.messagebox.askyesno;accounts.messagebox.askyesno=lambda *a,**k:True
        try:
            key=next(k for k,v in tab.records.items() if v['accountId']=='kp')
            tab.tree.selection_set(key);tab.delete()
            pump(root,lambda:not tab.busy)
            assert '最后一个' in tab.status.get() and not records['kp']['disabled']
            key=next(k for k,v in tab.records.items() if v['accountId']=='新增玩家')
            tab.tree.selection_set(key);tab.delete()
            pump(root,lambda:not tab.busy and records['新增玩家']['disabled'])
        finally:accounts.messagebox.askyesno=original
        checks.append('selection-based delete reports refusal or committed result without deleting historical row')
        window.notebook.select(tab);root.update();snapshot(root,output/'accounts-panel.png')
        window.url='';window.service.runtime=None
        pump(root,lambda:str(tab.create_button['state'])=='disabled')
        assert not tab.tree.get_children()
        checks.append('room stop clears account table and disables controls; no stale room mutation')
    finally:
        window.service.runtime=None
        window.destroy_window()


def real_host(output, checks, engine_snapshot=None):
    from harness import Account
    from verify_integrations import provider, ai, result
    from verify_panel import close_window
    import launch
    import httpx
    import accounts
    original_runtime=launch.Runtime
    def isolated_runtime(args):
        args.host_control_dir=output/'host-control'
        runtime=original_runtime(args)
        if engine_snapshot:
            runtime.command[2]=str(engine_snapshot/'engineering/backend/scripts/run.py')
        return runtime
    clients=[]
    with provider(output) as (config,calls), patch('launch.Runtime',isolated_runtime):
        root=tk.Tk();window=PanelWindow(root,output/'real-slots',False,ai_config=config,port=launch.free_port())
        try:
            pump(root,lambda:not window.scanning)
            window.slot_name.set('真实账号与默认权限');window.create_slot()
            assert window.password.get()==window.confirm.get()=='12345678'
            window.start_button.invoke();pump(root,lambda:bool(window.url) or window.failed,90)
            assert window.url,window.status.get()
            assert window.service.runtime.bootstrap_ai['serviceStatus']=='ready',window.service.runtime.bootstrap_ai
            origin=window.url.rstrip('/')
            kp,p1,p2=[Account(origin,name,'12345678') for name in ['kp','player1','player2']];clients.extend([kp,p1,p2])
            settings=kp.request('/api/v1/ai/settings')['settings'];access=kp.request('/api/v1/ai/access')
            assert settings['enabled'] and all(settings['externalSources'].values()),settings
            assert all(access[k] for k in ['allowPlayerChat','allowAdminRoomRead','allowDataQueries','allowRuntimeChanges','allowConfigurationChanges','allowKnowledgeRequests','allowPlayerRequests']),access
            assert not access['autoApproveBatches'] and not access['autoApproveConfigurations']
            assert all(access['effectiveAccess'][k] for k in ['roomRead','dataQueries','kpExternal','privateExternal'])
            assert p1.http.get('/api/v1/ai/settings').status_code==403
            checks.append('real new room: default kp/player1/player2 login, AI enabled with all capabilities and egress; manual approvals and PL settings isolation remain')
            tab=window.accounts_tab;pump(root,lambda:len(tab.records)==3 and not tab.busy,40)
            assert {v['roomRole'] for v in tab.records.values()}=={'kp','player'}
            tab.login.set('测试玩家');tab.password.set('test-password');tab.create_button.invoke()
            pump(root,lambda:not tab.busy and not tab.pending and len(tab.records)==4,40)
            extra=Account(origin,'测试玩家','test-password');clients.append(extra)
            assert extra.request('/api/v1/view')['role']=='player'
            p1.action('note',{'text':'ACCOUNT-DEFAULT-PERSISTENCE'})
            checks.append('real native account creation uses local CLI and creates a login-ready player membership')
            tab.login.set('测试玩家');tab.password.set('test-password');tab.create_button.invoke()
            pump(root,lambda:not tab.busy,40)
            assert 'ACCOUNT_EXISTS' in tab.status.get() and len(tab.records)==4
            key=next(k for k,v in tab.records.items() if v['accountId']=='测试玩家');tab.tree.selection_set(key)
            tab.new_password.set('changed-password');tab.reset_password()
            pump(root,lambda:not tab.busy and not tab.pending,40)
            assert extra.http.get('/api/v1/me').status_code==401
            changed=Account(origin,'测试玩家','changed-password');clients.append(changed)
            with patch.object(accounts.messagebox,'askyesno',return_value=True):
                tab.delete();pump(root,lambda:not tab.busy and not tab.pending,40)
            assert changed.http.get('/api/v1/me').status_code==401
            assert p1.state()['note']=='ACCOUNT-DEFAULT-PERSISTENCE'
            assert all(v['accountId']!='测试玩家' for v in tab.records.values()), 'deleted identity should leave the active account list'
            checks.append('duplicate create is rejected; password change and delete revoke actual sessions; player note/history remains')
            key=next(k for k,v in tab.records.items() if v['accountId']=='kp');tab.tree.selection_set(key)
            with patch.object(accounts.messagebox,'askyesno',return_value=True):
                tab.delete();pump(root,lambda:not tab.busy,40)
            assert 'LAST_KP_REQUIRED' in tab.status.get()
            checks.append('real panel displays LAST_KP_REQUIRED and preserves the final active host account')
            modified={k:settings[k] for k in ['enabled','profileId','externalSources','auto']}
            modified['auto']={k:settings['auto'][k] for k in ['enabled','channelIds','prefix']}
            modified['enabled']=False;modified['externalSources']={'public':False,'kp':False,'private':False}
            result(ai(kp,'ai.settings.update',modified))
            result(ai(kp,'ai.access.update',{'revision':access['revision'],'allowPlayerChat':False,'autoApproveBatches':False}))
            tab.new_password.set('kp-changed-password');tab.reset_password()
            pump(root,lambda:not tab.busy and not tab.pending,40)
            assert kp.http.get('/api/v1/me').status_code==401
            window.notebook.select(tab);snapshot(root,output/'accounts-real.png')
            window.stop();pump(root,lambda:not window.service.active and not window.busy,60)
            window.start();pump(root,lambda:bool(window.url) or window.failed,90)
            assert window.url,window.status.get()
            restarted=Account(window.url.rstrip('/'),'kp','kp-changed-password');clients.append(restarted)
            assert window.service.runtime.bootstrap_ai is None
            assert restarted.request('/api/v1/ai/settings')['settings']['enabled'] is False
            assert not restarted.request('/api/v1/ai/access')['allowPlayerChat']
            assert not any(restarted.request('/api/v1/ai/settings')['settings']['externalSources'].values())
            with httpx.Client(trust_env=False,headers={'Origin':window.url.rstrip('/')}) as raw:
                assert raw.post(window.url.rstrip('/')+'/api/v1/login',json={'loginName':'kp','password':'12345678'}).status_code==401
            assert not calls,'startup must not call any model'
            checks.append('same save restart preserves changed password and disabled AI/egress/PL choices; no automatic model calls')
        finally:
            for account in clients:account.http.close()
            close_window(window)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live-host',action='store_true');parser.add_argument('--engine-snapshot',type=Path);args=parser.parse_args()
    output=PACK/'tests/output'/('panel-defaults-'+secrets.token_hex(4));output.mkdir(parents=True)
    checks=[];error=None
    try:
        synthetic(output,checks)
        if args.live_host:
            real_host(output,checks,args.engine_snapshot.resolve() if args.engine_snapshot else None)
    except Exception as exc:
        error=type(exc).__name__+': '+str(exc)
        raise
    finally:
        report={'at':datetime.now().astimezone().isoformat(),'passed':error is None,'checks':checks,'error':error,
            'apiCalls':0,'mode':'native-and-real-host' if args.live_host else 'synthetic-native','engineSnapshot':str(args.engine_snapshot) if args.engine_snapshot else None,'output':str(output),'initialSmokeFailure':'A first ad-hoc stdin fixture omitted PYTHONUTF8 and decoded Chinese using Windows legacy codepage; actual Runtime.env sets UTF-8. Retained here; formal fixture matches runtime environment.'}
        path=PACK/'tests/panel-defaults-results.json'
        if path.exists():
            previous=json.loads(path.read_text(encoding='utf-8'));report['previousRuns']=previous.get('previousRuns',[])+[{k:v for k,v in previous.items() if k!='previousRuns'}]
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:report[k] for k in ['passed','mode','output','error']}|{'passedChecks':len(checks)},ensure_ascii=False))


if __name__=='__main__':main()
