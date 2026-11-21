"""Summarize distinct final tests, raw attempts and exact source hashes."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).parent
ROOT=HERE.parents[2]
FINAL=('history-cache.xml','cache-regression.xml')


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def save(name,value):(HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    attempts=[];unique={}
    for path in sorted(HERE.glob('*.xml')):
        rows=ET.parse(path).findall('.//testcase');failed=[]
        for row in rows:
            key=row.attrib.get('classname','')+'::'+row.attrib['name']
            error=row.find('failure');error=error if error is not None else row.find('error')
            status='failed' if error is not None else 'skipped' if row.find('skipped') is not None else 'passed'
            if status=='failed':failed.append({'test':key,'reason':error.attrib.get('message','')[:500]})
        attempts.append({'file':path.name,'tests':len(rows),'failures':failed,'passed':len(rows)-len(failed)})
    for name in FINAL:
        path=HERE/name
        if not path.exists():continue
        for row in ET.parse(path).findall('.//testcase'):
            unique[row.attrib.get('classname','')+'::'+row.attrib['name']]='failed' if row.find('failure') is not None or row.find('error') is not None else 'skipped' if row.find('skipped') is not None else 'passed'
    measured={}
    for name in ('baseline','optimized','optimized-final','history-performance-before','history-performance'):
        path=HERE/(name+'.json')
        if path.exists():measured[name]=read(path)
    changes={}
    baseline=read(HERE/'baseline-source.json')
    # Original hash manifest may contain metadata around its files mapping.
    source=baseline.get('files',baseline.get('sourceHashes',baseline))
    for name,expected in source.items():
        if not isinstance(expected,str):continue
        path=ROOT/name
        if path.is_file():
            actual=hashlib.sha256(path.read_bytes()).hexdigest()
            if actual!=expected:changes[name]={'before':expected,'after':actual}
    files=[*sorted((ROOT/'engineering/ai/src').rglob('*.py')),*sorted((ROOT/'engineering/ai/web').rglob('*.js')),
        ROOT/'engineering/ai/web/components/chat.css',ROOT/'engineering/ai/web/components/index.d.ts',
        *[ROOT/'engineering/ai/tests'/name for name in ('test_generation_snapshot.py','test_progress_ui.py','test_history_continuity.py')]]
    hashes={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    result={'finalEvidence':list(FINAL),'finalUniqueTests':len(unique),'passed':sum(v=='passed' for v in unique.values()),
        'failed':sum(v=='failed' for v in unique.values()),'skipped':sum(v=='skipped' for v in unique.values()),
        'cases':unique,'attempts':attempts,'performance':measured,'sourceChanges':changes,'sourceHashes':hashes,
        'live':read(HERE/'live-results.json'),'preflight':read(HERE/'live-preflight.json'),'storage':read(HERE/'storage-growth.json')}
    save('results.json',result)
    files=[p for p in HERE.iterdir() if p.is_file() and p.name!='manifest.json']
    save('manifest.json',{'files':[str(p.relative_to(ROOT)).replace('\\','/') for p in sorted(files+[HERE/'manifest.json'])],
        'newSourceFiles':['engineering/ai/src/onlinecoc_ai/generation.py','engineering/ai/tests/test_generation_snapshot.py','engineering/ai/tests/test_progress_ui.py']})
    print(json.dumps({k:result[k] for k in ('finalUniqueTests','passed','failed','skipped')}))


if __name__=='__main__':main()
