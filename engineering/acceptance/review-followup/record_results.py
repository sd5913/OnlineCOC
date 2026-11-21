"""Rebuild the aggregate from retained XML; repeated test IDs count once."""
import hashlib
import json
import ast
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ENGINEERING=HERE.parents[1]
RUNS=['initial','first','queue-first','ui-first','freeze','regression','nodes','nodes-final','nodes-verified','boundaries-initial','boundaries-final','dispatch-final','player-retry-initial','pl-dispatch-initial','pl-final','public-paths']
FINAL=['first','queue-first','ui-first','freeze','regression','nodes-verified','boundaries-final','dispatch-final','pl-final','public-paths']
CAUSES={
 'initial':'33 setup errors: missing parent of pytest basetemp; 1 old assertion expected expanded legacy data, intentionally replaced by compact references.',
 'nodes':'Collection error: standalone fixture used the wrong import root.',
 'nodes-final':'2 fixture failures: mutable alias changed the old artifact. A fresh room snapshot and a separate candidate data copy corrected the fixture.',
 'boundaries-initial':'5 product failures: active generation candidates were archivable (3 states), cancelled requests remained in active queue (2 kinds). One fixture failure used a nonexistent repository.directory attribute.',
 'player-retry-initial':'Product gap: direct player creation button omitted submissionKey after a lost response; retry could create another request. Added stable per-content key and browser regression.',
 'pl-dispatch-initial':'Product regression introduced by dispatch serialization: public player submit already had a repository transaction. Fixed by joining the existing transaction under the same lock, preserving the archive/dispatch barrier.'}
files=[f'src/onlinecoc_ai/{name}.py' for name in ('api','batches','history','known_answers','player_requests','proposals','repository','reviews','review_queue','rulings','sessions')]
files += ['web/components/'+name for name in ('chat.js','rulings.js','tools.js','index.d.ts')]
files += ['tests/'+name for name in ('test_review_followup.py','test_review_followup_ui.py','test_known_answers.py')]


def main():
    runs=[];unique={}
    local_names={}
    for path in HERE.glob('test_*.py'):
        for function in ast.parse(path.read_text(encoding='utf-8')).body:
            if isinstance(function,(ast.FunctionDef,ast.AsyncFunctionDef)) and function.name.startswith('test_'):
                assert function.name not in local_names
                local_names[function.name]=path
    for name in RUNS:
        path=HERE/(name+'.xml')
        if not path.exists():continue
        xml=ET.parse(path).getroot();suites=[xml] if xml.tag=='testsuite' else list(xml.iter('testsuite'))
        counts={key:sum(int(s.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')}
        counts['passed']=counts['tests']-counts['failures']-counts['errors']-counts['skipped']
        runs.append({'file':path.name,**counts,'successRate':round(counts['passed']/counts['tests'],6) if counts['tests'] else None,
            **({'causeAndDisposition':CAUSES[name]} if name in CAUSES else {})})
        if name in FINAL:
            for case in xml.iter('testcase'):
                name=case.get('name','');module=case.get('classname','').rsplit('.',1)[-1]
                path=local_names[name.split('[',1)[0]] if not module else HERE/(module+'.py') if (HERE/(module+'.py')).exists() else ENGINEERING/'ai/tests'/(module+'.py')
                assert path.exists(),path
                key=path.relative_to(ENGINEERING).as_posix()+'::'+name
                status='failed' if case.find('failure') is not None or case.find('error') is not None else 'skipped' if case.find('skipped') is not None else 'passed'
                unique[key]={'id':key,'status':status,'evidence':path.name}
    passed=sum(c['status']=='passed' for c in unique.values())
    result={'schemaVersion':1,'date':'2026-11-20','scope':'ISSUE-017 AI history, queue organization, compact known references',
        'externalModelCalls':0,'billedTokens':0,'runs':runs,'uniqueLatest':{'passed':passed,'total':len(unique),'successRate':passed/len(unique) if unique else None},
        'cases':sorted(unique.values(),key=lambda x:x['id']),
        'sources':{str((Path('engineering/ai')/name).as_posix()):hashlib.sha256((ENGINEERING/'ai'/name).read_bytes()).hexdigest() for name in files},
        'acceptanceSources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted([*HERE.glob('test_*.py'),HERE/'record_results.py'])},
        'limits':['Deterministic provider fixtures and real local hosts/browsers; this is not a paid model success rate.',
                  'Package integration and engine schema runs are recorded separately and not added to the unique AI count.',
                  'Historical permission revocation, deleted objects and unprovable legacy searches remain hidden. No formal room was migrated or modified.']}
    (HERE/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result['uniqueLatest']))


if __name__=='__main__':main()
