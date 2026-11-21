from pathlib import Path
import hashlib
import json
import shutil
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
target=ROOT/'engineering/acceptance/engine-accounts-interface-snapshot'/sys.argv[1]
target.mkdir(parents=True,exist_ok=False)
shutil.copytree(HERE/'work/engine/engineering',target/'engineering',ignore=shutil.ignore_patterns('__pycache__','*.pyc','.pytest_cache'))
source=json.loads((HERE/'source.json').read_text())
source['checkpointFiles']={str(p.relative_to(target)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted(target.rglob('*')) if p.is_file()}
(target/'source.json').write_text(json.dumps(source,indent=2),encoding='utf-8')
if not (target.parent/'.gitignore').exists():
    (target.parent/'.gitignore').write_text('v*/engineering/\n',encoding='utf-8')
print(json.dumps({'checkpoint':str(target),'files':len(source['checkpointFiles'])}))
