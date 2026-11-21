"""Chronological mixed-source queue in real browser; no host or model calls."""
import json
import secrets
import traceback
import threading
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

PACK = Path(__file__).resolve().parents[1]


def main():
    output = PACK/'tests/output'/('queue-chronology-'+secrets.token_hex(4)); output.mkdir(parents=True)
    report = {'checkedAt':datetime.now().astimezone().isoformat(),'checks':[],'externalModelCalls':0,'evidenceDirectory':output.relative_to(PACK).as_posix()}
    class Handler(SimpleHTTPRequestHandler):
        extensions_map = {**SimpleHTTPRequestHandler.extensions_map,'.js':'application/javascript'}
        def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(PACK),**kwargs)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            page=browser.new_page(viewport={'width':390,'height':844});page.on('pageerror',lambda e:errors.append(str(e)))
            page.route('**/fixture',lambda r:r.fulfill(content_type='text/html',body='<meta charset="utf-8"><link rel="stylesheet" href="/ui/styles.css"><main style="margin:0;padding:8px;height:540px;display:flex;flex-direction:column"><header>消息队列　裁决队列　已归档</header><div id="status" class="queue-status-host"></div><section id="scroll" style="overflow:auto;min-height:0"><div id="queue"></div><div id="timeline"></div></section></main>'))
            page.goto('http://127.0.0.1:'+str(server.server_port)+'/fixture')
            page.evaluate('''async()=>{
              const {mountRulingTimeline,rulingCard}=await import('/ui/ruling-card.js');
              const {mountKeeperAIQueue}=await import('/ui/keeper-queue.js');
              const {initLocale}=await import('/ui/i18n.js');await initLocale(new URL('/',location.href));
              globalThis.timeline=mountRulingTimeline(document.querySelector('#timeline'));
              const template=document.createElement('template');template.innerHTML=rulingCard({time:'14:13',timestamp:13,key:'manual:1',type:'人工申请',source:'player1',summary:'最早的人工申请',actions:'<button>人工处理</button>'});
              timeline.set('manual',[template.content.firstElementChild]);
              globalThis.tasks=[{requestId:'late',createdAt:20,initiator:'kp',text:'最新AI请求',status:'needs_input'},{requestId:'early',createdAt:14,initiator:'player1',text:'较早AI请求：已交付原文',status:'stale',sourceState:'stale',sourceNotice:'依据已变化'}];
              globalThis.rows=[{rulingId:'batch:middle',createdAt:17,kind:'runtime',status:'pending',summary:'中间修改方案',initiator:'kp'}];
              globalThis.readError=false;
              const client={connected:true,view:{role:'kp',accountId:'kp',authorityEpoch:1},subscribe:()=>()=>{},aiReceipt:async()=>({status:'committed'}),aiTasks:async()=>{if(readError)throw Object.assign(Error('等待主机响应超时（定位：read-1）'),{code:'HOST_TIMEOUT'});return{items:tasks}},aiRulings:async()=>({items:rows})};
              globalThis.queue=mountKeeperAIQueue(document.querySelector('#queue'),client,{mountMarkdown:(el,text)=>{el.textContent=text;return{destroy(){}}}},{scope:'isolated',account:'kp',timeline,statusTarget:document.querySelector('#status')});
            }''')
            cards=page.locator('#timeline>.ruling-card');expect(cards).to_have_count(4)
            assert cards.evaluate_all('(nodes)=>nodes.map(n=>Number(n.dataset.queueTime))')==[13,14,17,20]
            stale=page.locator('[data-ai-request=early]');expect(stale).to_contain_text('较早AI请求：已交付原文')
            assert stale.evaluate("n=>getComputedStyle(n).backgroundColor")=='rgb(232, 231, 227)'
            expect(stale.locator('.source-stale,.notice')).to_have_count(0)
            page.evaluate("queue.remember('original-command-id')")
            expect(page.locator('#status [data-recovery]')).to_be_visible();expect(page.locator('#status .queue-status')).to_be_hidden()
            geometry=page.locator('#status').bounding_box();page.locator('#scroll').evaluate('n=>n.scrollTop=n.scrollHeight')
            assert page.locator('#status').bounding_box()==geometry
            assert page.locator('.queue-status-line').evaluate("n=>getComputedStyle(n).fontSize")=='12px'
            assert page.locator('#status').evaluate('n=>n.scrollWidth<=n.clientWidth&&n.scrollHeight<=n.clientHeight')
            page.locator('#scroll').evaluate('n=>n.scrollTop=0');page.screenshot(path=str(output/'fixed-status-stale-390.png'),full_page=True)
            page.locator('#status button').click();expect(page.locator('#status [data-recovery]')).to_be_hidden();expect(page.locator('#status .queue-status')).to_have_text('处理结果已保存')
            report['checks'].append('390px固定12px单行，未知回执替代旧状态且核对后清除；滚动不移动；过期卡灰底原文无绿色提示')
            awaitable=page.evaluate('async()=>{tasks.reverse();rows.reverse();await queue.refresh();}');assert awaitable is None
            assert cards.evaluate_all('(nodes)=>nodes.map(n=>Number(n.dataset.queueTime))')==[13,14,17,20]
            cards.nth(2).get_by_role('button',name='查看并裁决',exact=True).click();expect(page.locator('.ruling-dialog')).to_contain_text('中间修改方案');page.get_by_role('button',name='关闭详情',exact=True).click()
            report['checks'].append('不同来源统一DOM按时间升序，倒序响应不改变排列，移动后的按钮仍可操作')
            page.evaluate("async()=>{tasks.push({requestId:'new',createdAt:22,initiator:'player1',text:'后来的申请',status:'needs_input'});await queue.refresh();}")
            expect(cards.last).to_contain_text('后来的申请')
            page.evaluate("async()=>{rows[0].queueStatus='history';rows[0].status='completed';queue.setArchived(true);timeline.set('manual',[]);await queue.refresh();}")
            expect(cards).to_have_count(1);expect(cards).to_contain_text('中间修改方案')
            page.evaluate('queue.setArchived(false)');expect(cards).to_have_count(3)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
            page.screenshot(path=str(output/'chronological-390.png'),full_page=True)
            report['checks'].append('新申请追加在下方，归档切换不混入旧卡片，390px无横向溢出')
            page.evaluate('async()=>{readError=true;await queue.refresh();}');expect(page.locator('.queue-status')).to_contain_text('定位：read-1')
            page.evaluate('async()=>{readError=false;await queue.refresh();}');expect(page.locator('.queue-status')).to_have_text('')
            report['checks'].append('查询失败保留可追溯原因，查询恢复后清除旧错误')
            assert not errors,errors;report['passed']=True;browser.close()
    except Exception as e:report.update(passed=False,error=traceback.format_exc()[-4000:])
    finally:server.shutdown();server.server_close();worker.join()
    report.update(passedCount=len(report['checks']),pageErrors=errors)
    canonical=PACK/'tests/queue-chronology-results.json'
    if canonical.exists():
        old=json.loads(canonical.read_text(encoding='utf-8'));report['previousRuns']=[*old.get('previousRuns',[]),{k:old.get(k) for k in ('passed','error','checks','evidenceDirectory')}]
    for p in (canonical,output/'report.json'):p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('passed','passedCount','error','evidenceDirectory')},ensure_ascii=True));return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
