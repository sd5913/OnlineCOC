"""Default online bootstrap plus real browser/HTTP checks in the isolated copy."""
import json, os, platform, socket, subprocess, sys, time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent
ROOT = Path(json.loads((OUT/'source.json').read_text(encoding='utf-8'))['root'])
# Previously prepared audit copies used the original project-root layout.
LAUNCHERS = ROOT / 'QuickStart' if (ROOT / 'QuickStart').is_dir() else ROOT
env = os.environ.copy()
for key in ('VIRTUAL_ENV','PYTHONPATH','PYTHONHOME','ONLINECOC_BOOTSTRAP_PASSWORD'): env.pop(key,None)
env['PATH'] = os.path.join(env['WINDIR'],'System32') + ';' + env['WINDIR']
config = json.loads((ROOT/'launcher-config.json').read_text(encoding='utf-8'))
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
config['application'].update(port=port,openBrowser=False)
path=ROOT/'audit-config.json'; path.write_text(json.dumps(config),encoding='utf-8')
result=(json.loads((OUT/'online-browser.json').read_text(encoding='utf-8')) if '--browser-only' in sys.argv else
        {'platform':platform.platform(),'pythonRemovedFromChildPath':True,'defaultCacheAbsentBefore':not (ROOT/config['python']['cacheFile']).exists()})
result['port']=port
def save(): (OUT/'online-browser.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
def run(exe,*args,timeout=360):
    return subprocess.run([str(LAUNCHERS/exe),'--headless','--config',str(path),*args],capture_output=True,encoding='utf-8',errors='replace',env=env,timeout=timeout)
if '--browser-only' not in sys.argv:
    save(); started=time.monotonic()
    installed=run('安装依赖.exe')
    (OUT/'online-install.log').write_text(installed.stdout+installed.stderr,encoding='utf-8')
    result['onlineInstall']={'exitCode':installed.returncode,'seconds':round(time.monotonic()-started,2),'dependencies29':'DEPENDENCIES_OK 29' in installed.stdout};save()
    assert installed.returncode==0, installed.stdout
    probe=subprocess.run([str(ROOT/config['python']['directory']/'python.exe'),'-I','-c',"import tkinter; t=tkinter.Tcl(); print(t.call('info','patchlevel')); import _tkinter; print(_tkinter.TK_VERSION)"],env=env,capture_output=True,text=True)
    result['tkImportAndTcl']={'exitCode':probe.returncode,'output':probe.stdout.strip()};assert probe.returncode==0
    no_password=run('启动OnlineCOC.exe','--no-browser','--run-seconds','1')
    result['firstStartRequiresPassword']=no_password.returncode==1 and '至少 8 位' in no_password.stdout
    assert result['firstStartRequiresPassword'];save()
env['ONLINECOC_BOOTSTRAP_PASSWORD']='isolated-desktop-audit-password'
base=f'http://127.0.0.1:{port}'
def launch(seconds):
    return subprocess.Popen([str(LAUNCHERS/'启动OnlineCOC.exe'),'--headless','--config',str(path),'--no-browser','--run-seconds',str(seconds)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,encoding='utf-8',errors='replace')
def wait_ready(process):
    with httpx.Client(trust_env=False,timeout=2) as client:
        for _ in range(200):
            assert process.poll() is None,process.communicate()
            try:
                response=client.get(base+'/api/v1/capabilities')
                if response.status_code==200:return response.json()
            except httpx.HTTPError:pass
            time.sleep(.1)
    raise AssertionError('Service did not become ready')
def finish(process,name):
    stdout,stderr=process.communicate(timeout=50)
    (OUT/(name+'.log')).write_text(stdout+stderr,encoding='utf-8')
    assert process.returncode==0 and '服务已停止' in stdout
    with socket.socket() as sock: assert sock.connect_ex(('127.0.0.1',port))!=0
process=launch(30)
try:
    result['capabilities']=wait_ready(process)
    assert result['capabilities']['ai']['available'] is False
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        result['browserVersion']=browser.version
        errors=[]; pages=[]
        for account in ('kp','player1','player2'):
            context=browser.new_context(viewport={'width':1360,'height':900})
            page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
            assert page.goto(base).status==200
            page.fill('#username',account);page.fill('#password',env['ONLINECOC_BOOTSTRAP_PASSWORD']);page.click('#login button')
            page.locator('#status').filter(has_text='已连接').wait_for()
            assert page.locator('#management').is_visible()==(account=='kp')
            pages.append(page)
        player=pages[1];player.select_option('#actions','demo.damage')
        player.select_option('[name=actor]','actor-player1');player.fill('[name=amount]','7');player.click('#invoke')
        player.locator('.entity').filter(has_text='actor-player1').filter(has_text='hp: 4').wait_for()
        pages[0].locator('.entity').filter(has_text='actor-player1').filter(has_text='hp: 4').wait_for()
        result['browser']={'accounts':['kp','player1','player2'],'separateContexts':True,'websocketConnected':True,'kpManagementOnly':True,'damageHp':4,'pageErrors':errors}
        pages[0].screenshot(path=str(OUT/'console-kp.png'),full_page=True)
        pages[1].screenshot(path=str(OUT/'console-player.png'),full_page=True)
        assert not errors;browser.close()
    finish(process,'browser-launch')
finally:
    if process.poll() is None:process.terminate();process.wait(timeout=10)
save();process=launch(6)
try:
    wait_ready(process)
    with httpx.Client(base_url=base,trust_env=False,headers={'Origin':base}) as client:
        assert client.post('/api/v1/login',json={'loginName':'player1','password':env['ONLINECOC_BOOTSTRAP_PASSWORD']}).status_code==200
        result['restartHp']=client.get('/api/v1/view').json()['entities']['actor-player1']['numbers']['hp']
        assert result['restartHp']==4
    finish(process,'restart')
finally:
    if process.poll() is None:process.terminate();process.wait(timeout=10)
result['passed']=True;save();print(json.dumps(result,ensure_ascii=True))
