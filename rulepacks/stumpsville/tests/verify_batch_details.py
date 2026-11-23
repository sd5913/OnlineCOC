"""Static browser contract checks; synthetic DTOs, no game host or provider calls."""
import copy
import functools
import json
import secrets
import threading
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

PACK = Path(__file__).resolve().parents[1]


class Quiet(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.js': 'text/javascript', '.css': 'text/css'}

    def do_GET(self):
        if self.path == '/__batch_test__.html':
            body = b'<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/styles.css"><main id="fixture"></main><div id="result"></div>'
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def log_message(self, *_):
        pass


def main():
    output = PACK / 'tests/output' / ('batch-details-' + secrets.token_hex(4))
    output.mkdir(parents=True)
    report = {'checkedAt': datetime.now().astimezone().isoformat(), 'checks': [],
              'realProviderCalls': 0, 'realSaveChanged': False,
              'scope': 'synthetic DTO browser presentation; does not prove engine atomicity',
              'evidenceDirectory': output.relative_to(PACK).as_posix()}
    fixture = {'kind': 'runtime', 'rulingId': 'batch:fixture', 'digest': 'fixture-digest',
               'status': 'pending', 'canDecide': True, 'createdAt': 1795170000,
               'summary': '消耗口粮，短休，再通知玩家。',
               'actions': [
                   {'target': 'host', 'op': 'action.invoke', 'args': {'actionId': 'sv.inventory', 'input': {'actor': 'actor-fixture', 'operation': 'use', 'slot': 5, 'value': 1}}},
                   {'target': 'host', 'op': 'action.invoke', 'args': {'actionId': 'sv.rest', 'input': {'actor': 'actor-fixture', 'kind': 'short', 'attribute': ''}}},
                   {'target': 'host', 'op': 'notification.send', 'args': {'recipientAccountIds': ['player1'], 'text': '已完成', 'sourceActionIndex': 1}}],
               'preflight': {'status': 'runtime_required', 'items': [
                   {'index': 0, 'status': 'passed', 'ruleId': 'sv.inventory'}, {'index': 1, 'status': 'runtime_required', 'code': 'BATCH_RUNTIME_REQUIRED', 'reason': '需要正式运行判定'}, {'index': 2, 'status': 'passed'}]}}
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(PACK / 'ui')))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    page_errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width': 1280, 'height': 960})
            page.on('pageerror', lambda e: page_errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{server.server_port}/__batch_test__.html')
            page.evaluate("""async item => {
                window.batchUI=await import('/batch-details.js');
                window.rulingsUI=await import('/keeper-rulings.js');
                window.item=item;window.notices=[];window.calls=[];
                const client={aiRulings:async()=>({items:[window.item]}),aiResolve:async()=>({items:[]})};
                const module={mountMarkdown:(target,text)=>{target.textContent=text;return{destroy(){}}}};
                window.view=window.rulingsUI.mountPackageRulings(document.querySelector('#fixture'),client,module,{
                    authorized:()=>true,onNotice:value=>window.notices.push(value),
                    command:async(op,args)=>{window.calls.push({op,args});return new Promise(resolve=>window.complete=value=>{window.item={...window.item,...value};resolve(value)})}
                });
            }""", fixture)
            page.locator('[data-open]').click()
            dialog = page.locator('dialog.ruling-dialog')
            expect(dialog.locator('ol>li')).to_have_count(3)
            expect(dialog.locator('ol>li').nth(0)).to_contain_text('使用物品 · 槽位 5')
            expect(dialog.locator('ol>li').nth(1)).to_contain_text('预检查：需运行判定')
            expect(dialog.locator('ol>li').nth(2)).to_contain_text('通知玩家 · player1')
            expect(dialog).to_contain_text('尚未执行')
            expect(dialog.locator('.batch-action-reason')).to_have_count(0)
            report['checks'].append('ordered-actions-and-non-guaranteed-preflight')

            dialog.get_by_role('button', name='接受并执行', exact=True).click()
            expect(page.locator('dialog.ruling-dialog')).to_have_count(0)
            assert page.evaluate('window.calls.length') == 1
            assert page.evaluate('window.notices.at(-1).status') == 'processing'
            report['checks'].append('dialog-closes-before-command-result')
            outcome = {'status': 'rolled_back', 'execution': {'status': 'rolled_back', 'committedCount': 0, 'failedCount': 1, 'notExecutedCount': 1, 'rolledBackCount': 1, 'items': [
                {'index': 0, 'status': 'rolled_back', 'commandId': 'cmd-0', 'result': {'passed': False}},
                {'index': 1, 'status': 'failed', 'commandId': 'cmd-1', 'code': 'RULE_FAILED', 'reason': '规则前置条件不满足', 'ruleCode': 'SV_DEAD_CANNOT_REST', 'ruleId': 'sv.rest'},
                {'index': 2, 'status': 'not_executed'}]}}
            page.evaluate('value=>window.complete(value)', outcome)
            page.wait_for_function('window.notices.at(-1).status === "rolled_back"')
            saved = page.evaluate('JSON.parse(JSON.stringify(window.notices.at(-1)))')
            assert saved['locator']['hostCommandId'] == 'cmd-1'
            assert 'args' not in saved['batch']['actions'][0]
            page.evaluate('value=>document.querySelector("#result").innerHTML=window.batchUI.batchDetailsHTML(value.batch)', saved)
            result = page.locator('#result')
            expect(result).to_contain_text('已提交 0 · 失败 1 · 未执行 1')
            expect(result).to_contain_text('已撤销，未生效')
            expect(result).not_to_contain_text('规则已正常结算')
            expect(result).to_contain_text('角色已死亡，不能通过休息恢复')
            expect(result).to_contain_text('SV_DEAD_CANNOT_REST')
            expect(result).to_contain_text('cmd-1')
            assert page.evaluate('window.notices.at(-1).batch.execution.rolledBackCount') == 1
            report['checks'].append('notification-retains-per-action-outcome-and-locator')

            blocked = copy.deepcopy(fixture)
            blocked['preflight'] = {'status': 'blocked', 'items': [{'index': 0, 'status': 'blocked', 'code': 'SLOT_INVALID', 'reason': '第3槽不是口粮'}]}
            page.evaluate('async value=>{window.item=value;await window.view.refresh()}', blocked)
            page.locator('[data-open]').click()
            expect(dialog.get_by_role('button', name='接受并执行', exact=True)).to_have_count(0)
            expect(dialog).to_contain_text('第3槽不是口粮')
            dialog.locator('[data-close]').click()
            report['checks'].append('blocked-preflight-cannot-be-approved-in-package-ui')

            legacy = copy.deepcopy(fixture)
            legacy.update(status='partial', canDecide=False, receipts=[{'id': 'legacy-command-0', 'target': 'host', 'receipt': {'status': 'rejected', 'code': 'RULE_FAILED'}}])
            legacy.pop('preflight')
            page.evaluate('value=>document.querySelector("#result").innerHTML=window.batchUI.batchDetailsHTML(value)', legacy)
            expect(result).to_contain_text('已提交 0 · 失败 1 · 未执行 2')
            expect(result).to_contain_text('旧记录为逐项执行')
            expect(result).not_to_contain_text('已撤销')
            report['checks'].append('legacy-first-rejection-is-zero-success-without-invented-rollback')

            unknown = copy.deepcopy(fixture)
            unknown.update(status='unknown', canDecide=False, receipts=[{'id': 'unknown-command-0', 'receipt': {'status': 'pending'}}])
            page.evaluate('async value=>{window.item=value;await window.view.refresh()}', unknown)
            page.locator('[data-open]').click()
            expect(dialog.get_by_role('button', name='核对原执行回执', exact=True)).to_be_visible()
            expect(dialog.get_by_role('button', name='接受并执行', exact=True)).to_have_count(0)
            expect(dialog).to_contain_text('未提供执行回执')
            expect(dialog).not_to_contain_text('已提交 0')
            dialog.locator('[data-close]').click()
            report['checks'].append('unknown-is-not-guessed-as-failure-or-success')

            business = copy.deepcopy(fixture)
            business.update(status='completed', execution={'status': 'completed', 'items': [
                {'index': 0, 'status': 'committed', 'result': {'public': {'outcome': 'blocked'}}},
                {'index': 1, 'status': 'committed', 'result': {'passed': False}},
                {'index': 2, 'status': 'committed'}]})
            page.evaluate('value=>document.querySelector("#result").innerHTML=window.batchUI.batchDetailsHTML(window.batchUI.batchNoticeSnapshot(value))', business)
            expect(result).not_to_contain_text('BATCH_RUNTIME_REQUIRED')
            expect(result).to_contain_text('执行前检查')
            expect(result).to_contain_text('条件不足，目标未完成')
            expect(result).to_contain_text('规则已正常结算；不会自动重掷')
            expect(result).not_to_contain_text('已撤销')
            report['checks'].append('business-outcome-is-distinct-from-transaction-commit')

            hostile = copy.deepcopy(fixture)
            hostile.update(outcome)
            hostile['execution']['items'][1]['reason'] = '<img src=x onerror="window.injected=true">' + '很长的诊断内容' * 30
            page.set_viewport_size({'width': 390, 'height': 844})
            page.evaluate('async value=>{window.item=value;await window.view.refresh();window.view.setHistory(true)}', hostile)
            page.locator('[data-open]').click()
            expect(dialog.locator('img')).to_have_count(0)
            assert not page.evaluate('Boolean(window.injected)')
            assert dialog.evaluate('(el)=>el.scrollWidth<=el.clientWidth+1')
            page.screenshot(path=str(output / 'batch-mobile.png'), full_page=True)
            report['checks'].append('diagnostic-escaping-and-mobile-layout')
            assert page.evaluate('window.rulingsUI.rulingIsArchived({status:"rolled_back"})')
            assert not page.evaluate('window.rulingsUI.rulingIsArchived({status:"unknown"})')
            assert not page_errors, page_errors
            report['checks'].append('terminal-archive-and-no-browser-errors')
            page.evaluate('window.view.destroy()')
            page.evaluate("""async full=>{
                window.view.destroy();
                window.detailsFetched=0;
                window.pageCalls=[];
                const client={
                  aiRulings:async options=>{
                    window.pageCalls.push(options);
                    const first=!options.before;
                    const id=first?'batch:current':'batch:earlier';
                    return {items:[{...full,rulingId:id,summary:id,compact:true,canDecide:false,actions:[]}],
                            activeCount:2,nextBefore:first?'batch:current':null};
                  },
                  aiRuling:async id=>{window.detailsFetched++;return {...full,rulingId:id};}
                };
                const module={mountMarkdown:(target,text)=>{target.textContent=text;return{destroy(){}}}};
                window.view=window.rulingsUI.mountPackageRulings(document.querySelector('#fixture'),client,module,
                    {authorized:()=>true,onNotice:()=>{}});
            }""", fixture)
            page.get_by_role('button',name='查看较早裁决').click()
            expect(page.locator('[data-ruling-id="batch:earlier"]')).to_have_count(1)
            assert page.evaluate('window.detailsFetched') == 0
            page.locator('[data-open]').click()
            expect(page.locator('dialog ol>li')).to_have_count(3)
            assert page.evaluate('window.detailsFetched') == 1
            page.locator('dialog [data-close]').click()
            page.get_by_role('button',name='返回较新裁决').click()
            expect(page.locator('[data-ruling-id="batch:current"]')).to_have_count(1)
            report['checks'].append('compact-pages-navigate-and-fetch-exact-detail-before-approval')
            browser.close()
        report['passed'] = True
    except Exception as exc:
        report.update(passed=False, errorType=type(exc).__name__, error=str(exc)[:3000])
    finally:
        server.shutdown()
        server.server_close()
    report.update(passedCount=len(report['checks']), pageErrors=page_errors)
    canonical = PACK / 'tests/batch-details-results.json'
    if canonical.exists():
        previous = json.loads(canonical.read_text(encoding='utf-8'))
        report['previousRuns'] = [*previous.get('previousRuns', []), {k: previous.get(k) for k in ('passed', 'checks', 'error', 'evidenceDirectory')}]
    for path in (output / 'report.json', canonical):
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report.get(k) for k in ('passed', 'passedCount', 'error', 'evidenceDirectory')}, ensure_ascii=True))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
