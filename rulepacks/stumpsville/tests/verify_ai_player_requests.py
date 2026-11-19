"""Personal evidence and explicit player creation requests; isolated fixtures only."""
import argparse
import copy
import json
from pathlib import Path
import secrets
import sys

PACK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PACK/'tools'))
from knowledge_provider import Provider,descriptor


def pure(checks):
    game=json.loads((PACK/'config/game.json').read_text(encoding='utf-8'))
    game=copy.deepcopy(game)
    needle=next(i for i,v in enumerate(game['items'],1) if v['id']=='needle')
    torch=next(i for i,v in enumerate(game['items'],1) if v['id']=='torch')
    game['items'][needle-1]['secret']='ITEM_SECRET_NOT_DISCLOSED'
    game['items'].append({'id':'hidden','name':'UNKNOWN_GM_ITEM','uses':1,'description':'PRIVATE_CATALOG_ENTRY'})
    actor={'instanceId':'p1-role','configurationId':'sv.character','owner':'player1','lifecycle':'active','name':'木栗',
        'numbers':{'item1':needle,'uses1':2,'ticks1':1,'item2':torch,'uses2':1},
        'metadata':{'secret':'ENTITY_SECRET_NOT_DISCLOSED'},'tags':['PRIVATE_TAG'],'components':{},'rules':{}}
    room={'entities':{'p1-role':actor},'activeRuleset':'r','artifacts':{'r':{'data':{'game.json':game}}}}
    context={'accountId':'player1','state':room}
    provider=Provider(None);resource={'namespace':'stumpsville','kind':'entity','id':'p1-role'}
    first=provider.read_live(resource,['sheet'],context)
    value=first['facets']['sheet'];items=value['metadata']['inventory']
    assert [i['name'] for i in items]==['针剑','火把']
    assert items[0]['uses']==2 and items[0]['maxUses']==3 and items[0]['damage']=='d6'
    assert items[1]['uses']==1 and items[1]['light'] is True
    checks.append('本人角色包含实际持有物品的名称、说明和当前用量')
    text=json.dumps(value,ensure_ascii=False)
    assert not any(x in text for x in ('ITEM_SECRET','ENTITY_SECRET','PRIVATE_TAG','UNKNOWN_GM_ITEM','PRIVATE_CATALOG_ENTRY'))
    assert actor['metadata']=={'secret':'ENTITY_SECRET_NOT_DISCLOSED'} and game['items'][needle-1]['secret']=='ITEM_SECRET_NOT_DISCLOSED'
    checks.append('语义投影不泄漏原metadata、隐藏定义或完整物品库，也不改源数据')
    try:provider.read_live(resource,['sheet'],{'accountId':'player2','state':room})
    except ValueError as e:assert str(e)=='FACET_UNAVAILABLE'
    else:raise AssertionError('other player obtained own sheet')
    checks.append('其他玩家不能借用角色引用读取本人装备')
    game['items'][needle-1]['description']='更新后的本人可读说明'
    second=provider.read_live(resource,['sheet'],context)
    assert second['sourceRevision']!=first['sourceRevision']
    assert provider.check_guard(first['sourceGuard'],context)
    assert descriptor()['facetSchemas']['sheet']['entityProjection'] is True
    checks.append('物品说明变化更新引用版本，既有个人授权和观察守卫保持兼容')


