"""Two real browser players and isolated game data; cloud tests require --cloud."""
import argparse
import json
import secrets
import ssl
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright, expect
from harness import PACK, running, Account
from verify_integrations import directory


@contextmanager
def test_directory(output,cloud,relay):
    if not cloud:
        with directory(output,web=True) as (config,url):yield config,url,None
        return
    source=PACK.parents[1]/'engineering/network-p2p/local/client-config.json'
    original=json.loads(source.read_text(encoding='utf-8-sig'))
    config={k:original[k] for k in ('directory','publisherToken','caFile') if k in original}
    if config.get('caFile'):config['caFile']=str((source.parent/config['caFile']).resolve())
    config['relayOnly']=relay
    target=output/'cloud-client.json';target.write_text(json.dumps(config),encoding='utf-8')
    yield target,config['directory'],config.get('caFile')


@contextmanager
def owned_room(url,ca_file,status,suffix):
    with httpx.Client(base_url=url,verify=ssl.create_default_context(cafile=ca_file),trust_env=False,timeout=30) as owner:
        registration=owner.post('/v1/web/auth/register',json={'name':'owner'+suffix,'password':'123456'}).json()
        owner.headers['X-CSRF-Token']=registration['csrf']
        response=owner.post('/v1/web/rooms/create',json={'setupString':status['creationString'],'public':False,'password':''});assert response.status_code==200,response.text
        try:yield owner
        finally:
            response=owner.post('/v1/web/rooms/'+status['roomId']+'/manage',json={'action':'close'})
            assert response.status_code==200,response.text


class WebPlayer:
    def __init__(self, frame): self.frame=frame
    def request(self,path,body=None,error=False):
        result=self.frame.locator('body').evaluate("async(_,a)=>{try{return {ok:true,result:await stumpsvilleWeb.api(a.path,a.body===null?undefined:a.body)}}catch(e){return {ok:false,result:{code:e.code||e.message,status:e.status}}}}",{'path':path.lstrip('/'),'body':body})
        assert result['ok'] or error,result
        return result['result']
    def state(self):return self.request('package/state')
    def action(self,op,args=None,key=None,error=False):return self.request('package/action',{'id':key or str(uuid.uuid4()),'operation':op,'args':args or {}},error)


