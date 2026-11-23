"""C assessment presentation and explicit proof submission with synthetic DTOs."""
import copy
from datetime import datetime
import functools
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
from playwright.sync_api import sync_playwright, expect
from verify_batch_details import Quiet, PACK


def main():
    output=PACK/'tests/output'/('c-review-ui-'+secrets.token_hex(4));output.mkdir(parents=True)
    report={'at':datetime.now().astimezone().isoformat(),'checks':[],'realApiCalls':0,'scope':'synthetic DTO, actual Edge, no server policy proof','output':str(output)}
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(PACK/'ui')))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    item={'kind':'configuration','rulingId':'proposal:synthetic-c','revision':1,'digest':'candidate-digest','status':'pending','canDecide':True,'canRevalidate':True,'highRisk':True,'createdAt':1795192000,
          'summary':'补充一项尚无作者实况场景覆盖的规则说明。','risks':[{'id':'gameplay-risk'}],
          'cAssessment':{'basisRevision':2,'basisDigest':'b'*64,'reportDigest':'c'*64,'requiresAcceptance':True,'adoptable':True,'stale':False,
              'findings':[{'code':'LIVE_SCENARIO_COVERAGE_MISSING','severity':'error','message':'此改动未被现有实况场景覆盖','path':'/rules/example.lua','evidence':{'changed':['example.lua'],'covered':[]},'suggestion':'请核对规则含义并决定是否采用。'}],
              'limitations':['评估未证明所有旧存档的玩法效果。']},
          'reports':[{'findings':[{'severity':'error','code':'LIVE_SCENARIO_COVERAGE_MISSING','message':'未覆盖'}]}]}
    errors=[]
    item['continuation'] = {'status':'waiting_publication'}
    item['changeOverview'] = {'total':2,'truncated':False,'items':[
        {'path':'/data/game.json/items/28','operation':'add','summary':'新增物品：测试盾'},
        {'path':'/sources/new.lua','operation':'add','summary':'<img src=x onerror=window.injected=true>'}]}
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            page=browser.new_page(viewport={'width':1280,'height':900});page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{server.server_port}/__batch_test__.html')
            page.evaluate('''async item=>{
                window.item=item;window.calls=[];window.notices=[];
                const {mountPackageRulings}=await import('/keeper-rulings.js');
                const client={aiRulings:async()=>({items:[window.item]}),aiResolve:async()=>({items:[]})};
                window.view=mountPackageRulings(document.querySelector('#fixture'),client,{mountMarkdown:(el,text)=>{el.textContent=text;return{destroy(){}}}},
                    {authorized:()=>true,onNotice:v=>window.notices.push(v),command:async(op,args)=>{
                        window.calls.push({op,args});
                        return new Promise(resolve=>window.complete=v=>{window.item={...window.item,...v};resolve(v)});
                    }});
            }''',item)
            page.locator('[data-open]').click();dialog=page.locator('dialog.ruling-dialog')
            expect(dialog.locator('.continuation-status')).to_have_text('发布后继续 · 等待配置发布')
            changes=dialog.locator('details.ruling-changes')
            assert not changes.evaluate('el=>el.open')
            changes.locator('summary').click()
            expect(changes.locator('li')).to_have_count(2)
            expect(changes).to_contain_text('config/game.json · items / 28')
            expect(changes).to_contain_text('rules/new.lua')
            assert not changes.locator('img').count()
            changes.locator('summary').click()
            report['checks'].append('concrete file, target and summary for each change; collapsed by default, literal HTML text')
            expect(dialog.locator('.c-review-assessment')).to_contain_text('判断依据版本 2')
            expect(dialog.locator('.c-review-assessment')).to_contain_text('LIVE_SCENARIO_COVERAGE_MISSING')
            expect(dialog.locator('textarea')).to_have_count(1)
            expect(dialog.locator('.ruling-decision-actions button')).to_have_count(3)
            expect(dialog.locator('.notice.error')).to_have_count(0)
            page.screenshot(path=str(output/'c-review-desktop.png'))
            report['checks'].append('C risk is readable with basis version, evidence, limitations, three actions and optional note')
            dialog.get_by_role('button',name='采纳评估并发布',exact=True).click()
            expect(dialog).to_have_count(0)
            call=page.evaluate('window.calls.at(-1)')
            assert call['op']=='ai.ruling.decide' and call['args']['cReview']=={k:item['cAssessment'][k] for k in ['basisRevision','basisDigest','reportDigest']}
            page.evaluate('value=>window.complete(value)',{**item,'status':'published'})
            page.wait_for_function('window.notices.at(-1).status === "published"')
            assert '采纳' in page.evaluate('window.notices.at(-1).reason')
            report['checks'].append('explicit adopt button submits exact C proof, closes immediately and reports publication separately from warning')
            page.evaluate('async v=>{window.item=v;await window.view.refresh()}',item)
            page.locator('[data-open]').click();dialog.get_by_role('button',name='拒绝',exact=True).click()
            assert 'cReview' not in page.evaluate('window.calls.at(-1).args')
            page.evaluate('value=>window.complete(value)',{'status':'rejected'})
            page.wait_for_function('window.notices.at(-1).status === "rejected"')
            report['checks'].append('reject does not submit C acceptance')
            stale=copy.deepcopy(item);stale.update(status='blocked',canDecide=False);stale['cAssessment']['stale']=True
            page.evaluate('async v=>{window.item=v;await window.view.refresh()}',stale)
            page.locator('[data-open]').click()
            expect(dialog.get_by_role('button',name='采纳评估并发布',exact=True)).to_have_count(0)
            dialog.get_by_role('button',name='重新检查',exact=True).click()
            page.wait_for_function('window.calls.at(-1).op === "ai.proposal.validate"')
            assert page.evaluate('window.calls.at(-1).args')=={'proposalId':'synthetic-c','revision':1}
            page.evaluate('value=>window.complete(value)',{**item,'proposal':{'status':'review_ready'},'revision':1})
            page.wait_for_function('window.notices.at(-1).status === "pending"')
            report['checks'].append('stale basis disables approval and rechecks the same proposal revision')
            hostile=copy.deepcopy(item);hostile['cAssessment']['findings'][0]['message']='<img src=x onerror="window.injected=1">'+('具体风险说明'*20)
            page.set_viewport_size({'width':390,'height':844})
            page.evaluate('async v=>{window.item=v;await window.view.refresh()}',hostile)
            page.locator('[data-open]').click()
            expect(dialog.locator('img')).to_have_count(0)
            assert not page.evaluate('Boolean(window.injected)')
            assert dialog.evaluate('el=>el.scrollWidth<=el.clientWidth+1')
            page.screenshot(path=str(output/'c-review-mobile.png'),full_page=True)
            assert not errors,errors
            report['checks'].append('long C findings escape HTML and fit 390px without script errors')
            page.evaluate('window.view.destroy()');browser.close()
        report['passed']=True
    except Exception as exc:report.update(passed=False,error=str(exc))
    finally:
        server.shutdown();server.server_close();thread.join(3)
        dest=PACK/'tests/c-review-ui-results.json'
        if dest.exists():
            old=json.loads(dest.read_text(encoding='utf-8'));report['previousRuns']=old.get('previousRuns',[])+[{k:v for k,v in old.items() if k!='previousRuns'}]
        dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
