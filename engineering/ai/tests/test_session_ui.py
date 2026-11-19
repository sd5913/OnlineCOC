"""Real-room session management and DOM-only answer rendering, without model calls."""
from pathlib import Path

from playwright.sync_api import sync_playwright, expect
from test_manager_ui import services, allow_players
from test_embeds import login

OUTPUT=Path(__file__).resolve().parents[2]/'acceptance/ai-runtime'
SAMPLE='''## 当前授权范围内的房间概览

**查询方式与覆盖范围**：共 10 个地点，仅包含本次授权可见内容。

### 地点实体
| 位置 | numbers.index | 可见性 | 备注 |
| --- | ---: | :---: | --- |
| 入口隧道 | 1 | public | 当前唯一公开位置 |
| 主门 | 2 | kp | |
| 库房 | 5 | kp | **待探索** |

参考 [[entity:lantern@1]]，不要将建议视为已生效裁决。

- 调查提灯
  - 检查油量
1. 提交需求
2. KP 审核

> 本轮资料覆盖有限。

```json
{"name":"提灯","ref":"[[entity:lantern@1]]"}
```

[说明](https://example.com/help) [危险](javascript:alert(1))
![远端图片](https://example.invalid/tracker.png)
<img src=x onerror="window.pwned=1"><script>window.pwned=1</script>
'''


def test_markdown_format_reference_security_and_mobile(services):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    allow_players(origin)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':760,'height':900});errors=[];remote=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:remote.append(r.url) if 'example.' in r.url else None)
        try:
            page.goto(origin+'/ai-ui/conversation.html')
            page.evaluate('''async text=>{
              const {mountMarkdown}=await import('/ai-ui/pack.js');document.querySelector('body').replaceChildren();
              const target=document.createElement('main');target.id='sample';target.style.cssText='max-width:680px;padding:16px;font:14px/1.7 system-ui;background:#faf6eb';document.body.append(target);
              window.markdown=mountMarkdown(target,text,{resolveReferences:async()=>({items:[{kind:'entity',id:'lantern',revision:'1',label:'提灯'}]})});
            }''',SAMPLE)
            expect(page.locator('.ai-markdown h2')).to_have_text('当前授权范围内的房间概览')
            expect(page.locator('tbody tr')).to_have_count(3)
            expect(page.locator('th')).to_have_count(4)
            expect(page.locator('.reference-chip')).to_have_text('提灯')
            expect(page.locator('pre code')).to_contain_text('[[entity:lantern@1]]')
            expect(page.locator('strong').first).to_have_text('查询方式与覆盖范围')
            expect(page.locator('ul ul li')).to_have_text('检查油量')
            expect(page.locator('ol li')).to_have_count(2)
            expect(page.locator('a')).to_have_count(1)
            assert page.locator('a').get_attribute('rel')=='noopener noreferrer'
            assert page.locator('img,script,iframe').count()==0 and not page.evaluate('window.pwned')
            page.screenshot(path=str(OUTPUT/'markdown-embedded.png'),full_page=True)
            page.set_viewport_size({'width':360,'height':820})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert page.locator('.md-table').evaluate('(e)=>e.scrollWidth>e.clientWidth')
            page.evaluate('text=>markdown.update(text,{plainText:true})',SAMPLE)
            expect(page.locator('.ai-markdown h2,.ai-markdown table')).to_have_count(0)
            expect(page.locator('.md-plain')).to_contain_text('## 当前授权范围')
            assert not errors and not remote,(errors,remote)
        finally:browser.close()


