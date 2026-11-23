"""Create one immutable, credential-free AI interface snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser();parser.add_argument('--version',choices=('v1','v2'),required=True);args=parser.parse_args()
target=ROOT/'engineering/acceptance/ai-staged-interface-snapshot'/args.version
assert not target.exists(), 'Never overwrite an already shared snapshot'
for area in ('src','tests','web','scripts','examples'):
    shutil.copytree(ROOT/'engineering/ai'/area,target/'engineering/ai'/area,
        ignore=shutil.ignore_patterns('__pycache__','.pytest_cache','output'))
for name in ('ai.json','ai-operations.json'):
    destination=target/'engineering/contracts'/name;destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'engineering/contracts'/name,destination)
files={p.relative_to(target).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.rglob('*')) if p.is_file()}
summary={'files':files,'fileCount':len(files),'filesDigest':hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
(target/'source.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
print(json.dumps({'path':str(target),'fileCount':len(files),'filesDigest':summary['filesDigest']}))
