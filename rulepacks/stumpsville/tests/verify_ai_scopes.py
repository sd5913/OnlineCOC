"""Exercise model tool queries through the real host, with a loopback provider only."""
import json
import secrets
import time
from datetime import datetime
from harness import PACK, running, provision
from verify_integrations import provider, ai, result


def verify_runtime(output, checks):
    """Check the current engine wire behavior through the package's public CLI."""
    observed = {}
    failures = []

    def call(identifier, name, args):
        return {'id': identifier, 'type': 'function', 'function': {
            'name': name, 'arguments': json.dumps(args, ensure_ascii=False)}}

    def respond(request):
        try:
            received = {m['tool_call_id']: json.loads(m['content'])
                        for m in request['messages'] if m['role'] == 'tool'}
            observed.update(received)
            if not received:
                payload = json.loads(request['messages'][1]['content'])
                guide = payload['sources']['stumpsville-guide']
                for text in ('pageSummary.returnedItems', 'data.channelId', 'kind="plan"',
                             '未读详情', '不能按编号顺序推断', 'cheese1不能仅凭名称', '个人知识未接入'):
                    assert text in guide, text
                calls = [call('entities1', 'room_search_data', {'types': ['entity'], 'query': '', 'limit': 25}),
                         call('configs', 'room_search_data', {'types': ['config'], 'query': '', 'limit': 50}),
                         call('channels', 'room_search_data', {'types': ['channel'], 'query': '', 'limit': 50})]
            elif 'entities2' not in received:
                assert received['entities1']['page']['nextCursor']
                calls = [call('entities2', 'room_search_data', {'types': ['entity'], 'query': '', 'limit': 25,
                             'cursor': received['entities1']['page']['nextCursor']}),
                         call('channel-detail', 'room_read_data', {'refs': [received['channels']['items'][0]['ref']]})]
            elif 'chat' not in received:
                channel = received['channel-detail']['items'][0]
                assert channel['data']['channelId'] != channel['ref']['id']
                npc = next(v['ref'] for page in ('entities1', 'entities2')
                           for v in received[page]['items'] if v['label'] == '蜘蛛一')
                calls = [call('chat', 'room_read_chat', {'channelId': channel['data']['channelId'], 'limit': 50}),
                         call('npc', 'room_read_data', {'refs': [npc], 'fields': ['name', 'configurationId', 'numbers']})]
            else:
                assert not request.get('tools'), 'final response turn must not expose tools'
                assert 'final response-only turn' in request['messages'][-1]['content']
                assert received['npc']['items'][0]['data']['configurationId'] == 'sv.npc'
                assert any(v['data']['text'] == 'OFFLINE_CHANNEL_EVIDENCE' for v in received['chat']['items'])
                return {'role': 'assistant', 'content': json.dumps({'kind': 'plan', 'text':
                    'OFFLINE_RUNTIME_CHECK: 已读取蜘蛛一与全局聊天；其余实体详情、规则和个人线索未读。'}, ensure_ascii=False)}
            assert request.get('tools'), 'query turns must expose tools'
            return {'role': 'assistant', 'content': None, 'tool_calls': calls}
        except Exception as error:
            # Return a bounded result so fixture assertion failures cannot hang the host.
            failures.append(repr(error))
            return {'role': 'assistant', 'content': json.dumps({'kind': 'plan', 'text': 'FIXTURE_FAILED'})}

    with provider(output, responder=respond) as (config, calls):
        isolated = json.loads(config.read_text(encoding='utf-8'))
        isolated['profiles'][0]['limits'].update(maxToolRounds=3, maxRepairAttempts=0, maxTransportRetries=0)
        config.write_text(json.dumps(isolated), encoding='utf-8')
        with running('ai-runtime', data=output/'runtime-game', ai_config=config, no_browser=True) as (runtime, password):
            kp, p1, p2 = provision(runtime, password)
            kp.action('chat', {'operation': 'chat.message.send', 'input': {
                'channelId': 'general', 'text': 'OFFLINE_CHANNEL_EVIDENCE'}})
            result(ai(kp, 'ai.settings.update', {'enabled': True, 'profileId': 'offline',
                'externalSources': {'public': True, 'kp': True, 'private': True},
                'auto': {'enabled': False, 'channelIds': [], 'prefix': '!ai '}}))
            expected = kp.request('/api/v1/ai/data/search', {'types': ['entity'], 'query': '', 'limit': 50})
            assert 'pageSummary' not in expected and expected['page']['nextCursor'] is None
            request = result(ai(kp, 'ai.request.create', {'sourceKind': 'manual', 'text': '查看房间概览与全局聊天'}))
            result(ai(kp, 'ai.request.dispatch', request))
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                task = next(t for t in kp.request('/api/v1/ai/tasks')['items'] if t['requestId'] == request['requestId'])
                if task['status'] not in ('received', 'queued', 'generating', 'validating'):
                    break
                time.sleep(.1)
            assert not failures, failures
            assert task['status'] == 'review_ready' and 'OFFLINE_RUNTIME_CHECK' in task['response'], task
            assert not task.get('proposalId') and len(calls) == 4, task
            assert task['diagnostics']['stage'] == 'completed' and task['diagnostics']['turn'] == 3
            assert len(task['diagnostics']['toolCalls']) == 7 and not task['diagnostics']['errors']
            first, last = observed['entities1'], observed['entities2']
            assert first['pageSummary'] == {'returnedItems': 25, 'countsByType': {'entity': 25}, 'hasMore': True, 'isFirstPage': True}
            assert last['pageSummary'] == {'returnedItems': len(last['items']),
                'countsByType': {'entity': len(last['items'])}, 'hasMore': False, 'isFirstPage': False}
            actual = [v['ref']['id'] for page in (first, last) for v in page['items']]
            assert len(actual) == len(set(actual)) and set(actual) == {v['ref']['id'] for v in expected['items']}
            configs = observed['configs']
            assert 0 < len(configs['items']) < 50
            assert configs['pageSummary'] == {'returnedItems': len(configs['items']),
                'countsByType': {'config': len(configs['items'])}, 'hasMore': False, 'isFirstPage': True}
            checks.append('current runtime provides actual authorized page counts and complete pagination; HTTP EvidencePage remains unchanged')
            checks.append('channel evidence reference resolves to general; actual chat text and NPC current fields reach the model')
            checks.append('updated pack guide reaches the model; three tool rounds end in one tool-free plan response with no proposal')


