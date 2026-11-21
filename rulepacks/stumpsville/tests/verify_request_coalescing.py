"""Browser concurrency checks for chat/history and ruling refreshes."""
from datetime import datetime
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
from playwright.sync_api import sync_playwright,expect

PACK=Path(__file__).resolve().parents[1]


def main():
    output=PACK/'tests/output'/('request-coalescing-'+secrets.token_hex(4));output.mkdir(parents=True)
    report={'checkedAt':datetime.now().astimezone().isoformat(),'checks':[],'realSaveChanged':False,'externalModelCalls':0,'evidenceDirectory':output.relative_to(PACK).as_posix()};errors=[]
    class Handler(SimpleHTTPRequestHandler):
        extensions_map={**SimpleHTTPRequestHandler.extensions_map,'.js':'application/javascript'}
        def __init__(self,*a,**k):super().__init__(*a,directory=str(PACK),**k)
        def log_message(self,*a):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True);page=browser.new_page()
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.route('**/fixture',lambda r:r.fulfill(content_type='text/html',body='<meta charset="utf-8"><main id="chat"></main><section id="queue"></section>'))
            page.goto('http://127.0.0.1:'+str(server.server_port)+'/fixture')
            page.evaluate('''async()=>{
              const {initLocale}=await import('/ui/i18n.js');await initLocale(new URL('/',location.href));
              globalThis.chat=(await import('/ui/chat.js')).chatUI;
              globalThis.pending=[];globalThis.calls=0;
              chat.configure({api:()=>{calls++;return new Promise(resolve=>pending.push(resolve));},send:async()=>({result:{}}),toast:()=>{}});
              globalThis.a={accountId:'player1',team:[],channels:{general:{channelId:'general',kind:'room',name:'general',revision:1,lastSequence:1,canPost:true}}};
              chat.update(a);chat.mount(document.querySelector('#chat'));
              globalThis.polls=Promise.all(Array.from({length:10},()=>chat.poll()));
            }''')
            assert page.evaluate('calls')==1
            page.evaluate('''async()=>{pending.shift()({items:[{messageId:'one',senderAccountId:'player1',text:'one response',createdAt:1}],nextBefore:null});await polls;}''')
            expect(page.locator('.chat-history')).to_contain_text('one response')
            report['checks'].append('同一频道版本的挂载与十次并发刷新只发出一次历史查询')
            page.evaluate('''()=>{a={...a,channels:{general:{...a.channels.general,revision:2}}};chat.update(a);chat.poll();chat.update({...a,accountId:'player2'});}''')
            assert page.evaluate('calls')==3
            page.evaluate('''async()=>{
              pending.shift()({items:[{messageId:'private',senderAccountId:'player1',text:'old-account-only',createdAt:2}],nextBefore:null});
              pending.shift()({items:[{messageId:'new',senderAccountId:'player2',text:'new account',createdAt:2}],nextBefore:null});
              await new Promise(r=>setTimeout(r,0));
            }''')
            expect(page.locator('.chat-history')).to_contain_text('new account');expect(page.locator('.chat-history')).not_to_contain_text('old-account-only')
            report['checks'].append('身份切换不复用旧账号请求，迟到的旧回复不会渲染')
            page.evaluate('''async()=>{
              const {mountPackageRulings}=await import('/ui/keeper-rulings.js');
              globalThis.rulingCalls=0;globalThis.active=0;globalThis.maxActive=0;globalThis.rows=[];
              const client={aiRulings:async()=>{rulingCalls++;active++;maxActive=Math.max(maxActive,active);await new Promise(r=>setTimeout(r,50));active--;return {items:rows};}};
              globalThis.rulings=mountPackageRulings(document.querySelector('#queue'),client,{mountMarkdown:()=>({destroy(){}})},{authorized:()=>true,command:async()=>{}});
              await Promise.all(Array.from({length:10},()=>rulings.refresh()));
            }''')
            assert page.evaluate('maxActive')==1
            assert page.evaluate('rulingCalls')==2
            report['checks'].append('十次并发裁决刷新合并为当前和一次后续读取，无并发堆积且保留刷新意图')
            page.evaluate('rulings.destroy()');assert not errors,errors;browser.close()
        report['passed']=True
    except Exception as error:report.update(passed=False,error=repr(error))
    finally:server.shutdown();server.server_close();thread.join()
    report.update(passedCount=len(report['checks']),pageErrors=errors)
    canonical=PACK/'tests/request-coalescing-results.json'
    if canonical.exists():
        old=json.loads(canonical.read_text(encoding='utf-8'));report['previousRuns']=[*old.get('previousRuns',[]),{k:old.get(k) for k in ('passed','error','evidenceDirectory')}]
    for path in (canonical,output/'report.json'):path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('passed','passedCount','error','evidenceDirectory')}));return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
