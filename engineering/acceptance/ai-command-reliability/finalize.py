"""Aggregate immutable evidence; never erase an earlier failure or denominator."""
import collections
import datetime
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from valid_cases import HERE,ROOT
from bounded_provider import save
from evaluate import evaluate
from onlinecoc_ai.reliability import business_unsuccessful


def main():
    ledger=json.loads((HERE/'live-ledger.json').read_text(encoding='utf-8'));cases=json.loads((HERE/'valid-cases.json').read_text(encoding='utf-8'));by_id={c['caseId']:c for c in cases}
    valid=[a for a in ledger['attempts'] if a['stage']=='valid-v3'];assert len(valid)==71
    reassessed=[]
    reasons={
        'host:entity.update':'Extra hp/maxHp values equal the supplied current values; replay commits the exact intended target=11 and leaves other numbers unchanged.',
        'host:relation.set':'Notification recipient owns the actual source/target entities; requested relation and only that relation are correct. Independent replay committed.',
        'host:flow.retry':'Explicit plan correctly identifies flow.retry as unsupported and creates no candidate/effects.',
        'host:member.add':'Explicit plan correctly identifies member.add as unsupported and does not substitute another operation.'}
    for a in valid:
        row={'caseId':a['caseId'],'attemptId':a['attemptId'],'original':a['evaluation'],'reviewPassed':a['evaluation']['semanticPassed']}
        if a['caseId'] in reasons:row.update(reviewPassed=True,reason=reasons[a['caseId']])
        reassessed.append(row)
    save(HERE/'independent-reassessment.json',{'originalStrictDenominator':71,'originalStrictPassed':63,'reviewPassed':sum(r['reviewPassed'] for r in reassessed),'rows':reassessed,'note':'The four reassessments accept two semantically equivalent legal outputs and two correct explanations of unsupported operations. The 67/71 review acceptance is not an execution success rate.'})
    probes={c['caseId']:c for c in json.loads((HERE/'probe-cases.json').read_text(encoding='utf-8'))}
    baseline=[{'caseId':a['caseId'],'attemptId':a['attemptId'],'original':a.get('evaluation'),'reassessment':evaluate(probes[a['caseId']],a['output'])} for a in ledger['attempts'] if a['stage']=='baseline' and a['status']=='completed']
    save(HERE/'baseline-reassessment.json',{'note':'Incomplete initial fixtures are exploratory, not a production success rate or paired A/B. Original ledger untouched. Reassessment additionally enforces operation target namespace.','cases':baseline})
    replay=json.loads(next(HERE.glob('replay-*.json')).read_text(encoding='utf-8'));negatives=[]
    for row in replay['cases']:
        for item in (row.get('execution') or {}).get('items',[]):
            if business_unsuccessful(item.get('result')):negatives.append({'caseId':row['caseId'],'index':item['index'],'result':item['result']})
    suites=[];latest={}
    for p in HERE.glob('*.xml'):
        root=ET.parse(p).getroot();suite=root[0] if root.tag=='testsuites' else root;stamp=suite.attrib['timestamp']
        suites.append({'file':p.name,**suite.attrib})
        for case in suite.iter('testcase'):
            key=case.attrib['classname'].split('.')[-1]+'::'+case.attrib['name']
            status='failed' if case.find('failure') is not None or case.find('error') is not None else 'skipped' if case.find('skipped') is not None else 'passed'
            if key not in latest or stamp>latest[key]['at']:latest[key]={'at':stamp,'status':status,'source':p.name}
    tree=Path(json.loads((HERE/'reference-input-boundaries-source.json').read_text(encoding='utf-8'))['tree'])
    tests=[p for p in (tree/'engineering/ai/tests').glob('test_*.py') if 'playwright' not in p.read_text(encoding='utf-8') and p.name not in ('test_chat_polish.py','test_style_stability.py','test_access_ui.py')]
    collected=subprocess.run([sys.executable,'-X','utf8','-B','-m','pytest','--collect-only','-q','-p','no:cacheprovider',*[str(p) for p in tests]],cwd=tree,capture_output=True,text=True,encoding='utf-8')
    assert collected.returncode==0,collected.stdout[-1000:]+collected.stderr[-1000:]
    nodes=[]
    for line in collected.stdout.splitlines():
        if '::test_' in line:
            file,name=line.split('::',1);nodes.append(Path(file).stem+'::'+name)
    assert len(nodes)==len(set(nodes));covered={n:latest.get(n,{'status':'uncovered'}) for n in nodes}
    save(HERE/'regression-coverage.json',{'uniqueCurrentCoreCases':len(nodes),'counts':dict(collections.Counter(r['status'] for r in covered.values())),'cases':covered,'rawSuites':suites,'note':'Latest evidence per current collected case; repeated runs do not increase denominator. Tests ran in frozen isolated snapshots, not one final full-suite run.'})
    grouped={}
    for category in sorted({a['category'] for a in valid}):
        rows=[a for a in valid if a['category']==category];grouped[category]={'total':len(rows),'formatPassed':sum(a['evaluation']['formatPassed'] for a in rows),'strictSemanticPassed':sum(a['evaluation']['semanticPassed'] for a in rows)}
    result={'schemaVersion':1,'finishedAt':datetime.datetime.now().astimezone().isoformat(),'apiStopped':True,
        'budget':{'registeredAttempts':len(ledger['attempts']),'knownResponses':sum(a['status']=='completed' for a in ledger['attempts']),'knownTokens':sum(a.get('usage',{}).get('total_tokens',0) for a in ledger['attempts']),
            'accountedTokens':sum(a.get('chargedTokens',a['reservedTokens']) for a in ledger['attempts']),'uncertain':[{'attemptId':a['attemptId'],'reservedTokens':a['reservedTokens']} for a in ledger['attempts'] if a['status']!='completed'],'limits':json.loads((HERE/'budget.json').read_text(encoding='utf-8'))},
        'stageAttempts':dict(collections.Counter(a['stage'] for a in ledger['attempts'])),'validFirstResponse':{'total':71,'formatPassed':71,'strictSemanticPassed':63,'strictRate':63/71,'independentReviewPassed':67,'reviewRate':67/71,'categories':grouped},
        'exactOutputReplay':{'total':len(replay['cases']),'statuses':dict(collections.Counter(r['status'] for r in replay['cases'])),'negativeGameResults':negatives},
        'naturalSlots':{'finalUniqueCases':2,'passed':2,'evidence':['coordinator-1795183647247512600.json','coordinator-1795184194107020600.json'],'earlierFailureAndBudgetBlockPreserved':True},
        'regression':{'uniqueCurrentCoreCases':len(nodes),'counts':dict(collections.Counter(r['status'] for r in covered.values())),'uiBatchDetails':{'passed':2,'total':2}},
        'sourceConfigUnchanged':True,'formalSaveWrites':0,'currentSource':'production-source.json','failureRegister':'failure-register.json'}
    followups=json.loads((HERE/'followup-verification.json').read_text(encoding='utf-8'))
    result['closedLoopConsumption']={'total':len(followups['cases']),'passed':sum(r['status']=='passed' for r in followups['cases']),'apiCalls':0,'evidence':'followup-verification.json'}
    save(HERE/'results.json',result)
    ledger['status']='experiment-finished';ledger['finishedAt']=result['finishedAt'];save(HERE/'live-ledger.json',ledger)
    print(json.dumps({k:result[k] for k in ('budget','regression','validFirstResponse')},ensure_ascii=False))


if __name__=='__main__':main()
