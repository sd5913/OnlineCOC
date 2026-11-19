"""Isolated public-API regression for per-player scene knowledge and model context."""
import json,secrets,time
from datetime import datetime
from harness import PACK,running,provision,Account
from integrations import write_json
from verify_integrations import provider,ai,result
from playwright.sync_api import sync_playwright,expect

def main():
    output=PACK/'tests/output'/('ai-knowledge-'+secrets.token_hex(4));output.mkdir(parents=True);checks=[];payloads=[]
    def respond(request):
        payloads.append(json.loads(request['messages'][1]['content']))
        return {'role':'assistant','content':json.dumps({'kind':'plan','text':'仅使用本人已知资料。'})}
    with provider(output,respond) as (config,calls):
        with running('ai-knowledge',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
            kp,p1,p2=provision(runtime,password)
            result(ai(kp,'ai.access.update',{'revision':1,'allowPlayerChat':True,'autoApproveBatches':False}))
            result(ai(kp,'ai.settings.update',{'enabled':True,'profileId':'offline','externalSources':{'public':True,'private':True,'kp':True},'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}))
            kp.action('location.publish',{'index':3,'clues':[]});kp.action('location.publish',{'index':2,'clues':[]})
            def scenes(client):
                refs=[r['ref'] for r in client.request('/api/v1/ai/data/search',{'types':['entity'],'limit':50})['items']]
                return [r for r in client.request('/api/v1/ai/data/read',{'refs':refs})['items'] if r['data']['configurationId']=='sv.location']
            assert all(r['data']['numbers']['index']!=3 for r in scenes(p1)+scenes(p2))
            assert next(l for l in p2.state()['locations'] if l['index']==3)['name']=='未探索地点'
            checks.append('global publication exposes navigation but not scene name/description/features to unvisited players or AI')
            actor=p1.state()['character']['instanceId'];kp.command('entity.update',{'id':actor,'numbers':{'location':3}});kp.state()
            courtyard=next(r for r in scenes(p1) if r['data']['numbers']['index']==3)
            assert not any(r['data']['numbers']['index']==3 for r in scenes(p2))
            denied=p2.request('/api/v1/ai/data/read',{'refs':[courtyard['ref']]},allow_error=True);assert 'items' not in denied,denied
            assert not p2.request('/api/v1/ai/references?kind=entity&q=庭院')['items']
            checks.append('only visiting player gains scene; copied evidence IDs and reference search cannot bypass the audience')
            kp.command('entity.update',{'id':actor,'numbers':{'location':1}});kp.state();assert any(r['data']['numbers']['index']==3 for r in scenes(p1))
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True)
                try:
                    page=browser.new_page();page.goto(runtime.origin+'/sessions/kp/')
                    page.locator('[name=loginName]').fill('kp');page.locator('[name=password]').fill(password)
                    page.get_by_role('button',name='进入冒险',exact=True).click();page.locator('.identity').wait_for()
                    page.goto(runtime.origin+'/sessions/kp/#/gm/locations/2')
                    page.locator('[data-action=select-location][data-args=\'{"index":2}\']').click()
                    page.get_by_role('button',name='向玩家揭示',exact=True).click()
                    page.locator('[name=account][value=player2]').check();page.get_by_role('button',name='揭示地点',exact=True).click()
                    expect(page.get_by_text('已向指定玩家揭示地点',exact=True).first).to_be_visible()
                finally:browser.close()
            assert any(r['data']['numbers']['index']==2 for r in scenes(p2))
            assert 'code' in p1.action('location.reveal',{'index':3,'accounts':['player2']},allow_error=True)
            checks.append('visits persist after leaving; KP UI reveals to named player; PL cannot invoke disclosure')
            session=result(ai(p2,'ai.session.create',{'title':'玩家知识验收'}));result(ai(p2,'ai.session.submit',{'sessionId':session['sessionId'],'text':'哪些信息是我能读取的？'}))
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                rows=p2.request('/api/v1/ai/sessions/'+session['sessionId'])['items']
                if rows and rows[-1]['status']=='review_ready':break
                time.sleep(.1)
            assert payloads and rows[-1]['status']=='review_ready'
            assert 'stumpsville-guide' not in payloads[-1]['sources']
            assert 'stumpsville-player-guide' in payloads[-1]['sources']
            assert 'ernieAwake' not in json.dumps(payloads[-1]['sources'])
            assert 'items' not in p1.request('/api/v1/ai/sessions/'+session['sessionId'],allow_error=True)
            checks.append('real provider payload uses player guide without KP scene hints; other player cannot read the session')
        with running('knowledge-restart',data=output/'game',ai_config=config,no_browser=True) as (runtime,_):
            p1=Account(runtime.origin,'player1',password,'restart1');p2=Account(runtime.origin,'player2',password,'restart2')
            assert any(r['data']['numbers']['index']==3 for r in scenes(p1))
            assert not any(r['data']['numbers']['index']==3 for r in scenes(p2))
            checks.append('restart retains personal visits and disclosure without copying another player knowledge')
    record={'checkedAt':datetime.now().astimezone().isoformat(),'passed':len(checks),'checks':checks,'realSaveChanged':False,'provider':'offline fixture'}
    write_json(PACK/'tests/ai-knowledge-results.json',record);print(json.dumps(record,ensure_ascii=False))

if __name__=='__main__':main()
