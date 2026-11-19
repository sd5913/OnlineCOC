"""Billable opt-in replay of the three reported PL questions in an isolated room."""
import argparse
from datetime import datetime
import json
import secrets
import time
from harness import PACK,running,provision
from integrations import ROOT,write_json
from verify_integrations import ai,result
from verify_ai_rulings_live import observed_provider


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--live',action='store_true');args=parser.parse_args()
    if not args.live:parser.error('--live is required for billable calls')
    path=ROOT/'engineering/ai/config/ai-providers.json';original=path.read_bytes()
    profile=next(p for p in json.loads(original)['profiles'] if p['profileId']=='deepseek-main');assert profile['enabled']
    output=PACK/'tests/output'/('ai-player-requests-live-'+secrets.token_hex(4));output.mkdir(parents=True)
    report={'checkedAt':datetime.now().astimezone().isoformat(),'cases':[],'calls':[],'model':profile['model'],
        'realSaveChanged':False,'evidenceDirectory':str(output.relative_to(PACK)).replace('\\','/')}
    prior=PACK/'tests/ai-player-requests-live-results.json'
    if prior.exists():
        previous=json.loads(prior.read_text(encoding='utf-8'))
        report['previousRuns']=[*previous.get('previousRuns',[]),{k:previous.get(k) for k in ('checkedAt','evidenceDirectory','passed','realCalls','confirmedTokens','caseStatus')}]
    outputs=[];evidence=[]
    try:
        with observed_provider(profile,report['calls'],outputs,inject_fault=False,call_limit=24,tool_evidence=evidence) as selected:
            config=output/'ai-providers.json';write_json(config,{'schemaVersion':1,'profiles':[selected]})
            with running('ai-player-live',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
                kp,p1,p2=provision(runtime,password)
                result(ai(kp,'ai.settings.update',{'enabled':True,'profileId':selected['profileId'],'externalSources':{'public':True,'kp':True,'private':True},'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}))
                access=kp.request('/api/v1/ai/access');result(ai(kp,'ai.access.update',{'revision':access['revision'],'allowPlayerChat':True,'allowPlayerRequests':True,'autoApproveBatches':False,'autoApproveConfigurations':False}))
                actor=p1.state()['character']['instanceId']
                result(kp.command('entity.update',{'id':actor,'numbers':{'location':3}}))
                kp.action('location.publish',{'index':3,'clues':[]})
                kp.action('location.reveal',{'index':3,'accounts':['player1'],'knowledge':['pool-treasure']})
                baseline=p1.state()['character']['numbers'];original_game=kp.request('/package/bundle')['data']['game.json']
                def ask(case,text):
                    sid=result(ai(p1,'ai.session.create',{'title':text}))['sessionId']
                    submitted=result(ai(p1,'ai.session.submit',{'sessionId':sid,'text':text}));start=time.monotonic()
                    print(json.dumps({'case':case,'status':'dispatched'},ensure_ascii=False),flush=True)
                    while time.monotonic()-start<320:
                        task=p1.request('/api/v1/ai/sessions/'+sid)['items'][-1]
                        if task['status'] not in ('received','queued','generating','validating'):break
                        time.sleep(1)
                    row={'id':case,'sessionId':sid,'requestId':submitted['requestId'],'prompt':text,'task':task,'passed':False,'seconds':round(time.monotonic()-start,2)}
                    report['cases'].append(row);write_json(output/'progress.json',report)
                    return row
                row=ask('P02','我现在应该做什么')
                response=row['task'].get('response','')
                row['passed']=row['task']['status']=='review_ready' and '资料不足' not in response and '权限不足' not in response and ('庭院' in response or '水池' in response)
                row=ask('P03','现在有什么线索')
                response=row['task'].get('response','')
                row['passed']=row['task']['status']=='review_ready' and '池底' in response and '资料不足' not in response
                row=ask('P11','我想用火把给针剑附魔，变成火焰针剑')
                rendered=json.dumps(row['task'],ensure_ascii=False)
                row['passed']=row['task']['status'] in ('review_ready','needs_input') and ('创作申请' in rendered or 'ask_kp_change' in rendered)
                before=kp.request('/api/v1/ai/rulings')['items']
                assert not any(x['kind']=='player_request' and x.get('sessionId')==row['sessionId'] for x in before)
                application=result(ai(p1,'ai.player.request',{'sessionId':row['sessionId'],'requestId':row['requestId']}));row['application']=application
                row['passed'] &= any(x['kind']=='player_request' and x['rulingId']==application['rulingId'] for x in kp.request('/api/v1/ai/rulings')['items'])
                row['passed'] &= p1.state()['character']['numbers']==baseline and kp.request('/package/bundle')['data']['game.json']==original_game
                assert p2.request('/api/v1/ai/sessions/'+row['sessionId'],allow_error=True).get('code')
                report['passed']=all(c['passed'] for c in report['cases'])
    except Exception as error:report.update(passed=False,errorType=type(error).__name__,error=str(error)[:500])
    finally:
        report['persistentProviderConfigUnchanged']=path.read_bytes()==original
        real=[c for c in report['calls'] if not c.get('injected')];report['realCalls']=len(real)
        report['confirmedTokens']=sum(c.get('usage',{}).get('total_tokens',0) for c in real)
        report['totalCalls']=report['realCalls']+sum(v.get('realCalls') or 0 for v in report.get('previousRuns',[]))
        report['totalTokens']=report['confirmedTokens']+sum(v.get('confirmedTokens') or 0 for v in report.get('previousRuns',[]))
        report['caseStatus']={c['id']:c['passed'] for c in report['cases']}
        write_json(output/'fixture-model-outputs.json',outputs);write_json(output/'fixture-model-tools.json',evidence)
        write_json(output/'report.json',report);write_json(prior,report)
        print(json.dumps({k:report.get(k) for k in ('passed','caseStatus','realCalls','confirmedTokens','errorType','evidenceDirectory')},ensure_ascii=False),flush=True)
    return 0 if report.get('passed') else 1

if __name__=='__main__':raise SystemExit(main())
