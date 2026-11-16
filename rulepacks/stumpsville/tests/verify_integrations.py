"""Public CLI/HTTP acceptance; all model traffic is an isolated loopback fixture."""
from contextlib import contextmanager
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import threading
import time
import urllib.parse
import uuid

import httpx
from harness import PACK, Account, running, provision
from integrations import write_json, ROOT
from launch import free_port


def ai(account, op, args, allow_error=False):
    view = account.request('/api/v1/view')
    return account.request('/api/v1/ai/commands', {'requestId': str(uuid.uuid4()),
        'authorityEpoch': view['authorityEpoch'], 'op': op, 'args': args}, allow_error)


def result(receipt):
    assert receipt['status'] == 'committed', receipt
    return receipt['result']


@contextmanager
def provider(output, responder=None):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            value = {'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': json.dumps({'kind': 'plan', 'text': 'OFFLINE_REPLY: consult the action receipt; no game state changed.'})}}],
                     'usage': {'prompt_tokens': 20, 'completion_tokens': 20, 'total_tokens': 40}}
            if responder:
                value['choices'][0]['message']=responder(requests[-1])
                if value['choices'][0]['message'].get('tool_calls'):value['choices'][0]['finish_reason']='tool_calls'
            body = json.dumps(value).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    config = json.loads((ROOT/'engineering/ai/examples/ai-providers.json').read_text(encoding='utf-8'))
    profile = config['profiles'][0]
    profile.update(profileId='offline', adapter='compatible-chat', baseUrl=f'http://127.0.0.1:{server.server_port}', model='test-only',
                   credentialRef='env:STUMPSVILLE_TEST_AI_KEY', enabled=True, allowPrivateEndpoint=True)
    old = os.environ.get('STUMPSVILLE_TEST_AI_KEY'); os.environ['STUMPSVILLE_TEST_AI_KEY'] = 'isolated-dummy-key'
    path = output/'ai-providers.json'; write_json(path, config)
    try: yield path, requests
    finally:
        server.shutdown(); server.server_close(); thread.join(3)
        if old is None: os.environ.pop('STUMPSVILLE_TEST_AI_KEY', None)
        else: os.environ['STUMPSVILLE_TEST_AI_KEY'] = old


