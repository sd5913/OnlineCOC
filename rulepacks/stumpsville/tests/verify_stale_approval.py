"""Real restart, stale high-risk approval and package UI revalidation; no model calls."""
import copy
import json
import secrets
from datetime import datetime

from harness import PACK, Account, running, provision
from verify_integrations import ai, provider, result
from integrations import write_json
from playwright.sync_api import expect, sync_playwright


def main():
    output=PACK/'tests/output'/('stale-approval-'+secrets.token_hex(4));output.mkdir(parents=True)
    prior=PACK/'tests/stale-approval-results.json'
    report={'checkedAt':datetime.now().astimezone().isoformat(),'checks':[],
            'realSaveChanged':False,'realProviderCalls':0,'evidenceDirectory':output.relative_to(PACK).as_posix()}
    if prior.exists():
        old=json.loads(prior.read_text(encoding='utf-8'))
        report['previousRuns']=[*old.get('previousRuns',[]),{k:old.get(k) for k in ['passed','error','checks','evidenceDirectory']}]
    errors=[]
    try:
        with provider(output) as (config,calls):
            with running('stale-before',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
                kp,_,_=provision(runtime,password)
                before=kp.request('/package/bundle');old_epoch=kp.request('/api/v1/view')['authorityEpoch']
                records=[]
                for suffix in ['a','b']:
                    game=copy.deepcopy(before['data']['game.json'])
                    game['items'].append({'id':'stale-pot-lid-'+suffix,'name':'锅盖重检'+suffix,'kind':'armor','shape':'offhand','slots':1,'armor':1,'uses':3,'useDie':True,'description':'隔离审批恢复验收'})
                    draft=result(ai(kp,'ai.draft.create',{'text':'追加锅盖，保留既有编号','changeSet':{'schemaVersion':1,'configurations':[],'sources':{},'data':{'game.json':game},'suggestions':[]}}))
                    checked=result(ai(kp,'ai.proposal.validate',{'proposalId':draft['proposalId'],'revision':1}))
                    assert checked['proposal']['status']=='review_ready',checked
                    records.append(draft)
            with running('stale-after',data=output/'game',ai_config=config,no_browser=True) as (runtime,_):
                kp=Account(runtime.origin,'kp',password,'stale-api')
                assert kp.request('/api/v1/view')['authorityEpoch']!=old_epoch
                def ruling(pid):return next(x for x in kp.request('/api/v1/ai/rulings')['items'] if x['rulingId']=='proposal:'+pid)
                for draft in records:
                    row=ruling(draft['proposalId']);assert row['status']=='pending'
                    denied=result(ai(kp,'ai.ruling.decide',{'rulingId':row['rulingId'],'digest':row['digest'],'decision':'approve','explicitHighRiskDigest':row['digest'],'riskDecisions':{r['id']:'隔离验收明确接受' for r in row['risks']}}))
                    assert denied['status']=='blocked' and denied['receipts'][0]['code']=='STALE_AUTHORITY',denied
                assert kp.request('/package/bundle')['data']==before['data']
                report['checks'].append('真实同档重启后，旧高危候选批准返回STALE_AUTHORITY；三检通过但未发布')
                first,second=[r['proposalId'] for r in records]
                with sync_playwright() as pw:
                    browser=pw.chromium.launch(channel='msedge',headless=True)
                    page=browser.new_page(viewport={'width':1440,'height':960});page.on('pageerror',lambda e:errors.append(str(e)));expect.set_options(timeout=30000)
                    try:
                        page.goto(runtime.origin+'/sessions/stale-browser/')
                        page.locator('[name=loginName]').fill('kp');page.locator('[name=password]').fill(password)
                        page.get_by_role('button',name='进入冒险',exact=True).click();page.locator('.identity').first.wait_for()
                        page.goto(runtime.origin+'/sessions/stale-browser/#/gm/rulings')
                        card=page.locator('[data-ruling-id="proposal:'+first+'"]');expect(card).to_be_visible()
                        card.get_by_role('button',name='查看并裁决',exact=True).click()
                        detail=page.locator('.ruling-dialog');expect(detail).to_contain_text('房间已重启或执行权限已换代')
                        expect(detail.get_by_role('button',name='重新检查',exact=True)).to_be_visible()
                        page.screenshot(path=str(output/'stale-recheck.png'),full_page=True)
                        sent=[]
                        def capture(route):sent.append(route.request.post_data_json);route.continue_()
                        page.route('**/api/v1/ai/drafts',capture);page.route('**/api/v1/ai/commands',capture)
                        detail.get_by_role('button',name='重新检查',exact=True).click();expect(detail).to_have_count(0)
                        expect(card).to_contain_text('等待 KP 裁决',timeout=60000)
                        renewed=ruling(first)
                        assert renewed['revision']==2 and renewed['digest']==records[0]['candidateDigest'] and renewed['status']=='pending'
                        assert kp.request('/package/bundle')['data']==before['data']
                        assert [x['op'] for x in sent]==['ai.proposal.revise','ai.proposal.validate'],sent
                        assert set(sent[0]['args']['changeSet']['data'])=={'game.json'} and not sent[0]['args']['changeSet']['sources']
                        report['checks'].append('界面解释失效原因；相同内容重检提升修订并更新审批上下文，指纹可保持相同，不执行且不调用模型')
                        card.get_by_role('button',name='查看并裁决',exact=True).click()
                        expect(page.locator('.ruling-dialog textarea')).to_have_count(1)
                        page.locator('.ruling-dialog').get_by_role('button',name='接受并执行',exact=True).click();expect(page.locator('.ruling-dialog')).to_have_count(0)
                        expect(card).to_have_count(0,timeout=60000)
                        applied=ruling(first);assert applied['status']=='completed' and len(applied['publications'])==1
                        items=kp.request('/package/bundle')['data']['game.json']['items']
                        assert sum(x['id']=='stale-pot-lid-a' for x in items)==1
                        assert sent[-1]['args']['explicitHighRiskDigest']==renewed['digest']
                        report['checks'].append('重新人工接受后按当前修订和整包指纹发布一次；可选备注和提交即关闭继续有效')
                        conflicting=page.locator('[data-ruling-id="proposal:'+second+'"]')
                        conflicting.get_by_role('button',name='查看并裁决',exact=True).click()
                        count=len(sent);page.locator('.ruling-dialog').get_by_role('button',name='重新检查',exact=True).click()
                        expect(page.locator('#toast')).to_contain_text('不能直接沿用旧内容')
                        assert len(sent)==count and ruling(second)['revision']==1
                        assert kp.request('/package/bundle')['data']['game.json']['items']==items
                        report['checks'].append('相关配置已变化时重检拒绝覆写；不创建新修订、不发布过期整文件')
                        page.get_by_role('tab',name='消息队列',exact=True).click()
                        notice=page.locator('#message-queue-list .ruling-card').filter(has_text='不能直接沿用旧内容').first
                        notice.get_by_role('button',name='详情与定位').click()
                        expect(page.locator('#dialog')).to_contain_text('ai-ruling:'+second+':1:approve')
                        expect(page.locator('#dialog')).to_contain_text('proposal:'+second)
                        page.screenshot(path=str(output/'conflict-location.png'),full_page=True)
                        report['checks'].append('失败通知保留原提案、版本、指纹及宿主批准命令定位')
                        assert not errors,errors
                    except Exception:
                        page.screenshot(path=str(output/'failure.png'),full_page=True);raise
                    finally:browser.close()
            assert not calls,calls
        report['passed']=True
    except Exception as e:report.update(passed=False,errorType=type(e).__name__,error=str(e)[:3000])
    report['pageErrors']=errors;report['passedCount']=len(report['checks'])
    write_json(output/'report.json',report);write_json(prior,report)
    print(json.dumps({k:report.get(k) for k in ['passed','passedCount','errorType','error','evidenceDirectory']},ensure_ascii=True),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
