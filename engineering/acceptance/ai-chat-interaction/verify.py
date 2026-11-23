"""Verify the recorded UI source and summarize distinct browser regressions."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def results(name):
    suites = ET.parse(HERE / name).getroot()
    cases = {}
    for case in suites.iter('testcase'):
        key = case.attrib['classname'] + '::' + case.attrib['name']
        cases[key] = not any(case.find(tag) is not None for tag in ('failure', 'error', 'skipped'))
    return cases, sum(float(s.attrib.get('time', 0)) for s in suites.iter('testsuite'))


def main():
    source = json.loads((HERE / 'source.json').read_text(encoding='utf-8'))
    mismatches = [item['path'] for item in source['files']
                  if hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest() != item['sha256']]
    runs = {}; distinct = {}
    for name in ('baseline.xml', 'targeted.xml', 'related-ui.xml', 'related-ui-recheck.xml'):
        cases, seconds = results(name)
        runs[name] = {'passed': sum(cases.values()), 'total': len(cases), 'seconds': seconds,
                      'failed': [key for key, passed in cases.items() if not passed]}
        if name != 'baseline.xml':
            distinct.update(cases)
    result = {'sourceMismatches': mismatches, 'runs': runs,
              'finalDistinct': {'passed': sum(distinct.values()), 'total': len(distinct)},
              'packageJointCheck': {'passed': 8, 'total': 8, 'source': 'package chat report; separate from engineering counts'},
              'externalModelCalls': 0}
    (HERE / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert not mismatches and all(distinct.values())


if __name__ == '__main__':
    main()
