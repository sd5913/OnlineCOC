"""Record run denominators and confirm the shared overlay matches current AI."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

base=ROOT/'engineering/acceptance/ai-staged-interface-snapshot/v2'
overlay=ROOT/'engineering/acceptance/ai-ambiguity-interface-snapshot/v2'
declared=json.loads((overlay/'source.json').read_text(encoding='utf-8'))
source_checks={key:sha(overlay/key)==value and sha(ROOT/key)==value for key,value in declared['files'].items()}
all_expected={**json.loads((base/'source.json').read_text(encoding='utf-8'))['files'],**declared['files']}
runtime_checks={key:sha(ROOT/key)==value for key,value in all_expected.items() if key.startswith('engineering/ai/src/')}
results={}
for path in sorted(HERE.glob('*.xml')):
    suites=list(ET.parse(path).getroot().iter('testsuite'))
    counts={key:sum(int(s.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')}
    counts['passed']=counts['tests']-counts['failures']-counts['errors']-counts['skipped']
    counts['passRate']=counts['passed']/counts['tests'] if counts['tests'] else None
    counts['seconds']=sum(float(s.get('time',0)) for s in suites)
    results[path.stem]=counts
verification={'externalApiCalls':0,'kind':'deterministic-synthetic-fixtures','results':results,
    'frozenOverlay':str(overlay.relative_to(ROOT)).replace('\\','/'),'filesDigest':declared['filesDigest'],
    'overlayFilesMatch':all(source_checks.values()),'runtimeMatchesFrozenComposition':all(runtime_checks.values()),
    'runtimeFileCount':len(runtime_checks),'failedFileChecks':[k for k,v in {**runtime_checks,**source_checks}.items() if not v],
    'browserTestsRun':False,'note':'Each run has its own denominator. Intermediate failures are retained; do not sum repeated cases.'}
(HERE/'verification.json').write_text(json.dumps(verification,indent=2)+'\n',encoding='utf-8')
paths=[ROOT/key for key in declared['files']]
paths += [ROOT/'docs/current/engineering'/name for name in ('ai-data-query.md','ai-debug-review.md','ai-responses.md','ai-runtime.md')]
paths += [p for p in HERE.iterdir() if p.is_file() and p.name!='files-manifest.json']
manifest={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(paths))}
(HERE/'files-manifest.json').write_text(json.dumps({'files':manifest,'fileCount':len(manifest)},indent=2)+'\n',encoding='utf-8')
print(json.dumps(verification))
assert verification['overlayFilesMatch'] and verification['runtimeMatchesFrozenComposition']