@contextmanager
def directory(output, web=False):
    python = ROOT/'engineering/network-p2p/.venv/Scripts/python.exe'
    port = free_port(); token = secrets.token_urlsafe(24)
    path = output/'directory-config.json'
    write_json(path, {'publishers': {'test': hashlib.sha256(token.encode()).hexdigest()}, 'stateFile': str(output/'directory-state.json'), 'webStateFile':str(output/'web-state.json')})
    log = (output/'directory.log').open('w', encoding='utf-8')
    process = subprocess.Popen([str(python), '-B', '-m', 'onlinecoc_web' if web else 'onlinecoc_p2p', 'serve' if web else 'directory', '--config', str(path), '--port', str(port)],
        cwd=ROOT/'engineering/network-p2p', stdout=log, stderr=log, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    url = f'http://127.0.0.1:{port}'
    try:
        with httpx.Client(trust_env=False) as http:
            for _ in range(100):
                assert process.poll() is None, 'directory startup failed'
                try:
                    if http.get(url+'/v1/rooms').status_code == 200: break
                except httpx.HTTPError: pass
                time.sleep(.1)
            else: raise AssertionError('directory timeout')
        config = output/'client.json'; write_json(config, {'directory': url, 'publisherToken': token})
        yield config, url
    finally:
        process.terminate(); process.wait(10); log.close()


def main():
    output=PACK/'tests/output'/('integrations-'+secrets.token_hex(4)); output.mkdir(parents=True)
    checks=[]
    with provider(output) as (config,calls), directory(output) as (network_config,directory_url):
        with running('integration', data=output/'game', ai_config=config, p2p_config=network_config, no_browser=True) as (runtime,password):
            kp,p1,p2=provision(runtime,password)
            caps=kp.request('/api/v1/capabilities'); assert caps['ai']['available'] and not caps['ai']['enabled']
            settings=kp.request('/api/v1/ai/settings')['settings']; assert not any(settings['externalSources'].values())
            assert not calls
            assert p1.http.get(p1.prefix+'/api/v1/ai/settings').status_code==403
            assert p1.http.get(p1.prefix+'/package/integrations').status_code==403
            assert kp.request('/package/integrations')['p2p']['running']
            assert kp.http.get(kp.prefix+'/ai-ui/client.js').status_code==200
            for path in ['/ai/guide.md','/runtime/integrations/p2p-client.json','/ai-ui/manager.js']:
                assert kp.http.get(kp.prefix+path).status_code==404
            checks.append('AI real host starts with complete companion; defaults off; private files and KP settings stay restricted')
            session=result(ai(p1,'ai.session.create',{'title':'PL request'}))
            submitted=result(ai(p1,'ai.session.submit',{'sessionId':session['sessionId'],'text':'Explain the result of my action; do not change the rules.'}))
            tasks=kp.request('/api/v1/ai/tasks')['items']; task=next(x for x in tasks if x['text'].startswith('Explain'))
            assert task['status']=='received' and not calls
            hidden=p2.http.get(p2.prefix+'/api/v1/ai/sessions/'+session['sessionId'])
            assert hidden.is_error and hidden.json()['code']=='NOT_VISIBLE',hidden.text
            denied=ai(p1,'ai.request.dispatch',{'requestId':task['requestId']},True)
            assert denied['status']=='rejected',denied
            result(ai(kp,'ai.settings.update',{'enabled':True,'profileId':'offline','externalSources':{'public':False,'kp':False,'private':False},'auto':{'enabled':False,'channelIds':['general'],'prefix':'!ai '}}))
            before=p1.state()['character']
            result(ai(kp,'ai.request.dispatch',{'requestId':task['requestId']}))
            for _ in range(150):
                t=next(x for x in kp.request('/api/v1/ai/tasks')['items'] if x['requestId']==task['requestId'])
                if t['status'] not in ('queued','generating','validating'):break
                time.sleep(.2)
            assert t['status']=='review_ready' and 'OFFLINE_REPLY' in t['response'],t
            assert len(calls)==1
            encoded=json.dumps(calls[0],ensure_ascii=False)
            assert '木栗' not in encoded and '豆叶' not in encoded
            assert 'OFFLINE_REPLY' not in json.dumps(p1.request('/api/v1/ai/sessions/'+session['sessionId']))
            assert p1.state()['character']==before
            assert kp.request('/api/v1/ai/drafts',{},True)['code']=='AI_CONSULTATION_ONLY'
            assert kp.command('publication.apply',{'approvalId':'anything'},True)['code']=='AI_CONSULTATION_ONLY'
            checks.append('PL requests / cross-account isolation / KP dispatch / offline provider response / no external context by default / no state changes / publication denied')
            # Borrow the actual package host through the networking module's local API.
            entry=urllib.parse.urlsplit(runtime.modules.entry); origin=entry.scheme+'://'+entry.netloc
            headers={'Origin':origin,'Authorization':'Bearer '+urllib.parse.parse_qs(entry.fragment)['token'][0]}
            with httpx.Client(base_url=origin,headers=headers,trust_env=False,timeout=30) as http:
                response=http.post('/local/host/start',json={'title':'Isolated Stumpsville acceptance','visibility':'public','approvalRequired':False})
                assert response.status_code==200,response.text
                room=response.json()['room']
                probe=output/'probe.json';write_json(probe,{'directory':directory_url,'roomId':room['roomId'],'password':password,'output':str(output/'peers')})
                child=subprocess.run([str(ROOT/'engineering/network-p2p/.venv/Scripts/python.exe'),'-B',str(PACK/'tests/probe_p2p.py'),str(probe)],
                    capture_output=True,text=True,encoding='utf-8',timeout=100,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                assert child.returncode==0,child.stdout+child.stderr
                checks.append('two real WebRTC players: account isolation, live state, basic chat; package/action and AI routes rejected')
                runtime.modules.close()
                assert kp.request('/api/v1/view')['accountId']=='kp'
                assert p1.state()['character']==before
                listing=httpx.get(directory_url+'/v1/rooms',trust_env=False).json()['items']
                assert room['roomId'] not in [r['roomId'] for r in listing]
                checks.append('stopping P2P withdraws directory room and keeps borrowed game host alive')
            browser_check(runtime,password,checks,output)
    record={'checkedAt':datetime.now().astimezone().isoformat(),'checks':checks,'passed':len(checks),'provider':'loopback fixture only','cloudTested':False}
    write_json(PACK/'tests/output/integrations-results.json',record)
    write_json(PACK/'tests/integrations-results.json',record)
    print(json.dumps({'passed':len(checks),'checks':checks},ensure_ascii=False,indent=2))


def browser_check(runtime,password,checks,output):
    from playwright.sync_api import sync_playwright,expect
    errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1366,'height':768})
        def login(name,suffix=''):
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(runtime.origin+'/sessions/browser-'+name+'/'+suffix)
            if not suffix:
                page.locator('[name=loginName]').fill(name);page.locator('[name=password]').fill(password)
                page.get_by_role('button',name='进入冒险',exact=True).click()
            page.locator('.identity').wait_for()
            if name=='kp' and not suffix:
                page.locator('a[href="#/gm/rulings"]').click();page.locator('#kp-ai-embedded .review-open').click()
                page.locator('.ai-dialog [data-create]').wait_for()
            else:
                page.locator('[data-action=ai-assistant]').click();page.locator('#player-ai-embedded .reference-editor').wait_for()
            return page
        gm=login('kp');gm.locator('.ai-dialog [data-settings] select').wait_for(state='attached')
        if gm.locator('.ai-dialog details').get_attribute('open') is None:gm.locator('.ai-dialog summary').click()
        gm.locator('.ai-dialog [data-settings] select').wait_for();gm.get_by_text('OFFLINE_REPLY:',exact=False).wait_for()
        gm.locator('.ai-dialog summary').click();gm.screenshot(path=str(output/'ai-kp.png'))
        assert gm.locator('.ai-guide-warning').count()==0
        gm.locator('.ai-dialog [data-close]').click()
        # A UI refresh can load new JS while the host still uses an old snapshot.
        def old_snapshot(route):
            response=route.fetch();data=response.json();data['ai'].pop('guideCurrent',None);data['ai'].pop('queryMode',None)
            route.fulfill(response=response,json=data)
        gm.route('**/package/integrations',old_snapshot)
        gm.locator('#kp-ai-embedded .review-open').click()
        expect(gm.locator('.ai-guide-warning')).to_contain_text('仅刷新网页不会更新 AI 快照')
        assert gm.locator('.ai-dialog details').get_attribute('open') is not None
        gm.locator('.ai-dialog [data-close]').click();gm.unroute('**/package/integrations',old_snapshot)
        player=login('player1');assert not player.locator('[data-settings],[data-tasks],.review-open:visible').count()
        player.locator('.session-select').select_option(label='PL request')
        expect(player.locator('#player-ai-embedded #history')).to_contain_text('Explain the result')
        expect(player.locator('#player-ai-embedded #history')).not_to_contain_text('OFFLINE_REPLY')
        player.locator('#dialog [data-action=close]').first.click();assert not player.locator('.reference-editor').count()
        own=login('kp','?view=player#/play/scene');assert not own.locator('[data-settings],[data-tasks],.review-open:visible').count()
        own.locator('.reference-editor').fill('KP own PL session');own.locator('#player-ai-embedded #send').click()
        expect(own.locator('#player-ai-embedded #history')).to_contain_text('等待 KP',timeout=20000)
        own.locator('#dialog [data-action=close]').first.click();own.locator('[name=locale]').select_option('en')
        expect(own.locator('[data-action=ai-assistant]')).to_have_text('AI assistant');own.locator('[data-action=ai-assistant]').click()
        expect(own.locator('.view-title')).to_have_text('AI assistant',timeout=20000)
        expect(own.locator('.session-select')).to_contain_text('KP own PL session')
        own.screenshot(path=str(output/'ai-player-en.png'))
        assert own.evaluate('document.documentElement.scrollHeight<=innerHeight+1')
        own.locator('#dialog [data-action=close]').first.click();own.locator('[data-action=logout]').click();assert not own.locator('.reference-editor').count()
        assert not errors,errors
        context.close();browser.close()
    checks.append('Edge: KP replies and settings, PL privacy, KP actual PL session, English UI, bounded viewport, logout cleanup; no JS errors')


if __name__=='__main__':main()
