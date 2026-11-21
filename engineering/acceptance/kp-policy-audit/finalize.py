from pathlib import Path
import hashlib,json,re,xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def stats(name):
 s=ET.parse(HERE/name).getroot().find('testsuite')
 return {k:int(s.attrib[k]) for k in ('tests','failures','errors','skipped')}
final=stats('official.xml');assert final['failures']==final['errors']==0
files=['engineering/backend/src/onlinecoc/publication.py','engineering/contracts/models.json','engineering/contracts/operations.json']
hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files}
source=json.loads((HERE/'source.json').read_text())
assert all(source[name]==value for name,value in hashes.items())
for name in ('README.md','../../../docs/current/engineering/high-risk-publication.md'):
 p=(HERE/name).resolve()
 for link in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
  if '://' not in link:assert (p.parent/link.split('#')[0]).exists(),(p,link)
out={'scope':'ISSUE-023 KP consultation acceptance host boundary','productionHashes':hashes,'final':final,
 'previousRuns':{'first-field-error.xml':stats('first-field-error.xml'),'parameter-expectation.xml':stats('parameter-expectation.xml')},
 'apiCalls':0,'formalRoomTouched':False,'gitOperations':False,'aiContracts':'engineering/acceptance/ai-compression-interface-snapshot/contracts-v1',
 'interfaceSnapshot':'engineering/acceptance/engine-kp-policy-interface-snapshot/v1',
 'remainingIntegration':'AI current runtime and package UI joint testing are owned by coordinator; host uses formal released AI contracts'}
(HERE/'results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
new=[p.relative_to(ROOT).as_posix() for p in HERE.iterdir() if p.is_file()]
new+=['engineering/acceptance/kp-policy-audit/new-files.json','engineering/acceptance/kp-policy-audit/work/',
 'engineering/acceptance/engine-kp-policy-interface-snapshot/.gitignore',
 'engineering/acceptance/engine-kp-policy-interface-snapshot/v1/source.json','engineering/acceptance/engine-kp-policy-interface-snapshot/v1/engineering/']
(HERE/'new-files.json').write_text(json.dumps(sorted(set(new)),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'final':final,'newFiles':len(set(new)),'sourceMatch':True}))
