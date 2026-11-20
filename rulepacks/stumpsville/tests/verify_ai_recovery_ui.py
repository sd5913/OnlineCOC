"""Package HTTP refusal recovery, top debug dialog and exported component smoke."""
from datetime import datetime
import json
from pathlib import Path
import secrets

from harness import PACK, Account, running
from integrations import write_json
from verify_integrations import provider, ai, result
from build_web import ai_modules, build
from playwright.sync_api import sync_playwright, expect


def main():
    output=PACK/'tests/output'/('ai-recovery-ui-'+secrets.token_hex(4));output.mkdir(parents=True)
    report={'checkedAt':datetime.now().astimezone().isoformat(),'realSaveChanged':False,
            'realProviderCalls':0,'checks':[],'evidenceDirectory':output.relative_to(PACK).as_posix()}
    prior=PACK/'tests/ai-recovery-ui-results.json'
    if prior.exists():
        old=json.loads(prior.read_text(encoding='utf-8'))
        report['previousRuns']=[*old.get('previousRuns',[]),{k:old.get(k) for k in ('checkedAt','passed','checks','error','evidenceDirectory')}]
    errors=[]
    try:
        build(output/'web-build')
        with provider(output) as (config,calls), running('ai-recovery-ui',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
            kp=Account(runtime.origin,'kp',password,'fixture')
            sid=result(ai(kp,'ai.session.create',{'title':'重启调试样本'}))['sessionId']
            marker='ISOLATED_DEBUG_BODY_20261120'
            request=result(ai(kp,'ai.session.submit',{'sessionId':sid,'text':marker}))
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True)
                page=browser.new_page(viewport={'width':1440,'height':900},accept_downloads=True)
                page.on('pageerror',lambda e:errors.append(str(e)));expect.set_options(timeout=25000)
                try:
                    page.goto(runtime.origin+'/sessions/recovery-browser/')
                    page.locator('[name=loginName]').fill('kp');page.locator('[name=password]').fill(password)
                    page.get_by_role('button',name='进入冒险',exact=True).click();page.locator('.identity').first.wait_for()
                    page.goto(runtime.origin+'/sessions/recovery-browser/#/gm/rulings')
                    root=page.locator('#kp-ai-embedded')
                    expect(root.locator('.new-chat')).to_be_visible()
                    expect(root.locator('.session-select option[value="'+sid+'"]')).to_have_count(1)
                    denied=[]
                    def reject_once(route):
                        body=route.request.post_data_json
                        if body and body.get('op')=='ai.session.create' and not denied:
                            denied.append(body['requestId'])
                            route.fulfill(status=403,content_type='application/json',body='{"code":"PERMISSION_DENIED"}')
                        else:route.continue_()
                    page.route('**/api/v1/ai/commands',reject_once)
                    root.locator('.new-chat').click()
                    expect(root.locator('#status')).to_contain_text('PERMISSION_DENIED')
                    assert page.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('sv.desktop.aiQueue.')).length")==0
                    root.locator('.new-chat').click()
                    expect(root.locator('.session-select')).not_to_have_value('')
                    assert len(denied)==1
                    report['checks'].append('真实包页面收到无status字段的HTTP403后，可继续创建会话，无遗留恢复标记')
                    root.locator('.session-select').select_option(sid)
                    expect(root.locator('#history')).to_contain_text(marker)
                    for width,height in [(1440,900),(390,844)]:
                        page.set_viewport_size({'width':width,'height':height})
                        if width<700:page.get_by_role('button',name='AI 对话',exact=True).click()
                        root.locator('.debug-slot .debug-open').click()
                        dialog=root.locator('.chat-debug-dialog')
                        expect(dialog).to_be_visible()
                        assert dialog.get_by_role('combobox',name='调试范围').locator('option').count()==2
                        dialog.get_by_role('combobox',name='调试范围').select_option(request['requestId'])
                        with page.expect_download() as downloaded:dialog.get_by_role('button',name='导出调试 JSON',exact=True).click()
                        clean=json.loads(Path(downloaded.value.path()).read_text(encoding='utf-8'))
                        assert marker not in json.dumps(clean,ensure_ascii=False)
                        dialog.get_by_role('checkbox').check()
                        with page.expect_download() as downloaded:dialog.get_by_role('button',name='导出调试 JSON',exact=True).click()
                        full=json.loads(Path(downloaded.value.path()).read_text(encoding='utf-8'))
                        assert marker in json.dumps(full,ensure_ascii=False)
                        bounds=dialog.bounding_box();assert bounds['x']>=0 and bounds['x']+bounds['width']<=width+1,bounds
                        page.screenshot(path=str(output/('debug-'+str(width)+'.png')),full_page=True)
                        dialog.get_by_role('button',name='关闭引用与调试').click();expect(dialog).not_to_be_visible()
                        report['checks'].append(str(width)+'px顶部调试弹窗：请求选择、默认无正文、显式正文导出、关闭及边界通过')
                    page.set_viewport_size({'width':1440,'height':900})
                    page.reload();expect(root.locator('.session-select')).to_be_visible()
                    root.locator('.session-select').select_option(sid);expect(root.locator('#history')).to_contain_text(marker)
                    report['checks'].append('重新加载包页面后可重新选择原会话并读取请求')
                    # Evaluate the exact exported component graph in a real browser.
                    exports=page.evaluate('()=>{const web={};'+ai_modules()+';globalThis.__exportedAI=web.aiModules;return Object.keys(web.aiModules);}')
                    assert {'appendDebugTools','mountAIConversation','AiClient'}<=set(exports)
                    page.evaluate("""async()=>{
                      const m=globalThis.__exportedAI,base=new URL('api/v1/',location.href);
                      const c=new m.AiClient(new m.HttpTransport(base));await c.resume();
                      const root=document.createElement('div');root.id='exported-component';document.body.replaceChildren(root);
                      globalThis.__exportedClient=c;globalThis.__exportedView=m.mountAIConversation(root,c,{review:false});
                    }""")
                    exported=page.locator('#exported-component');expect(exported.locator('.new-chat')).to_be_visible()
                    exported.locator('.session-select').select_option(sid)
                    exported.locator('.debug-open').click();expect(exported.locator('.chat-debug-dialog')).to_be_visible()
                    page.screenshot(path=str(output/'exported-debug.png'),full_page=True)
                    report['checks'].append('网页导出的真实组件图可加载并打开调试弹窗（不代替公网WebRTC全链路）')
                    assert not errors,errors
                    report['checks'].append('浏览器无未捕获脚本错误')
                except Exception:
                    page.screenshot(path=str(output/'failure.png'),full_page=True);raise
                finally:browser.close()
            assert not calls
        report['passed']=True
    except Exception as error:report.update(passed=False,errorType=type(error).__name__,error=str(error)[:3000])
    report['passedCount']=len(report['checks']);report['pageErrors']=errors
    write_json(output/'report.json',report);write_json(prior,report)
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
