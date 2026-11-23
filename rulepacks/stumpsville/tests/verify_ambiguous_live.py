"""Run one bounded, real DeepSeek session against a disposable Stumpsville room."""
import argparse
import copy
import json
import time
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from ambiguous_suite import EXTRA, READ_ONLY, DECISIONS, appended_rain, solve
from datetime import datetime
from pathlib import Path

from harness import PACK, provision, running
import launch
from integrations import ROOT, write_json
from verify_ai_rulings_live import observed_provider
from verify_integrations import ai, result

CASES = {
    'shield': ('给木栗做个叫「水纹盾」的小盾吧，强度照同类推荐。做好了发给他，也提醒他一声。',
               '采用你的推荐，任一能放下的空槽都可以。请继续完成还没做的步骤。'),
    'travel': ('想给一个玩家添点路费，你帮我安排一下吧。',
               '给木栗，也就是 player1，加 3 枚钱币。发一条通知就好，豆叶不用改。'),
    'courtyard': ('庭院有点冷清。帮我在现场描述里添一句雨天的气氛，别动玩法。',
                  '就是地图上名为庭院的地点。雨声或雨滴都行，你来定稿，提交修改。'),
}
CASES.update({key:value[:2] for key,value in EXTRA.items()})
ACTIVE = {'received','queued','generating','validating'}
def stamp():
    return datetime.now().astimezone().isoformat(timespec='seconds')

def decode(value):
    try:
        return json.loads(value)
    except (ValueError,TypeError):
        return value

def differences(old, new, path=''):
    if old == new:
        return []
    if isinstance(old,dict) and isinstance(new,dict):
        out=[]
        for k in sorted(old.keys() | new.keys()):
            p=path+'/'+k.replace('~','~0').replace('/','~1')
            if k not in old or k not in new:
                out.append({'path':p,'before':old.get(k),'after':new.get(k)})
            else:
                out.extend(differences(old[k],new[k],p))
        return out
    if isinstance(old,list) and isinstance(new,list):
        out=[]
        for i in range(max(len(old),len(new))):
            a=old[i] if i<len(old) else None
            b=new[i] if i<len(new) else None
            out.extend(differences(a,b,path+'/'+str(i)))
        return out
    return [{'path':path,'before':old,'after':new}]

def model_trace(exchanges):
    reads={}
    answers=[]
    for ex in exchanges:
        for message in ex['request']['messages']:
            key=message.get('tool_call_id')
            if key in reads and message['role']=='tool':
                reads[key]['result']=decode(message['content'])
        for choice in ex['response'].get('choices',[]):
            msg=choice.get('message',{})
            for call in msg.get('tool_calls',[]):
                reads[call['id']]={'name':call['function']['name'],'arguments':decode(call['function']['arguments'])}
            if msg.get('content'):
                output=decode(msg['content'])
                if isinstance(output,dict):
                    answers.append({k:output[k] for k in ('kind','text','afterPublish') if k in output})
    return list(reads.values()),answers

def observe(kp,p1,p2):
    b=kp.request('/package/bundle')
    return {'data':b['data'],'sources':b['sources'],'configurations':{x['configurationId']:x for x in b['configurations']},
            'players':{p.name:p.state()['character']['numbers'] for p in (p1,p2)},
            'notices':{p.name:[{'id':n.get('notificationId') or n.get('id'), 'text':n.get('text')} for n in p.request('/api/v1/notifications?after=0&limit=100')['items']] for p in (p1,p2)}}

def achieved(case, before, now):
    changed=differences(before,now)
    a=before['data']['game.json'];b=now['data']['game.json']
    if case=='courtyard':
        for i,place in enumerate(a['locations']):
            if place['name']=='庭院':
                return len(changed)==1 and changed[0]['path']==f'/data/game.json/locations/{i}/description' and appended_rain(place['description'], b['locations'][i]['description'])
    nums=now['players']['player1']
    notice=len(now['notices']['player1'])==len(before['notices']['player1'])+1
    other=now['players']['player2']==before['players']['player2'] and now['notices']['player2']==before['notices']['player2']
    if case=='travel':
        return nums.get('pips')==before['players']['player1'].get('pips',0)+3 and notice and other and all(v['path']=='/players/player1/pips' or v['path'].startswith('/notices/player1/') for v in changed)
    items=b['items']
    return (len(items)==len(a['items'])+1 and items[:-1]==a['items'] and '水纹盾' in items[-1]['name'] and items[-1]['kind']=='armor' and
            any(nums.get('item'+str(i))==len(items) for i in range(1,21)) and notice and other and
            all(v['path'].startswith(('/data/game.json/items/','/players/player1/','/notices/player1/')) for v in changed))

