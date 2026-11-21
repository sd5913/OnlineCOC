"""Record all runs, unique final outcomes, failure history and source manifests."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
reports=['initial.xml','client.xml','c-first.xml','c-fixed.xml','durability.xml','regression.xml','triage.xml','persisted.xml','final.xml','regression-fixed.xml','network-fixed.xml','c-command.xml','lifecycle-fixed.xml']
latest={};runs=[];failures=[]
for name in reports:
    path=HERE/name
    if not path.exists():continue
    counts={'passed':0,'failed':0,'errors':0,'skipped':0}
    for item in ET.parse(path).iter('testcase'):
        key=item.get('classname','')+'::'+item.get('name','')
        outcome='failed' if item.find('failure') is not None else 'errors' if item.find('error') is not None else 'skipped' if item.find('skipped') is not None else 'passed'
        counts[outcome]+=1;latest[key]={'outcome':outcome,'report':name}
        if outcome in ('failed','errors'):
            error=item.find('failure') if outcome=='failed' else item.find('error')
            failures.append({'report':name,'test':key,'outcome':outcome,'message':error.get('message','')[:1600]})
    runs.append({'report':name,**counts})
source=json.loads((HERE/'source.json').read_text())
source['verifiedUnchanged']=all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha for path,sha in source['sources'].items())
assert source['verifiedUnchanged']
source['aiSnapshotVerifiedUnchanged']=all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha for path,sha in source.get('aiSources',{}).items())
assert source['aiSnapshotVerifiedUnchanged']
new_files=[str(p.relative_to(ROOT)).replace('\\','/') for p in sorted(HERE.iterdir()) if p.is_file()]
new_files.extend(['engineering/backend/src/onlinecoc/local_accounts.py','engineering/backend/src/onlinecoc/host_control_client.py',
    'engineering/acceptance/engine-accounts-interface-snapshot/.gitignore',
    *[f'engineering/acceptance/engine-accounts-interface-snapshot/v{i}/source.json' for i in (1,2,3)]])
for name in ('README.md','results.json','initial-failures.json'):
    path=str((HERE/name).relative_to(ROOT)).replace('\\','/')
    if path not in new_files:new_files.append(path)
result={'date':'2026-11-21','scope':'Host local account transactions, local stdin client and C publication proof gate',
    'runs':runs,'totalExecutions':sum(sum(r[k] for k in ('passed','failed','errors','skipped')) for r in runs),
    'uniqueTests':len(latest),'finalCounts':{k:sum(v['outcome']==k for v in latest.values()) for k in ('passed','failed','errors','skipped')},
    'tests':latest,'source':source,'externalApiCalls':0,'formalDataAccessed':False,'newFiles':sorted(set(new_files)),
    'failureHistoryFile':'initial-failures.json','checkpoint':'../engine-accounts-interface-snapshot/v3/',
    'limitations':['No newly compiled WinForms binary or new native deletion UI; package panel is independently verified by its owner.',
        'C rejection cases intentionally forge trusted resolver reports to test the host boundary; real pass preparation uses Lua fixture execution.',
        'Initial suites used released AI v1; lifecycle and C publication rechecks use released AI v2. Package/model live calls are outside this suite.']}
(HERE/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(HERE/'initial-failures.json').write_text(json.dumps(failures,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:result[k] for k in ('uniqueTests','finalCounts','totalExecutions','externalApiCalls')}))