def accept_in_browser(runtime,password,kp,sid,ruling_id,checks,output):
    import time
    from playwright.sync_api import sync_playwright,expect
    errors=[];expect.set_options(timeout=25000)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        try:
            def login(account,route):
                page=browser.new_page(viewport={'width':1440,'height':900});page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(runtime.origin+'/sessions/request-ui-'+account+'/')
                page.locator('[name=loginName]').fill(account);page.locator('[name=password]').fill(password)
                page.get_by_role('button',name='进入冒险',exact=True).click();page.locator('.identity').wait_for()
                page.goto(runtime.origin+'/sessions/request-ui-'+account+'/#/'+route)
                return page
            player=login('player1','play/scene');player.locator('#comm-tab-ai').click()
            player.locator('.session-select').select_option(sid)
            expect(player.locator('.player-request-status')).to_contain_text('等待 KP 接收')
            page=login('kp','gm/rulings')
            row=page.locator('.ruling-row').filter(has_text='创作申请')
            expect(row).to_have_count(1)
            assert page.locator('.ai-assistance[data-ai-request]').count()==0
            row.get_by_role('button',name='查看并裁决',exact=True).click()
            page.screenshot(path=str(output/'creative-request.png'),full_page=True)
            row.get_by_role('button',name='接收并生成方案',exact=True).click()
            deadline=time.monotonic()+25;accepted=None
            while time.monotonic()<deadline:
                accepted=next(i for i in kp.request('/api/v1/ai/rulings')['items'] if i['rulingId']==ruling_id)
                if accepted['status']=='accepted':break
                time.sleep(.2)
            assert accepted and accepted['status']=='accepted'
            expect(page.locator('.session-select')).to_have_value(accepted['reviewSessionId'])
            expect(player.locator('.player-request-status')).to_contain_text('KP 已接收')
            expect(page.locator('.ruling-row').filter(has_text='创作申请')).to_have_count(0)
            checks.append('包内KP点击接收后自动打开私有审核会话，原申请不重复列为待办，PL仅见接收状态')
            player.locator('#text').fill('另一份创作需求：讨论把空水袋改成工具')
            player.get_by_role('button',name='提交创作申请',exact=True).click()
            expect(player.locator('.player-request-status').last).to_contain_text('等待 KP 接收')
            assert any(i['kind']=='player_request' and i['summary']=='另一份创作需求：讨论把空水袋改成工具' for i in kp.request('/api/v1/ai/rulings')['items'])
            player.set_viewport_size({'width':390,'height':844})
            player.locator('[data-action=workspace-column][data-args*=communication]').click()
            player.locator('#player-request').scroll_into_view_if_needed()
            expect(player.locator('#player-request')).to_be_visible()
            assert player.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            player.screenshot(path=str(output/'creative-request-mobile.png'),full_page=True)
            assert not errors,errors
            checks.append('包内PL可直接点击提交创作申请，390px按钮可达且无横向溢出')
            return accepted
        except Exception:
            if 'player' in locals():player.screenshot(path=str(output/'browser-failure.png'),full_page=True)
            raise
        finally:browser.close()


