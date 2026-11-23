"""Static deterministic DTO presentation; not an engine execution success test."""
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright,expect
from test_debug_dialog_ui import static_ui


@pytest.mark.parametrize('width',[1100,390])
def test_numbered_preflight_rollback_and_business_result(static_ui,width):
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':width,'height':850});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(static_ui+'/')
            page.evaluate('''async()=>{
              const {mountRulings}=await import('./rulings.js');document.body.replaceChildren();
              window.item={rulingId:'batch:fixture',kind:'runtime',sessionId:'s1',requestId:'q1',summary:'补充口粮后进行休息',status:'rolled_back',digest:'d',createdAt:1,canDecide:false,risks:[],receipts:[],
                actions:[{target:'host',op:'action.invoke',args:{actionId:'sv.inventory',input:{actor:'actor-one',operation:'use',slot:5,value:1}}},{target:'host',op:'action.invoke',args:{actionId:'sv.rest',input:{actor:'actor-one',kind:'short',attribute:''}}}],
                preflight:{status:'runtime_required',items:[{index:0,status:'passed',result:{public:{outcome:'success'}}},{index:1,status:'runtime_required'}]},
                execution:{status:'rolled_back',committedCount:0,rolledBackCount:1,failedCount:1,notExecutedCount:0,items:[{index:0,status:'rolled_back'},{index:1,status:'failed',code:'RULE_FAILED',ruleCode:'SV_EMPTY_SLOT',reason:'规则前置条件不满足。',path:'/actions/1/args'}]}};
              window.client={connected:true,generation:1,view:{accountId:'kp',role:'kp',authorityEpoch:'e'},subscribe:()=>()=>{},aiRulings:async()=>({items:[structuredClone(item)]}),aiResolve:async()=>({items:[]})};
              window.panel=mountRulings(document.body,client,{compact:true});
            }''')
            page.get_by_role('button',name='查看详情').click()
            expect(page.locator('.batch-steps>li')).to_have_count(2)
            expect(page.locator('.batch-result-summary')).to_contain_text('提交 0 项 · 撤销 1 项')
            expect(page.locator('.batch-steps')).to_contain_text('SV_EMPTY_SLOT')
            expect(page.locator('.batch-steps')).to_contain_text('/actions/1/args')
            assert page.get_by_role('button',name='批准并执行').count()==0
            page.screenshot(path=str(Path(__file__).parents[2]/'acceptance/ai-command-reliability'/f'batch-details-{width}.png'),full_page=True)
            page.evaluate("item.status='completed';item.execution={status:'committed',committedCount:2,items:[{index:0,status:'committed',result:{passed:false,rolled:99}},{index:1,status:'committed',result:{public:{outcome:'blocked'}}}]};panel.refresh()")
            page.get_by_role('button',name='查看详情').click()
            expect(page.locator('.batch-steps')).to_contain_text('业务结果未达成；不会自动重试。')
            assert page.locator('.ruling-dialog').evaluate('e=>e.scrollWidth<=e.clientWidth+1')
            page.evaluate("item.status='partial';delete item.execution;delete item.preflight;item.receipts=[{receipt:{status:'rejected',code:'RULE_FAILED'}}];panel.refresh()")
            page.get_by_role('button',name='查看详情').click()
            expect(page.locator('.batch-result-summary')).to_contain_text('旧批次没有成功提交项')
            assert not errors,errors
        finally:browser.close()
