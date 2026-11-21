"""Snapshot current AI and declared engine boundary; keep generated evidence isolated."""
import argparse
import json
import shutil
import subprocess
import sys
import time
import hashlib
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);parser.add_argument('--engine',choices=['baseline','final'],default='final');parser.add_argument('--core',action='store_true');parser.add_argument('tests',nargs='*');args=parser.parse_args()
    target=HERE/'work'/('current-'+args.label+'-'+str(time.time_ns()))
    shutil.copytree(HERE/'work/baseline/engineering',target/'engineering')
    for group in ('src','tests','web','scripts'):
        shutil.copytree(ROOT/'engineering/ai'/group,target/'engineering/ai'/group,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache','output'))
    for name in ('ai.json','ai-operations.json'):shutil.copy2(ROOT/'engineering/contracts'/name,target/'engineering/contracts'/name)
    if args.engine=='final':
        shutil.copytree(ROOT/'engineering/backend/src',target/'engineering/backend/src',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('operations.json','atomic-batches.json','models.json','messages.json','notifications.json','knowledge.json'):
            shutil.copy2(ROOT/'engineering/contracts'/name,target/'engineering/contracts'/name)
        for folder in ('client-sdk','test-console'):
            shutil.copytree(ROOT/'engineering'/folder,target/'engineering'/folder,dirs_exist_ok=True)
    for folder in ('ai-runtime','ai-snapshot-performance','ai-command-reliability'):(target/'engineering/acceptance'/folder).mkdir(parents=True,exist_ok=True)
    files={str(p.relative_to(target)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in target.rglob('*') if p.is_file()}
    (HERE/(args.label+'-source.json')).write_text(json.dumps({'engine':args.engine,'tree':str(target),'files':files},indent=2)+'\n',encoding='utf-8')
    command=[sys.executable,'-X','utf8','-B','-m','pytest','-q','-p','no:cacheprovider','--basetemp='+str(target/'pytest-tmp'),'--junitxml='+str(HERE/(args.label+'.xml'))]
    selected=args.tests
    if args.core:selected=[p.name for p in (target/'engineering/ai/tests').glob('test_*.py') if 'playwright' not in p.read_text(encoding='utf-8') and p.name not in ('test_chat_polish.py','test_style_stability.py','test_access_ui.py')]
    command.extend(str(target/'engineering/ai/tests'/name) for name in selected)
    print(json.dumps({'testTree':str(target),'engine':args.engine,'ai':'current snapshot','files':len(selected)}),flush=True)
    raise SystemExit(subprocess.call(command,cwd=target))


if __name__=='__main__':main()
