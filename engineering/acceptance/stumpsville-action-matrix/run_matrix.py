"""Real Host/FileDataStore/Lua matrix with a fixture-only controlled dice port."""
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
ENGINEERING=ROOT/'engineering'
sys.path[:0]=[str(ENGINEERING/'backend/src'),str(ENGINEERING/'data-management')]
from onlinecoc.host import Host
from onlinecoc.model import entity
from onlinecoc.registry import stage
from onlinecoc_data import canonical


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def subset(actual,expected,path='result'):
    if isinstance(expected,dict):
        assert isinstance(actual,dict),(path,type(actual))
        for key,value in expected.items():
            assert key in actual,(path,key)
            subset(actual[key],value,path+'.'+key)
    else:assert type(actual)==type(expected) and actual==expected,(path,actual,expected)


def fixture(host,case,configurations,artifact):
    state=host.state();state['entities']={};state['relations']={};state['progress']={}
    used={row['configurationId'] for row in case['stateSpec']['entities']}
    state['configurations']={key:copy.deepcopy(configurations[key]) for key in used}
    for row in case['stateSpec']['entities']:
        conf=configurations[row['configurationId']]
        value=entity(row['id'],conf['typeRef'],'Synthetic '+row['id'],row['owner'],**{**conf['defaults'],**row['numbers']})
        value.update(configurationId=conf['configurationId'],configurationRevision=conf['revision'],visibility=row['visibility'])
        state['entities'][row['id']]=value
    for index,row in enumerate(case['stateSpec']['relations']):
        rid='fixture-relation-'+str(index)
        state['relations'][rid]={'relationId':rid,'revision':1,'tags':[],'metadata':{},**row}
    state['artifacts']={artifact['revision']:copy.deepcopy(artifact)};state['activeRuleset']=artifact['revision']
    host.commit(state)
    return state


def business(state):return {k:v for k,v in state.items() if k!='commands'}
def expected_entities(before,case):
    result=copy.deepcopy(before['entities'])
    for key,changes in case['oracle']['numberUpdates'].items():
        result[key]['numbers'].update(changes)
    for key,row in result.items():
        if row['numbers']!=before['entities'][key]['numbers']:row['revision']+=1
    return result


