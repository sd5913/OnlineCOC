"""Zero-API independent replay of exact saved model outputs in copied stores."""
import copy
import json
import runpy
import shutil
import time
import traceback
from pathlib import Path
from valid_cases import HERE,ROOT,application,close,session,submit,command,committed,Context,DataQueryService,NAMES,data_edits,digest
from onlinecoc_ai.answers import parse_answer
from coordinator_live import approve,business
from bounded_provider import save


def query(app,case,message):
    function=message['tool_calls'][0]['function'];args=json.loads(function['arguments']);name=function['name']
    if case.get('knowledgeFixture'):
        example=runpy.run_path(str(ROOT/'engineering/ai/examples/knowledge-investigation.py'));example['install'](app.host)
        return app.host.knowledge.search('player1',args,player=True) if name=='room_search_knowledge' else app.host.knowledge.read('player1',args,player=True)
    if name in NAMES:return DataQueryService(app.host).execute('kp',NAMES[name],args,initiator='kp',read_scope='kp-room')
    if name=='room_read_sessions':return app.sessions.get('kp',args['sessionId'])
    if name=='room_manage_catalog':return app.batches.catalog_query('kp',args.get('operations'))
    if name=='room_read_management':return app.batches.read('kp',**args)
    s=session(app);r=submit(app,s);snapshot,payload=Context(app.proposals).capture('kp',app.repository.state()['requests'][r['requestId']])
    if name=='pack_read_config_data':return data_edits.read(app,'kp',snapshot,args,{})
    return payload if name=='room_read_context' else payload['pack']


def replay(case,attempt,work):
    row={'caseId':case['caseId'],'category':case['category'],'attemptId':attempt['attemptId'],'strictEvaluation':attempt['evaluation']};app=None
    try:
        path=work/case['caseId'].replace(':','-');shutil.copytree(HERE/case['fixturePath'],path)
        app=application(path,HERE/case['packPath'],fresh=False);before=business(app.host)
        if 'tool' in case:
            result=query(app,case,attempt['output']);row.update(status='query_passed',resultDigest=digest(result));return row
        value=parse_answer(attempt['output'].get('content'));row['modelAnswer']=value
        if value['kind'] in ('plan','clarification'):
            row.update(status='no_mutation',businessUnchanged=business(app.host)==before,unsupported=case.get('expectedExecution')=='unsupported');return row
        if value['kind']=='draft':
            delta=value['changeSet']
            if value.get('dataEdits'):
                source=case['replay'];delta,proof=data_edits.compile_edits(delta,value['dataEdits'],source['snapshot'][2],source['editPool'])
                gold,_=data_edits.compile_edits(case['expected']['changeSet'],case['expected']['dataEdits'],source['snapshot'][2],source['editPool'])
                assert delta==gold;row.update(status='data_compile_passed',proof=proof,compiled=delta,publication='not_tested_in_fixture; strict-pack full publication recorded in Coordinator experiment');return row
            p=app.proposals.create('kp',case['request'],delta,summary=value['text']);result=app.proposals.validate('kp',p['proposalId'],p['revision']);row['validation']=result
            if result['proposal']['status']!='review_ready':row.update(status='validation_blocked',businessUnchanged=business(app.host)==before);return row
            item=next(i for i in app.rulings.list('kp')['items'] if i['rulingId']=='proposal:'+p['proposalId'])
            receipt=approve(app,item,'replay:'+case['caseId']);row['receipt']=receipt
            assert committed(receipt)['status']=='completed';row.update(status='publication_committed',idempotentReplay=True,after=business(app.host));return row
        app.batches.validate_actions('kp',value['actions']);pre=app.batches.preflight('kp',value['actions']);row['preflight']=pre
        if pre['status'] in ('blocked','unsupported'):
            row.update(status='preflight_'+pre['status'],businessUnchanged=business(app.host)==before);return row
        # Execute even mismatched outputs only in synthetic stores, and keep the
        # independent semantic failure. Technical commit never changes that flag.
        s=session(app);r=submit(app,s,case['request']);request=app.repository.state()['requests'][r['requestId']];snapshot,_=Context(app.proposals).capture('kp',request)
        bid=app.batches.create('kp',request,value['actions'],value['text'],snapshot[0]);batch=app.repository.state()['settings']['batches'][bid]
        item=next(i for i in app.rulings.list('kp')['items'] if i['rulingId']=='batch:'+bid)
        row['receipt']=approve(app,item,'replay:'+case['caseId']);result=committed(row['receipt'])
        row.update(status='batch_'+result['status'],idempotentReplay=True,after=business(app.host),execution=result.get('execution'))
    except Exception as exc:row.update(status='error',code=getattr(exc,'code',type(exc).__name__),reason=str(exc),traceback=traceback.format_exc())
    finally:
        if app:close(app)
    return row


def main():
    cases=json.loads((HERE/'valid-cases.json').read_text(encoding='utf-8'));ledger=json.loads((HERE/'live-ledger.json').read_text(encoding='utf-8'));attempts={a['caseId']:a for a in ledger['attempts'] if a['stage']=='valid-v3' and a['status']=='completed'}
    run=str(time.time_ns());work=HERE/'work'/('replay-'+run);work.mkdir(parents=True);rows=[];path=HERE/('replay-'+run+'.json')
    for case in cases:
        if case['caseId'] not in attempts:continue
        row=replay(case,attempts[case['caseId']],work);rows.append(row);save(path,{'runId':run,'apiCalls':0,'exactModelOutputUnchanged':True,'cases':rows})
        print(json.dumps({k:row.get(k) for k in ('caseId','status','code','reason')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
