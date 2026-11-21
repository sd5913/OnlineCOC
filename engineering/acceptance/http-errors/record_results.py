"""Record only test totals, source digests and project-relative artifact paths."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def report(name):
    cases = list(ET.parse(HERE / name).getroot().iter('testcase'))
    failed = sum(case.find('failure') is not None or case.find('error') is not None for case in cases)
    skipped = sum(case.find('skipped') is not None for case in cases)
    return {'file': str((HERE / name).relative_to(ROOT)).replace('\\', '/'),
            'tests': len(cases), 'passed': len(cases) - failed - skipped, 'failed': failed, 'skipped': skipped}


sources = ['engineering/client-sdk/client.js', 'engineering/backend/src/onlinecoc/ai_api.py',
           'engineering/backend/src/onlinecoc/server.py', 'engineering/contracts/messages.json',
           'docs/current/engineering/first-test.md']
new_files = sorted(str(p.relative_to(ROOT)).replace('\\', '/') for p in HERE.iterdir() if p.is_file())
output = 'engineering/acceptance/http-errors/repair-results.json'
if output not in new_files:
    new_files.append(output)
    new_files.sort()
data = {'createdAt': datetime.now().astimezone().isoformat(),
        'scope': 'SDK error classification and two AI HTTP delivered=True call sites',
        'finalSdkTests': [report('sdk-retest.xml'), report('sdk-regression.xml')],
        'preservedInitialFailure': report('sdk-initial.xml'),
        'initialFailureReason': 'Test probe route was appended after root StaticFiles mount; fixed fixture route ordering.',
        'preservedAudit': {'summary': 'engineering/acceptance/http-errors/results.json', 'httpTests': 4},
        'aiDeliveryIntegrationOwner': 'AI module thread; evidence in engineering/acceptance/message-history/',
        'serverErrorEnvelopeChanged': False, 'automaticRetryAdded': False,
        'productionRoomAccessed': False, 'productionProcessChanged': False, 'modelCalls': 0,
        'actualScreenshotFailureReproduced': False,
        'modifiedSources': sources[:2] + [sources[-1]], 'newFiles': new_files,
        'hierarchyOwner': 'Stumpsville coordinator',
        'sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources}}
(HERE / 'repair-results.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'sdkTests': sum(r['tests'] for r in data['finalSdkTests']),
                  'failures': sum(r['failed'] for r in data['finalSdkTests']), 'newFiles': len(new_files)}, ensure_ascii=False))
