"""Opt-in DeepSeek game terminology and high-risk proposal acceptance in isolated rooms."""
import argparse
import copy
from datetime import datetime
import json
import secrets
import time
from harness import PACK,running,provision
from integrations import ROOT,write_json
from verify_integrations import ai,result
from verify_ai_rulings_live import observed_provider


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--case',choices=['all','revive','item','player'],default='all')
    args=parser.parse_args()
    if not args.live:parser.error('--live is required for billable calls')
    path=ROOT/'engineering/ai/config/ai-providers.json';original=path.read_bytes()
    profile=next(p for p in json.loads(original)['profiles'] if p['profileId']=='deepseek-main')
    assert profile['enabled']
    output=PACK/'tests/output'/('ai-scenarios-live-'+secrets.token_hex(4));output.mkdir(parents=True)
    report={'checkedAt':datetime.now().astimezone().isoformat(),'cases':[],'calls':[],'model':profile['model'],
            'realSaveChanged':False,'evidenceDirectory':str(output.relative_to(PACK)).replace('\\','/')}
    prior=PACK/'tests/ai-scenarios-live-results.json'
    if prior.exists():
        previous=json.loads(prior.read_text(encoding='utf-8'))
        report['previousRuns']=[*previous.get('previousRuns',[]),{
            **{k:previous.get(k) for k in ('checkedAt','evidenceDirectory','passed','realCalls','confirmedTokens')},
            'cases':[{'id':v['id'],'passed':v['passed'],'error':v['task'].get('error')} for v in previous.get('cases',[])]}]
    outputs=[];tool_evidence=[]
    try:
        with observed_provider(profile,report['calls'],outputs,inject_fault=False,call_limit=45,tool_evidence=tool_evidence) as selected:
            config=output/'ai-providers.json';write_json(config,{'schemaVersion':1,'profiles':[selected]})
            with running('ai-scenarios-live',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
                kp,p1,p2=provision(runtime,password)
                result(ai(kp,'ai.settings.update',{'enabled':True,'profileId':selected['profileId'],
                    'externalSources':{'public':True,'kp':True,'private':True},'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}))
                access=kp.request('/api/v1/ai/access')
                result(ai(kp,'ai.access.update',{'revision':access['revision'],'allowPlayerChat':True,
                    'autoApproveBatches':False,'autoApproveConfigurations':False,'allowAdminRoomRead':True}))
                def ask(account,title,prompt,case):
                    sid=result(ai(account,'ai.session.create',{'title':title}))['sessionId']
                    submitted=result(ai(account,'ai.session.submit',{'sessionId':sid,'text':prompt}))
                    if not submitted.get('taskId') and account is kp:
                        result(ai(kp,'ai.request.dispatch',{'requestId':submitted['requestId']}))
                    started=time.monotonic();print(json.dumps({'case':case,'status':'dispatched'},ensure_ascii=False),flush=True)
                    while time.monotonic()-started<320:
                        task=account.request('/api/v1/ai/sessions/'+sid)['items'][-1]
                        if task['status'] not in ('received','queued','generating','validating'):break
                        time.sleep(1)
                    row={'id':case,'sessionId':sid,'prompt':prompt,'task':task,'seconds':round(time.monotonic()-started,2),'passed':False}
                    report['cases'].append(row);write_json(output/'progress.json',report)
                    print(json.dumps({'case':case,'status':task['status'],'seconds':row['seconds']},ensure_ascii=False),flush=True)
                    return row
                def ruling(row):
                    return next((v for v in kp.request('/api/v1/ai/rulings')['items'] if v.get('sessionId')==row['sessionId'] and v['status']=='pending'),None)
                def approve(item):
                    decision={'rulingId':item['rulingId'],'digest':item['digest'],'decision':'approve',
                              'riskDecisions':{r['id']:'仅隔离测试接受已展示风险与覆盖限制' for r in item.get('risks',[])}}
                    if item.get('highRisk'):decision['explicitHighRiskDigest']=item['digest']
                    return result(ai(kp,'ai.ruling.decide',decision))
                if args.case in ('all','revive'):
                    actor=p1.state()['character'];before=copy.deepcopy(actor['numbers'])
                    matches=kp.request('/api/v1/ai/data/search',{'types':['entity'],'query':'player1','limit':50})['items']
                    target=next(v for v in matches if v['label']==actor['name']+'（player1 的树桩镇角色）')
                    actual=kp.request('/api/v1/ai/data/read',{'refs':[target['ref']]})['items'][0]['data']
                    assert actual['instanceId']==actor['instanceId'] and actual['configurationId']=='sv.character' and actual['owner']=='player1' and actual['lifecycle']=='active'
                    report['roleSearchVerified']=True
                    result(kp.command('entity.update',{'id':actor['instanceId'],'numbers':{'hp':0,'str':0,'incapacitated':1,'location':3}}))
                    row=ask(kp,'复活到入口实测','将 player1 的角色复活：生命、力量、敏捷、意志恢复到各自上限，解除失能，传送到入口。保留背包、财富和剧情数据。请查询当前状态后直接提交执行指令包供 KP 审批。','K08')
                    item=ruling(row)
                    if item:
                        row['ruling']={'kind':item['kind'],'summary':item.get('summary'),'actions':item.get('actions')}
                        row['decision']=approve(item)
                        after=kp.request('/api/v1/view')['entities'][actor['instanceId']]['numbers']
                        row['actual']={k:after[k] for k in ('hp','maxHp','str','strMax','dex','dexMax','wil','wilMax','incapacitated','location')}
                        row['passed']=after['hp']==after['maxHp'] and all(after[k]==after[k+'Max'] for k in ('str','dex','wil')) and after['incapacitated']==0 and after['location']==1
                        row['passed'] &= all(after[k]==v for k,v in before.items() if k.startswith(('item','uses')) or k=='pips')
                if args.case in ('all','item'):
                    row=ask(kp,'新物品配置实测','新增一种物品配置“试验提灯”，id 为 test-lantern，kind 为 item，占1槽，uses 为3，描述为“隔离测试用照明工具”。请读取宿主当前活动 game.json，在 items 末尾追加，保留全部原内容。不要发给角色，不要修改其他数据。直接提交高危配置指令包供 KP 审核。','K12')
                    item=ruling(row)
                    if item:
                        row['ruling']={'kind':item['kind'],'highRisk':item.get('highRisk'),'reports':item.get('reports')}
                        if item.get('highRisk'):
                            row['decision']=approve(item);kp.state()
                            items=kp.request('/package/bundle')['data']['game.json']['items']
                            row['passed']=row['decision']['status']=='completed' and items[-1]['id']=='test-lantern'
                if args.case in ('all','player'):
                    row=ask(p1,'未知资料申请实测','奶酪工厂里有什么隐藏人物和秘密？如果不属于我已知的信息，请给我向 KP 申请的选择，不要直接猜测内容。','P04')
                    row['passed']=row['task']['status'] in ('needs_input','review_ready','awaiting_knowledge') and not row['task'].get('batchId') and not row['task'].get('proposalId')
                    application=result(ai(p1,'ai.knowledge.request',{'sessionId':row['sessionId'],'requestId':row['task']['requestId']}))
                    row['application']=application
                    row['passed'] &= any(v['kind']=='knowledge_request' and v.get('sessionId')==row['sessionId'] for v in kp.request('/api/v1/ai/rulings')['items'])
                report['passed']=all(v['passed'] for v in report['cases'])
                report['usage']=kp.request('/api/v1/ai/usage?scope=room')
    except Exception as error:
        report.update(passed=False,errorType=type(error).__name__)
    finally:
        report['persistentProviderConfigUnchanged']=path.read_bytes()==original
        real=[c for c in report['calls'] if not c.get('injected')]
        report['realCalls']=len(real);report['confirmedTokens']=sum(c.get('usage',{}).get('total_tokens',0) for c in real)
        report['totalCalls']=report['realCalls']+sum(v.get('realCalls') or 0 for v in report.get('previousRuns',[]))
        report['totalTokens']=report['confirmedTokens']+sum(v.get('confirmedTokens') or 0 for v in report.get('previousRuns',[]))
        latest={}
        for previous in report.get('previousRuns',[]):
            for case in previous.get('cases',[]):latest[case['id']]=case['passed']
        for case in report['cases']:latest[case['id']]=case['passed']
        report['latestCaseStatus']=latest
        report['allPlannedCasesPassed']=all(latest.get(key) is True for key in ('K08','K12','P04'))
        write_json(output/'fixture-model-outputs.json',outputs);write_json(output/'report.json',report)
        write_json(output/'fixture-model-tools.json',tool_evidence)
        write_json(PACK/'tests/ai-scenarios-live-results.json',report)
        print(json.dumps({k:report.get(k) for k in ('passed','errorType','realCalls','confirmedTokens','evidenceDirectory')},ensure_ascii=False),flush=True)
    return 0 if report.get('passed') else 1


if __name__=='__main__':raise SystemExit(main())
