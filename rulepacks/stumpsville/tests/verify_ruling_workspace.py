"""Real package UI: shared cards, explicit high-risk decisions and traceable outcomes."""
import copy
import json
import secrets
from datetime import datetime
from harness import PACK, Account, running
from verify_integrations import provider, ai, result
from integrations import write_json
from playwright.sync_api import sync_playwright, expect


def main():
    output=PACK/'tests/output'/('ruling-workspace-'+secrets.token_hex(4));output.mkdir(parents=True)
    prior=PACK/'tests/ruling-workspace-results.json'
    report={'checkedAt':datetime.now().astimezone().isoformat(),'checks':[],'realSaveChanged':False,'realProviderCalls':0,'evidenceDirectory':output.relative_to(PACK).as_posix()}
    if prior.exists():
        old=json.loads(prior.read_text(encoding='utf-8'));report['previousRuns']=[*old.get('previousRuns',[]),{k:old.get(k) for k in ['passed','error','checks','evidenceDirectory']}]
    errors=[]
    try:
        with provider(output) as (config,calls),running('ruling-workspace',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
            kp,p1,p2=[Account(runtime.origin,n,password,n) for n in ['kp','player1','player2']]
            result(ai(kp,'ai.settings.update',{'enabled':False,'profileId':'offline','externalSources':{'public':True,'kp':True,'private':True},'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}))
            p1.action('draft',{'preset':'mul','name':'木栗'});p2.action('draft',{'preset':'dou','name':'待审核小鼠'})
            kp.action('approve',{'account':'player1'});p1.action('ready',{'ready':True});kp.action('world',{'operation':'start'})
            req=p1.action('request',{'kind':'free','manual':True,'text':'请批准检查门锁'})
            assistance=result(ai(kp,'ai.request.create',{'sourceKind':'manual','text':'请协助核对机关资料'}))
            game=copy.deepcopy(kp.request('/package/bundle')['data']['game.json'])
            game['items'].append({'id':'workspace-lantern','name':'队列验收灯','kind':'item','slots':1,'uses':3,'description':'隔离验收'})
            draft=result(ai(kp,'ai.draft.create',{'text':'追加验收灯，保留旧编号','changeSet':{'schemaVersion':1,'configurations':[],'sources':{},'data':{'game.json':game},'suggestions':[]}}))
            checked=result(ai(kp,'ai.proposal.validate',{'proposalId':draft['proposalId'],'revision':1}));assert checked['proposal']['status']=='review_ready'
            rid='proposal:'+draft['proposalId'];row=next(r for r in kp.request('/api/v1/ai/rulings')['items'] if r['rulingId']==rid);assert row['highRisk']
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True)
                page=browser.new_page(viewport={'width':1440,'height':960});page.on('pageerror',lambda e:errors.append(str(e)));expect.set_options(timeout=30000)
                try:
                    page.goto(runtime.origin+'/sessions/workspace-ui/')
                    page.locator('[name=loginName]').fill('kp');page.locator('[name=password]').fill(password);page.get_by_role('button',name='进入冒险',exact=True).click();page.locator('.identity').first.wait_for()
                    page.goto(runtime.origin+'/sessions/workspace-ui/#/gm/rulings')
                    card=page.locator('[data-ruling-id="'+rid+'"]');expect(card).to_be_visible()
                    for selector in ['[data-draft=player2]','[data-request-id="'+req['requestId']+'"]','[data-ai-request]','[data-ruling-id]']:
                        expect(page.locator(selector).first).to_have_class(__import__('re').compile('ruling-card'))
                        assert page.locator(selector+' .ruling-card-meta').first.locator('time').count()==1
                        expect(page.locator(selector+' .ruling-card-actions').first.locator('button')).to_have_count(3)
                    report['checks'].append('人工建角、行动、AI申请及配置共用卡片元信息和操作排布')
                    page.get_by_role('tab',name='消息队列',exact=True).click();expect(page.locator('#ruling-queue-list')).not_to_be_visible()
                    page.get_by_role('tab',name=__import__('re').compile('裁决队列')).click();expect(card).to_be_visible()
                    assert page.locator('#ruling-queue-list .activity-feed').count()==0
                    page.screenshot(path=str(output/'workspace-desktop.png'),full_page=True)
                    report['checks'].append('消息与裁决使用同一区域标签；记录不占主队列')
                    editor=page.locator('#kp-ai-embedded .reference-editor');editor.fill('/')
                    page.get_by_role('option',name='/entity',exact=False).click()
                    editor.fill('/entity 木栗')
                    page.get_by_role('option',name='木栗',exact=False).click()
                    page.locator('#kp-ai-embedded #preview').click()
                    expect(page.locator('#reference-preview')).to_be_visible()
                    expect(page.locator('#reference-preview .stumpsville-reference .stat')).to_have_count(3)
                    expect(page.locator('#reference-preview .stumpsville-reference')).to_contain_text('木栗')
                    expect(page.locator('#reference-preview .stumpsville-reference button')).to_have_count(0)
                    page.screenshot(path=str(output/'reference-integrated.png'),full_page=True)
                    editor.fill('')
                    report['checks'].append('真实包页面引用预览经通用组件传递授权DTO，以共用角色卡显示且无执行按钮')
                    def stale_task(route):
                        response=route.fetch();value=response.json()
                        for item in value['items']:
                            if item['requestId']==assistance['requestId']:
                                item.update(status='stale',sourceState='stale',sourceNotice='依赖资料已过时；这里只保留历史内容。',historicalReadOnly=True,response='历史回复：仍保留该申请内容。')
                        route.fulfill(response=response,json=value)
                    page.route('**/api/v1/ai/tasks*',stale_task)
                    assistance_card=page.locator('[data-ai-request="'+assistance['requestId']+'"]')
                    expect(assistance_card).to_have_class(__import__('re').compile('ruling-stale'))
                    expect(assistance_card.locator('.source-stale')).to_have_count(0)
                    expect(assistance_card).to_contain_text('请协助核对机关资料')
                    assistance_card.locator('.queue-summary').click()
                    request_detail=page.locator('.ai-request-detail:not(.ruling-history)')
                    expect(request_detail).to_have_attribute('title','依赖资料已过时；这里只保留历史内容。')
                    request_detail.locator('details summary').first.click()
                    expect(request_detail).to_contain_text('历史回复：仍保留该申请内容。')
                    request_detail.locator('[data-close]').click()
                    page.unroute('**/api/v1/ai/tasks*',stale_task)
                    report['checks'].append('包侧过期DTO以灰底替代绿色提醒，卡片与详情保留请求正文和历史回答')
                    for width in [1440,390]:
                        page.set_viewport_size({'width':width,'height':960 if width==1440 else 844})
                        expect(card).to_be_visible();card.get_by_role('button',name='查看并裁决',exact=True).click()
                        detail=page.locator('.ruling-dialog');expect(detail).to_be_visible()
                        expect(detail.locator('textarea')).to_have_count(1);expect(detail.get_by_label('备注（可选）')).to_be_visible()
                        expect(detail.locator('.ruling-decision-actions button')).to_have_count(3)
                        assert detail.locator('label').all_text_contents()==['备注（可选）','包含当前可见正文（可能含私密资料）']
                        if width==390:
                            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
                            box=detail.bounding_box();assert box['x']>=0 and box['x']+box['width']<=391
                        page.screenshot(path=str(output/('decision-'+str(width)+'.png')),full_page=True)
                        detail.get_by_role('button',name='关闭详情',exact=True).click()
                    report['checks'].append('高危详情桌面与390px均为三个操作、一个可选备注，无原风险问答框及横向溢出')
                    page.set_viewport_size({'width':1440,'height':960})
                    card.get_by_role('button',name='查看并裁决',exact=True).click()
                    page.locator('.ruling-dialog').get_by_role('button',name='转 AI 处理',exact=True).click();expect(page.locator('.ruling-dialog')).to_have_count(0)
                    expect(page.locator('#toast')).to_contain_text('已转交 AI')
                    assert next(r for r in kp.request('/api/v1/ai/rulings')['items'] if r['rulingId']==rid)['status']=='pending'
                    report['checks'].append('详情转AI立即关闭并通知，原高危裁决仍待审核且无模型调用')
                    seen=[];denied=[]
                    def fail_once(route):
                        body=route.request.post_data_json
                        if body.get('op')=='ai.ruling.decide':
                            seen.append(body)
                            if not denied:
                                denied.append(body['requestId']);route.fulfill(status=403,content_type='application/json',body='{"code":"PERMISSION_DENIED"}');return
                        route.continue_()
                    page.route('**/api/v1/ai/commands',fail_once)
                    card.get_by_role('button',name='查看并裁决',exact=True).click();page.locator('.ruling-dialog').get_by_role('button',name='接受并执行',exact=True).click()
                    expect(page.locator('.ruling-dialog')).to_have_count(0)
                    expect(page.locator('#toast')).to_contain_text('无权执行')
                    page.get_by_role('tab',name='消息队列',exact=True).click();notice=page.locator('#message-queue-list .ruling-card').filter(has_text='无权执行').first
                    notice.get_by_role('button',name='详情与定位').click();expect(page.locator('#dialog')).to_contain_text(rid);expect(page.locator('#dialog')).to_contain_text(denied[0]);page.locator('#dialog [data-action=close]').first.click()
                    report['checks'].append('明确403失败立即关闭详情，消息有可读原因、原裁决及命令定位，未发布')
                    page.get_by_role('tab',name=__import__('re').compile('裁决队列')).click();card.get_by_role('button',name='查看并裁决',exact=True).click()
                    page.locator('.ruling-dialog').get_by_role('button',name='接受并执行',exact=True).click();expect(page.locator('.ruling-dialog')).to_have_count(0)
                    expect(card).to_have_count(0,timeout=60000)
                    assert seen[-1]['args']['explicitHighRiskDigest']==row['digest']
                    assert set(seen[-1]['args']['riskDecisions'])=={r['id'] for r in row['risks']}
                    assert all('KP 点击接受并执行' in v for v in seen[-1]['args']['riskDecisions'].values())
                    assert sum(i['id']=='workspace-lantern' for i in kp.request('/package/bundle')['data']['game.json']['items'])==1
                    report['checks'].append('空备注明确批准仍提交全部风险ID及精确高危指纹，真实发布一次')
                    human=page.locator('[data-request-id="'+req['requestId']+'"]');human.get_by_role('button',name='处理',exact=True).click()
                    page.locator('#ruling-form [name=approve]').select_option('no');page.locator('#ruling-form [data-ruling-reply] summary').click();page.locator('#ruling-form [name=reason]').fill('门后危险，暂不允许')
                    page.locator('#ruling-form [type=submit]').click();expect(page.locator('#dialog')).not_to_be_visible()
                    expect(human).to_have_count(0);assert next(r for r in p1.state()['requests'] if r['id']==req['requestId'])['reason']=='门后危险，暂不允许'
                    page.get_by_role('tab',name='消息队列',exact=True).click();expect(page.locator('#message-queue-list')).to_contain_text('门后危险，暂不允许')
                    report['checks'].append('人工拒绝关闭窗口、通知保留原因，服务端与原玩家读取一致')
                    page.get_by_role('tab',name='已归档',exact=True).click()
                    expect(page.locator('#ruling-queue-list [data-ruling-id="'+rid+'"]')).to_be_visible()
                    expect(page.locator('[data-archived-request="'+req['requestId']+'"]')).to_contain_text('已拒绝')
                    expect(page.locator('[data-archived-draft=player1]')).to_be_visible()
                    expect(page.locator('[data-pending-rulings]')).to_be_hidden()
                    page.set_viewport_size({'width':390,'height':844})
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
                    page.screenshot(path=str(output/'archived-390.png'),full_page=True)
                    page.set_viewport_size({'width':1440,'height':960})
                    page.get_by_role('tab',name=__import__('re').compile('裁决队列')).click()
                    expect(page.locator('#ruling-queue-list [data-ruling-id="'+rid+'"]')).to_have_count(0)
                    expect(page.locator('[data-draft=player2]')).to_be_visible()
                    report['checks'].append('处理后的AI裁决、人工拒绝和已批准角色自动进入已归档标签；待审角色仍在原队列，390px无横向溢出')
                    page.locator('[data-action=ruling-history]').click();expect(page.locator('.ruling-history')).to_be_visible();expect(page.locator('.ruling-history')).to_contain_text('裁决与行动记录');expect(page.locator('.ruling-history [data-ruling-id="'+rid+'"]')).to_be_visible()
                    page.locator('[data-close-history]').click();expect(page.locator('.ruling-history')).to_have_count(0)
                    page.reload();page.get_by_role('tab',name='消息队列',exact=True).click();expect(page.locator('#message-queue-list')).to_contain_text('门后危险，暂不允许')
                    report['checks'].append('顶部记录子窗口展示已完成AI与人工历史；结果消息刷新后仍可追溯')
                    lost=[]
                    def lose_forward(route):
                        body=route.request.post_data_json
                        if body.get('op')=='ai.review.create':
                            lost.append(body['requestId']);route.fulfill(status=503,content_type='application/json',body='{"code":"SERVICE_UNAVAILABLE"}');return
                        route.continue_()
                    page.route('**/api/v1/ai/commands',lose_forward)
                    page.locator('.keeper-ai-queue').wait_for(state='attached')
                    page.locator('[data-action=ruling-history]').click()
                    page.locator('.ruling-history [data-ruling-id="'+rid+'"]').get_by_role('button',name='查看并裁决',exact=True).click()
                    page.locator('.ruling-dialog').get_by_role('button',name='转 AI 处理',exact=True).click();expect(page.locator('.ruling-dialog')).to_have_count(0)
                    expect(page.locator('#toast')).to_contain_text('结果待核对')
                    page.locator('[data-close-history]').click()
                    notice=page.locator('#message-queue-list .ruling-card').filter(has_text='SERVICE_UNAVAILABLE').first
                    notice.get_by_role('button',name='详情与定位').click();expect(page.locator('#dialog')).to_contain_text(lost[0]);expect(page.locator('#dialog')).to_contain_text('unknown')
                    assert lost[0] in page.evaluate('Object.keys(localStorage).filter(k=>k.startsWith("sv.desktop.aiQueue.")).map(k=>localStorage.getItem(k))')
                    page.locator('#dialog [data-action=close]').first.click()
                    report['checks'].append('503故障注入关闭详情，显示结果待核对并保留原命令定位与恢复标记')
                    page.route('**/api/v1/capabilities',lambda route:route.fulfill(status=200,content_type='application/json',body='{"ai":{"available":false}}'))
                    page.reload();page.locator('[data-action=ruling-history]').click();expect(page.locator('#dialog')).to_be_visible();expect(page.locator('#dialog')).to_contain_text('门后危险，暂不允许')
                    report['checks'].append('AI能力未加载时，顶部记录入口仍能查看人工裁决历史')
                    player=browser.new_page(viewport={'width':1100,'height':900});player.on('pageerror',lambda e:errors.append(str(e)))
                    online=[False]
                    def settlement(route):
                        response=route.fetch();value=response.json();value['sceneAutomation'].update(ready=True,executorOnline=online[0]);value['autoSceneTasks']=[]
                        route.fulfill(response=response,json=value)
                    player.route('**/package/state*',settlement)
                    player.goto(runtime.origin+'/sessions/settlement-ui/')
                    player.locator('[name=loginName]').fill('player1');player.locator('[name=password]').fill(password)
                    player.get_by_role('button',name='进入冒险',exact=True).click();player.locator('.identity').first.wait_for(state='attached')
                    player.goto(runtime.origin+'/sessions/settlement-ui/#/play/scene')
                    expect(player.locator('.scene-settlement')).to_have_text('自动结算 · 离线待结算')
                    expect(player.get_by_text('以下为该次观察中已知的做法',exact=False)).to_have_count(0)
                    expect(player.get_by_text('主持执行器暂时离线，行动会排队等待结算。',exact=True)).to_have_count(0)
                    player.screenshot(path=str(output/'settlement-offline.png'),full_page=True)
                    online[0]=True;player.reload();expect(player.locator('.scene-settlement')).to_have_text('自动结算')
                    player.close();report['checks'].append('移除行动说明长句；离线状态合并入自动结算标签，恢复在线后提示同步更新')
                    assert not errors,errors;assert not calls
                except Exception:page.screenshot(path=str(output/'failure.png'),full_page=True);raise
                finally:browser.close()
        report['passed']=True
    except Exception as e:report.update(passed=False,errorType=type(e).__name__,error=str(e)[:3000])
    report['pageErrors']=errors;report['passedCount']=len(report['checks']);write_json(output/'report.json',report);write_json(prior,report)
    print(json.dumps({k:report.get(k) for k in ['passed','passedCount','errorType','error','evidenceDirectory']},ensure_ascii=True),flush=True);return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
