from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def read(name):return json.loads((HERE/name).read_text(encoding='utf-8'))
def report(name):
 suite=ET.parse(HERE/name).getroot().find('testsuite')
 return {k:int(suite.attrib[k]) for k in ('tests','failures','errors','skipped')}
changes=['contracts.py','host.py','server.py','ai_api.py','data_queries.py']
hashes={name:hashlib.sha256((ROOT/'engineering/backend/src/onlinecoc'/name).read_bytes()).hexdigest() for name in changes}
frozen=read('after-source.json')
assert all(frozen['engineering/backend/src/onlinecoc/'+name]==value for name,value in hashes.items())
tests={name:report(name) for name in ('initial.xml','cache-fixed.xml','regression.xml')}
assert all(not r['failures'] and not r['errors'] for r in tests.values())
results={name:read(name) for name in ('before.json','after.json','before-control.json','after-control.json')}
assert all(r['chatFailureRate']==0 and r['sequenceUnique'] for r in results.values())
assert results['before.json']['approvalFailureRate']==1
assert all(results[n]['approvalFailureRate']==0 for n in ('after.json','before-control.json','after-control.json'))
summary={name:{k:r[k] for k in ('sendMs','allPagesSyncedMs','chatFailureRate','approvalFailureRate','sequenceUnique')} for name,r in results.items()}
out={'scope':'ISSUE-022 engine chat isolation','apiCalls':0,'syntheticOnly':True,'productionHashes':hashes,
 'tests':tests,'finalUniqueTests':tests['cache-fixed.xml']['tests']+tests['regression.xml']['tests'],
 'passedTestExecutions':sum(r['tests'] for r in tests.values()),
 'benchmarks':summary,'interfaceSnapshot':'engineering/acceptance/engine-chat-interface-snapshot/v2',
 'limitations':['Single-machine synthetic fixture; 30 sends and 4 approvals per run, no WAN claim','Package UI and current AI history integration have separate joint evidence'],
 'firstFailures':'first-failures.json'}
(HERE/'results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
files=[p.relative_to(ROOT).as_posix() for p in HERE.iterdir() if p.is_file()]
files+=['engineering/acceptance/chat-isolation/new-files.json','engineering/acceptance/chat-isolation/work/',
 'engineering/acceptance/engine-chat-interface-snapshot/.gitignore',
 'engineering/acceptance/engine-chat-interface-snapshot/v1/source.json','engineering/acceptance/engine-chat-interface-snapshot/v1/engineering/',
 'engineering/acceptance/engine-chat-interface-snapshot/v2/source.json','engineering/acceptance/engine-chat-interface-snapshot/v2/engineering/',
 'docs/current/engineering/chat-isolation.md']
(HERE/'new-files.json').write_text(json.dumps(sorted(set(files)),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'tests':tests,'files':len(set(files)),'sourceVerified':True}))
