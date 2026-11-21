"""Run current AI against a frozen backend, with all outputs in this round."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def snapshot(label, engine=None, ai_source=None):
    target = HERE / 'work' / (label + '-' + str(time.time_ns()))
    shutil.copytree(HERE.parent / 'ai-defaults-c-review/work/baseline', target, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', 'pytest-tmp'))
    for group in ('src', 'tests', 'web', 'scripts'):
        shutil.copytree(ROOT / 'engineering/ai' / group, target / 'engineering/ai' / group,
            dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', 'output'))
    if ai_source:
        source_target=(target / 'engineering/ai/src').resolve()
        if not source_target.is_relative_to((HERE / 'work').resolve()):raise ValueError('SNAPSHOT_TARGET_OUTSIDE_WORK')
        shutil.rmtree(source_target)
        shutil.copytree(Path(ai_source)/'engineering/ai/src',target/'engineering/ai/src')
    if engine:
        source = Path(engine)
        shutil.copytree(source / 'engineering/backend', target / 'engineering/backend', dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', 'output'))
        shutil.copytree(source / 'engineering/contracts', target / 'engineering/contracts', dirs_exist_ok=True)
    for name in ('ai.json', 'ai-operations.json'):
        shutil.copy2(ROOT / 'engineering/contracts' / name, target / 'engineering/contracts' / name)
    manifest = {p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for area in ('engineering/ai/src', 'engineering/ai/web', 'engineering/backend/src', 'engineering/contracts')
        for p in (target / area).rglob('*') if p.is_file()}
    (HERE / (label + '-source.json')).write_text(json.dumps({'tree': str(target), 'engine': engine or 'sealed-prior-round', 'files': manifest}, indent=2)+'\n', encoding='utf-8')
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--engine')
    parser.add_argument('--core', action='store_true')
    parser.add_argument('--ai-source')
    parser.add_argument('tests', nargs='*')
    args = parser.parse_args()
    target = snapshot(args.label, args.engine, args.ai_source)
    selected = args.tests
    if args.core:
        selected = [p.name for p in (target / 'engineering/ai/tests').glob('test_*.py')
            if 'playwright' not in p.read_text(encoding='utf-8') and p.name not in ('test_chat_polish.py', 'test_style_stability.py', 'test_access_ui.py')]
    command = [sys.executable, '-X', 'utf8', '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
        '--basetemp='+str(target/'pytest-tmp'), '--junitxml='+str(HERE/(args.label+'.xml'))]
    command += [str(target/'engineering/ai/tests'/name) for name in selected]
    print(json.dumps({'testTree':str(target),'files':len(selected)}), flush=True)
    raise SystemExit(subprocess.call(command, cwd=target))


if __name__ == '__main__':main()
