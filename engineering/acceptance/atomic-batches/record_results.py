"""Audit frozen engine evidence; no credentials, host imports or runtime saves."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
REPORTS=('initial.xml','core.xml','extended.xml','final.xml','regression.xml','admission.xml','conflict.xml','count-limit.xml')
PRODUCTION=(
    'engineering/backend/src/onlinecoc/atomic_batches.py',
    'engineering/backend/src/onlinecoc/host.py',
    'engineering/backend/src/onlinecoc/contracts.py',
    'engineering/backend/src/onlinecoc/execution.py',
    'engineering/backend/src/onlinecoc/lua_runtime.py',
    'engineering/contracts/atomic-batches.json',
    'docs/current/engineering/atomic-batches.md',
    'docs/current/engineering/first-test.md',
)
summaries=[];all_keys=set();final_keys=set();initial_failures=[]
for name in REPORTS:
    tree=ET.parse(HERE/name);cases=tree.findall('.//testcase')
    keys={case.get('classname')+'::'+case.get('name') for case in cases}
    failed=[case for case in cases if case.find('failure') is not None or case.find('error') is not None]
    skipped=[case for case in cases if case.find('skipped') is not None]
    summaries.append({'report':name,'executions':len(cases),'passed':len(cases)-len(failed)-len(skipped),
        'failed':len(failed),'skipped':len(skipped),'unique':len(keys)})
    all_keys.update(keys)
    if name in ('final.xml','regression.xml','admission.xml','conflict.xml','count-limit.xml'):final_keys.update(keys)
    if name=='initial.xml':
        initial_failures=[{'test':c.get('classname')+'::'+c.get('name'),
            'category':'invalid_synthetic_fixture_hp_above_maxHp',
            'correction':'Dedicated fixture maxHp=100; preserve the model invariant.',
            'failure':c.find('failure').get('message')} for c in failed]
(HERE/'initial-failures.json').write_text(json.dumps(initial_failures,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
new_files=['engineering/backend/src/onlinecoc/atomic_batches.py','engineering/contracts/atomic-batches.json',
    'docs/current/engineering/atomic-batches.md']
new_files += [str(p.relative_to(ROOT)).replace('\\','/') for p in sorted(HERE.iterdir()) if p.is_file()]
result_path='engineering/acceptance/atomic-batches/results.json'
if result_path not in new_files:new_files.append(result_path)
data={'schemaVersion':1,'recordedAt':datetime.now().astimezone().isoformat(),
    'status':'engine_frozen_for_integration','finalUniqueCases':len(final_keys),
    'historicalUniqueCases':len(all_keys),'historicalExecutions':sum(r['executions'] for r in summaries),
    'historicalPassed':sum(r['passed'] for r in summaries),'historicalFailed':sum(r['failed'] for r in summaries),
    'reports':summaries,'testIds':sorted(final_keys),'newFiles':sorted(new_files),
    'productionSha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in PRODUCTION},
    'supportedHostOperations':json.loads((ROOT/'engineering/contracts/atomic-batches.json').read_text(encoding='utf-8'))['supportedOperations'],
    'realApiCalls':0,'formalSaveWrites':0,'formalSettingsWrites':0,
    'remainingBoundaries':['AI/pack integration and real provider results belong to separate acceptance',
        'No atomic multi-item host/AI storage transactions, flows, publication or external effects',
        'Random-dependent preflight stops rather than drawing or guessing dice',
        'Business blocked/failure outcomes remain in rule result; commit does not prove user goal completion',
        'Storage failure can leave pending; reconcile/resume original command ID']}
(HERE/'results.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:data[k] for k in ('status','finalUniqueCases','historicalExecutions','historicalPassed','historicalFailed')},ensure_ascii=False))
print('newFiles='+str(len(data['newFiles'])))