def main():
    output=PACK/'tests/output'/('ai-scopes-'+secrets.token_hex(4));output.mkdir(parents=True)
    observations=[]
    payloads=[]
    searches=[('config','sv.npc'),('entity','蜘蛛'),('memory',''),('event',''),('entity','npc'),('entity','守卫蛇')]
    def call(identifier,name,args):
        return {'id':identifier,'type':'function','function':{'name':name,'arguments':json.dumps(args,ensure_ascii=False)}}
    def respond(request):
        tools={m['tool_call_id']:json.loads(m['content']) for m in request['messages'] if m['role']=='tool'}
        if not tools:
            payload=json.loads(request['messages'][1]['content']);payloads.append(payload)
            assert payload['dataAccess']['mode']=='demand'
            assert payload['roomFacts']['entities']=={} and payload['roomFacts']['configurations']=={}
            return {'role':'assistant','content':None,'tool_calls':[call('s'+str(i),'room_search_data',{'types':[kind],'query':query,'limit':5}) for i,(kind,query) in enumerate(searches)]}
        if tools['s1']['items'] and 'read-npc' not in tools:
            return {'role':'assistant','content':None,'tool_calls':[call('read-npc','room_read_data',{'refs':[v['ref'] for v in tools['s1']['items']]})]}
        observations.append(tools)
        return {'role':'assistant','content':json.dumps({'kind':'plan','text':'OFFLINE_SCOPE_CHECK'})}
    checks=[]
    with provider(output,responder=respond) as (config,calls),running('ai-scopes',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
        kp,p1,p2=provision(runtime,password)
        pending=p1.action('request',{'kind':'free','text':'观察门边','manual':True})
        kp.action('resolve',{'requestId':pending['requestId'],'approve':True,'reason':'可以观察'})
        def ask(policy,owner=kp):
            result(ai(kp,'ai.settings.update',{'enabled':True,'profileId':'offline','externalSources':policy,'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}))
            request=result(ai(owner,'ai.request.create',{'sourceKind':'manual','text':'查询场景NPC，验证资料范围'}))
            result(ai(kp,'ai.request.dispatch',request))
            deadline=time.monotonic()+25
            while time.monotonic()<deadline:
                task=next(t for t in kp.request('/api/v1/ai/tasks')['items'] if t['requestId']==request['requestId'])
                if task['status'] not in ('received','queued','generating','validating'):break
                time.sleep(.1)
            assert task['status']=='review_ready',task
            return observations[-1]
        closed=ask({'public':False,'kp':False,'private':False})
        assert all(not closed['s'+str(i)]['items'] for i in range(len(searches)))
        # HTTP preview uses membership; actual model calls additionally apply external policy.
        assert len(kp.request('/api/v1/ai/data/search',{'types':['entity'],'query':'蜘蛛'})['items'])==2
        checks.append('enabled model with all external scopes off receives empty lists despite real KP-visible NPCs')
        kp_only=ask({'public':False,'kp':True,'private':False})
        assert len(kp_only['s1']['items'])==2 and len(kp_only['s5']['items'])==1
        assert all(not kp_only['s'+str(i)]['items'] for i in (0,2,3,4))
        assert all(v['data']['configurationId']=='sv.npc' and v['data']['numbers']['location']==6 for v in kp_only['read-npc']['items'])
        checks.append('KP scope exposes authoritative spiders/snake and current locations; name search npc remains empty')
        opened=ask({'public':True,'kp':True,'private':True})
        assert len(opened['s0']['items'])==1 and opened['s3']['items'] and not opened['s2']['items']
        checks.append('public configurations and private events have distinct scopes; no confirmed memory is a valid empty source')
        player=ask({'public':True,'kp':True,'private':True},p1)
        assert player['s0']['items'] and not player['s1']['items'] and not player['s5']['items']
        assert 'read-npc' not in player
        checks.append('KP dispatch of a PL request still cannot export KP-only NPCs')
        guide=payloads[-1]['sources']['stumpsville-guide']
        assert '表示“尚未加载”' in guide and '"types":["entity"],"query":""' in guide and 'room_read_data' in guide
        assert kp.request('/package/integrations')['ai']['guideCurrent'] is True
        active=runtime.modules.ai_pack
        stale=output/'stale-pack/ai';stale.mkdir(parents=True);(stale/'guide.md').write_text('old guide',encoding='utf-8')
        try:
            runtime.modules.ai_pack=stale.parent
            assert kp.request('/package/integrations')['ai']['guideCurrent'] is False
        finally:runtime.modules.ai_pack=active
        checks.append('demand placeholders remain empty while queries return data; current guide ships with snapshot and stale guide is detected')
    verify_runtime(output, checks)
    report={'checkedAt':datetime.now().astimezone().isoformat(),'passed':len(checks),'checks':checks,'provider':'loopback fixture','realSavesModified':False}
    (PACK/'tests/ai-scopes-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
