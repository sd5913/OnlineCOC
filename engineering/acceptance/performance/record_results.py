"""Summarize timings and non-private evidence; retain raw samples and failures."""
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def load(name):return json.loads((HERE/name).read_text(encoding='utf-8'))
def percentiles(values):
    values=sorted(values)
    return {'n':len(values),'p50Ms':round(values[math.ceil(len(values)*.5)-1],3),
            'p95Ms':round(values[math.ceil(len(values)*.95)-1],3)}
def visible(samples):
    pending=None;result=[]
    for sample in samples:
        if sample['operation']=='chat.send':pending=sample if not sample.get('error') else None
        elif sample['operation']=='snapshot.after.response' and pending:
            result.append(pending['ms']+sample['ms']);pending=None
    return percentiles(result)
def comparison(before,after):
    rows=[]
    for old,new in zip(load(before)['results'],load(after)['results'],strict=True):
        assert old['pages']==new['pages'] and old['initial']['stateBytes']==new['initial']['stateBytes']
        rows.append({'pages':old['pages'],'initialStateBytes':old['initial']['stateBytes'],
            'historyMessages':old['historyMessages'],'historyReceipts':old['historyReceipts'],
            'throughputBefore':old['requestThroughputPerSecond'],'throughputAfter':new['requestThroughputPerSecond'],
            'before':old['operations'],'after':new['operations'],
            'chatVisibleBefore':visible(old['samples']),'chatVisibleAfter':visible(new['samples']),
            'protocolBefore':old.get('protocol'),'protocolAfter':new.get('protocol'),
            'errorsBefore':len(old['failedOperations']),'errorsAfter':len(new['failedOperations'])})
    return {'beforeFile':before,'afterFile':after,'cases':rows}
def tests(name):
    cases=list(ET.parse(HERE/name).getroot().iter('testcase'))
    failed=sum(c.find('failure') is not None or c.find('error') is not None for c in cases)
    skipped=sum(c.find('skipped') is not None for c in cases)
    return {'file':name,'tests':len(cases),'passed':len(cases)-failed-skipped,'failed':failed,'skipped':skipped}
sources=['engineering/backend/src/onlinecoc/host.py','engineering/backend/src/onlinecoc/contracts.py',
         'engineering/backend/src/onlinecoc/server.py','engineering/data-management/onlinecoc_data/store.py',
         'docs/current/engineering/first-test.md']
checks=[tests(name) for name in ('core.xml','boundaries.xml','regression.xml')]
identifiers={(case.get('classname'),case.get('name')) for name in ('core.xml','boundaries.xml','regression.xml')
             for case in ET.parse(HERE/name).getroot().iter('testcase')}
new_files=sorted(str(p.relative_to(ROOT)).replace('\\','/') for p in HERE.iterdir() if p.is_file())
output='engineering/acceptance/performance/results.json'
if output not in new_files:new_files.append(output);new_files.sort()
result={'createdAt':datetime.now().astimezone().isoformat(),'scope':'engine-only isolated Host/Uvicorn/SDK/Edge workloads; no package proxy or AI runtime',
        'comparisons':[comparison('baseline.json','optimized.json'),comparison('current-scale-baseline.json','current-scale-optimized.json')],
        'checks':checks,'passed':sum(r['passed'] for r in checks),'failed':sum(r['failed'] for r in checks),
        'uniqueTestCases':len(identifiers),
        'initialBoundaryFailure':tests('boundaries-initial.xml'),
        'initialBoundaryReason':'Test expected a trailing slash for additionalProperties error at the message object; assertion corrected, implementation unchanged.',
        'initialFixtureFailures':'initial-fixture-failure.json',
        'semanticsPreserved':['canonical generation bytes','fsync and atomic publication','fresh quota accounting','CAS and writer lock','receipt deduplication','all cross-record chat checks','live permission checks before snapshot.end','fresh isolated Lua processes'],
        'limitations':['Synthetic fixtures approximate counts/bytes, not the exact production record distribution. No production room opened.',
                       'Eight rounds/page; p95 is descriptive, not a service-level guarantee. Other development processes share this machine.',
                       'Fresh Lua process startup and room execution lock still affect mixed-load read tail latency; not all p95 values improved.',
                       'Snapshot reset and client.connected waits do not imply socket disconnect; current-scale runs count them separately.',
                       'Chat visibility includes the existing approximately 250ms snapshot polling cadence.'],
        'productionRoomTouched':False,'productionProcessChanged':False,'modelCalls':0,
        'modifiedFiles':sources,'newFiles':new_files,
        'sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources}}
(HERE/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'passed':result['passed'],'failed':result['failed'],'newFiles':len(new_files)},ensure_ascii=False))
