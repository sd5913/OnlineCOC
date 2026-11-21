"""Package reference-risk decisions in a real browser; synthetic server DTOs."""
import copy
from datetime import datetime
import functools
from http.server import ThreadingHTTPServer
import json
import secrets
import threading

from playwright.sync_api import sync_playwright, expect
from verify_batch_details import Quiet, PACK


def main():
    output = PACK/'tests/output'/('consultation-review-'+secrets.token_hex(4))
    output.mkdir(parents=True)
    report = {'at': datetime.now().astimezone().isoformat(), 'checks': [], 'externalApiCalls': 0,
              'scope': 'Synthetic DTO with actual package UI; server authorization tested separately', 'output': str(output)}
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(PACK/'ui')))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    item = {'kind': 'configuration', 'rulingId': 'proposal:reference-risk', 'digest': 'candidate-proof', 'revision': 1,
            'status': 'pending', 'canDecide': True, 'canRevalidate': True, 'highRisk': True, 'createdAt': 1795245000,
            'summary': '依据主持手记补充机关说明，当前配置已重新读取。', 'risks': [{'id': 'reference-source'}],
            'consultationAssessment': {'requiresAcceptance': True, 'sourceCount': 2, 'sourceDigest': 'a'*64,
                                       'notice': '手记与当前配置可能不同；请确认机关含义与受影响范围。'},
            'cAssessment': {'requiresAcceptance': True, 'adoptable': True, 'stale': False, 'basisRevision': 3,
                            'basisDigest': 'b'*64, 'reportDigest': 'c'*64, 'findings': [], 'limitations': []}}
    errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width': 1280, 'height': 900})
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}/__batch_test__.html')
            page.evaluate('''async item=>{
                window.item=item;window.calls=[];window.notices=[];
                const {mountPackageRulings}=await import('/keeper-rulings.js');
                window.view=mountPackageRulings(document.querySelector('#fixture'),
                    {aiRulings:async()=>({items:[window.item]}),aiResolve:async()=>({items:[]})},
                    {mountMarkdown:(el,text)=>{el.textContent=text;return{destroy(){}}}},
                    {authorized:()=>true,onNotice:n=>window.notices.push(n),command:async(op,args)=>{
                        window.calls.push({op,args});return new Promise(resolve=>window.complete=v=>{
                            window.item={...window.item,...v};resolve(v)});
                    }});
            }''', item)
            dialog = page.locator('dialog.ruling-dialog')
            page.locator('[data-open]').click()
            expect(dialog.locator('.consultation-assessment')).to_contain_text('手记与当前配置可能不同')
            expect(dialog.locator('.consultation-assessment')).to_contain_text('2 项参考来源')
            expect(dialog.locator('.ruling-decision-actions button')).to_have_count(3)
            expect(dialog.locator('textarea')).to_have_count(1)
            assert not page.evaluate('window.calls')
            page.screenshot(path=str(output/'assessment-desktop.png'))
            dialog.get_by_role('button', name='采纳评估并发布', exact=True).click()
            expect(dialog).to_have_count(0)
            sent = page.evaluate('window.calls.at(-1)')
            assert sent['args']['consultationReview'] == {'sourceDigest': 'a'*64}, sent
            assert sent['args']['cReview'] == {key: item['cAssessment'][key] for key in ('basisRevision', 'basisDigest', 'reportDigest')}
            assert sent['args']['explicitHighRiskDigest'] == item['digest']
            assert 'reference-source' in sent['args']['riskDecisions']
            page.evaluate('window.complete({status:"published"})')
            page.wait_for_function('window.notices.at(-1).status==="published"')
            assert '采纳参考资料评估' in page.evaluate('window.notices.at(-1).reason')
            report['checks'].append('reference and C risk are visible; one explicit decision sends both exact proofs and high-risk digest, closes immediately and reports actual publication')

            page.evaluate('async v=>{window.item=v;await window.view.refresh()}', item)
            page.locator('[data-open]').click()
            dialog.get_by_role('button', name='拒绝', exact=True).click()
            sent = page.evaluate('window.calls.at(-1)')
            assert 'consultationReview' not in sent['args'] and 'cReview' not in sent['args']
            page.evaluate('window.complete({status:"rejected"})')
            page.wait_for_function('window.notices.at(-1).status==="rejected"')
            report['checks'].append('rejection never implicitly accepts reference or C assessment')

            missing = copy.deepcopy(item)
            del missing['consultationAssessment']['sourceDigest']
            page.evaluate('async v=>{window.item=v;await window.view.refresh()}', missing)
            page.locator('[data-open]').click()
            expect(dialog.locator('.consultation-assessment')).to_contain_text('评估信息不完整')
            expect(dialog.get_by_role('button', name='采纳评估并发布', exact=True)).to_have_count(0)
            expect(dialog.get_by_role('button', name='重新检查', exact=True)).to_be_visible()
            dialog.locator('[data-close]').click()
            report['checks'].append('missing assessment proof cannot be fabricated or approved by the UI')

            runtime = copy.deepcopy(item)
            runtime.update(kind='runtime', rulingId='batch:reference-risk', highRisk=False)
            runtime.pop('cAssessment')
            runtime['consultationAssessment']['notice'] = '<img src=x onerror="window.injected=1">'+'需要核对参考资料与当前目标。'*24
            page.set_viewport_size({'width': 390, 'height': 844})
            page.evaluate('async v=>{window.item=v;await window.view.refresh()}', runtime)
            page.locator('[data-open]').click()
            expect(dialog.locator('img')).to_have_count(0)
            assert not page.evaluate('Boolean(window.injected)')
            assert dialog.evaluate('el=>el.scrollWidth<=el.clientWidth+1')
            page.screenshot(path=str(output/'assessment-mobile.png'), full_page=True)
            dialog.get_by_role('button', name='采纳评估并执行', exact=True).click()
            sent = page.evaluate('window.calls.at(-1)')
            assert 'explicitHighRiskDigest' not in sent['args'] and 'cReview' not in sent['args']
            assert sent['args']['consultationReview'] == {'sourceDigest': 'a'*64}
            page.evaluate('window.complete({status:"failed",error:"TARGET_CONFLICT"})')
            page.wait_for_function('window.notices.at(-1).status==="failed"')
            assert 'TARGET_CONFLICT' in page.evaluate('window.notices.at(-1).reason')
            report['checks'].append('runtime assessment fits 390px and escapes text; failed execution stays failed with its actual reason')
            assert not errors, errors
            page.evaluate('window.view.destroy()')
            browser.close()
        report['passed'] = True
    except Exception as exc:
        report.update(passed=False, error=repr(exc))
    finally:
        server.shutdown(); server.server_close(); thread.join(3)
    report.update(passedCount=len(report['checks']), pageErrors=errors)
    canonical = PACK/'tests/consultation-review-results.json'
    if canonical.exists():
        old = json.loads(canonical.read_text(encoding='utf-8'))
        report['previousRuns'] = old.get('previousRuns', []) + [{key: value for key, value in old.items() if key != 'previousRuns'}]
    for path in (canonical, output/'results.json'):
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: report.get(key) for key in ('passed', 'passedCount', 'error', 'output')}, ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