def main():
    document=json.loads((HERE/'cases.json').read_text(encoding='utf-8'))
    cases=document['cases'];configs={c['configurationId']:c for c in document['configurations']}
    assert len({c['caseId'] for c in cases})==len(cases)
    pack=ROOT/'rulepacks/stumpsville'
    sources={p.name:p.read_text(encoding='utf-8') for p in sorted((pack/'rules').glob('*.lua'))}
    data={p.name:json.loads(p.read_text(encoding='utf-8')) for p in (pack/'config').glob('*.json') if p.name!='configurations.json'}
    watched=list((pack/'rules').glob('*.lua'))+list((pack/'config').glob('*.json'))
    watched+=list((ENGINEERING/'backend/src').rglob('*.py'))+list((ENGINEERING/'contracts').glob('*.json'))
    before_hashes={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in watched}
    artifact=stage(sources,data)
    public={key for key,value in artifact['metadata'].items() if value['public']}
    positive={case['actionId'] for case in cases if case['category']=='positive'}
    assert len(public)==17 and public==positive,{'public':sorted(public),'positive':sorted(positive)}
    write(HERE/'catalog.json',{'artifactRevision':artifact['revision'],'publicActionIds':sorted(public),
        'actions':[artifact['metadata'][key] for key in sorted(public)],'sourceSha256':before_hashes})
    runs=HERE/'runs';runs.mkdir(exist_ok=True)
    number=max([int(p.stem.split('-')[-1]) for p in runs.glob('run-*.json')]+[0])+1
    run_id=f'run-{number:03d}';work=HERE/'work-tmp'/run_id;work.mkdir(parents=True,exist_ok=False)
    result={'schemaVersion':1,'runId':run_id,'startedAt':datetime.now().astimezone().isoformat(),
        'realApiCalls':0,'formalSaveWrites':0,'productionChanges':False,'artifactRevision':artifact['revision'],
        'catalogCoverage':{'actualPublic':sorted(public),'positiveCases':sorted(positive),'equal':True},'cases':[]}
    prestates={}
    for case in cases:
        started=time.perf_counter();host=None;row={'caseId':case['caseId'],'category':case['category'],'actionId':case['actionId']}
        try:
            host=Host(work/case['caseId'],bootstrap='synthetic-matrix-password')
            before=fixture(host,case,configs,artifact)
            assert {x['id'] for x in host.catalog('kp')['actions']}==public
            prestates[case['caseId']]={key:copy.deepcopy(before[key]) for key in ('roomId','status','members','entities','relations','configurations','progress','collectionRevision')}
            actions=[case['action']];generation=host.store.generation;raw_before=canonical(host.state())
            preflight=host.preflight_batch(case['principal'],actions);row['preflight']=preflight
            assert host.store.generation==generation and canonical(host.state())==raw_before,'Preflight wrote state'
            assert preflight['status']==case['oracle']['preflightStatus'],preflight
            draws=case['randomPolicy']['draws'];calls=[]
            def random(sides):
                index=len(calls)
                assert index<len(draws),('Unexpected random draw',index,sides)
                expected=draws[index];assert expected['sides']==sides,(expected,sides)
                calls.append(copy.deepcopy(expected));return expected['value']-1
            with patch('onlinecoc.atomic_batches.secrets.randbelow',random):
                receipt=host.execute_batch(case['principal'],actions,command_id=case['caseId'])
                row['receipt']=receipt
                assert receipt['status']==case['oracle']['receiptStatus'],receipt
                assert len(calls)==len(draws),('Unused draws',calls,draws)
                after=host.state();row['randomDraws']=calls
                item=receipt['result']['items'][0]
                if case['category']=='technical_rejection':
                    assert receipt['result']['committedCount']==0 and item['status']=='failed',receipt
                    assert item['code']==case['oracle']['itemCode'],item
                    if 'ruleCode' in case['oracle']:assert item['ruleCode']==case['oracle']['ruleCode'],item
                    assert business(after)==business(before),'Technical rejection left business effects'
                else:
                    assert receipt['result']['committedCount']==1 and item['status']=='committed',receipt
                    subset(item['result'],case['oracle']['resultSubset'])
                    assert after['entities']==expected_entities(before,case),'Unexpected entity change'
                    for key in ('relations','progress','configurations','members','flows','waits'):
                        assert after[key]==before[key],('Unexpected collection change',key)
                    assert len(after['audit'])==1 and len(after['outbox'])==1
                g=host.store.generation;saved=canonical(after)
                assert host.execute_batch(case['principal'],actions,command_id=case['caseId'])==receipt
                assert host.store.generation==g and canonical(host.state())==saved and len(calls)==len(draws)
            row.update(passed=True,numberStateAfter={key:value['numbers'] for key,value in after['entities'].items()},
                idempotentReplay=True)
        except Exception as error:
            row.update(passed=False,errorType=type(error).__name__,error=str(error),traceback=traceback.format_exc())
        finally:
            if host:host.close()
        row['durationMs']=round((time.perf_counter()-started)*1000,2);result['cases'].append(row)
        print(json.dumps({k:row[k] for k in ('caseId','category','passed','durationMs')},ensure_ascii=False),flush=True)
        write(runs/(run_id+'.json'),result)
    after_hashes={name:sha(ROOT/name) for name in before_hashes}
    result['productionChanges']=before_hashes!=after_hashes
    result['finishedAt']=datetime.now().astimezone().isoformat()
    result['uniqueCases']=len(cases);result['passed']=sum(c['passed'] for c in result['cases'])
    result['failed']=len(cases)-result['passed'];result['skipped']=0
    result['countsByCategory']={key:{'total':sum(c['category']==key for c in result['cases']),
        'passed':sum(c['category']==key and c['passed'] for c in result['cases'])} for key in sorted({c['category'] for c in cases})}
    result['productionSha256']=after_hashes
    write(runs/(run_id+'.json'),result);write(HERE/'prestates.json',prestates)
    result['newFiles']=sorted(str(p.relative_to(ROOT)).replace('\\','/') for p in HERE.rglob('*') if p.is_file()
        and 'work-tmp' not in p.parts and '__pycache__' not in p.parts and p.name!='results.json')
    result['newFiles'].append(str((HERE/'results.json').relative_to(ROOT)).replace('\\','/'))
    write(HERE/'results.json',result)
    print(json.dumps({k:result[k] for k in ('runId','uniqueCases','passed','failed','countsByCategory','productionChanges')},ensure_ascii=False))
    return 0 if result['failed']==0 and not result['productionChanges'] else 1


if __name__=='__main__':raise SystemExit(main())
