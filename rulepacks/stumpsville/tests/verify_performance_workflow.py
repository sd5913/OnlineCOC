"""Four real package pages, warm history, local latency and generation continuity."""
from contextlib import contextmanager
from datetime import datetime
import json
import secrets
import statistics
import threading
import time
import traceback
import argparse
from pathlib import Path
from harness import PACK, Account, provision, running
import harness
import launch
from verify_integrations import ai, provider, result
from verify_review_followup import wait_task,submit
from playwright.sync_api import sync_playwright,expect


def distribution(values):
    values=sorted(values)
    return {'samples':len(values),'p50Ms':round(statistics.median(values),2),
            'p95Ms':round(values[min(len(values)-1,int(len(values)*.95))],2),'maxMs':round(max(values),2)}


def main(source=None):
    output=PACK/'tests/output'/('performance-workflow-'+secrets.token_hex(4));output.mkdir(parents=True)
    report={'checkedAt':datetime.now().astimezone().isoformat(),'checks':[],'measurements':{},'realSaveChanged':False,'externalModelCalls':0,'evidenceDirectory':output.relative_to(PACK).as_posix()}
    original_root=launch.ROOT
    if source:launch.ROOT=source.resolve();report['source']=str(launch.ROOT)
    mode=['plan'];target=[None];entered=threading.Event();release=threading.Event();pause_next=[False];calls=[];errors=[]
    def responder(request):
        if pause_next[0]:
            pause_next[0]=False;entered.set()
            if not release.wait(55):raise TimeoutError('isolated fixture was not released')
        tools=[m for m in request['messages'] if m.get('role')=='tool']
        def call(name,args):return {'role':'assistant','content':None,'tool_calls':[{'id':'fixture-'+str(len(tools)),'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}
        if mode[0]=='batch':
            if not tools:return call('room_search_data',{'types':['room'],'query':'/entities/'+target[0]['instanceId'],'limit':10})
            if len(tools)==1:return call('room_read_data',{'refs':[i['ref'] for i in json.loads(tools[-1]['content'])['items']]})
            answer={'kind':'batch','text':'根据发送时的角色资料，建议给木栗增加一枚钱币，等待KP审批。',
                    'actions':[{'target':'host','op':'entity.update','args':{'id':target[0]['instanceId'],'numbers':{'pips':target[0]['numbers']['pips']+1}}}]}
        else:answer={'kind':'plan','text':'已记录本次隔离性能查询，不修改游戏状态。'}
        return {'role':'assistant','content':json.dumps(answer)}
    def measured(name,operation,count=8):
        values=[]
        for i in range(count):
            start=time.perf_counter();operation(i);values.append((time.perf_counter()-start)*1000)
        report['measurements'][name]=distribution(values)
        print(name,report['measurements'][name],flush=True)
    @contextmanager
    def room(config):
        original=harness.Runtime
        def traced_runtime(args):
            runtime=original(args)
            if source:runtime.command[2]=str(source.resolve()/'engineering/backend/scripts/run.py')
            # Stack samples belong only to this disposable fixture. They make
            # client timeouts attributable without changing a live service.
            runtime.command=[runtime.command[0],'-B','-c',
                "import faulthandler,runpy,sys;faulthandler.dump_traceback_later(30,repeat=True);sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')",
                *runtime.command[2:]]
            return runtime
        harness.Runtime=traced_runtime
        try:
            with running('performance-workflow',data=output/'game',ai_config=config,no_browser=True) as value:
                try:yield value
                finally:release.set()
        finally:harness.Runtime=original
    try:
        with provider(output,responder) as (config,calls):
            with room(config) as (runtime,password):
                kp,p1,p2=provision(runtime,password)
                result(ai(kp,'ai.settings.update',{'enabled':True,'profileId':'offline','externalSources':{'public':True,'kp':True,'private':True},'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}))
                access=kp.request('/api/v1/ai/access');result(ai(kp,'ai.access.update',{'revision':access['revision'],'allowPlayerChat':True,'autoApproveBatches':False,'autoApproveConfigurations':False}))
                for i in range(32):kp.action('chat',{'operation':'chat.message.send','input':{'channelId':'general','text':'隔离历史 '+str(i)}})
                sid=result(ai(kp,'ai.session.create',{'title':'并发性能与生成连续性'}))['sessionId']
                for i in range(8):
                    submitted=submit(kp,{'sessionId':sid,'text':'性能查询 '+str(i)});wait_task(kp,sid,submitted['requestId'])
                report['fixture']={'seedChat':32,'seedAiTasks':8,'browserPages':4,'packageBytes':(runtime.data/'package.json').stat().st_size}
                with sync_playwright() as pw:
                    browser=pw.chromium.launch(channel='msedge',headless=True)
                    pages=[];http_samples=[]
                    for i,(name,route) in enumerate([('kp','gm/rulings'),('player1','play/scene'),('player2','play/scene'),('kp','gm/room')]):
                        page=browser.new_page(viewport={'width':1440,'height':960});page.on('pageerror',lambda e:errors.append(str(e)))
                        page.on('response',lambda r:http_samples.append({'route':r.url.split('/api/v1/')[-1].split('?')[0] if '/api/v1/' in r.url else r.url.split('/package/')[-1].split('?')[0],'status':r.status,'serverTiming':r.headers.get('server-timing')}) if '/api/v1/' in r.url or '/package/' in r.url else None)
                        page.goto(runtime.origin+'/sessions/perf-'+str(i)+'/');page.locator('[name=loginName]').fill(name);page.locator('[name=password]').fill(password)
                        page.get_by_role('button',name='进入冒险',exact=True).click();page.locator('.identity').first.wait_for(state='attached')
                        page.goto(runtime.origin+'/sessions/perf-'+str(i)+'/#/'+route);pages.append(page)
                    kp_page,pl_page=pages[:2]
                    measured('packageStateWithFourPages',lambda i:p1.state())
                    measured('chatSendWithFourPages',lambda i:kp.action('chat',{'operation':'chat.message.send','input':{'channelId':'general','text':'并发发送 '+str(i)}}))
                    measured('actionCheckWithFourPages',lambda i:p1.action('check',{'attribute':'dex','mode':'normal'}))
                    pending=[p2.action('request',{'kind':'free','manual':True,'text':'性能裁决 '+str(i)})['requestId'] for i in range(8)]
                    measured('rulingWithFourPages',lambda i:kp.action('resolve',{'requestId':pending[i],'approve':False,'reason':'隔离测量结束'}))
                    measured('aiTasksWithFourPages',lambda i:kp.request('/api/v1/ai/tasks?limit=30'))
                    acceptance=[]
                    for i in range(4):
                        start=time.perf_counter();item=submit(kp,{'sessionId':sid,'text':'并发消息 '+str(i)})
                        acceptance.append((time.perf_counter()-start)*1000)
                        wait_task(kp,sid,item['requestId'])
                    report['measurements']['aiSubmitAndDispatchAcceptance']=distribution(acceptance)
                    report['checks'].append('四个真实页面带聊天与AI历史并发，状态、聊天、行动、裁决、AI读取及发送接受均完成')
                    # The original private chat case: pause the provider while
                    # unrelated messages change the live host, then approve.
                    target[0]=p1.state()['character'];mode[0]='batch';entered.clear();release.clear();pause_next[0]=True
                    submitted=submit(kp,{'sessionId':sid,'text':'给木栗增加一枚钱币，请准备审批方案'})
                    assert entered.wait(15),'provider not entered'
                    direct=kp.action('chat',{'operation':'chat.direct.open','input':{'accountId':'player1'}})['channelId']
                    measured('privateChatDuringAiGeneration',lambda i:kp.action('chat',{'operation':'chat.message.send','input':{'channelId':direct,'text':'与申请者的普通闲聊 '+str(i)}}),count=3)
                    kp_page.bring_to_front();kp_page.locator('.session-select').select_option(sid)
                    expect(kp_page.locator('.task-progress').last).to_be_visible()
                    expect(kp_page.locator('.task-progress li[data-status="running"]').last).to_be_visible()
                    kp_page.locator('.task-progress').last.scroll_into_view_if_needed()
                    kp_page.screenshot(path=str(output/'generation-in-progress.png'),full_page=True)
                    release.set();task=wait_task(kp,sid,submitted['requestId'])
                    assert task.get('batchId') and task.get('response'),task
                    events=task['events'];seq=[e['seq'] for e in events]
                    assert seq==sorted(set(seq)) and all(e['at']>0 for e in events),events
                    assert {'provider_complete','tool_execute','output_validate','dependency_check','completed'} <= {e['stage'] for e in events},events
                    assert task['dependencyCheck']['status']=='unchanged',task['dependencyCheck']
                    row=next(r for r in kp.request('/api/v1/ai/rulings')['items'] if r['rulingId']=='batch:'+task['batchId'])
                    assert row['canDecide'],row
                    result(ai(kp,'ai.ruling.decide',{'rulingId':row['rulingId'],'digest':row['digest'],'decision':'approve'}))
                    assert p1.state()['character']['numbers']['pips']==target[0]['numbers']['pips']+1
                    task=next(t for t in kp.request('/api/v1/ai/sessions/'+sid)['items'] if t['requestId']==submitted['requestId'])
                    assert any(e['stage']=='command_execute' and e.get('receiptStatus')=='committed' for e in task['events']),task['events']
                    report['checks'].append('AI生成期间向申请玩家私聊，生成保留正文和候选；原候选可批准且实际只增加一次钱币')
                    report['checks'].append('窗口显示运行中进度；返回有序带时间的模型、工具、校验与完成事件，审批后含实际命令回执')
                    target[0]=p1.state()['character'];entered.clear();release.clear();pause_next[0]=True
                    changed=submit(kp,{'sessionId':sid,'text':'再次给木栗增加一枚钱币，准备新方案'})
                    assert entered.wait(15),'second provider not entered'
                    kp.action('actor.update',{'id':target[0]['instanceId'],'numbers':{'pips':target[0]['numbers']['pips']+10}})
                    release.set();changed_task=wait_task(kp,sid,changed['requestId'])
                    assert changed_task.get('response') and changed_task['dependencyCheck']['status']=='changed',changed_task
                    assert changed_task['dependencyCheck']['changes'] and changed_task['dependencyCheck']['canRegenerate'],changed_task
                    def verify_changed_state(_):
                        assert p1.state()['character']['numbers']['pips']==target[0]['numbers']['pips']+10
                    measured('packageStateAfterDependencyChange',verify_changed_state,count=3)
                    measured('aiTasksAfterDependencyChange',lambda _:kp.request('/api/v1/ai/tasks?limit=30'),count=3)
                    measured('aiRulingsAfterDependencyChange',lambda _:kp.request('/api/v1/ai/rulings'),count=3)
                    measured('aiSessionAfterDependencyChange',lambda _:kp.request('/api/v1/ai/sessions/'+sid),count=3)
                    expect(kp_page.locator('.dependency-warning').last).to_be_visible(timeout=15000)
                    regenerate=kp_page.get_by_role('button',name='按最新资料重新生成',exact=True).last;expect(regenerate).to_be_visible()
                    before=len(calls);regenerate.click();kp_page.wait_for_timeout(300);assert len(calls)==before
                    kp_page.locator('.dependency-warning').last.scroll_into_view_if_needed()
                    kp_page.screenshot(path=str(output/'dependency-changed.png'),full_page=True)
                    report['workspaceGeometry']=kp_page.evaluate("()=>Object.fromEntries(['#main','.rulings-grid','.ruling-queues','.queue-heading','#keeper-queue-status','.ruling-ai','.native-ai-body'].map(s=>{const n=document.querySelector(s),r=n.getBoundingClientRect(),c=getComputedStyle(n);return [s,{y:r.y,height:r.height,clientHeight:n.clientHeight,scrollHeight:n.scrollHeight,scrollTop:n.scrollTop,display:c.display,overflow:c.overflow,rows:c.gridTemplateRows}]}))")
                    expect(kp_page.locator('.queue-heading')).to_be_in_viewport()
                    report['checks'].append('相关角色值改变后保留原生成正文并列出变化；KP可准备按最新资料重新生成，未点击发送不擅自调用模型或覆盖实际数值')
                    # A transient refresh error must not destroy the component.
                    kp_page.locator('#history.messages').wait_for()
                    kp_page.locator('.embedded-ai-root').evaluate('(node)=>node.dataset.testContinuity="kept"')
                    kp_page.route('**/package/state*',lambda route:route.fulfill(status=503,content_type='application/json',body='{"code":"HOST_TIMEOUT","message":"isolated timeout"}'))
                    kp_page.wait_for_timeout(3200)
                    expect(kp_page.locator('.embedded-ai-root')).to_have_attribute('data-test-continuity','kept')
                    kp_page.unroute('**/package/state*')
                    expect(kp_page.get_by_text('连接中断',exact=True)).not_to_be_visible(timeout=15000)
                    expect(kp_page.locator('.embedded-ai-root')).to_have_attribute('data-test-continuity','kept')
                    report['checks'].append('状态查询503不销毁既有AI窗口和消息；恢复后继续复用同组件')
                    progress=kp_page.locator('.task-progress').last
                    if progress.get_attribute('open') is None:progress.locator('summary').click()
                    progress.scroll_into_view_if_needed()
                    kp_page.screenshot(path=str(output/'generation-completed.png'),full_page=True)
                    kp_page.set_viewport_size({'width':390,'height':844})
                    kp_page.get_by_role('button',name='AI 对话',exact=True).click()
                    progress.scroll_into_view_if_needed()
                    bounds=progress.bounding_box();assert bounds and bounds['width']<=390 and bounds['x']>=-2,bounds
                    kp_page.screenshot(path=str(output/'generation-progress-390.png'),full_page=True)
                    report['checks'].append('完成过程可展开回看，390px进度卡可读且不越出视口')
                    report['httpSummary']={'count':len(http_samples),'failedStatuses':[r for r in http_samples if r['status']>=400],'withServerTiming':sum(bool(r['serverTiming']) for r in http_samples)}
                    assert not errors,errors;browser.close()
        report['passed']=True
    except Exception as error:report.update(passed=False,errorType=type(error).__name__,error=str(error)[:4000],traceback=traceback.format_exc())
    finally:release.set();launch.ROOT=original_root
    report.update(passedCount=len(report['checks']),loopbackCalls=len(calls),pageErrors=errors)
    canonical=PACK/'tests/performance-workflow-results.json'
    if canonical.exists():
        old=json.loads(canonical.read_text(encoding='utf-8'));report['previousRuns']=[*old.get('previousRuns',[]),{k:old.get(k) for k in ('passed','error','checks','evidenceDirectory')}]
    for path in (canonical,output/'report.json'):path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('passed','passedCount','error','evidenceDirectory')},ensure_ascii=True));return 0 if report['passed'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path);args=parser.parse_args();raise SystemExit(main(args.source))