def approve(kp,row):
    args={'rulingId':row['rulingId'],'digest':row['digest'],'decision':'approve','riskDecisions':{v['id']:'隔离房间核对目标与候选' for v in row.get('risks',[])}}
    if row.get('highRisk'):args['explicitHighRiskDigest']=row['digest']
    c=row.get('cAssessment') or {}
    if c.get('requiresAcceptance'):args['cReview']={k:c[k] for k in ('basisRevision','basisDigest','reportDigest')}
    c=row.get('consultationAssessment') or {}
    if c.get('requiresAcceptance'):args['consultationReview']={'sourceDigest':c['sourceDigest']}
    receipt=ai(kp,'ai.ruling.decide',args,allow_error=True)
    return {k:receipt[k] for k in ('status','code','requestId') if k in receipt}|{'resultStatus':(receipt.get('result') or {}).get('status')}

def probe_repeat(kp,p1,p2,session,exchanges,calls):
    """Same receipt versus a new, explicit expense, in a disposable room."""
    checks=[]
    for extra, prompt in ((False,'继续。'),(True,'另有一笔新饭钱，请再从木栗当前余额扣一枚，并另发一次定向通知。')):
        prior=observe(kp,p1,p2)
        known={x['rulingId'].split(':',1)[-1] for x in kp.request('/api/v1/ai/rulings')['items']}
        start_calls=len(calls);start_exchanges=len(exchanges)
        submitted=result(ai(kp,'ai.session.submit',{'sessionId':session,'text':prompt}))
        req=submitted['requestId']
        if not submitted.get('taskId'):
            saved=next(x for x in kp.request('/api/v1/ai/sessions/'+session)['items'] if x['requestId']==req)
            if saved['status']=='received':
                result(ai(kp,'ai.request.dispatch',{'requestId':req}))
        deadline=time.monotonic()+360
        while time.monotonic()<deadline:
            item=next(x for x in kp.request('/api/v1/ai/sessions/'+session)['items'] if x['requestId']==req)
            if item['status'] not in ACTIVE:break
            time.sleep(.5)
        else:
            raise TimeoutError('核对重复意图超时')
        row={'user':prompt,'reply':item.get('response') or item.get('error'),'status':item['status'],'calls':len(calls)-start_calls}
        row['tools'],row['outputs']=model_trace(exchanges[start_exchanges:])
        candidate=item.get('batchId') or item.get('proposalId')
        row['candidateId']=candidate
        if extra and item.get('batchId'):
            batch=kp.request('/api/v1/ai/rulings/batch:'+item['batchId'])
            row['actions']=batch.get('actions');row['preflight']=batch.get('preflight')
            if batch.get('canDecide') and batch['status']=='pending':
                row['approval']=approve(kp,batch)
        after=observe(kp,p1,p2)
        row['actualChanges']=differences(prior,after)
        if extra:
            row['passed']=(after['players']['player1']['pips']==prior['players']['player1']['pips']-1 and
                           len(after['notices']['player1'])==len(prior['notices']['player1'])+1 and
                           all(c['path']=='/players/player1/pips' or c['path'].startswith('/notices/player1/') for c in row['actualChanges']))
        else:
            row['passed']=(not candidate or candidate in known) and not row['actualChanges'] and item['status'] in ('review_ready','completed','published','approved')
        checks.append(row)
    return checks

