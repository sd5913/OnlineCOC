"""ISSUE-018 real local entry: published history, timestamps, reveal and restart."""
import hashlib
import json
import secrets
from datetime import datetime
from harness import PACK,Account,running,provision
from verify_integrations import ai,provider,result
from verify_review_followup import wait_task
from verify_strict_known import known
from playwright.sync_api import sync_playwright,expect


def main():
    output=PACK/'tests/output'/('message-continuity-'+secrets.token_hex(4));output.mkdir(parents=True)
    report={'checkedAt':datetime.now().astimezone().isoformat(),'checks':[],'realSaveChanged':False,'externalModelCalls':0,'evidenceDirectory':output.relative_to(PACK).as_posix()}
    errors=[];mode=['known'];calls=[]
    def respond(request):
        if mode[0]=='plan':return {'role':'assistant','content':json.dumps({'kind':'plan','text':'已收到原玩家的问题，请KP选择要揭示的资料。','choices':{'prompt':'选择接下来的处理','options':[{'id':'reveal','label':'揭示资料','text':'请向原玩家揭示该地点公开资料'},{'id':'later','label':'暂不处理','text':'稍后处理'}]}})}
        tools=[m for m in request['messages'] if m.get('role')=='tool']
        def call(name,args):return {'role':'assistant','content':None,'tool_calls':[{'id':'fixture-'+str(len(tools)),'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}
        if not tools:return call('room_search_knowledge',{'query':'入口隧道','limit':10})
        items=json.loads(tools[-1]['content'])['items'];assert items
        if not items[0].get('evidenceId'):return call('room_read_knowledge',{'refs':[items[0]['ref']]})
        return {'role':'assistant','content':json.dumps({'kind':'known','evidence':[items[0]['evidenceId']],'next':'none'})}
    try:
        with provider(output,respond) as (config,calls):
            with running('message-continuity',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
                kp,p1,p2=provision(runtime,password)
                result(ai(kp,'ai.settings.update',{'enabled':True,'profileId':'offline','externalSources':{'public':True,'kp':True,'private':True},'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}))
                access=kp.request('/api/v1/ai/access');result(ai(kp,'ai.access.update',{'revision':access['revision'],'allowPlayerChat':True,'autoApproveBatches':False,'autoApproveConfigurations':False}))
                sid=result(ai(p1,'ai.session.create',{'title':'已发送消息与不可访问引用'}))['sessionId']
                sent=result(ai(p1,'ai.session.submit',{'sessionId':sid,'text':'我想了解入口隧道里已知的情况'}))
                initial=wait_task(p1,sid,sent['requestId']);assert initial['response'],initial
                assert initial['sentAt']>0 and initial['responseAt']>=initial['sentAt'],initial
                saved_time=(initial['sentAt'],initial['responseAt'])
                mode[0]='plan';review=result(ai(kp,'ai.review.create',{'source':{'kind':'request','requestId':sent['requestId']}}))
                review_task=wait_task(kp,review['sessionId'],review['requestId']);assert review_task['recipientAccountId']=='player1',review_task
                with sync_playwright() as pw:
                    browser=pw.chromium.launch(channel='msedge',headless=True)
                    def login(name,route):
                        page=browser.new_page(viewport={'width':1440,'height':960});page.on('pageerror',lambda e:errors.append(str(e)))
                        page.goto(runtime.origin+'/sessions/message-'+name+'/');page.locator('[name=loginName]').fill(name);page.locator('[name=password]').fill(password)
                        page.get_by_role('button',name='进入冒险',exact=True).click();page.locator('.identity').first.wait_for(state='attached')
                        page.goto(runtime.origin+'/sessions/message-'+name+'/#/'+route);return page
                    pl=login('player1','play/scene');pl.locator('#comm-tab-ai').click();pl.locator('.session-select').select_option(sid)
                    chip=pl.locator('.reference-chip').first;expect(chip).to_be_visible();chip.click();expect(pl.locator('dialog .stumpsville-reference')).to_contain_text('入口隧道');pl.locator('dialog[open]').evaluate('(d)=>d.close()')
                    stamp=pl.locator('#history.messages time').evaluate_all('(nodes)=>nodes.map(n=>n.dateTime)')
                    assert len(stamp)>=2 and all(stamp),stamp
                    report['checks'].append('本机PL正常回复及可视化引用可读，发送和回复使用各自真实时间')
                    scene=next(i for i in known(p1) if i['facetId']=='scene' and i['data']['index']==1)
                    grants=kp.request('/api/v1/knowledge/grants/query',{'subjectMemberId':'member-player1','policyId':'stumpsville-personal-v1','status':'active','limit':50})['items']
                    grant=next(g for g in grants if g['resource']['id']==scene['data']['entityId'])
                    kp.action('knowledge.revoke',{'grantId':grant['grantId'],'revision':grant['revision']})
                    after=next(i for i in p1.request('/api/v1/ai/sessions/'+sid)['items'] if i['requestId']==sent['requestId'])
                    assert after['response']==initial['response'] and (after['sentAt'],after['responseAt'])==saved_time,after
                    pl.reload();pl.locator('#comm-tab-ai').click();pl.locator('.session-select').select_option(sid)
                    expect(pl.locator('#history.messages')).to_contain_text('我想了解入口隧道里已知的情况');expect(pl.locator('#history.messages')).to_contain_text('入口隧道')
                    expect(pl.locator('.reference-chip').first).to_be_disabled()
                    assert pl.locator('#history.messages time').evaluate_all('(nodes)=>nodes.map(n=>n.dateTime)')==stamp
                    pl.screenshot(path=str(output/'unavailable-reference-desktop.png'),full_page=True)
                    pl.set_viewport_size({'width':390,'height':844});pl.locator('[data-action=workspace-column][data-args*=communication]').click();pl.locator('.reference-chip').first.scroll_into_view_if_needed()
                    pl.screenshot(path=str(output/'unavailable-reference-390.png'),full_page=True)
                    report['checks'].append('撤回资料后原消息与原时间保持，引用灰显禁用，390px可读')
                    page=login('kp','gm/rulings');card=page.locator('[data-ai-request="'+review['requestId']+'"]');expect(card).to_be_visible()
                    card.get_by_role('button',name='执行信息揭示',exact=True).click();expect(page.locator('[name=knowledge-ruling-account]')).to_have_value('player1')
                    submitted=[];page.on('request',lambda r:submitted.append(r.post_data_json) if '/package/action' in r.url and r.method=='POST' else None)
                    page.get_by_role('button',name='执行揭示',exact=True).click();expect(page.locator('#dialog')).not_to_be_visible()
                    expect(page.locator('#toast')).to_contain_text('已向指定玩家揭示地点')
                    assert len(submitted)==1 and submitted[0]['args']['accounts']==['player1'],submitted
                    assert any(i['facetId']=='scene' and i['data']['index']==1 for i in known(p1))
                    times=page.locator('#keeper-ruling-timeline>.ruling-card').evaluate_all('(nodes)=>nodes.map(n=>Number(n.dataset.queueTime))');assert times==sorted(times),times
                    page.screenshot(path=str(output/'local-reveal-queue.png'),full_page=True)
                    report['checks'].append('真实本机审核请求揭示使用原玩家身份，一次提交成功；混合队列按时间升序')
                    # A committed action followed by a failed refresh must stay completed.
                    fail_refresh=[False]
                    page.on('response',lambda response:fail_refresh.__setitem__(0,True) if '/package/action' in response.url and response.request.method=='POST' and response.status==200 else None)
                    def intercept(route):
                        if fail_refresh[0]:
                            fail_refresh[0]=False
                            route.fulfill(status=503,content_type='application/json',body=json.dumps({'code':'HOST_TIMEOUT','message':'验收模拟：刷新超时','traceId':'refresh-only'}))
                        else:route.continue_()
                    page.route('**/package/state*',intercept)
                    card=page.locator('[data-ai-request="'+review['requestId']+'"]');card.get_by_role('button',name='执行信息揭示',exact=True).click()
                    page.get_by_role('button',name='执行揭示',exact=True).click()
                    expect(page.locator('#toast')).to_contain_text('行动已完成，但刷新资料失败')
                    assert len(submitted)==2 and any(r['id']==submitted[-1]['id'] for r in kp.state()['receipts']),submitted
                    assert page.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('stumpsville.pending.')).every(k=>!localStorage.getItem(k))")
                    page.unroute('**/package/state*',intercept)
                    report['checks'].append('写入成功后刷新失败仍报告已完成，原成功回执存在且不残留待恢复写行动')
                    browser.close()
                assert not errors,errors
            before_calls=len(calls)
            with running('message-continuity-restart',data=output/'game',ai_config=config,no_browser=True) as (runtime,_):
                p1=Account(runtime.origin,'player1',password,'restart')
                row=next(i for i in p1.request('/api/v1/ai/sessions/'+sid)['items'] if i['requestId']==sent['requestId'])
                assert row['response']==initial['response'] and (row['sentAt'],row['responseAt'])==saved_time,row
                assert len(calls)==before_calls
                report['checks'].append('同档重启保持原正文及发送回复时间，读取历史不再调用模型')
        report['passed']=True
    except Exception as error:report.update(passed=False,errorType=type(error).__name__,error=str(error)[:3000])
    report.update(passedCount=len(report['checks']),pageErrors=errors,loopbackCalls=len(calls))
    canonical=PACK/'tests/message-continuity-results.json'
    if canonical.exists():
        old=json.loads(canonical.read_text(encoding='utf-8'));report['previousRuns']=[*old.get('previousRuns',[]),{k:old.get(k) for k in ('passed','error','checks','evidenceDirectory')}]
    for p in (canonical,output/'report.json'):p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('passed','passedCount','error','evidenceDirectory')},ensure_ascii=True));return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
