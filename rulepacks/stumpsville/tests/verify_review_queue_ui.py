"""Package-only queue UI contract checks; no engine or external provider calls."""
import json
import secrets
import threading
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

PACK = Path(__file__).resolve().parents[1]


def main():
    output = PACK / 'tests/output' / ('review-queue-ui-' + secrets.token_hex(4)); output.mkdir(parents=True)
    prior = PACK / 'tests/review-queue-ui-results.json'
    report = {'checkedAt': datetime.now().astimezone().isoformat(), 'checks': [], 'realSaveChanged': False,
              'realProviderCalls': 0, 'scope': 'package UI with deterministic DTOs', 'evidenceDirectory': output.relative_to(PACK).as_posix()}
    if prior.exists():
        old = json.loads(prior.read_text(encoding='utf-8'))
        report['previousRuns'] = [*old.get('previousRuns', []), {k: old.get(k) for k in ['passed', 'error', 'checks', 'evidenceDirectory']}]
    class Handler(SimpleHTTPRequestHandler):
        extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.js': 'application/javascript'}
        def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(PACK), **kwargs)
        def log_message(self, *args): pass
        def do_GET(self):
            path = self.path.split('?')[0]
            if path not in {'/ui/keeper-rulings.js', '/ui/keeper-queue.js', '/ui/ruling-card.js', '/ui/batch-details.js', '/ui/ai-recovery.js', '/ui/i18n.js', '/ui/messageformat.js', '/ui/styles.css', '/locales/zh-CN/ui.json', '/locales/meta/catalog/ui.json'}:
                self.send_error(404); return
            super().do_GET()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start(); errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width': 390, 'height': 844}); page.on('pageerror', lambda e: errors.append(str(e)))
            page.route('**/fixture', lambda route: route.fulfill(content_type='text/html', body='<meta charset="utf-8"><link rel="stylesheet" href="/ui/styles.css"><main style="max-width:700px;margin:0 auto"><div id="list"></div></main>'))
            page.goto('http://127.0.0.1:' + str(server.server_port) + '/fixture')
            page.evaluate('''async()=>{
              const {mountKeeperAIQueue}=await import('/ui/keeper-queue.js');
              const {initLocale}=await import('/ui/i18n.js');await initLocale(new URL('/',location.href));
              globalThis.rows=[{rulingId:'proposal:'+'1'.repeat(32),queueTargetId:'proposal:'+'1'.repeat(32),queueDigest:'digest',kind:'configuration',highRisk:true,status:'pending',canDecide:true,canArchive:true,createdAt:1,initiator:'kp',summary:'保留原方案：检查入口奶酪机关。',sourceState:'stale',sourceNotice:'依赖资料已过时，仍显示原方案。',risks:[]}];
              globalThis.tasks=[];globalThis.commands=[];globalThis.notices=[];globalThis.counts=[];
              const client={connected:true,view:{role:'kp',accountId:'kp',authorityEpoch:1},subscribe:()=>()=>{},aiTasks:async()=>({items:tasks}),aiRulings:async()=>({items:rows}),aiResolve:async()=>({items:[]}),aiCommand:async(op,args)=>{
                commands.push({op,args});const item=[...rows,...tasks].find(r=>r.queueTargetId===args.targetId);
                if(op==='ai.queue.archive'){item.archived=args.archived;item.queueStatus=args.archived?'archived':'active';item.canArchive=!args.archived;item.canRestore=args.archived;item.archiveReason=args.reason;}
                return {status:'committed',result:item||{}};
              }};
              globalThis.queue=mountKeeperAIQueue(document.querySelector('#list'),client,{mountMarkdown:(target,text)=>{target.textContent=text;return{destroy(){}};}},{scope:'fixture',account:'kp',onCount:n=>counts.push(n),onNotice:n=>notices.push(n)});
            }''')
            card = page.locator('[data-ruling-id]'); expect(card).to_have_count(1)
            card.get_by_role('button', name='查看并裁决', exact=True).click()
            dialog = page.locator('.ruling-dialog'); expect(dialog).to_contain_text('保留原方案')
            expect(dialog).to_have_attribute('title','依赖资料已过时，仍显示原方案。'); expect(dialog.locator('.source-stale')).to_have_count(0); expect(dialog.locator('.ruling-decision-actions button')).to_have_count(3)
            expect(dialog.locator('textarea')).to_have_count(1); expect(dialog.locator('[data-queue-archive]')).to_be_visible()
            page.screenshot(path=str(output / 'archive-control-390.png'), full_page=True)
            report['checks'].append('高危详情保留原摘要和过期提示，三个裁决动作及单备注不变，附归档入口')
            dialog.get_by_role('button', name='归档此项', exact=True).click(); expect(dialog).to_have_count(0); expect(card).to_have_count(0)
            assert page.evaluate('commands[0].op') == 'ai.queue.archive'
            assert page.evaluate('commands[0].args.reason') and page.evaluate('rows[0].status') == 'pending'
            assert page.evaluate('counts.at(-1)') == 0
            page.evaluate('queue.setArchived(true)'); expect(card).to_have_count(1)
            card.get_by_role('button', name='查看并裁决', exact=True).click()
            dialog.get_by_role('button', name='恢复到裁决队列', exact=True).click()
            page.evaluate('queue.setArchived(false)'); expect(card).to_have_count(1)
            assert page.evaluate('counts.at(-1)') == 1
            report['checks'].append('归档和恢复提交精确整理封套、自动关闭详情并同步计数，保留业务状态')
            page.evaluate('''async()=>{rows[0].queueStatus='superseded';rows[0].archived=true;rows[0].canArchive=false;rows[0].canRestore=false;rows[0].canDecide=false;rows[0].supersededBy='batch:'+'2'.repeat(32);await queue.refresh();}''')
            expect(card).to_have_count(0); page.evaluate('queue.setArchived(true)'); expect(card).to_contain_text('已由后续方案替代')
            card.get_by_role('button', name='查看并裁决', exact=True).click()
            expect(dialog.get_by_role('button', name='接受并执行', exact=True)).to_have_count(0)
            expect(dialog.get_by_role('button', name='查看后续方案', exact=True)).to_be_visible()
            dialog.get_by_role('button', name='关闭详情', exact=True).click()
            report['checks'].append('已替代裁决进入历史并保留后续入口，详情不再提供批准')
            page.evaluate('''async()=>{rows=[...['unknown','partial','executing'].map((status,i)=>({rulingId:'batch:'+String(i+3).repeat(32),kind:'runtime',status,archived:true,queueStatus:'archived',createdAt:2,summary:'仍需核对的'+status}))];queue.setArchived(false);await queue.refresh();}''')
            expect(card).to_have_count(3); assert page.evaluate('counts.at(-1)') == 3
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2'), page.evaluate('({scroll:document.documentElement.scrollWidth,viewport:innerWidth})')
            report['checks'].append('异常DTO也不能把执行中、结果未知和部分完成隐藏出待处理队列；窄屏无溢出')
            assert not errors, errors; report['passed'] = True; browser.close()
    except Exception as error:
        report.update(passed=False, errorType=type(error).__name__, error=str(error)[:2500])
    finally:
        server.shutdown(); server.server_close(); worker.join()
    report.update(pageErrors=errors, passedCount=len(report['checks']))
    for path in [prior, output / 'report.json']: path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report.get(k) for k in ['passed', 'passedCount', 'error', 'evidenceDirectory']}, ensure_ascii=True), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__': raise SystemExit(main())
