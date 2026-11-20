"""Unified KP queue over real host APIs and a loopback-only AI provider."""
import copy
from datetime import datetime
import json
import secrets
import time
from urllib.parse import urlsplit, parse_qs, urlencode
from harness import PACK, running, Account
from verify_integrations import provider, ai, result
from playwright.sync_api import sync_playwright, expect


def main():
    expect.set_options(timeout=20000)
    checks, errors = [], []
    output = PACK / 'tests/output' / ('keeper-queue-' + secrets.token_hex(4))
    output.mkdir(parents=True)
    def respond(request):
        return {'role': 'assistant', 'content': json.dumps({'kind': 'plan', 'text': '已为KP整理所引用的申请；尚未执行。'})}
    with provider(output, respond) as (config, calls), running('keeper-queue', data=output/'game', ai_config=config, no_browser=True) as (runtime, password):
        kp, p1, p2 = [Account(runtime.origin, name, password, name) for name in ('kp', 'player1', 'player2')]
        p1.action('draft', {'preset': 'mul', 'name': '木栗'})
        p2.action('draft', {'preset': 'dou', 'name': '待审核小鼠'})
        kp.action('approve', {'account': 'player1'})
        p1.action('ready', {'ready': True})
        kp.action('world', {'operation': 'start'})
        game_request = p1.action('request', {'kind': 'free', 'manual': True, 'text': '玩家行动申请：请求检查桥梁'})
        result(ai(kp, 'ai.access.update', {'revision': 1, 'allowPlayerChat': True, 'autoApproveBatches': False}))
        result(ai(kp, 'ai.settings.update', {'enabled': True, 'profileId': 'offline', 'externalSources': {'public': True, 'kp': True, 'private': True}, 'auto': {'enabled': False, 'channelIds': [], 'prefix': '!ai '}}))
        session = result(ai(p1, 'ai.session.create', {'title': '玩家辅助 AI 的说明请求'}))
        knowledge = result(ai(p1, 'ai.session.submit', {'sessionId': session['sessionId'], 'text': '请 KP 说明本次问题中允许我获知的信息。'}))
        assert knowledge['awaitingKnowledge'] and not calls
        keeper_request = result(ai(kp, 'ai.request.create', {'sourceKind': 'manual', 'text': '另一个等待转交的 AI 需求'}))
        assert 'items' not in p1.request('/api/v1/ai/rulings', allow_error=True)
        assert 'keeperWaits' not in p1.state() and 'keeperFlows' not in p1.state()
        denied = p1.action('host-flow', {'operation': 'flow.respond', 'input': {'waitId': 'fake', 'revision': 1, 'answer': True}}, allow_error=True)
        assert 'code' in denied
        assert 'code' in kp.action('host-flow', {'operation': 'entity.archive', 'input': {'id': 'fake'}}, allow_error=True)
        checks.append('KP queue data and flow operations remain host-authorized; player AI request retains player ownership')

        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width': 1660, 'height': 960})
            page.on('pageerror', lambda e: errors.append(str(e)))
            # Force genuine server pagination to prove an older received request
            # is found without depending on the first page or a Load More button.
            pages = []
            def small_pages(route):
                url = urlsplit(route.request.url)
                query = parse_qs(url.query); query['limit'] = ['1']
                response = route.fetch(url=url._replace(query=urlencode({k: v[0] for k, v in query.items()})).geturl())
                pages.append(query.get('before'))
                route.fulfill(response=response)
            page.route('**/api/v1/ai/tasks?*', small_pages)
            page.goto(runtime.origin + '/sessions/kp/')
            page.locator('[name=loginName]').fill('kp'); page.locator('[name=password]').fill(password)
            page.get_by_role('button', name='进入冒险', exact=True).click()
            page.locator('.identity').wait_for()
            page.goto(runtime.origin + '/sessions/kp/#/gm/rulings')
            queue = page.locator('.ruling-work')
            pl_row = queue.locator(f'[data-ai-request="{knowledge["requestId"]}"]')
            kp_row = queue.locator(f'[data-ai-request="{keeper_request["requestId"]}"]')
            expect(pl_row).to_contain_text('请 KP 说明')
            expect(pl_row).to_contain_text('player1')
            expect(kp_row).to_be_visible()
            expect(queue.locator('[data-draft=player2]')).to_be_visible()
            expect(queue).to_contain_text('玩家行动申请：请求检查桥梁')
            assert any(pages), pages
            checks.append('game request, character draft, player assistance and pending AI handoff appear in the ruling page, including older pages')
            page.screenshot(path=str(output/'unified-queue.png'), full_page=True)

            queue.locator('[data-settings]').click()
            expect(page.locator('#kp-ai-settings')).to_be_visible()
            expect(page.locator('.ai-dialog')).to_have_count(0)
            page.locator('.sidebar a[href="#/gm/rulings"]').click()
            page.goto(runtime.origin + '/sessions/kp/#/gm/console')
            expect(page.locator('[data-action=approve]')).to_have_count(0)
            page.get_by_role('button', name='打开裁决队列', exact=True).click()
            queue.locator('[data-draft=player2] [data-action=approve]').click()
            expect(queue.locator('[data-draft=player2]')).to_have_count(0)
            assert p2.state()['character']['name'] == '待审核小鼠'
            checks.append('character approval executes in ruling queue; console and AI settings point to the same queue')

            # A checked configuration is reviewed by the existing public engine
            # component, including its immutable digest and required risk inputs.
            template = copy.deepcopy(kp.request('/api/v1/admin')['configurations']['sv.npc'])
            template.update(configurationId='sv.ext.npc.queue', revision='1')
            template['defaults']['isNpc'] = 1
            delta = {'schemaVersion': 1, 'configurations': [{'kind': 'add', 'id': template['configurationId'], 'expectedRevision': None, 'value': template}], 'sources': {}, 'data': {}, 'suggestions': []}
            proposal = result(ai(kp, 'ai.draft.create', {'text': '队列内配置裁决', 'changeSet': delta}))
            validation = result(ai(kp, 'ai.proposal.validate', {'proposalId': proposal['proposalId'], 'revision': 1}))
            assert validation['proposal']['status'] == 'review_ready', [(r['level'],r['status'],r['findings']) for r in validation['reports']]
            card = queue.locator('dialog[aria-label="AI 修改裁决详情"]').filter(has_text='sv.ext.npc.queue').locator('..')
            expect(card).to_be_visible(timeout=15000)
            expect(card).to_contain_text('等待 KP 裁决')
            card.get_by_role('button',name='查看并裁决',exact=True).click()
            expect(card.locator('.ruling-dialog')).to_be_visible()
            expect(card.locator('textarea')).to_have_count(2)
            for textarea in card.locator('textarea').all():
                textarea.fill('隔离样例中确认此项风险')
            page.wait_for_timeout(4500)
            for textarea in card.locator('textarea').all():
                assert textarea.input_value() == '隔离样例中确认此项风险'
            card.get_by_role('button', name='拒绝', exact=True).click()
            expect(card).to_have_count(0)
            assert next(i for i in kp.request('/api/v1/ai/rulings')['items'] if i['rulingId']=='proposal:'+proposal['proposalId'])['status'] == 'rejected'
            checks.append('AI configuration ruling shares the queue; polling preserves risk input and rejection uses the authoritative digest')

            queue.locator('[data-request-id="'+game_request['requestId']+'"] [data-action=console-request]').last.click()
            page.locator('#ruling-form [data-ruling-reply] > summary').click()
            page.locator('#ruling-form [name=reason]').fill('同意检查，请保持安全距离。')
            page.wait_for_timeout(3000)
            expect(page.locator('#ruling-form [name=reason]')).to_have_value('同意检查，请保持安全距离。')
            page.locator('#ruling-form button[type=submit]').click()
            expect(page.locator('#ruling-form')).to_have_count(0)
            request = next(r for r in p1.state()['requests'] if r['id'] == game_request['requestId'])
            assert request['status']=='approved' and '安全距离' in request['reason']
            checks.append('ordinary ruling preserves text during refresh and delivers the persisted decision to the original player')

            expect(pl_row).to_be_visible()
            before_other = p2.state()['locations']
            pl_row.get_by_role('button', name='执行信息揭示', exact=True).click()
            expect(page.locator('#dialog')).to_contain_text('木栗')
            page.locator('#dialog button[type=submit]').click()
            expect(page.locator('#dialog')).not_to_be_visible()
            assert any(p['index']==1 for p in p1.state()['locations'])
            assert p2.state()['locations']==before_other
            checks.append('information request opens an executable disclosure form for its original player only')
            pl_row.get_by_role('button', name='查看对应会话', exact=True).click()
            expect(page.locator('#kp-ai-embedded #session-access')).to_contain_text('player1')
            pl_row.get_by_role('button', name='转 AI 处理', exact=True).click()
            deadline = time.monotonic()+70
            review_id=None; items=[]
            while time.monotonic()<deadline:
                review_id=page.locator('#kp-ai-embedded .session-select').input_value()
                if review_id and review_id!=session['sessionId']:
                    items=kp.request('/api/v1/ai/sessions/'+review_id)['items']
                    if items and items[-1]['status']=='review_ready':break
                page.wait_for_timeout(200)
            assert calls and review_id!=session['sessionId'] and items and items[-1]['status']=='review_ready', {'reviewId':review_id,'items':items,'status':queue.locator('.queue-status').inner_text()}
            assert items[-1]['initiator']=='kp' and items[-1]['reviewSource']['sessionId']==session['sessionId']
            assert items[-1]['text']!='请 KP 说明本次问题中允许我获知的信息。'
            assert p1.request('/api/v1/ai/sessions/'+review_id,allow_error=True).get('code')
            original=p1.request('/api/v1/ai/sessions/'+session['sessionId'])
            assert original['items'][0]['requestId']==knowledge['requestId'] and review_id not in json.dumps(original)
            checks.append('queue forwarding quotes the original player request in a separate KP review; private output does not return to the player')

            # Simulate a lost response after a real cancellation is committed.
            def lose_reply(route):
                body=route.request.post_data_json
                if body.get('op')=='ai.request.cancel' and body.get('args',{}).get('requestId')==keeper_request['requestId']:
                    route.fetch(); route.abort('failed')
                else:route.continue_()
            page.route('**/api/v1/ai/commands',lose_reply)
            kp_row.get_by_role('button',name='取消请求',exact=True).click()
            expect(queue.locator('[data-recovery]')).to_be_visible()
            page.unroute('**/api/v1/ai/commands',lose_reply)
            page.reload(); expect(page.locator('.ruling-work [data-recovery]')).to_be_visible()
            page.locator('.ruling-work [data-recovery] button').click()
            expect(page.locator('.ruling-work [data-recovery]')).to_be_hidden()
            assert next(i for i in kp.request('/api/v1/ai/tasks?limit=100')['items'] if i['requestId']==keeper_request['requestId'])['status']=='cancelled'
            page.locator('.ruling-work [data-history]').check()
            expect(queue.locator('dialog[aria-label="AI 修改裁决详情"]').filter(has_text='sv.ext.npc.queue').locator('..')).to_contain_text('已拒绝')
            checks.append('lost AI response persists its original receipt ID across reload; recovery does not repeat the command; finished rulings remain in history')
            bundle = kp.request('/package/bundle')
            bundle['sources']['queue-wait.lua'] = "return flow('sv.queue.wait', {}, {ask('decision',{role='kp',seconds=300,yes='end',no='end',timeout='end'})})"
            bundle['sources']['queue-failure.lua'] = "return flow('sv.queue.failure', {}, {step('failure',function(r) error('queue_fixture_failure') end)})"
            revision = result(kp.command('rule.stage', {'sources':bundle['sources'], 'data':bundle['data']}))
            result(kp.command('rule.activate', {'revision':revision}))
            flow = result(kp.command('action.invoke', {'actionId':'sv.queue.wait','input':{}}))
            waiting = next(w for w in kp.state()['keeperWaits'] if w['flowId']==flow['flowId'])
            wait_card = queue.locator('[data-wait="'+waiting['id']+'"]')
            expect(wait_card).to_be_visible()
            assert 'keeperWaits' not in p1.state()
            wait_card.locator('[data-action=host-flow]').first.click()
            expect(wait_card).to_have_count(0)
            assert kp.request('/api/v1/view')['flows'][flow['flowId']]['status']=='completed'
            failure = result(kp.command('action.invoke', {'actionId':'sv.queue.failure','input':{}}))
            failed_card = queue.locator('[data-flow="'+failure['flowId']+'"]')
            expect(failed_card).to_be_visible()
            failed_card.get_by_role('button',name='取消流程',exact=True).click()
            expect(failed_card).to_have_count(0)
            assert kp.request('/api/v1/view')['flows'][failure['flowId']]['status']=='cancelled'
            checks.append('real host KP waits and needs-attention flows appear in the same queue and resolve through revision-checked host commands')
            assert not errors, errors
            browser.close()
        checks.append('browser reported no uncaught JavaScript errors')
    report={'passed':True,'checkedAt':datetime.now().astimezone().isoformat(),'checks':checks,'models':'loopback fixture only; no real provider calls'}
    (PACK/'tests/keeper-queue-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
