"""Stumpsville strict knowledge, public HTTP + embedded browser acceptance."""
import json
import secrets
import time
from datetime import datetime
from harness import PACK,running,provision,Account
from verify_integrations import provider,ai,result
from integrations import write_json
from build_web import build
from playwright.sync_api import sync_playwright,expect


def known(account):
    page=account.request('/api/v1/knowledge/search',{'limit':50})
    refs=[i['ref'] for i in page['items']]
    return [i for offset in range(0,len(refs),12)
        for i in account.request('/api/v1/knowledge/read',{'refs':refs[offset:offset+12]})['items']]


def main():
    output=PACK/'tests/output'/('strict-known-'+secrets.token_hex(4));output.mkdir(parents=True)
    checks=[];payloads=[]
    def respond(request):
        payloads.append(request)
        return {'role':'assistant','content':json.dumps({'kind':'known','evidence':[],'next':'ask_kp'})}
    with provider(output,respond) as (config,calls):
        with running('strict-known',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
            kp,p1,p2=provision(runtime,password)
            assert p1.state()['knowledge']['status']=='ready'
            assert len([i for i in known(p1) if i['facetId']=='scene'])==1
            assert p1.state()['character']['owner']=='player1'
            checks.append('initial entry observation and explicitly subscribed own sheet work through normal player UI')
            assert p1.state()['session']['numbers']['phase']==1
            kp.action('location.publish',{'index':2,'clues':[]})
            p1.action('request',{'kind':'travel','destination':2,'text':'正常 PL 移动验收'})
            assert p1.state()['character']['numbers']['location']==2
            assert any(i['facetId']=='scene' and i['data']['index']==2 for i in known(p1))
            assert p1.state()['sceneActions']
            checks.append('ordinary player travel uses disclosed navigation and updates personal scene actions')
            kp.action('location.publish',{'index':3,'clues':[]})
            assert not any(i['facetId']=='scene' and i['data']['index']==3 for i in known(p1)+known(p2))
            assert not any(p['index']==3 and p.get('known') for p in p2.state()['locations'])
            assert all(e['configurationId'] not in ('sv.location','sv.scene','sv.world') for e in p1.request('/api/v1/view')['entities'].values())
            checks.append('publishing does not disclose scenes and legacy /view excludes managed world data')
            actor=p1.state()['character']['instanceId']
            kp.command('entity.update',{'id':actor,'numbers':{'location':3}})
            courtyard=next(i for i in known(p1) if i['facetId']=='scene' and i['data']['index']==3)
            assert 'items' not in p2.request('/api/v1/knowledge/read',{'refs':[courtyard['ref']]},allow_error=True)
            assert 'items' not in p2.request('/api/v1/ai/references?kind=entity&q=庭院',allow_error=True)
            checks.append('trusted movement observes only for its owner; copied refs and legacy references fail')
            npc=next(e for e in kp.request('/api/v1/view')['entities'].values() if e['configurationId']=='sv.npc')
            kp.action('actor.reveal',{'id':npc['instanceId'],'accounts':['player1'],'visible':True})
            identity=next(i for i in known(p1) if i['facetId']=='identity' and i['data']['entityId']==npc['instanceId'])
            assert not any(i['facetId']=='identity' and i['data']['entityId']==npc['instanceId'] for i in known(p2))
            kp.action('actor.reveal',{'id':npc['instanceId'],'accounts':['player1'],'visible':False})
            assert 'items' not in p1.request('/api/v1/knowledge/read',{'refs':[identity['ref']]},allow_error=True)
            checks.append('NPC identity disclosure is personal and legacy discover controls revoke the actual grant')
            place=kp.state()['allLocations']['3']
            kp.action('location.save',{'index':3,'revision':place.get('revision',0),'description':'ONLY_NEW_OBSERVATION_20261117','truth':place.get('truth','')})
            kp.action('location.publish',{'index':3,'clues':[]})
            old=p1.request('/api/v1/knowledge/read',{'refs':[courtyard['ref']]})['items'][0]
            assert old==courtyard and 'ONLY_NEW_OBSERVATION' not in json.dumps(p1.state(),ensure_ascii=False)
            checks.append('fixed scene and UI remain byte-identical after current description publication')
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True)
                try:
                    page=browser.new_page();page.goto(runtime.origin+'/sessions/kp/')
                    page.locator('[name=loginName]').fill('kp');page.locator('[name=password]').fill(password)
                    page.get_by_role('button',name='进入冒险',exact=True).click();page.locator('.identity').wait_for()
                    page.goto(runtime.origin+'/sessions/kp/#/gm/locations/3')
                    page.get_by_role('button',name='向玩家揭示',exact=True).click()
                    page.locator('[name=account][value=player2]').check()
                    page.get_by_role('button',name='揭示地点',exact=True).click()
                    expect(page.get_by_text('已向指定玩家揭示地点',exact=True).first).to_be_visible()
                    page.goto(runtime.origin+'/sessions/kp/#/gm/room')
                    expect(page.get_by_role('heading',name='个人已知资料',exact=True)).to_be_visible()
                    page.screenshot(path=str(output/'kp-known.png'),full_page=True)
                    player=browser.new_page();player.goto(runtime.origin+'/sessions/player1/')
                    player.locator('[name=loginName]').fill('player1');player.locator('[name=password]').fill(password)
                    player.get_by_role('button',name='进入冒险',exact=True).click();player.locator('.identity').wait_for()
                    player.goto(runtime.origin+'/sessions/player1/#/play/scene')
                    expect(player.locator('.scene-heading')).to_contain_text('观察记录')
                    expect(player.locator('.scene-description')).not_to_contain_text('ONLY_NEW_OBSERVATION')
                    player.screenshot(path=str(output/'pl-known.png'),full_page=True)
                finally:browser.close()
            new=next(i for i in known(p2) if i['facetId']=='scene' and i['data']['index']==3)
            assert new['data']['description']=='ONLY_NEW_OBSERVATION_20261117'
            assert old['ref']!=new['ref']
            checks.append('KP reveal UI issues a new personal snapshot without replacing another player old observation')
            result(ai(kp,'ai.access.update',{'revision':1,'allowPlayerChat':True,'autoApproveBatches':False}))
            result(ai(kp,'ai.settings.update',{'enabled':True,'profileId':'offline','externalSources':{'public':True,'private':True,'kp':True},'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}))
            session=result(ai(p2,'ai.session.create',{'title':'严格已知资料验收'}))
            submitted=result(ai(p2,'ai.session.submit',{'sessionId':session['sessionId'],'text':'我知道哪些场景？'}));assert submitted.get('taskId'),submitted
            deadline=time.monotonic()+25
            while time.monotonic()<deadline:
                rows=p2.request('/api/v1/ai/sessions/'+session['sessionId'])['items']
                if rows and rows[-1]['status'] not in ('received','queued','generating'):break
                time.sleep(.1)
            assert rows[-1]['status']=='needs_input',rows
            initial=json.loads(payloads[-1]['messages'][1]['content'])
            assert 'pack' not in initial and 'sources' not in initial and 'roomFacts' not in initial
            assert rows[-1]['choices']['options'][0]['id']=='ask_kp'
            assert 'items' not in p1.request('/api/v1/ai/sessions/'+session['sessionId'],allow_error=True)
            checks.append('actual provider payload omits package guides and supports only trusted known-answer choices')
            grants=kp.request('/api/v1/knowledge/grants/query',{'subjectMemberId':'member-player2','policyId':'stumpsville-personal-v1','status':'active','limit':50})['items']
            grant=next(g for g in grants if g['resource']['id']==courtyard['data']['entityId'])
            kp.action('knowledge.revoke',{'grantId':grant['grantId'],'revision':grant['revision']})
            assert 'items' not in p2.request('/api/v1/knowledge/read',{'refs':[new['ref']]},allow_error=True)
            assert not any(p['index']==3 and p.get('known') for p in p2.state()['locations'])
            checks.append('KP revoke invalidates detail and player scene projection without revealing new content')
            # Isolated legacy marker only, not a live room or fabricated observation.
            runtime.package.state['locationKnowledge']={'player2':['3']};runtime.package.save()
            before=len(known(p2));p2.state();assert len(known(p2))==before
            kp.action('knowledge.import-current',{'items':[{'account':'player2','index':3}]})
            imported=next(i for i in known(p2) if i['facetId']=='scene' and i['data']['index']==3)
            assert imported['ref']!=new['ref'] and imported['observedAt']>=new['observedAt']
            checks.append('legacy location sets do not authorize reads; explicit import creates a current observation')
        with running('strict-restart',data=output/'game',no_browser=True) as (runtime,_):
            p1=Account(runtime.origin,'player1',password,'restart')
            assert p1.request('/api/v1/knowledge/read',{'refs':[courtyard['ref']]})['items'][0]==courtyard
            assert p1.request('/api/v1/capabilities')['ai']['available'] is False
            checks.append('knowledge survives host restart with AI disabled')
    export=output/'export';build(export)
    text=(export/'index.html').read_text(encoding='utf-8')
    game=json.loads((PACK/'config/game.json').read_text(encoding='utf-8'))
    for place in game['locations']:
        if len(place.get('truth',''))>12:assert place['truth'] not in text
    assert not (export/'config').exists() and not (export/'ai').exists()
    checks.append('player static export excludes package truth, configuration data and AI guide source files')
    record={'checkedAt':datetime.now().astimezone().isoformat(),'passed':len(checks),'checks':checks,
        'realSaveChanged':False,'provider':'deterministic loopback fixture','output':str(output)}
    write_json(PACK/'tests/strict-known-results.json',record);print(json.dumps(record,ensure_ascii=False))


if __name__=='__main__':main()
