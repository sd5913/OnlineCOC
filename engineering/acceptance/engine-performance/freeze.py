"""Copy only registered engine inputs and the independently frozen AI dependency."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent
name = sys.argv[1]
target = OUT / 'work' / name / 'engineering'
assert not target.exists(), target
frozen = ROOT / 'engineering/acceptance' / (sys.argv[2] if len(sys.argv)>2 else 'engine-kp-policy-interface-snapshot/v1') / 'engineering'
ignore = shutil.ignore_patterns('__pycache__', '*.pyc', '.pytest_cache', '*-tmp', '.venv', '.test-output', 'engineering', 'work', 'tmp')
for part in ('backend', 'data-management', 'rulepacks', 'client-sdk', 'test-console'):
    shutil.copytree(ROOT / 'engineering' / part, target / part, ignore=ignore)
shutil.copytree(frozen / 'ai', target / 'ai', ignore=ignore)
(target / 'contracts').mkdir()
for part in ('messages.json', 'knowledge.json', 'host-control.json', 'notifications.json', 'operations.json', 'models.json', 'atomic-batches.json', 'ai-operations.json'):
    shutil.copy2(ROOT / 'engineering/contracts' / part, target / 'contracts' / part)
shutil.copy2(frozen / 'contracts/ai.json', target / 'contracts/ai.json')
shutil.copytree(ROOT / 'engineering/contracts/fixtures', target / 'contracts/fixtures')
(target/'acceptance').mkdir()
for part in ('crash_worker.py','offline_server.py'):
    shutil.copy2(ROOT/'engineering/acceptance/engine-kp-policy-interface-snapshot/v1/engineering/acceptance'/part,target/'acceptance'/part)
files = {str(p.relative_to(target)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in target.rglob('*') if p.is_file()}
(OUT / (name + '-source.json')).write_text(json.dumps({'files': files, 'aiDependency': str(frozen)}, indent=2), encoding='utf-8')
print(target)
