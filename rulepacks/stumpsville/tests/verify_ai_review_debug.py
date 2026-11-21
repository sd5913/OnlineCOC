"""KP source reviews, debug exports and player boundaries in isolated fixtures."""
import argparse
import copy
from datetime import datetime
import json
from pathlib import Path
import secrets
import sys
from types import SimpleNamespace

PACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK/'tools'))
import ai_review


def pure(checks):
    state = {'drafts': {'p1': {'account': 'p1', 'name': '新角色', 'status': 'submitted'}},
             'requests': {'r1': {'id': 'r1', 'account': 'p1', 'text': '我想附魔', 'status': 'pending'}},
             'events': {'p1': [{'id': 'e1', 'account': 'p1', 'requestId': 'r1', 'status': 'approved'}]}}
    view = {'role': 'kp', 'accountId': 'kp', 'authorityEpoch': 'epoch', 'members': [{'accountId': 'p1'}, {'accountId': 'kp'}],
            'waits': {'w1': {'id': 'w1', 'role': 'kp', 'status': 'waiting', 'options': {'prompt': '是否继续'}}},
            'flows': {'f1': {'id': 'f1', 'status': 'needs_attention', 'error': '示例异常'}}}
    before = copy.deepcopy(state)
    for kind, key in [('draft', 'p1'), ('request', 'r1'), ('wait', 'w1'), ('flow', 'f1'), ('event', 'e1')]:
        args = {'kind': kind, 'id': key, **({'account': 'p1'} if kind == 'event' else {})}
        found = ai_review.source(state, view, args)
        assert found['kind'] == 'package' and found['category'] == kind
        assert found['context']['sourceLocator'] == args
        assert found.get('requestedBy') == ('p1' if kind in {'draft', 'request', 'event'} else None)
    assert state == before
    checks.append('五类来源按真实记录解析，原申请人与当前KP分离，原裁决不变')
    request_source = ai_review.source(state, view, {'kind': 'request', 'id': 'r1'})
    event_source = ai_review.source(state, view, {'kind': 'event', 'id': 'e1', 'account': 'p1'})
    assert request_source['correlationKey'] == event_source['correlationKey']
    assert 'correlationKey' not in ai_review.source(state, view, {'kind': 'draft', 'id': 'p1'})
    view['waits']['w1']['flowId'] = 'f1'
    assert ai_review.source(state, view, {'kind': 'wait', 'id': 'w1'})['correlationKey'] == ai_review.source(state, view, {'kind': 'flow', 'id': 'f1'})['correlationKey']
    state['requests']['r2'] = {**state['requests']['r1'], 'id': 'r2'}
    assert ai_review.source(state, view, {'kind': 'request', 'id': 'r2'})['correlationKey'] != request_source['correlationKey']
    state['events']['p1'].append({'id': 'orphan', 'requestId': 'missing', 'account': 'p1'})
    assert 'correlationKey' not in ai_review.source(state, view, {'kind': 'event', 'id': 'orphan', 'account': 'p1'})
    checks.append('仅真实request/event和flow/wait关联共用事件键；同文不同请求、重复建角及悬空事件不误合并')
    invalid = [{'kind': {}, 'id': 'x'}, {'kind': 'request', 'id': 'missing'},
               {'kind': 'request', 'id': 'r1', 'account': 'kp'}, {'kind': 'event', 'id': 'e1', 'account': 'unknown'}]
    for args in invalid:
        try: ai_review.source(state, view, args)
        except ValueError: pass
        else: raise AssertionError(args)
    try: ai_review.source(state, {**view, 'role': 'player'}, {'kind': 'request', 'id': 'r1'})
    except ValueError: pass
    else: raise AssertionError('PL obtained KP source')
    checks.append('PL、伪造账号、无效来源和已移除记录被拒绝')
    first = ai_review.source(state, view, {'kind': 'request', 'id': 'r1'})
    state['requests']['r1']['text'] = '改过的申请'
    second = ai_review.source(state, view, {'kind': 'request', 'id': 'r1'})
    assert first['revision'] != second['revision'] and first['summary'] == '我想附魔'
    state['requests']['r1']['large'] = '测试' * 20000
    bounded = ai_review.source(state, view, {'kind': 'request', 'id': 'r1'})
    assert bounded['context']['contentOmitted'] and len(json.dumps(bounded['context']).encode()) < 32768
    state['requests']['r1']['text'] = '长申请' * 3000
    bounded = ai_review.source(state, view, {'kind': 'request', 'id': 'r1'})
    assert len(json.dumps(bounded).encode()) < 32768 and bounded['context']['summaryTruncated']
    checks.append('来源修订随内容变化；超大快照显式省略，不伪装完整正文')
    calls = []; committed = {}
    def request(path, envelope=None):
        calls.append(path)
        if path.startswith('/ai/receipts/'):
            return committed.get(path.rsplit('/', 1)[-1], {'status': 'unknown'})
        assert path == '/ai/commands' and envelope['op'] == 'ai.review.create'
        receipt = {'status': 'committed', 'result': {'sessionId': 'review-session', 'requestId': 'review-request'}}
        committed[envelope['requestId']] = receipt
        raise ConnectionError('lost reply after committed')
    record = {'requestKey': 'kp:test-request', 'steps': {}}
    job = SimpleNamespace(record=record, client=SimpleNamespace(request=request), store=SimpleNamespace(save=lambda: None))
    try: ai_review.submit(job, view, first)
    except ConnectionError: pass
    else: raise AssertionError('fault did not fire')
    result = ai_review.submit(job, view, second)
    assert result['sessionId'] == 'review-session' and calls.count('/ai/commands') == 1
    assert job.record['aiReview']['envelope']['args']['source'] == first and not record['steps']
    assert ai_review.submit(job, view, first) == result
    checks.append('AI响应丢失后先查原回执，不重复创建、不重新解释来源或写游戏指令')
    from ai_bridge import consultation
    from client import HostError
    proxy = SimpleNamespace(request=lambda path: {'path': path})
    good = 'ai/debug?sessionId=mine&includeContent=false'
    assert consultation(proxy, {'method': 'GET', 'path': good}) == {'path': '/'+good}
    for path in ['ai/debug', 'ai/debug?sessionId=', 'ai/debug?sessionId=a&account=kp',
                 'ai/debug?sessionId=a&sessionId=b', 'ai/debug?sessionId=a&includeContent=1',
                 'https://example.com/ai/debug?sessionId=a', 'ai/debug?sessionId=a#private']:
        try: consultation(proxy, {'method': 'GET', 'path': path})
        except HostError as error: assert error.response['code'] == 'AI_ROUTE_NOT_EXPOSED'
        else: raise AssertionError(path)
    checks.append('调试桥只允许明确定位与内容开关，拒绝账号注入、重复参数及任意URL')


