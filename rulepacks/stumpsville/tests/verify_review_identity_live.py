"""Bounded real DeepSeek review identity and stale follow-up integration cases."""
import argparse
import copy
import hashlib
import json
import secrets
import time
from datetime import datetime
from harness import PACK, running, provision
from integrations import ROOT, write_json
from verify_integrations import ai, result
from verify_ai_rulings_live import observed_provider


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--model',choices=['deepseek-flash','deepseek-v4-pro'],default='deepseek-flash')
    parser.add_argument('--call-limit',type=int,default=32)
    args=parser.parse_args()
    if not args.live:parser.error('--live is required for billable calls')
    if not 1<=args.call_limit<=40:parser.error('call-limit must be 1..40')
    config_path=ROOT/'engineering/ai/config/ai-providers.json';original=config_path.read_bytes()
    profile=copy.deepcopy(next(p for p in json.loads(original)['profiles'] if p['profileId']=='deepseek-main'))
    profile['model']=args.model
    output=PACK/'tests/output'/('review-identity-live-'+args.model+'-'+secrets.token_hex(4));output.mkdir(parents=True)
    prior=PACK/'tests'/('review-identity-live-'+args.model+'-results.json')
    report={'checkedAt':datetime.now().astimezone().isoformat(),'requestedModel':args.model,'thinking':'disabled','callLimit':args.call_limit,'cases':[],'executionChecks':[],'calls':[],'realSaveChanged':False,'evidenceDirectory':output.relative_to(PACK).as_posix()}
    report['sourceDigests']={name:hashlib.sha256((PACK/name).read_bytes()).hexdigest() for name in ['ai/guide.md','ai/game-terms.json']}
    report['testConfiguration']={'maxOutputTokens':8192,'maxToolRounds':profile['limits'].get('maxToolRounds'),'maxRepairAttempts':5,'maxTransportRetries':0,'thinking':'disabled'}
    if prior.exists():
        old=json.loads(prior.read_text(encoding='utf-8'));report['previousRuns']=[*old.get('previousRuns',[]),{k:old.get(k) for k in ['passed','rates','realCalls','confirmedTokens','failureAnalysis','evidenceDirectory']}]
    outputs=[];evidence=[]
    try:
        with observed_provider(profile,report['calls'],outputs,inject_fault=False,call_limit=args.call_limit,tool_evidence=evidence) as selected:
            selected['request']=copy.deepcopy(profile['request']);selected['request']['maxOutputTokens']=8192
            config=output/'ai-providers.json';write_json(config,{'schemaVersion':1,'profiles':[selected]})
            with running('identity-live',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
                kp,p1,p2=provision(runtime,password)
                result(ai(kp,'ai.settings.update',{'enabled':True,'profileId':selected['profileId'],'externalSources':{'public':True,'kp':True,'private':True},'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}))
                access=kp.request('/api/v1/ai/access')
                result(ai(kp,'ai.access.update',{'revision':access['revision'],'allowPlayerChat':True,'allowAdminRoomRead':True,'allowRuntimeChanges':True,'allowConfigurationChanges':True,'autoApproveBatches':False,'autoApproveConfigurations':False}))
                def actor(player):return player.state()['character']
                def inbox(player):return player.request('/api/v1/notifications')['items']
                def clear_notices():
                    for player in (p1,p2):
                        for notice in inbox(player):player.action('notification.ack',{'notificationId':notice['notificationId']})
                clear_notices()
                def wait(sid):
                    deadline=time.monotonic()+320
                    while time.monotonic()<deadline:
                        rows=kp.request('/api/v1/ai/sessions/'+sid)['items']
                        if rows and rows[-1]['status'] not in {'received','queued','generating','validating'}:return rows[-1]
                        time.sleep(1)
                    raise TimeoutError('MODEL_TASK_TIMEOUT')
                def ask(sid,text):
                    submitted=result(ai(kp,'ai.session.submit',{'sessionId':sid,'text':text}))
                    if not submitted.get('taskId') and submitted.get('requestId'):result(ai(kp,'ai.request.dispatch',{'requestId':submitted['requestId']}))
                    return wait(sid)
                def proposed(sid,entity,expected):
                    rows=kp.request('/api/v1/ai/rulings')['items']
                    row=next((r for r in rows if r.get('sessionId')==sid and r['kind']=='runtime' and r['status']=='pending'),None)
                    assert row,'No pending runtime batch: inspect task status, output and diagnostics'
                    writes=[a for a in row['actions'] if a['op'].startswith('entity.') or a['op'] in {'action.invoke','behavior.invoke'}]
                    assert len(writes)==1,writes
                    write=writes[0]
                    assert write['target']=='host' and write['op']=='entity.update' and write['args']['id']==entity['instanceId'],writes
                    assert write['args']['numbers']=={'pips':expected},writes
                    notices=[a for a in row['actions'] if a['op']=='notification.send']
                    assert len(notices)==1,'The reviewed batch must include one explicit recipient notification'
                    assert notices[0]['args']['recipientAccountIds']==[entity['owner']],notices
                    assert notices[0]['args']['sourceActionIndex']==row['actions'].index(write),notices
                    return row
                def decide(row):
                    return result(ai(kp,'ai.ruling.decide',{'rulingId':row['rulingId'],'digest':row['digest'],'decision':'approve','riskDecisions':{r['id']:'隔离验收：目标、增量与通知已核对' for r in row.get('risks',[])}}))
                first={'id':'quoted-player-intent','goal':'来源第一人称属于player1；当前KP收到待审批次，不再询问是否提交','attempts':[],'passed':False};report['cases'].append(first)
                started=time.monotonic();calls_before=len(report['calls'])
                try:
                    before=actor(p1);other=copy.deepcopy(actor(p2)['numbers'])
                    request=p1.action('request',{'kind':'free','manual':True,'text':'给我的角色增加1枚钱币，请直接准备给KP审核的指令包，不用再问我是否要提交。'})
                    review=kp.action('ai.review',{'kind':'request','id':request['requestId']});sid=review['sessionId'];task=wait(sid)
                    attempt={'task':task,'calls':len(report['calls'])};first['attempts'].append(attempt)
                    row=proposed(sid,before,before['numbers']['pips']+1);attempt['ruling']=row
                    assert actor(p1)['numbers']['pips']==before['numbers']['pips'] and actor(p2)['numbers']==other
                    outcome=decide(row);assert outcome['status']=='completed',outcome
                    assert actor(p1)['numbers']['pips']==before['numbers']['pips']+1 and actor(p2)['numbers']==other
                    notices=inbox(p1);assert len(notices)==1 and not inbox(p2),notices
                    assert notices[0]['source']['op']=='entity.update' and notices[0]['source']['status']=='committed'
                    assert decide(row)['status']=='completed' and inbox(p1)==notices
                    report['executionChecks'].append({'id':'reviewed-notice-once','passed':True,'notificationId':notices[0]['notificationId'],'source':notices[0]['source']})
                    first['passed']=True;attempt['passed']=True
                    report['executionChecks'].append({'id':'approved-target-only','passed':True,'rulingId':row['rulingId']})
                except Exception as error:first.update(errorType=type(error).__name__,error=str(error)[:2000])
                first.update(elapsedSecondsIncludingApproval=round(time.monotonic()-started,2),realCalls=len(report['calls'])-calls_before)
                write_json(output/'progress.json',report);print(json.dumps({'case':first['id'],'passed':first['passed'],'calls':len(report['calls'])}),flush=True)
                second={'id':'stale-short-confirmation','goal':'旧依据变化后保留对话意图，短确认直接提交player2加2钱币待审批次','attempts':[],'passed':False};report['cases'].append(second)
                started=time.monotonic();calls_before=len(report['calls'])
                try:
                    before=actor(p2);other=copy.deepcopy(actor(p1)['numbers'])
                    sid=result(ai(kp,'ai.session.create',{'title':'过期方案短确认验收'}))['sessionId']
                    prompt='给 player2 的角色增加2枚钱币。先读取角色当前钱币并说明具体方案，暂不生成指令包，等我下一条同意后再提交。'
                    plan=ask(sid,prompt);second['plan']=plan;assert plan.get('response') and not plan.get('batchId'),plan
                    # An unrelated field changes the entity version, so the old facts are stale.
                    kp.action('actor.update',{'id':before['instanceId'],'numbers':{'armor':before['numbers']['armor']+1}})
                    historical=kp.request('/api/v1/ai/sessions/'+sid)['items'][-1]
                    second['historicalDisplay']={k:historical.get(k) for k in ['status','text','response','error','sourceState','sourceError','sourceNotice','historicalReadOnly']}
                    assert historical.get('response')==plan['response'],'Stale source incorrectly erased the readable answer'
                    clear_notices()
                    task=ask(sid,'是的，按此方案处理，直接提交给我审批。')
                    attempt={'task':task,'calls':len(report['calls'])};second['attempts'].append(attempt)
                    row=proposed(sid,before,before['numbers']['pips']+2);attempt['ruling']=row
                    assert actor(p2)['numbers']['pips']==before['numbers']['pips']
                    outcome=decide(row);assert outcome['status']=='completed',outcome
                    assert actor(p2)['numbers']['pips']==before['numbers']['pips']+2 and actor(p1)['numbers']==other
                    notices=inbox(p2);assert len(notices)==1 and not inbox(p1),notices
                    count=len(report['calls']);repeated=result(ai(kp,'ai.session.submit',{'sessionId':sid,'text':'批准'}))
                    assert repeated.get('ruling',{}).get('status')=='completed',repeated
                    assert actor(p2)['numbers']['pips']==before['numbers']['pips']+2 and len(report['calls'])==count
                    assert inbox(p2)==notices
                    second['passed']=True;attempt['passed']=True
                    report['executionChecks'].append({'id':'repeat-confirm-no-replay','passed':True,'rulingId':row['rulingId']})
                except Exception as error:second.update(errorType=type(error).__name__,error=str(error)[:2000])
                second.update(elapsedSecondsIncludingApproval=round(time.monotonic()-started,2),realCalls=len(report['calls'])-calls_before)
                report['usage']=kp.request('/api/v1/ai/usage?scope=room')
                print(json.dumps({'case':second['id'],'passed':second['passed'],'calls':len(report['calls'])}),flush=True)
    except Exception as error:report.update(errorType=type(error).__name__,error=str(error)[:1600])
    finally:
        report['persistentProviderConfigUnchanged']=config_path.read_bytes()==original
        report['realCalls']=len([c for c in report['calls'] if not c.get('injected')])
        report['confirmedTokens']=sum(c.get('usage',{}).get('total_tokens',0) for c in report['calls'])
        report['returnedModels']=sorted({e.get('response',{}).get('model') for e in evidence if e.get('response',{}).get('model')})
        observed_tasks={task['requestId']:task for case in report['cases'] for task in [case.get('plan'),*[attempt.get('task') for attempt in case.get('attempts',[])]] if task and task.get('requestId')}
        report['modelOutputRepairFailures']=sum(len(task.get('diagnostics',{}).get('outputFailures',[])) for task in observed_tasks.values())
        passed=sum(c['passed'] for c in report['cases']);total=len(report['cases'])
        report['rates']={'firstAttemptPassed':passed,'totalCases':total,'firstAttemptRate':passed/total if total else 0,'note':'按用户请求计，包含额度内自动格式修正；原始输出修正另列。小样本专项，不代表全部跑团需求成功率'}
        report['passed']=total==2 and passed==total and report['persistentProviderConfigUnchanged']
        write_json(output/'provider-evidence.json',evidence);write_json(output/'model-outputs.json',outputs)
        write_json(output/'report.json',report);write_json(prior,report)
        print(json.dumps({k:report.get(k) for k in ['passed','rates','realCalls','confirmedTokens','returnedModels','error','evidenceDirectory']},ensure_ascii=True),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
