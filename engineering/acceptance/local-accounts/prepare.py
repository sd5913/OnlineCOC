"""Freeze only reserved engine inputs; AI input is a prior immutable snapshot."""
from pathlib import Path
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEST = HERE / 'work/engine/engineering'
FROZEN = ROOT / 'engineering/acceptance/ai-command-reliability/work/atomic-engine/engineering'
shutil.copytree(FROZEN, DEST, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.pytest_cache'))
AI_SNAPSHOT = ROOT / 'engineering/acceptance/ai-c-review-interface-snapshot/v2/engineering'
shutil.copytree(AI_SNAPSHOT, DEST, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.pytest_cache'))
names = '''__init__ ai_contracts ai_sources assets atomic_batches chat cli contracts data_adapter data_queries errors execution gateway host host_control host_control_client identity local_accounts lua_runtime model notifications publication registry room_lifecycle room_migration room_read room_validation server version worker_entry worker_process'''.split()
sources = [ROOT / f'engineering/backend/src/onlinecoc/{name}.py' for name in names]
for directory in ('engineering/data-management', 'engineering/rulepacks', 'engineering/backend/src/onlinecoc/knowledge', 'engineering/backend/scripts', 'engineering/backend/tests', 'engineering/client-sdk', 'engineering/test-console'):
    sources.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
sources.extend(ROOT / f'engineering/contracts/{name}.json' for name in ('models','messages','notifications','knowledge','operations','host-control'))
sources.extend(ROOT / f'engineering/acceptance/{name}.py' for name in ('offline_server','crash_worker'))
hashes = {}
for source in sorted(set(sources)):
    relative = source.relative_to(ROOT / 'engineering')
    target = DEST / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    hashes[str(source.relative_to(ROOT)).replace('\\','/')] = hashlib.sha256(source.read_bytes()).hexdigest()
for name in ('client-sdk', 'test-console'):
    (DEST/name).mkdir(exist_ok=True)
(HERE/'source.json').write_text(json.dumps({'sources':hashes,'aiSource':str(AI_SNAPSHOT.relative_to(ROOT)).replace('\\','/'),
    'aiSources':{str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(AI_SNAPSHOT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'},
    'aiContractDigest':hashlib.sha256((DEST/'contracts/ai.json').read_bytes()).hexdigest()},indent=2),encoding='utf-8')
print(json.dumps({'mirroredFiles':len(hashes),'destination':str(DEST)}))
