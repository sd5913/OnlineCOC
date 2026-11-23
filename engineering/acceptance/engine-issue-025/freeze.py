"""Build an isolated engine + frozen AI test tree without reading live AI."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent
name = sys.argv[1]
target = OUT / 'work' / name / 'engineering'
assert not target.exists()
ignore = shutil.ignore_patterns('__pycache__', '*.pyc', '.pytest_cache', '.test-output', '*-tmp', 'work', 'tmp')
shutil.copytree(ROOT / 'engineering/acceptance/engine-performance-interface-snapshot/v2/engineering', target, ignore=ignore)
for part in ('backend', 'data-management'):
    shutil.copytree(ROOT / 'engineering' / part, target / part, dirs_exist_ok=True, ignore=ignore)
dependency = ROOT / 'engineering/acceptance/ai-staged-interface-snapshot/v2/engineering'
shutil.copytree(dependency / 'ai', target / 'ai', dirs_exist_ok=True, ignore=ignore)
for source in (ROOT / 'engineering/contracts').glob('*.json'):
    shutil.copy2(source, target / 'contracts' / source.name)
shutil.copy2(dependency / 'contracts/ai.json', target / 'contracts/ai.json')
files = {'engineering/' + p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in sorted(target.rglob('*')) if p.is_file()}
(OUT / (name + '-source.json')).write_text(json.dumps({'aiDependency': 'ai-staged-interface-snapshot/v2', 'files': files}, indent=2), encoding='utf-8')
print(target)
