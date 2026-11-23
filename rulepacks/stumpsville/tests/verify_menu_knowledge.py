"""Menu disclosure: real HTTP, two players, deterministic AI and real Edge."""
import copy
import json
import secrets
import time
import uuid
from datetime import datetime
from harness import PACK, running, provision
from verify_integrations import provider, ai, result
from verify_strict_known import known
from playwright.sync_api import sync_playwright, expect
from build_web import build
import scene_knowledge


def choices(actions, action):
    return [c['id'] for a in actions if a['id'] == action for c in a['choices']]


def scene(account, index):
    return next(i for i in known(account) if i['facetId'] == 'scene' and i['data']['index'] == index)


def act(kp, player, action, choice):
    key = str(uuid.uuid4()); args = {'action': action, 'choice': choice}
    response = player.action('scene.action', args, key)
    for _ in range(12):
        if response['status'] != 'processing':
            break
        for task in kp.request('/package/scene-executor', {})['jobs']:
            kp.action('scene.autorun', {'jobId': task['id']}, task['commandId'])
        response = player.action('scene.action', args, key)
    assert response['status'] == 'completed', response
    return response


def answer(request):
    tools = [json.loads(m['content']) for m in request['messages'] if m['role'] == 'tool']
    if not tools:
        name, args = 'room_search_knowledge', {}
    elif 'evidenceId' not in tools[-1]['items'][0]:
        selected = next(i for i in tools[-1]['items'] if i['label'] == '庭院')
        name, args = 'room_read_knowledge', {'refs': [selected['ref']]}
    else:
        return {'role': 'assistant', 'content': json.dumps({'kind': 'known',
            'evidence': [tools[-1]['items'][0]['evidenceId']], 'next': 'none'})}
    return {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'c'+str(len(tools)),
        'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}


def ask(account):
    session = result(ai(account, 'ai.session.create', {'title': '菜单知识验收'}))
    submitted = result(ai(account, 'ai.session.submit', {'sessionId': session['sessionId'], 'text': '整理本人庭院观察中的行动。'}))
    assert submitted.get('taskId'), submitted
    deadline = time.monotonic()+30
    while time.monotonic() < deadline:
        rows = account.request('/api/v1/ai/sessions/'+session['sessionId'])['items']
        if rows and rows[-1]['status'] not in ('received', 'queued', 'generating', 'validating'):
            break
        time.sleep(.1)
    assert rows[-1]['status'] == 'review_ready', rows
    return session, rows[-1]


def pure(checks):
    original = copy.deepcopy(scene_knowledge.BASELINE)
    initial = [a for index in range(1, 15) for a in scene_knowledge.menu(original, index, [])]
    text = json.dumps([a for a in initial if not a['id'].startswith('storm-')], ensure_ascii=False)
    for hidden in ('钱袋', '鼠像', 'Jack', '蛇笛', '北方', 'd12', 'd20', '毒咬', 'Ernie', '蜘蛛', '村民', '搅拌桨', '滤布', '屋顶货口', '睡者'):
        assert hidden not in text, hidden
    assert choices(initial, 'courtyard-pool') == ['inspect']
    assert choices(initial, 'factory-exits') == ['survey']
    assert choices(initial, 'cave-sleeper') == ['observe']
    expanded = [a for index in range(1, 15) for a in scene_knowledge.menu(original,index,original['playerKnowledge'])]
    assert len(expanded) == len(original['actions'])
    for action in original['actions']:
        assert set(choices(expanded,action['id'])) == {c['id'] for c in action['choices']}
    assert original == scene_knowledge.BASELINE
    checks.append('Scene definitions: initial menus omit hidden names/outcomes; explicit discoveries unlock every declared choice without mutating sources')
    legacy = {'actions':[scene_knowledge.plain_definition(a) for a in original['actions']]}
    assert scene_knowledge.menu(legacy,3,[]) == scene_knowledge.menu(original,3,[])
    legacy['actions'][4]['hint'] = 'CUSTOM_UNREVIEWED_MECHANISM'
    assert not choices(scene_knowledge.menu(legacy,3,[]),'courtyard-pool')
    poisoned=copy.deepcopy(original);poisoned['actions'][4]['choices'][0]['player']['requiresAny']='pool-treasure'
    assert not choices(scene_knowledge.menu(poisoned,3,[]),'courtyard-pool')
    outcome = {'outcome':'success'}
    assert scene_knowledge.outcome_clues(original,'cave-sleeper','observe',outcome,scene_knowledge.STOCK_SOURCE)
    assert not scene_knowledge.outcome_clues(original,'cave-sleeper','observe',outcome,'return customResult')
    assert not scene_knowledge.outcome_clues(original,'cave-sleeper','observe',{'outcome':'blocked'},scene_knowledge.STOCK_SOURCE)
    checks.append('stock v1 definitions use exact-match safe wording; changed legacy definitions and malformed declarations fail closed')


def main():
    output = PACK/'tests/output'/('menu-knowledge-'+secrets.token_hex(4));output.mkdir(parents=True)
    checks=[];pure(checks)
    with provider(output,answer) as (config,calls):
        with running('menu-knowledge',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
            kp,p1,p2=provision(runtime,password)
            kp.action('location.publish',{'index':3,'clues':[]})
            for player in (p1,p2):
                kp.command('entity.update',{'id':player.state()['character']['instanceId'],'numbers':{'location':3}})
            before=scene(p2,3)
            assert choices(before['data']['actions'],'courtyard-pool') == ['inspect']
            assert 'sceneDefinitions' not in p2.state() and 'sceneKnowledge' not in p2.state()
            kp_raw=next(a for a in kp.state()['sceneDefinitions'] if a['id']=='courtyard-pool')
            assert 'd4' in json.dumps(kp_raw,ensure_ascii=False)
            denied=p2.action('scene.action',{'action':'courtyard-pool','choice':'money'},allow_error=True)
            forged=p2.action('scene.action',{'action':'courtyard-pool','choice':'invented'},allow_error=True)
            assert denied['code']==forged['code'] and '本人已知' in denied['code']
            assert not kp.request('/package/scene-executor',{})['jobs']
            checks.append('KP receives full mechanism; PL raw DTO contains only known choices; hidden and forged submissions share a neutral rejection')
            act(kp,p1,'courtyard-pool','inspect')
            assert choices(scene(p1,3)['data']['actions'],'courtyard-pool')==['inspect','money','idol']
            assert p2.request('/api/v1/knowledge/read',{'refs':[before['ref']]})['items'][0]==before
            kp.action('location.reveal',{'index':3,'accounts':['player2']})
            assert choices(scene(p2,3)['data']['actions'],'courtyard-pool')==['inspect']
            checks.append('one player discovering treasure and changing global poolKnown does not unlock another player, even on a fresh basic disclosure')
            result(ai(kp,'ai.access.update',{'revision':1,'allowPlayerChat':True,'autoApproveBatches':False}))
            result(ai(kp,'ai.settings.update',{'enabled':True,'profileId':'offline','externalSources':{'public':True,'private':True,'kp':True},'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}))
            session,reply=ask(p2)
            for hidden in ('钱袋','鼠像','d4 伤害','moneyRemaining'):
                assert hidden not in json.dumps(calls,ensure_ascii=False),hidden
                assert hidden not in reply['response']
            assert '行动选项' in reply['response'] and '"choices"' not in reply['response']
            checks.append('actual AI search/read/evidence HTTP path sees only the player-safe observation and renders semantic lists')
            # An old queue entry from before the menu version must not execute.
            queued=p2.action('scene.action',{'action':'courtyard-pool','choice':'inspect'})
            runtime.package.state['autoSceneQueue'][queued['jobId']].pop('menuVersion');runtime.package.save()
            task=kp.request('/package/scene-executor',{})['jobs'][0]
            blocked=kp.action('scene.autorun',{'jobId':task['id']},task['commandId'])
            assert blocked['outcome']=='blocked' and '菜单已更新' in str(blocked)
            manual=p2.action('scene.action',{'action':'courtyard-pool','choice':'inspect','manual':True})
            runtime.package.state['requests'][manual['requestId']]['args'].pop('menuVersion');runtime.package.save()
            refused=kp.action('resolve',{'requestId':manual['requestId'],'approve':True},allow_error=True)
            assert '菜单已更新' in refused['code']
            assert runtime.package.state['requests'][manual['requestId']]['status']=='pending'
            kp.action('resolve',{'requestId':manual['requestId'],'approve':False,'reason':'旧菜单请求重新提交'})
            checks.append('uncommitted pre-upgrade automatic and manual requests cannot execute through the current KP executor')
            errors=[]
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True)
                try:
                    def login(account):
                        page=browser.new_page(viewport={'width':1440,'height':1000})
                        page.on('pageerror',lambda e:errors.append(str(e)))
                        page.goto(runtime.origin+'/sessions/'+account+'/')
                        page.locator('[name=loginName]').fill(account);page.locator('[name=password]').fill(password)
                        page.get_by_role('button',name='进入冒险',exact=True).click();page.locator('.identity').wait_for()
                        return page
                    player=login('player2');player.goto(runtime.origin+'/sessions/player2/#/play/scene')
                    player.get_by_role('button',name='调查池塘',exact=True).click()
                    expect(player.locator('dialog select[name=scene-choice] option')).to_have_count(1)
                    expect(player.locator('dialog')).not_to_contain_text('钱袋')
                    player.screenshot(path=str(output/'player-menu.png'))
                    player.locator('dialog').evaluate('el=>el.close()')
                    gm=login('kp');gm.goto(runtime.origin+'/sessions/kp/#/gm/locations/3')
                    gm.locator('.keeper-scene-menu summary').filter(has_text='调查池塘').click()
                    expect(gm.locator('.keeper-scene-menu')).to_contain_text('d4')
                    gm.locator('.keeper-scene-menu').screenshot(path=str(output/'keeper-menu.png'))
                    gm.get_by_role('button',name='向玩家揭示',exact=True).click()
                    expect(gm.locator('[name=knowledge]:checked')).to_have_count(0)
                    gm.locator('[name=account][value=player2]').check()
                    gm.locator('[name=knowledge][value=pool-treasure]').check()
                    gm.get_by_role('button',name='揭示地点',exact=True).click()
                    expect(gm.get_by_text('已向指定玩家揭示地点',exact=True).first).to_be_visible()
                    player.reload();player.get_by_role('button',name='调查池塘',exact=True).click()
                    expect(player.locator('dialog select[name=scene-choice] option')).to_have_count(3)
                    player.set_viewport_size({'width':390,'height':844})
                    assert player.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                    player.screenshot(path=str(output/'player-disclosed-mobile.png'))
                finally:browser.close()
            assert not errors,errors
            after=scene(p2,3)
            assert choices(after['data']['actions'],'courtyard-pool')==['inspect','money','idol']
            assert p2.request('/api/v1/knowledge/read',{'refs':[before['ref']]})['items'][0]==before
            checks.append('Edge: KP mechanism panel, unchecked explicit per-player disclosure, newly unlocked PL dialog and 390px layout; old snapshot unchanged')
            grants=kp.request('/api/v1/knowledge/grants/query',{'subjectMemberId':'member-player2','policyId':'stumpsville-personal-v1','status':'active','limit':50})['items']
            for grant in grants:
                if grant['resource']['id']==after['data']['entityId']:
                    kp.action('knowledge.revoke',{'grantId':grant['grantId'],'revision':grant['revision']})
            assert 'items' not in p2.request('/api/v1/knowledge/read',{'refs':[after['ref']]},allow_error=True)
            assert not p2.request('/api/v1/ai/sessions/'+session['sessionId'])['items'][-1].get('response')
            assert not p2.state()['sceneActions']
            assert '本人已知' in p2.action('scene.action',{'action':'courtyard-pool','choice':'inspect'},allow_error=True)['code']
            checks.append('revoking all scene grants clears menus, blocks submissions and removes prior AI history response')
    build(output/'export')
    html=(output/'export/index.html').read_text(encoding='utf-8')
    assert 'keeperSceneMenu' in html and '已知的做法' in html
    assert '失败受到 d4 伤害' not in html and not (output/'export/config').exists()
    checks.append('current static webpage build includes safe UI logic but no gameplay definitions or private mechanism data')
    report={'checkedAt':datetime.now().astimezone().isoformat(),'passed':len(checks),'checks':checks,
        'output':str(output),'realSaveChanged':False,'realProviderCalls':0,'browserErrors':errors}
    (PACK/'tests/menu-knowledge-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
