"""Real Edge, fake transport: account/connection races need no live private data."""
from pathlib import Path
from playwright.sync_api import sync_playwright


def test_sdk_discards_previous_account_and_connection():
    sdk = Path(__file__).resolve().parents[2] / 'client-sdk/client.js'
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page()
        page.route('http://sdk.test/**', lambda route: route.fulfill(
            content_type='text/javascript' if route.request.url.endswith('.js') else 'text/html',
            body=sdk.read_text(encoding='utf-8') if route.request.url.endswith('.js') else '<html></html>'))
        page.goto('http://sdk.test/')
        result = page.evaluate("""async()=>{
          const {Client}=await import('/client.js');
          const sockets=[]; let resolveRead;
          const transport={request:async(path)=>path==='knowledge/read'
            ?new Promise(resolve=>resolveRead=resolve):{csrf:'test-only'},
            open:(message,close)=>{const s={message,lateClose:close,close:()=>close()};sockets.push(s);return s;}};
          const client=new Client(transport);
          const frame=(s,id,account)=>{s.message({type:'snapshot.begin',id,parts:1});s.message({type:'snapshot.part',id,index:0,data:JSON.stringify({accountId:account})});s.message({type:'snapshot.end',id});};
          const check=(ok,why)=>{if(!ok)throw new Error(why);};
          await client.login('first','x'); frame(sockets[0],'first','first');
          client.pending.set('old',{});client.aiPending=new Map([['old',{}]]);
          const read=client.knowledgeRead([]).then(()=>false,e=>e.message==='SESSION_CHANGED');
          const switched=client.login('second','x');
          check(client.view===null&&client.parts===null&&!client.connected&&!client.pending.size&&!client.aiPending.size,'switch must clear immediately');
          await switched;frame(sockets[1],'second','second');
          frame(sockets[0],'late','first');sockets[0].lateClose();
          check(client.view.accountId==='second'&&client.connected,'old socket affected new session');
          resolveRead({items:[{secret:'old-account'}]});check(await read,'old async read was accepted');
          const s=sockets[1];s.message({type:'snapshot.begin',id:'partial',parts:1});s.message({type:'snapshot.part',id:'partial',index:0,data:'{}'});s.message({type:'reset'});s.message({type:'snapshot.end',id:'partial'});
          check(client.view===null&&client.parts===null&&!client.connected,'reset kept a partial view');
          client.connect();frame(sockets[2],'fresh','second');frame(sockets[1],'stale','first');
          check(client.view.accountId==='second','reconnect accepted old frames');
          await client.logout();frame(sockets[2],'after-logout','second');
          check(client.view===null&&!client.connected,'logout accepted late snapshot');
          return true;
        }""")
        assert result
        browser.close()
