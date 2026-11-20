"""Receipt-bound KP notifications: offline delivery, recipient isolation and UI dedup."""
import copy
import json
import secrets
import time
from datetime import datetime
from harness import PACK, Account, running, provision
from integrations import write_json
from playwright.sync_api import expect, sync_playwright


def main():
    output=PACK/'tests/output'/('command-notices-'+secrets.token_hex(4));output.mkdir(parents=True)
    prior=PACK/'tests/command-notification-results.json'
    report={'checkedAt':datetime.now().astimezone().isoformat(),'checks':[],'realSaveChanged':False,'realProviderCalls':0,'evidenceDirectory':output.relative_to(PACK).as_posix()}
    if prior.exists():
        old=json.loads(prior.read_text(encoding='utf-8'));report['previousRuns']=[*old.get('previousRuns',[]),{k:old.get(k) for k in ['passed','error','checks','evidenceDirectory']}]
    errors=[]
    try:
        with running('command-notices',data=output/'game',no_browser=True) as (runtime,password):
            kp,p1,p2=provision(runtime,password)
            def inbox(player):return player.request('/api/v1/notifications?after=0&limit=100')['items']
            for player in (p1,p2):
                for notice in inbox(player):player.action('notification.ack',{'notificationId':notice['notificationId']})
            before=p1.state()['character'];other=copy.deepcopy(p2.state()['character']['numbers'])
            slot=next(i for i in range(4,11) if before['numbers'].get('item'+str(i),0)==0)
            body={'actor':before['instanceId'],'item':2,'slot':slot,'uses':3};command='grant-'+secrets.token_hex(8)
            kp.action('grant',body,command);notice=inbox(p1)[0]
            assert len(inbox(p1))==1 and not inbox(p2)
            assert notice['source']['status']=='committed' and notice['source']['op']=='action.invoke'
            assert 'args' not in notice['source'] and 'recipientAccountIds' not in notice
            event=next(e for e in p1.state()['events'] if e.get('notificationId')==notice['notificationId'])
            assert event['changes'] and p2.state()['character']['numbers']==other
            kp.action('grant',body,command)
            assert len(inbox(p1))==1 and p1.state()['character']['numbers']['item'+str(slot)]==2
            report['checks'].append('KP发放物品同时持久提交通知；原行动和通知绑定，重放原包不重复，其他PL不可见')
            forbidden=p2.action('notification.ack',{'notificationId':notice['notificationId']},allow_error=True)
            assert forbidden.get('status')=='rejected' or forbidden.get('code'),forbidden
            assert inbox(p1)
            report['checks'].append('另一PL不能确认他人的通知，不暴露原动作私密参数')
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True)
                page=browser.new_page(viewport={'width':1440,'height':960});page.on('pageerror',lambda e:errors.append(str(e)));expect.set_options(timeout=20000)
                fail_ack=[True]
                def intercept(route):
                    body=route.request.post_data_json
                    if fail_ack[0] and body.get('operation')=='notification.ack':route.fulfill(status=503,content_type='application/json',body='{"code":"NOTICE_ACK_TEST_OUTAGE"}');return
                    route.continue_()
                page.route('**/package/action*',intercept)
                try:
                    page.goto(runtime.origin+'/sessions/notice-player/')
                    page.locator('[name=loginName]').fill('player1');page.locator('[name=password]').fill(password)
                    page.get_by_role('button',name='进入冒险',exact=True).click();page.locator('.identity').first.wait_for(state='attached')
                    page.goto(runtime.origin+'/sessions/notice-player/#/play/scene')
                    popup=page.locator('.effects-popup');expect(popup).to_be_visible()
                    expect(popup).to_have_attribute('data-event-id','notification:'+notice['notificationId'])
                    expect(popup).to_contain_text('主持已完成发放装备')
                    page.screenshot(path=str(output/'offline-grant-notice.png'),full_page=True)
                    assert inbox(p1),'Injected ack outage should leave server record pending'
                    page.reload();page.locator('.available-actions').wait_for()
                    expect(page.locator('.effects-popup')).not_to_be_visible()
                    fail_ack[0]=False
                    deadline=time.monotonic()+20
                    while inbox(p1) and time.monotonic()<deadline:page.wait_for_timeout(200)
                    assert not inbox(p1)
                    expect(page.locator('.effects-popup')).not_to_be_visible()
                    report['checks'].append('离线发放在首次登录展示一次；确认断线后刷新不重弹并自动重试确认')
                    old_pips=p1.state()['character']['numbers']['pips']
                    kp.action('actor.update',{'id':before['instanceId'],'numbers':{'pips':old_pips+2}})
                    expect(popup).to_be_visible();expect(popup).to_contain_text('主持已完成调整属性')
                    expect(popup.locator('.change-list')).to_contain_text(str(old_pips+2))
                    expect(popup).to_be_hidden(timeout=5000);page.wait_for_timeout(2000);expect(popup).to_be_hidden()
                    report['checks'].append('在线属性调整与旧事件合并为一条通知；快照差异不再额外重复弹出')
                    snapshot=copy.deepcopy(p1.state()['character']['numbers'])
                    rejected=kp.action('grant',body,allow_error=True)
                    assert rejected.get('status')=='rejected' or rejected.get('failure'),rejected
                    assert p1.state()['character']['numbers']==snapshot and not inbox(p1)
                    report['checks'].append('被拒绝的重复占槽不改变装备，也不生成成功通知')
                    assert not errors,errors
                except Exception:
                    page.screenshot(path=str(output/'failure.png'),full_page=True);raise
                finally:browser.close()
            # A fresh mutation while the player is offline remains available after a real host restart.
            n=p1.state()['character']['numbers']
            kp.action('actor.update',{'id':before['instanceId'],'numbers':{'pips':n['pips']+1}})
            pending=inbox(p1);assert len(pending)==1
        with running('command-notices-restart',data=output/'game',no_browser=True) as (runtime,_):
            player=Account(runtime.origin,'player1',password,'restart-notice')
            current=player.request('/api/v1/notifications')['items'];assert current==pending
            player.action('notification.ack',{'notificationId':current[0]['notificationId']})
            assert not player.request('/api/v1/notifications')['items']
            report['checks'].append('宿主真实重启保留未确认通知和来源定位；确认后不再投递')
        report['passed']=True
    except Exception as error:report.update(passed=False,errorType=type(error).__name__,error=str(error)[:2800])
    report['pageErrors']=errors;report['passedCount']=len(report['checks'])
    write_json(prior,report);write_json(output/'report.json',report)
    print(json.dumps({k:report.get(k) for k in ['passed','passedCount','error','evidenceDirectory']},ensure_ascii=True),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
