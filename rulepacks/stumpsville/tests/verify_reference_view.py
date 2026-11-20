"""Package-only reference rendering: same display helpers, fixed input and no reads."""
import json
import secrets
import threading
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

PACK=Path(__file__).resolve().parents[1]


def main():
    output=PACK/'tests/output'/('reference-view-'+secrets.token_hex(4));output.mkdir(parents=True)
    report={'checkedAt':datetime.now().astimezone().isoformat(),'checks':[],'evidenceDirectory':output.relative_to(PACK).as_posix(),'realSaveChanged':False}
    prior=PACK/'tests/reference-view-results.json'
    if prior.exists():
        old=json.loads(prior.read_text(encoding='utf-8'));report['previousRuns']=[*old.get('previousRuns',[]),{k:old.get(k) for k in ['passed','error','checks','evidenceDirectory']}]
    class Handler(SimpleHTTPRequestHandler):
        extensions_map={**SimpleHTTPRequestHandler.extensions_map,'.js':'application/javascript'}
        def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(PACK),**kwargs)
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path.split('?')[0] not in {'/ui/reference-view.js','/ui/i18n.js','/ui/messageformat.js','/locales/zh-CN/ui.json','/locales/meta/catalog/ui.json'}:self.send_error(404);return
            super().do_GET()
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            page=browser.new_page(viewport={'width':800,'height':900});page.on('pageerror',lambda e:errors.append(str(e)))
            page.route('**/fixture',lambda r:r.fulfill(content_type='text/html',body='<html lang="zh-CN"><meta charset="utf-8"><style>body{background:#f9f5e9;font:16px serif;padding:20px}main{max-width:650px;margin:auto}</style><main></main></html>'))
            page.goto('http://127.0.0.1:'+str(server.server_port)+'/fixture')
            page.evaluate('''async()=>{globalThis.views=await import('/ui/reference-view.js');const i18n=await import('/ui/i18n.js');await i18n.initLocale(new URL('/',location.href));globalThis.show=item=>{const node=views.renderPackageReference(item);document.querySelector('main').replaceChildren(...(node?[node]:[]));return !!node;};}''')
            actor={'kind':'knowledge','value':{'data':{'configurationId':'sv.character','name':'木栗','numbers':{'str':8,'strMax':9,'dex':10,'dexMax':10,'wil':7,'wilMax':7,'hp':2,'maxHp':4,'armor':1,'pips':12},'metadata':{'inventory':[{'name':'铜锅盖','kind':'armor','slots':1,'slot':4,'uses':2,'maxUses':3,'armor':1,'description':'观察记录中的盾'}]}}}}
            assert page.evaluate('show',actor)
            expect(page.locator('.stat')).to_have_count(3);expect(page.locator('.reference-item')).to_contain_text('槽位 4 · 铜锅盖')
            expect(page.locator('.reference-item')).to_contain_text('2 / 3')
            expect(page.locator('button')).to_have_count(0)
            report['checks'].append('角色属性卡和携带物品卡使用授权记录内名称、槽位和用量；引用无执行按钮')
            page.screenshot(path=str(output/'character.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
            page.screenshot(path=str(output/'character-390.png'),full_page=True)
            report['checks'].append('390px角色卡不横向溢出')
            scene={'kind':'knowledge','value':{'data':{'index':3,'name':'庭院','description':'旧观察中的池塘。','exits':[2,4],'clues':[{'title':'足迹','text':'只保存这次发现'}],'actions':[{'label':'观察池塘','hint':'岸边查看','choices':[{'label':'观察','process':'只显示已知做法'}]}]}}}
            assert page.evaluate('show',scene);expect(page.locator('main')).to_contain_text('旧观察中的池塘')
            expect(page.locator('.tag')).to_have_count(2);page.locator('summary').click();expect(page.locator('main')).to_contain_text('只显示已知做法')
            report['checks'].append('场景按观察记录展示描述、通路、线索和做法，不用当前世界补名称或状态')
            dangerous={'kind':'data','value':{'data':{'name':'<img src=x onerror=alert(1)>','kind':'item','slots':1,'uses':0,'description':'<script>alert(1)</script>'}}}
            assert page.evaluate('show',dangerous);expect(page.locator('img,script')).to_have_count(0)
            expect(page.locator('h3')).to_have_text(dangerous['value']['data']['name'])
            report['checks'].append('物品名称和说明转为安全文本，恶意内容不创建可执行节点')
            assert not page.evaluate('show',{'kind':'data','value':{'unrecognized':True}})
            assert not page.evaluate('show',{'kind':'entity','value':{'configurationId':4,'numbers':{}}})
            assert not page.evaluate('show',{'kind':'entity','value':{'configurationId':'sv.world','numbers':{'round':8}}})
            assert not page.evaluate('show',{'kind':'entity','value':{'configurationId':'sv.character','numbers':'invalid'}})
            report['checks'].append('未知数据类型交还通用展示，不误套游戏字段')
            requests=[];page.on('request',lambda req:requests.append(req.url))
            unchanged=page.evaluate('''item=>{const saved=JSON.stringify(item);show(item);return saved===JSON.stringify(item);}''',actor)
            assert unchanged and not requests
            report['checks'].append('展示不改写授权DTO，不请求额外数据或新状态')
            assert not errors,errors;report['passed']=True;browser.close()
    except Exception as e:report.update(passed=False,errorType=type(e).__name__,error=str(e)[:2500])
    finally:server.shutdown();server.server_close();thread.join()
    report['pageErrors']=errors;report['passedCount']=len(report['checks'])
    for target in [prior,output/'report.json']:target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ['passed','passedCount','error','evidenceDirectory']},ensure_ascii=True),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