def main(cloud=False,relay=False):
    # Remote control/storage/action calls cross the relay in sequence. Keep a
    # bounded cloud UI wait without treating the local 5-second default as SLA.
    expect.set_options(timeout=30000 if cloud else 5000)
    suffix=secrets.token_hex(4) if cloud else ''
    output=PACK/'tests/output'/('web-'+('cloud-turn-' if relay else 'cloud-' if cloud else '')+secrets.token_hex(4));output.mkdir(parents=True)
    checks=[];errors=[]
    with test_directory(output,cloud,relay) as (config,url,ca_file),running('web',data=output/'game',web_config=config,no_browser=True) as (runtime,password):
        kp=Account(runtime.origin,'kp',password,'web-test-kp')
        status=kp.request('/package/web/status');assert status['running'],status
        assert runtime.modules.p2p_config is None
        with owned_room(url,ca_file,status,suffix) as owner:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True)
                games=[];players=[];contexts=[];accounts=[]
                for i in (1,2):
                    # Only automated test browsers accept the project's test CA this way.
                    # Python and the actual host still verify it explicitly.
                    context=browser.new_context(viewport={'width':1440,'height':960},ignore_https_errors=cloud);contexts.append(context)
                    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(url);page.locator('#name').fill('webplayer'+str(i)+suffix);page.locator('#password').fill('123456');page.get_by_role('button',name='注册',exact=True).click();page.locator('#lobby').wait_for()
                    accounts.append(context.request.get(url+'/v1/web/me').json()['accountId'])
                    page.locator('#room-code').fill(status['roomCode']);page.get_by_role('button',name='加入房间',exact=True).click();page.locator('#room-title').wait_for()
                    assert page.locator('#package-frame iframe').count()==0
                    with context.expect_page() as popup:page.locator('#enter-game').click()
                    game=popup.value;games.append(game);game.on('pageerror',lambda e:errors.append(str(e)));game.wait_for_load_state();page.close()
                    if relay:game.locator('#relay').check()
                    game.locator('#connect').click();game.locator('#game-login').wait_for(timeout=45000)
                    game.locator('#game-name').fill('kp' if i==1 else 'player2');game.locator('#game-password').fill(password);game.locator('#game-login button[type=submit]').click()
                    if i==1:
                        expect(game.locator('#error')).to_contain_text('REMOTE_PLAYER_REQUIRED');assert game.locator('#package-frame iframe').count()==0
                        game.locator('#game-name').fill('player1');game.locator('#game-password').fill(password);game.locator('#game-login button[type=submit]').click()
                    frame=game.frame_locator('#package-frame iframe');frame.locator('.identity').wait_for(timeout=40000)
                    if relay:expect(game.locator('#network')).to_contain_text('TURN 中继',timeout=15000)
                    assert not frame.locator('[data-action=web-room],[name=loginName]').count()
                    assert frame.locator('body').evaluate("()=>{try{parent.document.body;return false}catch{return true}}")
                    assert frame.locator('body').evaluate("()=>{try{window.localStorage;return false}catch{return true}}")
                    players.append(WebPlayer(frame))
                p1,p2=players
                if cloud:checks.append('public HTTPS directory and two real browser players; '+('both connections verified as TURN relay' if relay else 'public signaling with negotiated ICE route'))
                checks.append('platform code admission and independent game pages; six-character passwords; two game identities; KP remote login rejected; opaque sandbox')
                for i,p in enumerate(players,1):
                    p.action('draft',{'preset':'mul' if i==1 else 'dou','name':'网页鼠'+str(i)});kp.action('approve',{'account':'player'+str(i)});p.action('ready',{'ready':True})
                kp.action('world',{'operation':'start'})
                for game in games:game.frame_locator('#package-frame iframe').locator('body').evaluate("()=>location.hash='/play/scene'")
                actor=p1.state()['character']['instanceId'];kp.action('actor.update',{'id':actor,'numbers':{'dexMax':20,'dex':20,'wilMax':20,'wil':20,'maxHp':100,'hp':100}})
                pending_id=str(uuid.uuid4());first=p1.action('scene.action',{'action':'tunnel-ground','choice':'inspect'},pending_id)
                assert first['status']=='processing' and not p1.state()['sceneAutomation']['executorOnline']
                gm=browser.new_page();gm.goto(runtime.origin+'/sessions/browser-web-kp/');gm.locator('[name=loginName]').fill('kp');gm.locator('[name=password]').fill(password);gm.get_by_role('button',name='进入冒险',exact=True).click();gm.locator('.identity').wait_for()
                for _ in range(40):
                    result=p1.action('scene.action',{'action':'tunnel-ground','choice':'inspect'},pending_id)
                    if result.get('status')=='completed':break
                    games[0].wait_for_timeout(300)
                assert result['status']=='completed',result
                gm.close()
                actions=set()
                def act(action,choice):
                    key=str(uuid.uuid4());args={'action':action,'choice':choice};result=p1.action('scene.action',args,key)
                    for _ in range(8):
                        if result.get('status')!='processing':break
                        for job in kp.request('/package/scene-executor',{})['jobs']:kp.action('scene.autorun',{'jobId':job['id']},job['commandId'])
                        result=p1.action('scene.action',args,key)
                    assert result['status']=='completed' and result['narrative'] and result['process'],result
                    assert p1.action('scene.action',args,key)==result
                    actions.add(action);return result
                def move(place):assert p1.action('request',{'kind':'travel','destination':place})['status']=='automatic'
                act('tunnel-ground','inspect');act('tunnel-cheese','inspect');assert act('tunnel-cheese','careful')['checks'][0]['passed']
                assert all(c['id']!='tunnel-trap' for p in p2.state()['locations'] for c in p['clues'])
                move(2);act('gate-handle','inspect');act('gate-open','brace');move(3);act('courtyard-pool','inspect');act('courtyard-pool','money');act('courtyard-ladders','inspect')
                move(4);act('house-pots','search');act('house-pots','take');move(3);move(5);act('house-painting','inspect');move(3);move(6);act('web-inspect','inspect');act('web-call','whisper');act('web-call','rescue')
                move(3);move(7);act('hall-observe','inspect');act('hall-negotiate','talk');move(8);act('factory-equipment','inspect');act('factory-equipment','paddle');act('factory-exits','survey');act('factory-exits','iron');move(9);act('cage-gate','inspect');act('cage-listen','listen');act('cage-listen','flute');act('cage-gate','open');move(10);act('cave-cheese','inspect');act('cave-sleeper','observe');act('cave-sleeper','talk');act('cave-cheese','take')
                assert len(actions)==18 and runtime.package.state['sceneState']['cheese10']==7
                checks.append('two PL characters/readiness; KP browser resumes queued action; all 18 presets over actual WebRTC with dice/narrative/resources/clues and same-ID idempotence')
                for path in ('package/bundle','package/integrations','package/scene-executor','package/web/status','api/v1/ai/tasks','api/v1/host-control/accounts'):
                    assert p1.request(path,error=True)['code'] in ('ROUTE_NOT_EXPOSED','CONTENT_NOT_READY')
                assert p1.request('package/state?preview=kp',error=True)['code']=='QUERY_NOT_EXPOSED'
                assert p1.action('actor.update',{'id':actor,'numbers':{'pips':999}},error=True).get('code')
                assert 'truth' not in json.dumps(p1.state()) and 'allLocations' not in p1.state()
                p1.action('chat',{'operation':'chat.message.send','input':{'channelId':'sv-party','text':'队伍网页测试'}})
                assert any(m['text']=='队伍网页测试' for m in p2.request('package/chat/history',{'channelId':'sv-party','limit':20})['items'])
                dm=p1.action('chat',{'operation':'chat.direct.open','input':{'accountId':'player2'}})['channelId']
                p1.action('chat',{'operation':'chat.message.send','input':{'channelId':dm,'text':'双人网页私聊'}})
                assert any(m['text']=='双人网页私聊' for m in p2.request('api/v1/chat/history',{'channelId':dm,'limit':20})['items'])
                assert kp.request('/api/v1/chat/history',{'channelId':dm,'limit':20},True).get('code')
                p1.action('chat',{'operation':'chat.message.send','input':{'channelId':'sv-scene-10','text':'当前场景私域测试'}})
                assert p2.request('package/chat/history',{'channelId':'sv-scene-10','limit':20},error=True).get('code')
                checks.append('remote management/AI/setup and query injection denied; game-side permission guards remain active; scene and personal clue isolation')
                frame=games[0].frame_locator('#package-frame iframe')
                before=p1.state()['character']['numbers']['checks']
                frame.locator('body').evaluate("()=>{const original=stumpsvilleWeb.api;let lost=false;stumpsvilleWeb.api=async(path,body)=>{const result=await original(path,body);if(!lost&&path.startsWith('package/action')&&body?.operation==='check'){lost=true;throw Error('SIMULATED_RESPONSE_LOST')}return result;};}")
                frame.locator('[data-action=check]').click();frame.locator('#dialog-form button[type=submit]').click()
                expect(frame.locator('#toast')).to_contain_text('SIMULATED_RESPONSE_LOST');frame.locator('#dialog').press('Escape')
                expect(frame.locator('[data-action=recover]')).to_be_visible(timeout=15000)
                key='stumpsville.pending./.player1'
                saved=frame.locator('body').evaluate('(el,key)=>stumpsvilleWeb.storage.getItem(key)',key);assert saved
                stale=json.loads(saved);stale['_webRules']='old-rules'
                frame.locator('body').evaluate('(el,a)=>{stumpsvilleWeb.storage.setItem(a.key,a.value);return stumpsvilleWeb.flush()}',{'key':key,'value':json.dumps(stale)})
                frame.locator('[data-action=recover]').click();expect(frame.locator('#toast')).to_contain_text('规则版本已变化')
                assert p1.state()['character']['numbers']['checks']==before+1
                frame.locator('body').evaluate('(el,a)=>{stumpsvilleWeb.storage.setItem(a.key,a.value);return stumpsvilleWeb.flush()}',{'key':key,'value':saved})
                frame.locator('[data-action=recover]').click();expect(frame.locator('[data-action=recover]')).to_have_count(0)
                assert p1.state()['character']['numbers']['checks']==before+1
                checks.append('real UI lost-response recovery persists original command ID; stale rules stop replay; recovery does not reroll; private and party chats cross browsers')
                frame=games[0].frame_locator('#package-frame iframe');frame.locator('[name=locale]').select_option('en');expect(frame.locator('.brand')).to_contain_text('Stumpsville')
                frame.locator('body').evaluate("()=>{stumpsvilleWeb.storage.setItem('sv.font','18');return stumpsvilleWeb.flush()}")
                assert players[1].frame.locator('body').evaluate("()=>stumpsvilleWeb.storage.getItem('sv.font')") is None
                try:frame.locator('body').evaluate("()=>{stumpsvilleWeb.storage.setItem('password','bad');return stumpsvilleWeb.flush()}")
                except Exception as e:assert 'STORAGE_KEY_REJECTED' in str(e)
                else:raise AssertionError('storage key escaped')
                assert frame.locator('body').evaluate('()=>document.documentElement.scrollHeight<=innerHeight+1')
                assert games[0].evaluate('document.documentElement.scrollHeight<=innerHeight+1')
                games[0].screenshot(path=str(output/'web-player.png'))
                games[0].locator('#leave').click();games[0].locator('#connect').click();games[0].locator('#game-login').wait_for(timeout=45000)
                games[0].locator('#game-name').fill('player1');games[0].locator('#game-password').fill(password);games[0].locator('#game-login button[type=submit]').click();frame.locator('.identity').wait_for(timeout=40000)
                expect(frame.locator('[name=locale]')).to_have_value('en');assert frame.locator('body').evaluate("()=>stumpsvilleWeb.storage.getItem('sv.font')")=='18'
                checks.append('on-demand English and portraits; declared storage only; platform/room/game scoping; reconnect restores preferences; one viewport')
                response=owner.post('/v1/web/rooms/'+status['roomId']+'/manage',json={'action':'ban','accountId':accounts[0]});assert response.status_code==200,response.text
                expect(games[0].locator('#package-frame iframe')).to_have_count(0,timeout=20000)
                assert p2.state()['accountId']=='player2'
                response=owner.post('/v1/web/rooms/'+status['roomId']+'/manage',json={'action':'unban','accountId':accounts[0]});assert response.status_code==200,response.text
                assert not errors,errors
                browser.close()
                checks.append('blacklist tears down old peer/frame without affecting another player; unban; no browser JavaScript errors')
            kp.request('/package/web/stop',{});assert not kp.request('/package/web/status')['running'];assert kp.state()['initialized']
            checks.append('stop-file graceful web shutdown preserves borrowed host and game archive')
    record={'passed':True,'checkedAt':datetime.now().astimezone().isoformat(),'presets':sorted(actions),'checks':checks,'cloud':cloud,'forcedTurn':relay,
            'browserTestCAException':cloud,'samePhysicalComputer':True,'temporaryRoomClosed':True}
    result_name='web-cloud-turn-results.json' if relay else 'web-cloud-results.json' if cloud else 'web-results.json'
    (PACK/'tests'/result_name).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(record,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--cloud',action='store_true');parser.add_argument('--relay',action='store_true')
    args=parser.parse_args()
    if args.relay and not args.cloud:parser.error('--relay requires --cloud')
    main(args.cloud,args.relay)