def integration(output,checks):
    import time
    import uuid
    from harness import running,provision
    from verify_integrations import provider,ai,result
    from verify_strict_known import known
    candidate=[None]
    def respond(request):
        assert candidate[0] is not None
        return {'role':'assistant','content':json.dumps({'kind':'draft','text':'将玩家的火焰针剑创意转为待审物品定义；不改变原装备。',
            'changeSet':{'schemaVersion':1,'configurations':[],'sources':{},'data':{'game.json':candidate[0]},'suggestions':[]}})}
    with provider(output,respond) as (config,calls),running('ai-player-requests',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
        kp,p1,p2=provision(runtime,password)
        result(ai(kp,'ai.settings.update',{'enabled':True,'profileId':'offline','externalSources':{'public':True,'kp':True,'private':True},'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}))
        access=kp.request('/api/v1/ai/access')
        result(ai(kp,'ai.access.update',{'revision':access['revision'],'allowPlayerChat':True,'allowPlayerRequests':True,'autoApproveBatches':True,'autoApproveConfigurations':True}))
        actor=p1.state()['character'];actor_id=actor['instanceId']
        mine=next(x for x in known(p1) if x['facetId']=='sheet' and x['data']['instanceId']==actor_id)
        assert {'needle','torch'}<={x['id'] for x in mine['data']['metadata']['inventory']}
        assert 'items' not in p2.request('/api/v1/knowledge/read',{'refs':[mine['ref']]},allow_error=True)
        checks.append('真实PL知识接口读取本人现有道具，复制引用不能越过玩家边界')
        kp.action('location.publish',{'index':3,'clues':[]})
        kp.action('location.reveal',{'index':3,'accounts':['player1'],'knowledge':['pool-treasure']})
        assert any(x['facetId']=='scene' and any(c['id']=='pool-treasure' for c in x['data']['clues']) for x in known(p1))
        assert not any('pool-treasure' in json.dumps(x,ensure_ascii=False) for x in known(p2))
        checks.append('已有个人线索可读，未获披露的另一玩家仍不可读')
        original=kp.request('/package/bundle')['data']['game.json'];candidate[0]=copy.deepcopy(original)
        candidate[0]['items'].append({'id':'fire-needle','name':'火焰针剑','kind':'weapon','slots':1,'uses':3,'damage':'d6','useDie':True,'description':'玩家创意的隔离测试候选，须KP批准定义。'})
        session=result(ai(p1,'ai.session.create',{'title':'组合道具创作申请'}))
        sid=session['sessionId'];view=p1.request('/api/v1/view')
        body={'requestId':str(uuid.uuid4()),'authorityEpoch':view['authorityEpoch'],'op':'ai.player.request',
            'args':{'sessionId':sid,'text':'我想用火把给针剑附魔，变成火焰针剑'}}
        envelope={'path':'ai/commands','method':'POST','body':body}
        submitted=result(p1.request('/package/ai',envelope))
        assert result(p1.request('/package/ai',envelope))==submitted
        queue=kp.request('/api/v1/ai/rulings')['items'];row=next(x for x in queue if x['rulingId']==submitted['rulingId'])
        assert row['kind']=='player_request' and row['status']=='pending'
        assert not calls and kp.request('/package/bundle')['data']['game.json']==original
        denied=ai(p2,'ai.player.request',body['args'],allow_error=True)
        assert denied.get('status')!='committed'
        denied=p1.request('/package/ai',{'path':'ai/commands','method':'POST','body':{**body,'requestId':str(uuid.uuid4()),'op':'ai.draft.create','args':{}}},allow_error=True)
        assert denied.get('code')=='AI_ROUTE_NOT_EXPOSED'
        checks.append('玩家无需先得到模型回答即可主动创作申请；桥接重复提交幂等、他人会话与直接配置写入被拒')
        before={x['sessionId'] for x in kp.request('/api/v1/ai/sessions?archived=false')['items']}
        decision={'rulingId':row['rulingId'],'digest':row['digest'],'decision':'approve'}
        accepted=accept_in_browser(runtime,password,kp,sid,row['rulingId'],checks,output)
        repeat=result(ai(kp,'ai.ruling.decide',decision))
        new=[x for x in kp.request('/api/v1/ai/sessions?archived=false')['items'] if x['sessionId'] not in before]
        assert len(new)==1 and new[0]['accessLevel']=='administrator'
        review=new[0]['sessionId']
        assert p1.request('/api/v1/ai/sessions/'+review,allow_error=True).get('code')
        deadline=time.monotonic()+90;proposal=None
        while time.monotonic()<deadline:
            proposal=next((x for x in kp.request('/api/v1/ai/rulings')['items'] if x.get('sessionId')==review and x['kind']=='configuration'),None)
            if proposal and proposal['status'] not in ('draft','validating'):break
            time.sleep(.25)
        assert proposal is not None, kp.request('/api/v1/ai/sessions/'+review)
        assert proposal['status']=='pending' and proposal['highRisk'] is True, proposal
        assert kp.request('/package/bundle')['data']['game.json']==original
        assert p1.state()['character']['numbers']==actor['numbers']
        personal=p1.request('/api/v1/ai/sessions/'+sid)
        assert review not in json.dumps(personal,ensure_ascii=False)
        checks.append('KP接收后仅新建一个私有审阅会话；自动审批已开也不发布高危物品，玩家看不到KP审阅内容')
        explicit={'rulingId':proposal['rulingId'],'digest':proposal['digest'],'explicitHighRiskDigest':proposal['digest'],'decision':'approve',
            'riskDecisions':{r['id']:'隔离验收已核对物品定义和存量兼容' for r in proposal.get('risks',[])}}
        receipt=result(ai(kp,'ai.ruling.decide',explicit));assert receipt['status']=='completed'
        kp.state();assert kp.request('/package/bundle')['data']['game.json']['items'][-1]['id']=='fire-needle'
        assert p1.state()['character']['numbers']==actor['numbers']
        checks.append('第二次明确批准高危提案后才发布新物品定义；既有背包和财富不被顺带改动')
        access=kp.request('/api/v1/ai/access');result(ai(kp,'ai.access.update',{'revision':access['revision'],'allowPlayerChat':access['allowPlayerChat'],'autoApproveBatches':access['autoApproveBatches'],'autoApproveConfigurations':access['autoApproveConfigurations'],'allowPlayerRequests':False}))
        blocked=ai(p1,'ai.player.request',{'sessionId':sid,'text':'另一份新的创作申请'},allow_error=True)
        assert blocked.get('status')!='committed'
        checks.append('独立玩家创作申请开关由服务端实际拦截')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--pure',action='store_true');args=parser.parse_args()
    output=PACK/'tests/output'/('ai-player-requests-'+secrets.token_hex(4));output.mkdir(parents=True)
    checks=[];report={'realSaveChanged':False,'evidenceDirectory':str(output.relative_to(PACK)).replace('\\','/')}
    try:
        pure(checks)
        if not args.pure:integration(output,checks)
        report['passed']=True
    except Exception as error:
        report.update(passed=False,error=repr(error));raise
    finally:
        report.update(passedCount=len(checks),checks=checks,phase='pure' if args.pure else 'integration')
        (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if not args.pure:(PACK/'tests/ai-player-requests-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