def test_embedded_management_settings_drafts_and_identity(services):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    allow_players(origin)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1280,'height':900});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(origin+'/ai-ui/conversation.html');login(page,'kp')
            page.locator('.new-chat').click();expect(page.locator('#status')).to_have_text('新会话已创建')
            first=page.locator('.session-select').input_value();page.locator('#text').fill('保留尚未发送的提灯草稿')
            page.locator('.manage-sessions').click();expect(page.locator('.settings')).to_be_visible()
            page.locator('.settings [name=title]').fill('提灯讨论');page.locator('[name=pinned]').check()
            page.locator('[name=historyTurns]').select_option('2');page.locator('[name=renderMode]').select_option('plain');page.locator('[name=showDiagnostics]').uncheck()
            page.locator('.save').click();expect(page.locator('.session-manager .status')).to_have_text('设置已保存')
            page.locator('.create input').fill('地图规划');page.locator('.create button').click();expect(page.locator('.session-manager .status')).to_have_text('会话已创建')
            page.locator('.open').click();expect(page.locator('.session-dialog')).not_to_be_visible()
            expect(page.locator('#text')).to_be_empty();page.locator('#text').fill('地图草稿')
            page.locator('.session-select').select_option(first);expect(page.locator('#text')).to_have_text('保留尚未发送的提灯草稿')
            page.locator('.manage-sessions').click();expect(page.locator('[name=historyTurns]')).to_have_value('2')
            expect(page.locator('[name=renderMode]')).to_have_value('plain');expect(page.locator('[name=showDiagnostics]')).not_to_be_checked()
            expect(page.locator('.session-manager .session-link').first).to_contain_text('★ 提灯讨论')
            page.locator('.search').fill('地图');expect(page.locator('.session-manager .session-link')).to_have_count(1)
            page.locator('.search').fill('');page.locator('.session-manager .archive').click();expect(page.locator('.session-manager .status')).to_have_text('会话已归档')
            page.locator('[data-filter=archived]').click();expect(page.locator('.session-manager .session-link')).to_have_count(1)
            page.locator('.archive').last.click();expect(page.locator('.session-manager .status')).to_have_text('会话已恢复')
            page.locator('[data-filter=all]').click();expect(page.locator('.session-manager .session-link')).to_have_count(2)
            page.screenshot(path=str(OUTPUT/'session-management.png'),full_page=True)
            page.locator('.session-close').click();page.reload();page.locator('.session-select').select_option(first)
            expect(page.locator('#rename')).to_have_value('提灯讨论');page.locator('.manage-sessions').click()
            expect(page.locator('[name=historyTurns]')).to_have_value('2');expect(page.locator('[name=pinned]')).to_be_checked()
            page.locator('.session-close').click();page.locator('#logout').click();login(page,'player1');page.locator('.manage-sessions').click()
            expect(page.locator('.session-manager .session-link')).to_have_count(0)
            page.locator('.create input').fill('玩家的会话');page.locator('.create button').click();expect(page.locator('.settings')).to_be_visible()
            expect(page.locator('.diagnostics')).to_be_hidden();expect(page.locator('.session-manager')).not_to_contain_text('提灯讨论')
            assert not errors,errors
        finally:browser.close()


def test_standalone_manager_and_same_origin_frame(services):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    allow_players(origin)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':390,'height':840})
        try:
            response=page.goto(origin+'/ai-ui/sessions.html');assert "frame-ancestors 'self'" in response.headers['content-security-policy'];login(page,'player1')
            page.locator('.create input').fill('独立管理页面');page.locator('.create button').click();expect(page.locator('.settings')).to_be_visible()
            page.locator('.open').click();expect(page.locator('#rename')).to_have_value('独立管理页面')
            page.evaluate("()=>{const frame=document.createElement('iframe');frame.id='manager-frame';frame.src='sessions.html';frame.style.cssText='width:100%;height:680px';document.body.prepend(frame);}")
            frame=page.frame_locator('#manager-frame');expect(frame.locator('.session-link')).to_contain_text('独立管理页面')
            assert frame.locator('body').evaluate('()=>document.documentElement.scrollWidth<=innerWidth')
        finally:browser.close()


def test_management_lost_response_and_version_conflict(services):
    _,entry,_=services;origin=f'http://127.0.0.1:{entry["roomPort"]}'
    allow_players(origin)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page()
        try:
            page.goto(origin+'/ai-ui/sessions.html');login(page,'player1');sent=[]
            def lose_response(route):
                sent.append(route.request.post_data_json);route.fetch();route.abort('failed')
            page.route('**/api/v1/ai/commands',lose_response,times=1)
            page.locator('.create input').fill('不可重复创建');page.locator('.create button').click()
            expect(page.locator('.receipt')).to_be_visible();expect(page.locator('.create button')).to_be_disabled()
            page.locator('.create').evaluate("form=>form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))");expect(page.locator('.status')).to_have_text('请先查询原操作结果')
            page.locator('.receipt').click();expect(page.locator('.status')).to_have_text('操作已确认')
            expect(page.locator('.session-link')).to_have_count(1);assert len(sent)==1
            page.evaluate('''async()=>{const {AiClient}=await import('/ai-ui/pack.js');const other=new AiClient();await other.resume();try{
              const session=(await other.aiSessions()).items[0];await other.aiCommand('ai.session.update',{sessionId:session.sessionId,revision:session.revision,title:'来自另一页面'});
            }finally{other.destroy();}}''')
            page.locator('.settings [name=title]').fill('旧页面修改');page.locator('.save').click()
            expect(page.locator('.status')).to_have_text('会话已在其他页面修改，请重新选择后再保存。')
            page.locator('.session-link').click();expect(page.locator('.settings [name=title]')).to_have_value('来自另一页面')
        finally:browser.close()
