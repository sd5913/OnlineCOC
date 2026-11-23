"""Immutable overlay on the last staged-configuration AI snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser();parser.add_argument('--version',required=True);args=parser.parse_args()
assert args.version in ('v1','v2','v3')
base=ROOT/'engineering/acceptance/ai-staged-interface-snapshot/v2'
target=ROOT/'engineering/acceptance/ai-ambiguity-interface-snapshot'/args.version
assert not target.exists(),'Never overwrite a shared snapshot'
files={}
for group in ('src','tests','web','scripts','examples'):
    for p in sorted((ROOT/'engineering/ai'/group).rglob('*')):
        if not p.is_file() or any(x in p.parts for x in ('__pycache__','.pytest_cache','output')):continue
        relative=p.relative_to(ROOT);old=base/relative
        if old.is_file() and old.read_bytes()==p.read_bytes():continue
        out=target/relative;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,out)
        files[relative.as_posix()]=hashlib.sha256(out.read_bytes()).hexdigest()
summary={'kind':'overlay','base':'engineering/acceptance/ai-staged-interface-snapshot/v2',
    'baseFilesDigest':json.loads((base/'source.json').read_text())['filesDigest'],
    'files':files,'fileCount':len(files),'removedFiles':[],
    'filesDigest':hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
(target/'source.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'path':str(target),'fileCount':len(files),'filesDigest':summary['filesDigest'],'files':list(files)}))
