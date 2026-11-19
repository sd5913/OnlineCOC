"""Actual host + browser checks for actionable, persistent failure feedback."""
import json
import secrets
from datetime import datetime
from unittest.mock import patch
from harness import PACK, running, provision
from client import HostError
from playwright.sync_api import sync_playwright, expect


def main():
    checks=[]
    with running('action-reasons') as (runtime,password):
        kp,p1,p2=provision(runtime,password)
        actor=p1.state()['character']['instanceId']
        def fail(account,op,args,code,key=None):
            result=account.action(op,args,key,allow_error=True)
            assert result['status']=='rejected' and result['failure']['code']==code,result
            assert result['failure']['reason'] and result['failure']['nextStep'] and result['failure']['actionId']
            return result
        p1.action('ready',{'ready':False})
        failed=fail(p1,'check',{'attribute':'dex','mode':'normal'},'NOT_READY')
        p1.action('ready',{'ready':True})
        kp.action('actor.update',{'id':actor,'numbers':{'incapacitated':1}})
        fail(p1,'check',{'attribute':'dex','mode':'normal'},'INCAPACITATED')
        kp.action('actor.update',{'id':actor,'numbers':{'incapacitated':0,'dex':0}})
        fail(p1,'check',{'attribute':'dex','mode':'normal'},'ZERO_ATTRIBUTE')
        kp.action('actor.update',{'id':actor,'numbers':{'dex':10}})
        session=kp.state()['session']['instanceId']
        kp.command('entity.update',{'id':session,'numbers':{'phase':0}})
        fail(p1,'check',{'attribute':'dex','mode':'normal'},'NOT_STARTED')
        kp.command('entity.update',{'id':session,'numbers':{'phase':1}})
        checks.append('not ready, incapacitated, zero attribute and unopened session have distinct causes and PL/KP recovery instructions')

        n=p1.state()['character']['numbers'];torch=next(i for i in range(1,21) if n['item'+str(i)]==2)
        kp.command('entity.update',{'id':actor,'numbers':{'uses'+str(torch):0}})
        key='reasons-'+secrets.token_hex(8)
        before=p1.state()['character']['numbers']
        failed=fail(p1,'inventory',{'operation':'use','slot':torch,'value':0},'ITEM_EXHAUSTED',key)
        assert fail(p1,'inventory',{'operation':'use','slot':torch,'value':0},'ITEM_EXHAUSTED',key)==failed
        assert p1.state()['character']['numbers']==before
        assert len([e for e in p1.state()['events'] if e['id']=='player1:'+key])==1
        assert not any(e['id']=='player1:'+key for e in p2.state()['events'])
        fail(p1,'inventory',{'operation':'move','slot':torch,'value':1},'SLOT_OCCUPIED')
        fail(p1,'inventory',{'operation':'use','slot':20,'value':0},'EMPTY_SLOT')
        two=next(i for i,item in enumerate(runtime.package.game['items'],1) if item['slots']==2 and item.get('shape')!='offhand-body')
        fail(kp,'grant',{'actor':actor,'item':two,'slot':10,'uses':0},'TWO_SLOTS')
        checks.append('inventory explains exhaustion, empty/occupied slots and multi-cell layout; rejected actions change no numbers and repeated IDs create one private event')

        req=p1.action('request',{'kind':'inventory','input':{'operation':'use','slot':torch,'value':0},'manual':True,'text':'请批准使用火把'})
        fail(kp,'resolve',{'requestId':req['requestId'],'approve':True,'reason':'可以使用'},'ITEM_EXHAUSTED')
        pending=next(r for r in kp.state()['requests'] if r['id']==req['requestId'])
        assert pending['status']=='pending' and pending['failure']['code']=='ITEM_EXHAUSTED'
        assert any(e['operation']=='resolve' and e['result'].get('failure',{}).get('code')=='ITEM_EXHAUSTED' for e in p1.state()['events'])
        kp.command('entity.update',{'id':actor,'numbers':{'uses'+str(torch):2}})
        kp.action('resolve',{'requestId':req['requestId'],'approve':True,'reason':'补足用量后批准'})
        assert p1.state()['character']['numbers']['uses'+str(torch)]==1
        assert 'failure' not in next(r for r in kp.state()['requests'] if r['id']==req['requestId'])
        checks.append('failed KP approval remains pending with the same reason delivered to PL; correcting the condition allows approval without replaying the failed attempt')

        task=p1.action('scene.action',{'action':'tunnel-ground','choice':'inspect'})
        kp.action('actor.update',{'id':actor,'numbers':{'incapacitated':1}})
        automatic=kp.request('/package/scene-executor',{})['jobs'][0]
        blocked=kp.action('scene.autorun',{'jobId':automatic['id']},automatic['commandId'])
        assert blocked['outcome']=='blocked' and blocked['failure']['code']=='INCAPACITATED'
        assert next(e for e in p1.state()['events'] if e['id']==task['jobId'])['result']['failure']['code']=='INCAPACITATED'
        kp.action('actor.update',{'id':actor,'numbers':{'incapacitated':0}})
        checks.append('condition changes between queuing and execution produce a precise blocked result on the original player card')

        from package import Job
        with patch.object(Job,'invoke',side_effect=HostError({'status':'rejected','code':'RULE_FAILED','diagnostic':'PRIVATE_NPC_SECRET'})):
            unknown=fail(p1,'check',{'attribute':'dex','mode':'normal'},'RULE_FAILED')
        assert 'PRIVATE_NPC_SECRET' not in json.dumps(unknown)
        assert '未返回' in unknown['failure']['reason']
        checks.append('unknown host rejection stays explicitly uncertain about its cause; private diagnostics never reach player feedback')

        errors=[]
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            page=browser.new_page(viewport={'width':1440,'height':900})
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(runtime.origin+'/sessions/reasons/')
            page.locator('[name=loginName]').fill('player1');page.locator('[name=password]').fill(password)
            page.get_by_role('button',name='进入冒险',exact=True).click();page.locator('.identity').wait_for()
            page.goto(runtime.origin+'/sessions/reasons/#/play/scene')
            kp.action('actor.update',{'id':actor,'numbers':{'incapacitated':1}})
            page.get_by_role('button',name='属性检定',exact=True).click()
            page.get_by_role('button',name='投骰',exact=True).click()
            expect(page.locator('[data-action-error]')).to_contain_text('失能')
            expect(page.locator('[data-action-error]')).to_contain_text('如何处理')
            page.locator('#dialog [data-action=close]').first.click()
            page.locator('[data-action=notebook-toggle][data-args*=records]').click()
            expect(page.locator('#action-feedback')).to_contain_text('失能')
            expect(page.locator('#action-feedback .log-entry').first.locator('summary')).to_contain_text('条件不满足')
            page.reload()
            expect(page.locator('#action-feedback')).to_contain_text('失能')
            page.screenshot(path=str(PACK/'tests/output/screenshots/action-blocked.png'))
            assert not errors,errors
            browser.close()
        checks.append('browser dialog and persistent log show reason, next steps and action ID; blocked badge survives reload with no JS errors')
    report={'passed':True,'checkedAt':datetime.now().astimezone().isoformat(),'checks':checks}
    (PACK/'tests/action-reasons-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
