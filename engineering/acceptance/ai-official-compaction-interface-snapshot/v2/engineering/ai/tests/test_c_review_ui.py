"""C review and editable evidence in actual Edge, using deterministic DTOs."""
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright, expect
from test_debug_dialog_ui import static_ui


@pytest.mark.parametrize('width', [1100,390])
def test_c_adoption_is_explicit_and_note_optional(static_ui, width):
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport={'width':width,'height':850});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(static_ui+'/')
            page.evaluate('''async()=>{
              document.body.replaceChildren();window.calls=[];
              const {mountRulings}=await import('./rulings.js');
              window.item={rulingId:'proposal:fixture',kind:'configuration',summary:'新增规则；实况覆盖不完整',status:'pending',digest:'candidate',revision:1,createdAt:1,canDecide:true,highRisk:true,risks:[{id:'gameplay-risk',question:'接受已报告的未覆盖范围'}],reports:[],receipts:[],
                cAssessment:{basisRevision:2,basisDigest:'basis',reportDigest:'reports',adoptable:true,requiresAcceptance:true,stale:false,findings:[{code:'LIVE_SCENARIO_COVERAGE_MISSING',message:'新规则未被声明场景覆盖',severity:'error',path:''}],limitations:['尚未验证全部现存角色']}};
              window.client={connected:true,generation:1,view:{accountId:'kp',role:'kp',authorityEpoch:'e'},subscribe:()=>()=>{},aiResolve:async()=>({items:[]}),aiRulings:async()=>({items:[structuredClone(item)]}),aiCommand:async(op,args)=>{calls.push({op,args});item.status='completed';item.canDecide=false;return{status:'committed',result:item};}};
              window.panel=mountRulings(document.body,client,{compact:true});
            }''')
            page.get_by_role('button',name='查看并裁决').click()
            expect(page.get_by_text('C 类游戏性评估 · 依据版本 2',exact=True)).to_be_visible()
            expect(page.get_by_text('尚未验证全部现存角色',exact=True)).to_be_visible()
            assert page.get_by_role('checkbox').count()==0
            assert page.get_by_role('textbox',name='裁决备注（可选）').count()==1
            assert page.evaluate('calls.length')==0
            page.get_by_role('button',name='采纳评估并发布',exact=True).click()
            expect(page.locator('.ruling-state')).to_have_text('已执行')
            call=page.evaluate('calls[0]')
            assert call['args']['cReview']=={'basisRevision':2,'basisDigest':'basis','reportDigest':'reports'}
            assert '未填写备注' in call['args']['riskDecisions']['gameplay-risk']
            assert page.evaluate('calls.length')==1
            page.get_by_role('button',name='查看详情').click()
            assert page.locator('.ruling-dialog').evaluate('e=>e.scrollWidth<=e.clientWidth+1')
            target=Path(__file__).parents[2]/'acceptance/ai-defaults-c-review';target.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(target/f'c-review-{width}.png'),full_page=True)
            assert not errors,errors
        finally:browser.close()


@pytest.mark.parametrize('width', [1100,390])
def test_edit_basis_version_conflict_feedback_and_clear(static_ui,width):
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport={'width':width,'height':850});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(static_ui+'/')
            page.evaluate('''async()=>{
              document.body.replaceChildren();window.calls=[];window.listeners=[];
              const {mountAISettings}=await import('./settings.js');
              window.data={settings:{enabled:true,profileId:'one',externalSources:{public:true,private:true,kp:true},auto:{enabled:false,channelIds:[],prefix:'!ai '}},access:{revision:1,allowPlayerChat:true,autoApproveBatches:false,autoApproveConfigurations:false},profiles:[{profileId:'one',model:'test',enabled:true}],
                cReviewBasis:{revision:2,basisDigest:'0123456789abcdef',metricOverrides:{},liveScenarios:[],notes:'原依据',authorLiveScenarios:[],metrics:[{metricId:'success',unit:'概率',threshold:{absoluteDelta:.1,risk:'high'}}]}};
              window.client={connected:true,generation:1,view:{accountId:'kp',role:'kp',authorityEpoch:'e'},subscribe:fn=>{listeners.push(fn);return()=>{};},aiSettings:async()=>structuredClone(data),aiCommand:async(op,args)=>{calls.push({op,args});return{status:'rejected',code:'C_BASIS_VERSION_CONFLICT',requestId:'test-conflict'};}};
              window.panel=mountAISettings(document.body,client);
            }''')
            expect(page.locator('#basis-version')).to_contain_text('当前版本 2')
            page.locator('#basis-metrics input[type=checkbox]').check()
            page.get_by_label('success 变化阈值',exact=True).fill('0.25')
            page.get_by_label('success 风险级别',exact=True).select_option('medium')
            page.locator('#basis-notes').fill('新判定说明')
            page.get_by_role('button',name='保存评估依据').click()
            expect(page.locator('#status')).to_contain_text('C_BASIS_VERSION_CONFLICT')
            args=page.evaluate('calls[0].args')
            assert args=={'revision':2,'metricOverrides':{'success':{'absoluteDelta':.25,'risk':'medium'}},'liveScenarios':[],'notes':'新判定说明'}
            assert page.locator('#c-basis').evaluate('e=>e.scrollWidth<=e.clientWidth+1')
            target=Path(__file__).parents[2]/'acceptance/ai-defaults-c-review';target.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(target/f'c-basis-{width}.png'),full_page=True)
            page.evaluate("client.view.role='player';client.generation++;listeners.forEach(f=>f())")
            expect(page.locator('#settings')).to_be_hidden()
            expect(page.locator('#basis-notes')).to_have_value('')
            assert not errors,errors
        finally:browser.close()