def integration(output, checks):
    import time
    import uuid
    from harness import Account, running
    from verify_integrations import ai, provider, result
    from playwright.sync_api import sync_playwright, expect
    errors = []
    def respond(request):
        tools = [message for message in request['messages'] if message.get('role') == 'tool']
        if not tools:
            return {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'catalog', 'type': 'function',
                'function': {'name': 'room_manage_catalog', 'arguments': json.dumps({'operations': ['entity.update']})}}]}
        return {'role': 'assistant', 'content': json.dumps({'kind': 'plan', 'text': '已为 KP 整理来源申请；方案待人工审核，尚未修改游戏。'})}
    with provider(output, respond) as (config, calls), running('ai-review-debug', data=output/'game', ai_config=config, no_browser=True) as (runtime, password):
        kp, p1, p2 = [Account(runtime.origin, name, password, name) for name in ('kp', 'player1', 'player2')]
        p1.action('draft', {'preset': 'mul', 'name': '木栗'})
        p2.action('draft', {'preset': 'dou', 'name': '待审核小鼠'})
        kp.action('approve', {'account': 'player1'}); p1.action('ready', {'ready': True}); kp.action('world', {'operation': 'start'})
        text = 'SOURCE_FIRE_NEEDLE：我想用火把给针剑附魔'
        request = p1.action('request', {'kind': 'free', 'manual': True, 'text': text})
        rid = request['requestId']
        result(ai(kp, 'ai.settings.update', {'enabled': True, 'profileId': 'offline', 'externalSources': {'public': True, 'kp': True, 'private': True}, 'auto': {'enabled': False, 'channelIds': [], 'prefix': '!ai '}}))
        access = kp.request('/api/v1/ai/access')
        result(ai(kp, 'ai.access.update', {'revision': access['revision'], 'allowPlayerChat': True, 'autoApproveBatches': True, 'autoApproveConfigurations': True}))
        bundle = kp.request('/package/bundle')
        bundle['sources']['review-wait.lua'] = "return flow('sv.review.wait', {}, {ask('decision',{role='kp',seconds=900,yes='end',no='end',timeout='end'})})"
        bundle['sources']['review-error.lua'] = "return flow('sv.review.error', {}, {step('failure',function(r) error('review_fixture_failure') end)})"
        revision = result(kp.command('rule.stage', {'sources': bundle['sources'], 'data': bundle['data']}))
        result(kp.command('rule.activate', {'revision': revision}))
        waiting_flow = result(kp.command('action.invoke', {'actionId': 'sv.review.wait', 'input': {}}))
        wait = next(w for w in kp.state()['keeperWaits'] if w['flowId'] == waiting_flow['flowId'])
        failure = result(kp.command('action.invoke', {'actionId': 'sv.review.error', 'input': {}}))
        event = next(e for e in kp.state()['events'] if e.get('requestId') == rid and e['account'] == 'player1')
        baseline = p1.state()['character']['numbers']
        def wait_review(sid):
            deadline = time.monotonic()+70
            while time.monotonic() < deadline:
                data = kp.request('/api/v1/ai/sessions/'+sid)
                if data['items'] and data['items'][-1]['status'] not in {'received', 'queued', 'generating', 'validating'}:
                    assert data['items'][-1]['status'] == 'review_ready', data
                    return data
                time.sleep(.2)
            raise AssertionError({'sessionId': sid, 'lastState': data})
        sources = [{'kind': 'draft', 'id': 'player2'}, {'kind': 'request', 'id': rid},
                   {'kind': 'wait', 'id': wait['id']}, {'kind': 'flow', 'id': failure['flowId']},
                   {'kind': 'event', 'id': event['id'], 'account': 'player1'}]
        reviews = {}
        for source in sources:
            located = kp.request('/package/ai-source', source)
            assert located['category'] == source['kind']
            if source['kind'] in {'request', 'event'}: assert located['requestedBy'] == 'player1'
            if source['kind'] == 'draft': assert located['requestedBy'] == 'player2'
            action_id = str(uuid.uuid4())
            submitted = kp.action('ai.review', source, action_id=action_id)
            assert kp.action('ai.review', source, action_id=action_id) == submitted
            assert kp.action('ai.review', source)['sessionId'] == submitted['sessionId']
            reviews[source['kind']] = submitted
            data = wait_review(submitted['sessionId'])
            print(json.dumps({'source': source['kind'], 'status': 'review_ready'}, ensure_ascii=False), flush=True)
            item = data['items'][-1]
            assert item['text'] != text and item.get('reviewSource'), item
            assert item['reviewSource']['category'] == ('request' if source['kind'] == 'event' else source['kind'])
            assert p1.request('/api/v1/ai/sessions/'+submitted['sessionId'], allow_error=True).get('code')
        assert reviews['event']['sessionId'] == reviews['request']['sessionId']
        checks.append('五类真实裁决进入KP私有审核；同request事件及连续转交复用会话，不重复提交')
        view = kp.request('/api/v1/view'); state = kp.state()
        assert p1.state()['character']['numbers'] == baseline
        assert next(r for r in state['requests'] if r['id'] == rid)['status'] == 'pending'
        assert state['drafts']['player2']['status'] == 'submitted'
        assert view['waits'][wait['id']]['status'] == 'waiting'
        assert view['flows'][failure['flowId']]['status'] == 'needs_attention'
        checks.append('转AI未批准角色、执行申请或响应宿主等待；原裁决及角色数值保持不变')
        assert p1.request('/package/ai-source', sources[1], allow_error=True).get('code')
        assert p1.action('ai.review', sources[1], allow_error=True).get('code')
        private_sid = reviews['request']['sessionId']
        assert p1.request('/package/ai', {'method': 'GET', 'path': 'ai/debug?sessionId='+private_sid}, allow_error=True).get('code')
        personal = result(ai(p1, 'ai.session.create', {'title': '个人调试'}))['sessionId']
        marker = 'PERSONAL_DEBUG_CONTENT'
        personal_request = result(ai(p1, 'ai.player.request', {'sessionId': personal, 'text': marker}))
        clean = p1.request('/package/ai', {'method': 'GET', 'path': 'ai/debug?sessionId='+personal})
        content = p1.request('/package/ai', {'method': 'GET', 'path': 'ai/debug?sessionId='+personal+'&includeContent=true'})
        assert marker not in json.dumps(clean, ensure_ascii=False) and marker in json.dumps(content, ensure_ascii=False)
        assert p2.request('/package/ai', {'method': 'GET', 'path': 'ai/debug?sessionId='+personal+'&includeContent=true'}, allow_error=True).get('code')
        checks.append('PL调试桥只导出本人记录，默认不含正文，不能导出他人或KP私有审核')
        native_reviews = {}
        for kind, source in [('ruling', {'kind': 'ruling', 'rulingId': personal_request['rulingId']}),
                             ('request', {'kind': 'request', 'requestId': personal_request['requestId']})]:
            reviewed = result(ai(kp, 'ai.review.create', {'source': source}))
            wait_review(reviewed['sessionId']); native_reviews[kind] = reviewed['sessionId']
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
            page.on('pageerror', lambda error: errors.append(str(error)))
            expect.set_options(timeout=25000)
            try:
                page.goto(runtime.origin+'/sessions/debug-browser/')
                page.locator('[name=loginName]').fill('kp'); page.locator('[name=password]').fill(password)
                page.get_by_role('button', name='进入冒险', exact=True).click(); page.locator('.identity').wait_for()
                page.goto(runtime.origin+'/sessions/debug-browser/#/gm/rulings')
                for selector in ['[data-draft="player2"]', '[data-request-id="'+rid+'"]', '[data-wait="'+wait['id']+'"]', '[data-flow="'+failure['flowId']+'"]']:
                    expect(page.locator(selector+' [data-action=ruling-ai]')).to_be_visible()
                page.locator('[data-request-id="'+rid+'"] [data-action=ruling-ai]').click()
                expect(page.locator('#kp-ai-embedded')).to_contain_text('玩家行动申请')
                expect(page.locator('#kp-ai-embedded .session-select')).to_have_value(private_sid)
                source_card = page.locator('#kp-ai-embedded .ai-review-source').first
                source_card.locator(':scope > summary').click()
                source_card.get_by_role('button', name='查看原裁决', exact=True).click()
                expect(page.locator('#dialog [name=requestId]')).to_have_value(rid)
                page.locator('#dialog .ruling-debug summary').click()
                with page.expect_download() as downloaded:
                    page.locator('#dialog [data-action=ruling-export]').click()
                exported = json.loads(Path(downloaded.value.path()).read_text(encoding='utf-8'))
                assert not exported['contentIncluded'] and text not in json.dumps(exported, ensure_ascii=False)
                page.locator('#dialog [data-review-content]').check()
                with page.expect_download() as downloaded:
                    page.locator('#dialog [data-action=ruling-export]').click()
                exported = json.loads(Path(downloaded.value.path()).read_text(encoding='utf-8'))
                assert exported['contentIncluded'] and text in json.dumps(exported, ensure_ascii=False)
                page.evaluate("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw Error('blocked')}}});document.execCommand=()=>false")
                page.locator('#dialog [data-action=ruling-reference]').click()
                expect(page.get_by_role('textbox', name='可复制的裁决引用')).to_have_value(__import__('re').compile(rid))
                page.screenshot(path=str(output/'ruling-debug.png'), full_page=True)
                page.locator('#dialog [data-action=close]').first.click()
                checks.append('网页全部待办有转AI入口，跳转引用会话；裁决调试导出按显式勾选包含正文')
                page.set_viewport_size({'width': 390, 'height': 844})
                page.locator('[data-action=ruling-pane][data-args*=queue]').click()
                expect(page.locator('[data-request-id="'+rid+'"] [data-action=ruling-ai]')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
                page.screenshot(path=str(output/'review-mobile.png'), full_page=True)
                checks.append('390px裁决转AI入口可达，页面无横向溢出')
                kp.action('resolve', {'requestId': rid, 'approve': False, 'reason': '仅隔离验收：保留已处理来源'})
                page.set_viewport_size({'width': 1440, 'height': 900})
                page.reload()
                expect(page.locator('[data-request-id="'+rid+'"]')).to_have_count(0)
                page.locator('#kp-ai-embedded .session-select').select_option(private_sid)
                expect(page.locator('#kp-ai-embedded .session-debug')).to_have_attribute('data-session', private_sid)
                source_card = page.locator('#kp-ai-embedded .ai-review-source').first
                source_card.locator(':scope > summary').click()
                source_card.get_by_role('button', name='查看原裁决', exact=True).click()
                expect(page.locator('#dialog')).to_contain_text(text)
                expect(page.locator('#dialog')).to_contain_text('rejected')
                expect(page.locator('#dialog [data-ruling-submit]')).to_have_count(0)
                checks.append('已处理申请仍可从来源卡回看，只读详情不重新执行旧裁决')
                page.locator('#dialog [data-action=close]').first.click()
                for kind, sid in native_reviews.items():
                    page.locator('#kp-ai-embedded .session-select').select_option(sid)
                    expect(page.locator('#kp-ai-embedded .session-debug')).to_have_attribute('data-session', sid)
                    source_card = page.locator('#kp-ai-embedded .ai-review-source').first
                    source_card.locator(':scope > summary').click()
                    source_card.get_by_role('button', name='查看原裁决', exact=True).click()
                    expect(page.locator('.ai-request-detail')).to_contain_text(marker)
                    if kind == 'ruling': expect(page.locator('.ai-request-detail > header h2')).to_have_text('原 AI 裁决')
                    page.locator('.ai-request-detail > header [data-close]').click()
                checks.append('AI原裁决与原请求引用均能定位当前授权记录，不混用包来源')
                assert not errors, errors
            except Exception:
                page.screenshot(path=str(output/'browser-failure.png'), full_page=True)
                raise
            finally:
                browser.close()
        result(ai(kp, 'ai.settings.update', {'enabled': True, 'profileId': 'offline', 'externalSources': {'public': True, 'kp': False, 'private': True}, 'auto': {'enabled': False, 'channelIds': [], 'prefix': '!ai '}}))
        catalog_sid = result(ai(kp, 'ai.session.create', {'title': '公共指令目录'}))['sessionId']
        submitted = result(ai(kp, 'ai.session.submit', {'sessionId': catalog_sid, 'text': '查询公开操作Schema，不读取KP私密资料'}))
        if not submitted.get('taskId'):
            result(ai(kp, 'ai.request.dispatch', {'requestId': submitted['requestId']}))
        data = wait_review(catalog_sid)
        assert data['items'][-1].get('error') is None
        checks.append('KP资料外发关闭时仍可查询公共操作Schema，私密资料设置保持关闭')



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pure', action='store_true')
    args = parser.parse_args()
    output = PACK/'tests/output'/('ai-review-debug-'+secrets.token_hex(4))
    output.mkdir(parents=True)
    checks = []; report = {'checkedAt': datetime.now().astimezone().isoformat(), 'realSaveChanged': False, 'evidenceDirectory': output.relative_to(PACK).as_posix()}
    try:
        pure(checks)
        if not args.pure:
            integration(output, checks)
        report['passed'] = True
    except Exception as error:
        report.update(passed=False, error=repr(error))
        raise
    finally:
        report.update(passedCount=len(checks), checks=checks, phase='pure' if args.pure else 'integration')
        (output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        if not args.pure:
            (PACK/'tests/ai-review-debug-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
