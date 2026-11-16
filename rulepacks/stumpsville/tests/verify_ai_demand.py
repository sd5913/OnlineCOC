"""Opt-in live consultation using generated fixtures, never the user's room.

Makes billable requests only with --live. The configured credential is resolved
by the normal host; this script never reads or prints its value.
"""
import argparse
from datetime import datetime
import json
import secrets
import re
import hashlib
import time

from harness import PACK, running, provision
from integrations import ROOT
from verify_integrations import ai, result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Explicitly allow billable model calls using sample room data')
    parser.add_argument('--profile',default='deepseek-main')
    parser.add_argument('--result-name', default='ai-demand-results.json', help='Report filename inside tests; use a new name to preserve prior evidence')
    parser.add_argument('--token-budget', type=int, default=100000, help='Isolated profile daily token reservation ceiling, 10000..200000')
    parser.add_argument('--max-output-tokens', type=int, default=2200, help='Per-response output cap for this isolated run, 128..8192')
    args=parser.parse_args()
    if not 128 <= args.max_output_tokens <= 8192:parser.error('output cap must be 128..8192')
    if not 10000 <= args.token_budget <= 200000:parser.error('token budget must be 10000..200000')
    if not re.fullmatch(r'ai-demand-[a-zA-Z0-9-]+\.json', args.result_name):parser.error('invalid result filename')
    if not args.live:parser.error('--live is required; normal regressions must use loopback fixtures')
    output=PACK/'tests/output'/('ai-demand-'+secrets.token_hex(4));output.mkdir(parents=True)
    original_config=ROOT/'engineering/ai/config/ai-providers.json'
    config_bytes=original_config.read_bytes()
    config=json.loads(config_bytes)
    profile=next(p for p in config['profiles'] if p['profileId']==args.profile)
    assert profile['enabled'],'Selected profile must already be enabled'
    # Keep provider, model and credential reference unchanged. Bound this test.
    profile['limits'].update(maxToolRounds=6,maxRepairAttempts=0,maxTransportRetries=0,taskTimeoutMs=240000,dailyTokenBudget=args.token_budget)
    profile['request']['maxOutputTokens']=args.max_output_tokens
    config_path=output/'ai-providers.json'
    config_path.write_text(json.dumps({'schemaVersion':1,'profiles':[profile]},ensure_ascii=False),encoding='utf-8')
    report={'checkedAt':datetime.now().astimezone().isoformat(),'model':profile['model'],
        'liveProvider':True,'realSaveChanged':False,'scope':'isolated generated sample room only','passed':False,
        'acceptanceScope':'automatic query-chain checks; answer quality requires separate evidence review',
        'evidenceDirectory':str(output.relative_to(PACK)).replace('\\','/'),
        'limits':profile['limits'], 'maxOutputTokens':profile['request']['maxOutputTokens'],
        'prompt':'查看所有房间信息并梳理'}
    try:
        with running('ai-demand',data=output/'game',ai_config=config_path,no_browser=True) as (runtime,password):
            kp,_,_=provision(runtime,password)
            result(ai(kp,'ai.settings.update',{'enabled':True,'profileId':args.profile,
                'externalSources':{'public':True,'kp':True,'private':True},
                'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}))
            # Deliberately the user's natural question, with no forced tool names.
            request=result(ai(kp,'ai.request.create',{'sourceKind':'manual','text':'查看所有房间信息并梳理'}))
            result(ai(kp,'ai.request.dispatch',request))
            print('Isolated live consultation dispatched',flush=True)
            deadline=time.monotonic()+255
            while time.monotonic()<deadline:
                task=next(t for t in kp.request('/api/v1/ai/tasks')['items'] if t['requestId']==request['requestId'])
                if task['status'] not in ('received','queued','generating','validating'):break
                time.sleep(1)
            # Read only this test's repository for actual query provenance.
            latest=max((output/'game/host/ai/generations').glob('*.json'),key=lambda p:p.stat().st_mtime)
            repository=json.loads(latest.read_text(encoding='utf-8'))['payload']
            saved=repository['tasks'][task['taskId']]
            context=repository['contexts'].get(saved.get('contextRef'),{})
            queries=context.get('facts',{}).get('dataQueries',[])
            summary=[{'operation':q['operation'],'types':q['args'].get('types'),
                'query':q['args'].get('query'),'references':len(q['args'].get('refs',[])),
                'hasCursor':bool(q['args'].get('cursor')), 'limit':q['args'].get('limit')} for q in queries]
            call_ids={call['callId'] for call in saved['calls']}
            budget_calls=[call for budget in repository['budgets'].values() for cid,call in budget['calls'].items() if cid in call_ids]
            report.update(unsettledCalls=sum(call['status']!='settled' for call in budget_calls),
                budgetCharged=sum(call['charged'] for call in budget_calls),
                usageComplete=all(call['status']=='settled' for call in budget_calls))
            room_file=max((output/'game/host/rooms/demo/generations').glob('*.json'))
            room=json.loads(room_file.read_text(encoding='utf-8'))['payload']
            report['sampleGroundTruth']={'activeEntities':sum(e['lifecycle']=='active' for e in room['entities'].values()),'configurations':len(room['configurations']), 'hostChannels':len(room['chat']['channels'])}
            reply=saved.get('text') or ''
            report.update(status=saved['status'],error=saved['error'],providerCalls=len(saved['calls']),tokens=saved['usage'],queries=summary,
                providerResponses=sum('responseDigest' in call for call in saved['calls']),
                usage={key:sum(call.get('usage',{}).get(key,0) for call in saved['calls']) for key in ('prompt_tokens','completion_tokens','total_tokens')},
                rawModelResponseStored=False, diagnostics=saved.get('diagnostics'),
                replySha256=hashlib.sha256(reply.encode()).hexdigest(),replyCharacters=len(reply),
                checks={'entityEnumeration':any(q['operation']=='search' and 'entity' in q['args'].get('types',[]) and not q['args'].get('query') for q in queries),
                    'configEnumeration':any(q['operation']=='search' and 'config' in q['args'].get('types',[]) and not q['args'].get('query') for q in queries),
                    'detailsRead':any(q['operation']=='read' for q in queries),
                    'actualNamesInReply':any(name in reply for name in ('蜘蛛','守卫蛇','木栗','豆叶'))})
            report['passed']=saved['status']=='review_ready' and all(report['checks'].values())
            (output/'reply.txt').write_text(reply,encoding='utf-8')
            assert report['passed'], {'status':report['status'],'error':report['error'],'report':args.result_name}
    finally:
        report['persistentProviderConfigUnchanged']=original_config.read_bytes()==config_bytes
        encoded=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
        (output/'report.json').write_text(encoded,encoding='utf-8')
        (PACK/'tests'/args.result_name).write_text(encoded,encoding='utf-8')
        print(json.dumps({k:report.get(k) for k in ('passed','status','error','providerCalls','tokens','checks','evidenceDirectory')},ensure_ascii=True),flush=True)


if __name__=='__main__':main()
