"""Player-only KP map, discovered contacts, separated pages and public AI embeds."""
from datetime import datetime
import json
import secrets
import uuid
from playwright.sync_api import sync_playwright, expect
from harness import PACK, running, provision, Account
from integrations import write_json
from verify_integrations import provider, directory, ai, result
from verify_web import owned_room, WebPlayer


def main():
    output=PACK/'tests/output'/('map-ai-'+secrets.token_hex(4));output.mkdir(parents=True)
    checks=[];errors=[];saved_password=None
    with provider(output,lambda request:{'role':'assistant','content':json.dumps({'kind':'plan','choices':{'prompt':'接下来做什么','options':[{'id':'more','label':'继续了解','text':'请继续说明可见资料'},{'id':'later','label':'稍后再看','text':'先保留当前结论'}]},'text':'OFFLINE_REPLY\n\n## 房间概览\n**查询结果**\n\n| 位置 | 可见性 |\n| --- | --- |\n| 入口隧道 | public |'})}) as (config,calls),directory(output,web=True) as (network,url):
        with running('map-ai',data=output/'game',ai_config=config,web_config=network,no_browser=True) as (runtime,password):
            saved_password=password
            kp,p1,p2=provision(runtime,password)
            assert ai(p1,'ai.session.create',{'title':'禁用时不可创建'},True)['code']=='PLAYER_AI_DISABLED'
            result(ai(kp,'ai.access.update',{'revision':1,'allowPlayerChat':True,'autoApproveBatches':False}))
            kp.action('draft',{'preset':'mul','name':'KP自己的鼠'});kp.action('approve',{'account':'kp'})
            assert kp.request('/api/v1/ai/references?kind=config&q=sv.npc')['items'][0]['label']=='NPC 模板'
            one=p1.state()['character']['instanceId'];two=p2.state()['character']['instanceId']
            def move(actor,place):
                kp.command('entity.update',{'id':actor,'numbers':{'location':place}});kp.state()
            def contacts(player):return player.state()['mapContacts']
            assert len(contacts(p1))==3 and all(a['kind']=='pc' for a in contacts(p1))
            for index in (3,6,8):kp.action('location.publish',{'index':index,'clues':[]})
            move(one,6);move(two,6)
            assert len(contacts(p1))==2 and not any(a['kind']=='npc' for a in contacts(p1))
            key=str(uuid.uuid4());args={'action':'web-inspect','choice':'inspect'}
            p1.action('scene.action',args,key)
            for job in kp.request('/package/scene-executor',{})['jobs']:kp.action('scene.autorun',{'jobId':job['id']},job['commandId'])
            outcome=p1.action('scene.action',args,key);assert outcome['status']=='completed',outcome
            assert len([a for a in contacts(p1) if a['kind']=='npc'])==4,contacts(p1)
            assert not any(a['kind']=='npc' for a in contacts(p2))
            for actor in contacts(p1):assert set(actor)<={'id','name','kind','location','self'}
            hidden=p2.action('actor.reveal',{'id':one,'accounts':['player2'],'visible':True},allow_error=True);assert hidden.get('code')
            kp.action('actor.reveal',{'id':two,'accounts':['player1'],'visible':False})
            assert two not in [a['id'] for a in contacts(p1)]
            move(one,3);assert not any(a['kind']=='npc' for a in contacts(p1))
            spider=kp.state()['npcs'][0]['instanceId'];move(spider,3)
            assert spider in [a['id'] for a in contacts(p1)]
            kp.action('actor.reveal',{'id':spider,'accounts':['player1'],'visible':False})
            assert spider not in [a['id'] for a in contacts(p1)]
            move(one,6)
            # A custom hidden NPC does not become visible just because a preset reveals spiders.
            secret=kp.action('npc.create',{'name':'不得泄露的暗哨','numbers':{'str':10,'dex':10,'wil':10,'hp':3,'armor':0,'location':6}})['id']
            assert secret not in [a['id'] for a in contacts(p1)]
            checks.append('server-side sightings: same-room players, per-player preset NPC discovery, no cross-room/other-player leaks, manual hide and current NPC movement; only display fields')
            status=kp.request('/package/web/status');assert status['running'],status
            with owned_room(url,None,status,'native'),sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True)
                gm=browser.new_page(viewport={'width':1600,'height':1000});gm.on('pageerror',lambda e:errors.append(str(e)))
                gm.goto(runtime.origin+'/sessions/native-kp/')
                gm.locator('[name=loginName]').fill('kp');gm.locator('[name=password]').fill(password)
                gm.get_by_role('button',name='进入冒险',exact=True).click();gm.locator('.identity').wait_for()
                assert not gm.locator('#room-network,.kp-map,#kp-ai-embedded').count()
                gm.locator('a[href="#/gm/room"]').click();gm.locator('#room-network').wait_for()
                assert not gm.locator('.kp-map,#kp-ai-embedded').count()
                gm.locator('[data-action=web-room]').click()
                assert gm.locator('#web-setup').input_value().startswith('OCOC-ROOM1.')
                for route in ('create','manage','join'):
                    assert gm.locator('#dialog a[href="'+url+'/'+route+'"]').count()==1
                gm.locator('#dialog [data-action=close]').first.click()
                gm.locator('a[href="#/gm/map"]').click();expect(gm.locator('.kp-map [data-action=map-room]')).to_have_count(10)
                gm.locator('.kp-map [data-args=\'{"index":6}\']').click()
                expect(gm.locator('.room-roster')).to_contain_text('角色 2 位')
                expect(gm.locator('.kp-map')).not_to_contain_text('蜘蛛')
                expect(gm.locator('.room-roster')).not_to_contain_text('不得泄露')
                gm.screenshot(path=str(output/'kp-map.png'))
                gm.locator('a[href="#/gm/rulings"]').click()
                gm.locator('#kp-ai-embedded .reference-editor').wait_for()
                expect(gm.locator('#kp-ai-embedded .ai-view')).to_have_css('min-height','420px',timeout=15000)
                expect(gm.locator('#chat-column .messenger')).to_be_visible()
                assert not gm.locator('#room-network,.kp-map,.console-tabs').count()
                p2.action('request',{'kind':'free','manual':True,'text':'请裁决门后的声音'})
                expect(gm.locator('.ruling-work')).to_contain_text('请裁决门后的声音',timeout=15000)
                p2.action('chat',{'operation':'chat.message.send','input':{'channelId':'general','text':'裁决页聊天测试'}})
                expect(gm.locator('#message-queue-list')).to_contain_text('1',timeout=15000)
                expect(gm.locator('#chat-column')).to_contain_text('裁决页聊天测试',timeout=15000)
                draft=gm.locator('#kp-ai-embedded .reference-editor');draft.fill('尚未发送的主持草稿')
                kp.action('world',{'operation':'round'})
                gm.wait_for_timeout(3200);expect(draft).to_contain_text('尚未发送的主持草稿')
                assert not calls
                for width,height in [(1600,1000),(1440,900),(1366,768)]:
                    gm.set_viewport_size({'width':width,'height':height})
                    gm.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                    assert gm.evaluate('document.documentElement.scrollWidth<=innerWidth+1 && document.documentElement.scrollHeight<=innerHeight+1')
                    assert not gm.locator('#main .page-head').count()
                    outer=gm.locator('.ruling-ai').bounding_box();inner=gm.locator('#kp-ai-embedded .ai-view').bounding_box()
                    assert abs(outer['height']-inner['height'])<3 and abs(outer['width']-inner['width'])<3,(width,height,outer,inner)
                before=gm.locator('.rulings-grid').bounding_box()['height']
                gm.get_by_role('button',name='收起顶栏',exact=True).click()
                assert gm.locator('.rulings-grid').bounding_box()['height']>before+40
                expect(draft).to_contain_text('尚未发送的主持草稿')
                assert gm.locator('.topbar').bounding_box()['height']==30
                gm.screenshot(path=str(output/'kp-rulings-collapsed.png'))
                gm.get_by_role('button',name='展开顶栏',exact=True).click()
                gm.screenshot(path=str(output/'kp-rulings.png'))
                checks.append('independent room/map/rulings pages; KP map excludes NPCs; queues, pinned chat and embedded conversation coexist; drafts survive polling; desktop viewport fits')
                gm.locator('#kp-ai-embedded .review-open').click();gm.locator('.keeper-ai-queue [data-settings]').click()
                gm.locator('.ai-dialog [data-settings] [name=enabled]').check();gm.locator('.ai-dialog [data-settings] button').click()
                expect(gm.locator('[data-status]')).to_contain_text('已保存')
                expect(gm.locator('[data-ai-readiness]')).to_contain_text('AI 查询将返回空列表')
                gm.locator('[data-close]').click()
                draft.fill('主持咨询：请说明怎样进行探索。');gm.locator('#kp-ai-embedded #send').click()
                expect(gm.locator('#kp-ai-embedded #history')).to_contain_text('OFFLINE_REPLY',timeout=30000)
                assert len(calls)==1
                expect(gm.locator('#kp-ai-embedded #history h2')).to_have_text('房间概览')
                expect(gm.locator('#kp-ai-embedded #history tbody td').first).to_have_text('入口隧道')
                gm.locator('#kp-ai-embedded .manage-sessions').click()
                expect(gm.locator('[name=historyTurns]')).to_have_value('4')
                gm.locator('[name=pinned]').check();gm.locator('[name=historyTurns]').select_option('2');gm.locator('.session-manager .save').click()
                expect(gm.locator('.session-manager .status')).to_have_text('设置已保存')
                gm.locator('.session-close').click();gm.locator('#kp-ai-embedded .review-open').click()
                gm.locator('.keeper-ai-queue [data-history]').check()
                gm.locator('.ai-assistance-list details summary').first.click()
                expect(gm.locator('.ai-assistance-list .ai-markdown h2')).to_contain_text('房间概览',timeout=15000)
                expect(gm.locator('.ai-assistance-list table')).to_have_count(1)
                gm.locator('.keeper-ai-queue [data-history]').uncheck()
                gm.screenshot(path=str(output/'ai-markdown.png'))
                gm.locator('#kp-ai-embedded .usage-open').click();expect(gm.locator('.usage-status')).to_have_text('查询完成')
                expect(gm.locator('.metric strong').first).to_have_text('40');expect(gm.locator('.budgets')).to_contain_text('每日不限额')
                gm.screenshot(path=str(output/'ai-usage.png'));gm.locator('.usage-close').click()
                checks.append('native KP usage panel reports provider-confirmed 40 tokens separately from reserves with unlimited daily default')
                checks.append('native KP and consultation queue render Markdown headings/tables; embedded owner preferences persist through package public API')
                for path in ('pack.js','views.js','reference-editor.js','views.css','markdown.js','markdown.css','session-manager.js','session-manager.css','usage.js','usage.css'):
                    assert kp.http.get(kp.prefix+'/ai-ui/'+path).status_code==200
                assert kp.http.get(kp.prefix+'/ai-ui/providers.js').status_code==404
                assert kp.request('/api/v1/ai/drafts',{},True)['code']=='INPUT_INVALID'
                checks.append('updated native AI component and semantic editor load through explicit public resources; KP send dispatches once; provider admin stays private; malformed drafts remain rejected')
                players=[];games=[]
                for i in (1,2):
                    context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();page.goto(url)
                    page.locator('#name').fill('nativeplayer'+str(i));page.locator('#password').fill('123456')
                    page.get_by_role('button',name='注册',exact=True).click();page.locator('#lobby').wait_for()
                    page.locator('#room-code').fill(status['roomCode']);page.get_by_role('button',name='加入房间',exact=True).click()
                    with context.expect_page() as popup:page.locator('#enter-game').click()
                    game=popup.value;game.on('pageerror',lambda e:errors.append(str(e)));game.wait_for_load_state();page.close()
                    game.locator('#connect').click();game.locator('#game-login').wait_for(timeout=45000)
                    game.locator('#game-name').fill('player'+str(i));game.locator('#game-password').fill(password);game.locator('#game-login button[type=submit]').click()
                    frame=game.frame_locator('#package-frame iframe');frame.locator('.identity').wait_for(timeout=40000)
                    players.append(WebPlayer(frame));games.append(game)
                a,b=players;frame=a.frame
                frame.locator('body').evaluate("()=>location.hash='/play/scene'")
                expect(frame.locator('.player-map-contacts')).to_contain_text('Roquefort')
                expect(frame.locator('.player-map-contacts')).not_to_contain_text('不得泄露')
                assert 'mapNpcCatalog' not in a.state() and 'characters' not in a.state()
                frame.locator('#comm-tab-ai').click();frame.locator('#player-ai-embedded .reference-editor').wait_for()
                editor=frame.locator('#player-ai-embedded .reference-editor')
                editor.fill('/');frame.get_by_role('option',name='/entity',exact=False).click()
                frame.get_by_role('option',name='木栗',exact=False).click()
                expect(editor.locator('.reference-chip')).to_contain_text('木栗')
                frame.locator('#player-ai-embedded #send').click()
                expect(frame.locator('#player-ai-embedded #history')).to_contain_text('等待 KP',timeout=15000)
                frame.locator('#player-ai-embedded #history .user .reference-chip').click()
                expect(frame.locator('.reference-details dialog')).to_be_visible()
                expect(frame.locator('.reference-details h2')).to_have_text('木栗')
                expect(frame.locator('.reference-details .reference-value')).to_contain_text('数值')
                expect(frame.locator('.reference-details dialog')).to_have_css('border-radius','16px')
                frame.get_by_role('button',name='关闭引用详情').click()
                checks.append('bundled reference inspector resolves authorized values over WebRTC with packaged CSS and close control')
                assert len(calls)==1
                def bridge(player,path,method='GET',body=None,error=False):
                    return player.request('package/ai',{'path':path,'method':method,**({'body':body} if body is not None else {})},error)
                a.action('chat',{'operation':'chat.message.send','input':{'channelId':'sv-scene-6','text':'网页资料查询验收'}})
                found=bridge(a,'ai/data/search','POST',{'types':['chat'],'query':'网页资料查询验收'})['items']
                assert len(found)==1
                detail=bridge(a,'ai/data/read','POST',{'refs':[found[0]['ref']]})['items']
                assert detail[0]['data']['text']=='网页资料查询验收'
                assert bridge(a,'ai/data/search','POST',{'types':['chat'],'accountId':'kp'},True).get('code')
                bridge(a,'ai/data/chat','POST',{'channelId':'sv-scene-6'})
                events=bridge(a,'ai/data/search','POST',{'types':['event']})['items']
                assert events
                assert bridge(a,'ai/data/case','POST',{'refs':[events[0]['ref']]})['items']
                sessions=bridge(a,'ai/sessions?archived=false')['items'];assert len(sessions)==1
                sid=sessions[0]['sessionId'];assert bridge(b,'ai/sessions/'+sid,error=True)['code']=='NOT_VISIBLE'
                frame.locator('#player-ai-embedded .manage-sessions').click()
                expect(frame.locator('.session-manager .settings')).to_be_visible();expect(frame.locator('.session-manager .diagnostics')).to_be_hidden()
                frame.locator('[name=pinned]').check();frame.locator('[name=historyTurns]').select_option('1');frame.locator('.session-manager .save').click()
                expect(frame.locator('.session-manager .status')).to_have_text('设置已保存')
                saved=bridge(a,'ai/sessions/'+sid)['session'];assert saved['pinned'] and saved['historyTurns']==1
                frame.locator('.session-manager .archive').click();expect(frame.locator('.session-manager .status')).to_have_text('会话已归档')
                frame.locator('.session-manager .archive').click();expect(frame.locator('.session-manager .status')).to_have_text('会话已恢复')
                frame.locator('.session-close').click()
                checks.append('bundled web session manager saves per-owner preferences and archives/restores through WebRTC bridge; KP diagnostics hidden')
                for path in ('ai/settings','ai/tasks','ai/references?kind=data&q=','ai/references?kind=entity&q=&accountId=kp'):
                    assert bridge(a,path,error=True)['code']=='AI_ROUTE_NOT_EXPOSED'
                task=bridge(a,'ai/sessions/'+sid)['items'][0]
                assert bridge(a,'ai/references/resolve','POST',{'tokens':['[[entity:'+secret+'@1]]']},True).get('code') or '不得泄露' not in json.dumps(bridge(a,'ai/references/resolve','POST',{'tokens':['[[entity:'+secret+'@1]]']},True),ensure_ascii=False)
                denied=ai(kp,'ai.request.dispatch',{'requestId':task['requestId']},True)
                assert denied.get('code')=='EXTERNAL_SCOPE_DISABLED',denied
                assert len(calls)==1
                result(ai(kp,'ai.settings.update',{'enabled':True,'profileId':'offline','externalSources':{'public':True,'kp':False,'private':True},'auto':{'enabled':False,'channelIds':['general'],'prefix':'!ai '}}))
                result(ai(kp,'ai.request.dispatch',{'requestId':task['requestId']}))
                expect(frame.locator('#player-ai-embedded #history')).to_contain_text('需要补充信息',timeout=30000)
                expect(frame.locator('#player-ai-embedded #history')).to_contain_text('OFFLINE_REPLY')
                assert len(calls)==2
                editor.fill('玩家直接对话验收');frame.locator('#player-ai-embedded #send').click()
                expect(frame.locator('#player-ai-embedded #history .assistant h2')).to_have_count(2,timeout=30000)
                assert len(calls)==3
                expect(frame.locator('.response-choices fieldset').last).to_have_css('border-radius','12px')
                frame.get_by_role('button',name='继续了解',exact=True).last.click()
                expect(frame.locator('#player-ai-embedded #text')).to_have_text('请继续说明可见资料')
                assert len(calls)==3
                frame.locator('#player-ai-embedded #text').fill('')
                checks.append('bundled structured choices fill composer without extra calls or execution')
                # The data API and semantic references use the same package knowledge projection.
                visible_entities=bridge(a,'ai/data/search','POST',{'types':['entity'],'limit':50})['items']
                assert all(v['label']!='不得泄露的暗哨' for v in visible_entities)
                assert bridge(a,'ai/access')['defaultLevel']=='player'
                frame.locator('#player-ai-embedded .usage-open').click();expect(frame.locator('.usage-status')).to_have_text('查询完成')
                expect(frame.locator('.metric strong').first).to_have_text('80');expect(frame.locator('.scope option[value=room]')).to_be_hidden()
                assert bridge(a,'ai/usage?scope=room',error=True)['code']=='PERMISSION_DENIED'
                assert bridge(a,'ai/usage?scope=mine&accountId=kp',error=True)['code']=='AI_ROUTE_NOT_EXPOSED'
                assert bridge(b,'ai/usage')['totals']['confirmedTokens']==0
                frame.locator('.usage-close').click()
                checks.append('bundled WebRTC usage component and API show only requesting player usage; room/account injection denied')
                assert frame.locator('#player-ai-embedded #send').evaluate('(e)=>{const r=e.getBoundingClientRect();return r.right<=innerWidth && r.bottom<=innerHeight}')
                games[0].screenshot(path=str(output/'ai-web.png'))
                frame.locator('body').evaluate("""()=>{const original=stumpsvilleWeb.api;let lost=false;stumpsvilleWeb.api=async(path,body)=>{const r=await original(path,body);if(!lost&&path==='package/ai'&&body?.body?.op==='ai.session.create'){lost=true;throw Error('SIMULATED_AI_RESPONSE_LOST');}return r;};}""")
                frame.locator('#player-ai-embedded .new-chat').click()
                expect(frame.locator('.native-ai-recovery')).to_be_visible()
                frame.locator('.native-ai-recovery button').click()
                expect(frame.locator('.native-ai-recovery')).to_be_hidden()
                assert len(bridge(a,'ai/sessions?archived=false')['items'])==2
                frame.locator('#player-ai-embedded .manage-sessions').click();frame.locator('.session-manager .delete').click();frame.locator('.confirm-delete').click()
                expect(frame.locator('.session-manager .status')).to_have_text('会话已删除')
                assert len(bridge(a,'ai/sessions?archived=false')['items'])==1
                frame.locator('[data-filter=archived]').click();expect(frame.locator('.session-manager .session-link')).to_have_count(0)
                frame.locator('.session-close').click()
                frame.locator('#comm-tab-chat').click();expect(frame.locator('#player-ai-embedded')).not_to_be_visible()
                frame.get_by_role('button',name='收起顶栏',exact=True).click()
                assert frame.locator('.topbar').bounding_box()['height']==30
                assert b.frame.get_by_role('button',name='收起顶栏',exact=True).is_visible()
                frame.get_by_role('button',name='展开顶栏',exact=True).click()
                assert not errors,errors
                checks.append('two real web players load bundled native components/CSS; player enable switch, direct dispatch and player-safe replies; account/known-data/hidden-reference/management isolation, archive view and deletion; lost-response receipt recovery does not duplicate sessions; tab switch hides AI while preserving its mounted conversation')
                browser.close()
        with running('sight-restart',data=output/'game',ai_config=config,no_browser=True) as (runtime,_):
            p1=Account(runtime.origin,'player1',saved_password,'restart')
            seen=p1.state()['mapContacts'];assert any(a['name']=='Roquefort' for a in seen)
            assert two not in [a['id'] for a in seen] and spider not in [a['id'] for a in seen]
            checks.append('same-archive restart preserves personal discoveries and explicit hides')
    record={'checkedAt':datetime.now().astimezone().isoformat(),'passed':len(checks),'checks':checks,'provider':'loopback fixture only','cloudTested':False,'realSaveChanged':False}
    write_json(PACK/'tests/map-ai-results.json',record);print(json.dumps(record,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