def run(case,out,receipt_probe=False):
    if os.environ.get('SV_AMBIGUITY_ENGINE'):
        launch.ROOT=Path(os.environ['SV_AMBIGUITY_ENGINE']).resolve()
        assert (launch.ROOT/'engineering/backend/scripts/run.py').is_file()
    out.mkdir(parents=True,exist_ok=False)
    path=out/'observations.json'
    profile=next(p for p in json.loads((ROOT/'engineering/ai/config/ai-providers.json').read_bytes())['profiles'] if p['profileId']=='deepseek-main' and p['enabled'])
    report={'case':case,'fixtureEngine':str(launch.ROOT),'model':profile['model'],'started':stamp(),'turns':[],'complete':False,'providerCalls':[]}
    overlays = launch.ROOT/'frozen-overlays.json'
    if overlays.is_file():
        report['overlayManifests'] = json.loads(overlays.read_bytes())
    write_json(path,report)
    exchange=[];calls=report['providerCalls']
    try:
        with observed_provider(profile,calls,[],inject_fault=False,call_limit=32,tool_evidence=exchange) as selected:
            selected['request']=copy.deepcopy(profile['request'])
            config=out/'ai-providers.json';write_json(config,{'schemaVersion':1,'profiles':[selected]})
            with running(data=out/'game',host_control_dir=out/'control',ai_config=config,no_browser=True) as (room,pw):
                k,p1,p2=provision(room,pw)
                result(ai(k,'ai.settings.update',{'enabled':True,'profileId':selected['profileId'],'externalSources':{'public':True,'kp':True,'private':True},'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}))
                access=k.request('/api/v1/ai/access')
                result(ai(k,'ai.access.update',{'revision':access['revision'],'allowPlayerChat':access['allowPlayerChat'],'allowAdminRoomRead':True,'allowRuntimeChanges':True,'allowConfigurationChanges':True,'autoApproveConfigurations':False,'autoApproveBatches':False}))
                sid=result(ai(k,'ai.session.create',{'title':'模糊需求验收 '+case}))['sessionId']
                if case=='heal':
                    actor=p2.state()['character']
                    result(k.command('entity.update',{'id':actor['instanceId'],'numbers':{'hp':max(1,actor['numbers']['maxHp']-2)}}))
                initial=observe(k,p1,p2);current=initial
                human=0;prompt=CASES[case][0];next_from=None;offset=0;calls_offset=0
                for n in range(6):
                    if not next_from:
                        if human>=4 or len(calls)>=32:break
                        human+=1
                    turn={'number':n+1,'humanRound':human,'automatic':bool(next_from),'user':None if next_from else prompt,'start':stamp()}
                    report['turns'].append(turn);write_json(path,report)
                    if next_from:
                        rid=None
                    else:
                        q=result(ai(k,'ai.session.submit',{'sessionId':sid,'text':prompt}))
                        rid=q['requestId']
                        if not q.get('taskId'):result(ai(k,'ai.request.dispatch',{'requestId':rid}))
                    end=time.monotonic()+380
                    while time.monotonic()<end:
                        rows=k.request('/api/v1/ai/sessions/'+sid)['items']
                        item=next((x for x in rows if (rid and x['requestId']==rid) or (next_from and (x.get('continuationOrigin') or {}).get('proposalId')==next_from)),None)
                        if item and item['status'] not in ACTIVE:break
                        time.sleep(.6)
                    else:raise TimeoutError('等待本轮答复超时')
                    next_from=None
                    turn.update(requestId=item['requestId'],status=item['status'],error=item.get('error'),finished=stamp(),
                                events=item.get('events',[]),dependencyCheck=item.get('dependencyCheck'),deliveredAnswer=bool(item.get('response')))
                    turn['tools'],turn['outputs']=model_trace(exchange[offset:]);offset=len(exchange)
                    turn['providerCallRange']=[calls_offset+1,len(calls)];calls_offset=len(calls)
                    turn['reply']=item.get('response') or item.get('historicalText') or next((v['text'] for v in reversed(turn['outputs']) if v.get('text')),None)
                    if not turn['reply']:turn['reply']=item.get('error') or '未交付回复正文'
                    key='proposal:'+item['proposalId'] if item.get('proposalId') else 'batch:'+item['batchId'] if item.get('batchId') else None
                    if key:
                        row=k.request('/api/v1/ai/rulings/'+key)
                        turn['ruling']={f:row[f] for f in ('rulingId','status','summary','changeOverview','reports','actions','preflight','blockingReason','consultationAssessment','continuation') if f in row}
                        changes=[]
                        for d in row.get('diff',[]):
                            changes+=differences(d.get('before'),d.get('after'),'/'+d['target']+'/'+d['id'])
                        turn['proposedChanges']=changes
                        # A guessed player/amount cannot satisfy a deliberately unspecified choice.
                        allow=(case not in DECISIONS or human>=2) and case not in READ_ONLY
                        if case=='courtyard' and key.startswith('proposal:'):
                            expected='/data/game.json/locations/'+str(next(i for i,v in enumerate(initial['data']['game.json']['locations']) if v['name']=='庭院'))+'/description'
                            allow=bool(changes) and all(v['path']==expected for v in changes)
                        if case=='shield' and key.startswith('proposal:'):
                            allow=bool(changes) and all(v['path'].startswith('/data/game.json/items/') for v in changes)
                        if row.get('canDecide') and row['status']=='pending' and allow:
                            turn['approval']=approve(k,row)
                            final=k.request('/api/v1/ai/rulings/'+key)
                            turn['decisionEvidence']={field:final[field] for field in ('status','blockingReason','receipts','publications','execution') if field in final}
                            if row.get('continuation') and turn['approval']['resultStatus']=='completed':
                                next_from=item['proposalId']
                        elif not allow:turn['withheld']='候选目标或范围尚未符合验收约定'
                    now=observe(k,p1,p2);turn['actualChanges']=differences(current,now);current=now
                    turn['overallPaths']=[x['path'] for x in differences(initial,now)]
                    report['complete']=solve(case,initial,now,turn,k,p1) if case in EXTRA else achieved(case,initial,now)
                    report['humanRounds']=human
                    write_json(path,report)
                    print(case,human,item['status'],len(calls),report['complete'],flush=True)
                    if report['complete'] or (calls and calls[-1].get('httpStatus') in (401,403,503)):break
                    if human==1:prompt=CASES[case][1]
                    elif case=='shield' and len(now['data']['game.json']['items'])>len(initial['data']['game.json']['items']):
                        prompt='盾的定义已经发布，请核对木栗的实际空位，把这件盾发给他并定向通知。不需要再创建定义。'
                    elif turn.get('ruling') and turn['ruling'].get('blockingReason'):
                        prompt='请根据刚才校验报告修正失败项，沿用已确认的目标，提交可采用的方案。'
                    else:prompt='就按刚才说好的做法继续，查当前数据，把未完成的部分提交裁决。'
                report['goalProviderCallCount']=len(calls)
                if receipt_probe and report['complete']:
                    report['receiptProbe']=probe_repeat(k,p1,p2,sid,exchange,calls)
    except Exception as e:
        report['runError']=type(e).__name__+': '+str(e)[:1400]
    finally:
        report['responseModels']=sorted({entry['response']['model'] for entry in exchange if entry.get('response',{}).get('model')})
        report['finished']=stamp();write_json(path,report)
    return report['complete'] and (not receipt_probe or len(report.get('receiptProbe',[]))==2 and all(x['passed'] for x in report['receiptProbe']))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case',choices=[*CASES,'all'])
    parser.add_argument('--workers',type=int,choices=range(1,5),default=4)
    parser.add_argument('--engine-root',type=Path,help='Isolated checkout containing engineering/backend and engineering/ai')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--live',action='store_true',required=True)
    parser.add_argument('--receipt-probe',action='store_true',help='After dinner also test continue and a new explicit expense')
    args=parser.parse_args()
    if args.receipt_probe and args.case not in ('dinner','all'):
        parser.error('--receipt-probe requires dinner or all')
    if args.engine_root:
        os.environ['SV_AMBIGUITY_ENGINE']=str(args.engine_root.resolve(strict=True))
    if args.case=='all':
        parent=args.output.resolve()
        parent.mkdir(parents=True,exist_ok=False)
        def child(key):
            with (parent/(key+'.log')).open('wb') as log:
                command=[sys.executable,'-B',str(Path(__file__).resolve()),key,'--live','--output',str(parent/key)]
                if args.receipt_probe and key=='dinner':
                    command.append('--receipt-probe')
                return subprocess.run(command,stdout=log,stderr=subprocess.STDOUT).returncode
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            codes=list(pool.map(child,CASES))
        raise SystemExit(int(any(codes)))
    raise SystemExit(0 if run(args.case,args.output.resolve(),args.receipt_probe) else 1)
