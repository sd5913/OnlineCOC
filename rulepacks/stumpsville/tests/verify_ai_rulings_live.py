"""Opt-in billable experiments with isolated sample rooms and a single format fault."""
import argparse, copy, json, secrets, threading, time, re
from contextlib import contextmanager
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import httpx
from harness import PACK, running, provision
from integrations import ROOT, write_json
from verify_integrations import ai, result


@contextmanager
def observed_provider(profile, observations, observations_output, *, inject_fault=True, call_limit=24, tool_evidence=None):
    assert profile['adapter']=='deepseek-chat' and profile['baseUrl'].rstrip('/')=='https://api.deepseek.com'
    class Handler(BaseHTTPRequestHandler):
        injected=not inject_fault
        def log_message(self,*args):pass
        def do_POST(self):
            body=self.rfile.read(int(self.headers.get('Content-Length','0')))
            if not Handler.injected:
                Handler.injected=True
                value={'choices':[{'message':{'role':'assistant','content':'{broken JSON'},'finish_reason':'stop'}],
                    'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}}
                code=200;observations.append({'injected':True,'reason':'synthetic invalid JSON','usage':value['usage']})
            elif sum(not c.get('injected') for c in observations)>=call_limit:
                code=429;value={'error':{'message':'EXPERIMENT_CALL_LIMIT'}}
            else:
                start=time.monotonic()
                try:
                    response=httpx.post('https://api.deepseek.com/chat/completions',content=body,
                        headers={'Authorization':self.headers.get('Authorization',''),'Content-Type':'application/json'},timeout=180,trust_env=False)
                    code=response.status_code;value=response.json()
                    if tool_evidence is not None:
                        tool_evidence.append({'request':json.loads(body),'response':value})
                    outputs=[c.get('message',{}).get('content') for c in value.get('choices',[]) if c.get('message',{}).get('content')]
                    if outputs:observations_output.extend(outputs)
                    observations.append({'injected':False,'httpStatus':code,'seconds':round(time.monotonic()-start,2),
                        'usage':value.get('usage',{}),'finishReasons':[c.get('finish_reason') for c in value.get('choices',[])]})
                except Exception:
                    code=503;value={'error':{'message':'EXPERIMENT_TRANSPORT_ERROR'}}
                    outputs=[c.get('message',{}).get('content') for c in value.get('choices',[]) if c.get('message',{}).get('content')]
                    if outputs:observations_output.extend(outputs)
                    observations.append({'injected':False,'httpStatus':code,'seconds':round(time.monotonic()-start,2)})
            raw=json.dumps(value).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    selected=copy.deepcopy(profile);selected.update(baseUrl='http://127.0.0.1:'+str(server.server_port),allowPrivateEndpoint=True)
    selected['limits'].update(maxRepairAttempts=5,maxTransportRetries=0,taskTimeoutMs=300000,dailyTokenBudget=None)
    selected['request']['maxOutputTokens']=8192
    try:yield selected
    finally:server.shutdown();server.server_close();thread.join()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--live',action='store_true');parser.add_argument('--configuration-only',action='store_true');parser.add_argument('--result-name',default='ai-rulings-live-results.json');args=parser.parse_args()
    if not re.fullmatch(r'ai-rulings-live-[a-zA-Z0-9-]+\.json',args.result_name):parser.error('invalid result filename')
    if not args.live:parser.error('--live is required for billable API calls')
    path=ROOT/'engineering/ai/config/ai-providers.json';original=path.read_bytes();profile=next(p for p in json.loads(original)['profiles'] if p['profileId']=='deepseek-main')
    assert profile['enabled']
    output=PACK/'tests/output'/('ai-rulings-live-'+secrets.token_hex(4));output.mkdir(parents=True)
    model_outputs=[]
    report={'checkedAt':datetime.now().astimezone().isoformat(),'model':profile['model'],'realSaveChanged':False,
        'evidenceDirectory':str(output.relative_to(PACK)).replace('\\','/'),'calls':[],'cases':[],'passed':False}
    try:
        with observed_provider(profile,report['calls'],model_outputs) as selected:
            config=output/'ai-providers.json';write_json(config,{'schemaVersion':1,'profiles':[selected]})
            with running('ai-rulings-live',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
                kp,_,_=provision(runtime,password)
                result(ai(kp,'ai.settings.update',{'enabled':True,'profileId':selected['profileId'],'externalSources':{'public':True,'kp':True,'private':True},'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}))
                def session(title):return result(ai(kp,'ai.session.create',{'title':title}))['sessionId']
                def ask(sid,text,case):
                    start=time.monotonic();submitted=result(ai(kp,'ai.session.submit',{'sessionId':sid,'text':text}))
                    if not submitted.get('taskId'):result(ai(kp,'ai.request.dispatch',{'requestId':submitted['requestId']}))
                    print(json.dumps({'case':case,'status':'dispatched'},ensure_ascii=False),flush=True)
                    deadline=start+320
                    while time.monotonic()<deadline:
                        item=kp.request('/api/v1/ai/sessions/'+sid)['items'][-1]
                        if item['status'] not in ('received','queued','generating','validating'):break
                        time.sleep(1)
                    row={'id':case,'prompt':text,'seconds':round(time.monotonic()-start,2),'task':item,'passed':False}
                    report['cases'].append(row);write_json(output/'progress.json',report)
                    print(json.dumps({'case':case,'status':item['status'],'seconds':row['seconds']},ensure_ascii=False),flush=True)
                    return row
                if not args.configuration_only:
                    row=ask(session('格式修正实测'),'请用一句简短的话介绍你能怎样帮助 KP，不需要读取资料。','R9')
                    row['passed']=row['task']['status']=='review_ready' and any(c.get('injected') for c in report['calls'])
                    sid=session('NPC 决策与执行实测')
                    row=ask(sid,'想给庭院增加一个 NPC，但友好向导还是敌对守卫我还没决定。请先问我并提供选项，不要代替我选择，也先不要提交修改。','R4-live')
                    row['passed']=row['task']['status']=='needs_input' and bool(row['task'].get('choices'))
                    row=ask(sid,'选友好向导，名称为实验向导，位置为庭院，先仅 KP 可见。沿用现有 NPC 模板默认属性，仅创建一个实例，不增加剧情。方向已确定，请直接提交执行批次。','R5-live')
                    queue=kp.request('/api/v1/ai/rulings')['items'];batch=next((r for r in queue if r['sessionId']==sid and r['kind']=='runtime' and r['status']=='pending'),None)
                    if batch:
                        before=len(report['calls']);a=result(ai(kp,'ai.session.submit',{'sessionId':sid,'text':'批准'}));b=result(ai(kp,'ai.session.submit',{'sessionId':sid,'text':'批准'}))
                        row['decisions']=[a['ruling']['status'],b['ruling']['status']]
                        row['passed']=row['decisions']==['completed','completed'] and len(report['calls'])==before
                        row['instances']=sum(e['name']=='实验向导' for e in kp.request('/api/v1/view')['entities'].values());row['passed'] &= row['instances']==1
                row=ask(session('模板与规则实测'),'请新增独立 NPC 模板 sv.ext.npc.liveguide，完整复制现有 NPC 默认值，仅将生命上限与生命改为 6，增加 isNpc=1。另新增计算规则 sv.ext.live_score，输入 actor，返回力量加意志，KP 专用；每个 Lua 文件只返回一个规则。不要建实例，不要改核心规则。方向已经确定，请提交可供 KP 整批裁决的配置。','R6-live')
                pid=row['task'].get('proposalId');item=next((r for r in kp.request('/api/v1/ai/rulings')['items'] if r['rulingId']=='proposal:'+str(pid)),None)
                if item:
                    row['reports']=[{'level':r['level'],'status':r['status'],'findings':r['findings']} for r in item['reports']]
                    if item['status']=='pending':
                        decision=result(ai(kp,'ai.ruling.decide',{'rulingId':item['rulingId'],'digest':item['digest'],'decision':'approve','riskDecisions':{r['id']:'仅隔离实验：接受报告中的数值影响及覆盖限制' for r in item['risks']}}))
                        row['decision']=decision['status'];row['passed']=decision['status']=='completed'
                report['usage']=kp.request('/api/v1/ai/usage?scope=room')
                report['passed']=all(c['passed'] for c in report['cases'])
    except Exception as exc:
        report['errorType']=type(exc).__name__
        # No exception message: it might contain raw HTTP or credential metadata.
    finally:
        report['persistentProviderConfigUnchanged']=path.read_bytes()==original
        real=[c for c in report['calls'] if not c.get('injected')]
        report['realCalls']=len(real);report['confirmedTokens']=sum(c.get('usage',{}).get('total_tokens',0) for c in real)
        write_json(output/'fixture-model-outputs.json',model_outputs)
        write_json(output/'report.json',report);write_json(PACK/'tests'/args.result_name,report)
        print(json.dumps({k:report.get(k) for k in ('passed','errorType','realCalls','confirmedTokens','evidenceDirectory')},ensure_ascii=False),flush=True)
    return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
