"""Real HTTP capability failures and package startup diagnostics; no cloud writes."""
import json
import secrets
import sys
import threading
from contextlib import contextmanager
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK/'tools'))
from integrations import Modules, WebStartError, check_web_directory


@contextmanager
def endpoint(status=200, body=b'{"packageBridge":1,"storageBridge":1,"roomCreation":1,"publicRooms":1}', headers=None):
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.path,dict(self.headers)))
            self.send_response(status)
            for key,value in (headers or {}).items():self.send_header(key,value)
            self.end_headers();self.wfile.write(body)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{server.server_port}',requests
    finally:server.shutdown();server.server_close();thread.join()


def failure(config,code):
    try:check_web_directory(config)
    except WebStartError as error:assert error.code==code,(error.code,code)
    else:raise AssertionError('Expected '+code)


def main():
    checks=[]
    with endpoint(404,b'404: Not Found') as (url,requests):
        failure({'directory':url},'WEB_BRIDGE_REQUIRED')
        assert requests[0][0]=='/v1/web/capabilities'
    checks.append('plain-text HTTP 404 becomes missing cloud bridge, not JSON parser failure')
    for status,body,code in [(200,b'{}','WEB_BRIDGE_REQUIRED'),(200,b'{"packageBridge":1,"storageBridge":1}','WEB_PLATFORM_REQUIRED'),(200,b'[]','WEB_DIRECTORY_RESPONSE_INVALID'),(200,b'<html>gateway</html>','WEB_DIRECTORY_RESPONSE_INVALID'),(200,b'x'*65537,'WEB_DIRECTORY_RESPONSE_INVALID'),(503,b'busy','WEB_DIRECTORY_HTTP_ERROR')]:
        with endpoint(status,body) as (url,_):failure({'directory':url},code)
    checks.append('old capabilities, malformed/oversize responses and HTTP server errors stay distinct')
    with endpoint(302,b'',{'Location':'http://127.0.0.1:1/unexpected'}) as (url,requests):
        failure({'directory':url},'WEB_DIRECTORY_REDIRECT');assert len(requests)==1
    failure({'directory':'https://name:password@example.com'},'WEB_CONFIG_INVALID')
    failure({'directory':'https://[invalid'},'WEB_CONFIG_INVALID')
    failure({'directory':'https://localhost:bad'},'WEB_CONFIG_INVALID')
    with endpoint() as (url,requests):
        check_web_directory({'directory':url,'publisherToken':'do-not-send'})
        assert all('authorization' not in {k.lower() for k in headers} for _,headers in requests)
    checks.append('capability check sends no publisher credential; redirects and credential-bearing URLs rejected')
    failure({'directory':'https://example.invalid','caFile':str(PACK/'tests/output/nonexistent-ca.pem')},'WEB_CA_MISSING')
    checks.append('missing CA classified without disabling TLS validation')
    output=PACK/'tests/output'/('web-startup-'+secrets.token_hex(4));output.mkdir(parents=True)
    with endpoint(404,b'404: Not Found') as (url,_):
        config=output/'client.json';config.write_text(json.dumps({'directory':url,'publisherToken':'private-marker'}),encoding='utf-8')
        modules=Modules(SimpleNamespace(args=SimpleNamespace(web_config=config,bind='127.0.0.1'),data=output))
        with patch('build_web.build',side_effect=AssertionError('must stop before build')),patch('integrations.subprocess.Popen',side_effect=AssertionError('must not publish')):
            modules.start_web()
        state=modules.web_status(private=True)
        assert not state['running'] and state['errorCode']=='WEB_BRIDGE_REQUIRED'
        assert '云端' in state['hint'] and 'HTTP 404' in (output/'web.log').read_text(encoding='utf-8')
        assert not (output/'integrations').exists()
        assert 'private-marker' not in json.dumps(state)+(output/'web.log').read_text(encoding='utf-8')
        assert 'logPath' not in modules.web_status()
    checks.append('failed startup preserves host/data, stops before export/publish, logs stage and code without credentials')
    from harness import running, Account
    from playwright.sync_api import sync_playwright, expect
    with endpoint(404,b'404: Not Found') as (url,_):
        config.write_text(json.dumps({'directory':url,'publisherToken':'private-marker'}),encoding='utf-8')
        with running('web-startup',data=output/'game',web_config=config,no_browser=True) as (runtime,password):
            kp=Account(runtime.origin,'kp',password)
            assert kp.request('/package/web/status')['errorCode']=='WEB_BRIDGE_REQUIRED'
            assert kp.state()['role']=='kp'
            pl=Account(runtime.origin,'player1',password)
            assert pl.request('/package/web/status',allow_error=True)['code']=='LOCAL_KP_REQUIRED'
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True)
                page=browser.new_page(viewport={'width':1280,'height':800});errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(runtime.origin+'/sessions/diagnostic-kp/')
                page.locator('[name=loginName]').fill('kp');page.locator('[name=password]').fill(password)
                page.get_by_role('button',name='进入冒险',exact=True).click()
                page.locator('a[href="#/gm/room"]').click();page.locator('[data-action=web-room]').click()
                expect(page.locator('#dialog')).to_contain_text('WEB_BRIDGE_REQUIRED')
                expect(page.locator('#dialog')).to_contain_text('仅重启本机或修改游戏端口不能补齐云端接口')
                assert 'private-marker' not in page.locator('#dialog').inner_text()
                assert page.locator('#dialog').evaluate('e=>e.scrollWidth<=e.clientWidth')
                page.screenshot(path=str(output/'startup-error.png'))
                assert not errors,errors
                browser.close()
    checks.append('real host remains playable after 404; only local KP sees diagnostics; Edge renders guidance and log path without overflow')
    report={'passed':True,'checkedAt':datetime.now().astimezone().isoformat(),'checks':checks,'cloudMutation':False}
    (PACK/'tests/web-startup-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
