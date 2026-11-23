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


def snapshot(label, engine=None, ai_source=None, overlays=()):
    target = HERE / 'work' / (label + '-' + str(time.time_ns()))
    source = Path(engine) if engine else HERE.parent / 'engine-kp-policy-interface-snapshot/v1'
    if not (source/'engineering').exists():source = source / 'tree' if (source/'tree/engineering').exists() else source
    if not (source/'engineering').exists():raise ValueError('ENGINE_SNAPSHOT_LAYOUT: '+str(source))
    target.mkdir(parents=True)
    for area in (source / 'engineering').iterdir():
        if area.name == 'ai':continue
        if area.is_dir():shutil.copytree(area, target / 'engineering' / area.name,
            ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', 'output'))
        else:shutil.copy2(area, target / 'engineering' / area.name)
    for overlay in overlays:
        overlay=Path(overlay)
        if not (overlay/'engineering').is_dir():raise ValueError('OVERLAY_LAYOUT: '+str(overlay))
        shutil.copytree(overlay/'engineering',target/'engineering',dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('__pycache__','.pytest_cache','output'))
    ai_root = Path(ai_source) if ai_source else ROOT
    for group in ('src', 'tests', 'web', 'scripts', 'examples'):
        shutil.copytree(ai_root / 'engineering/ai' / group, target / 'engineering/ai' / group,
            dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', 'output'))
    for name in ('ai.json', 'ai-operations.json'):
        shutil.copy2(ai_root / 'engineering/contracts' / name, target / 'engineering/contracts' / name)
    # Existing core tests write these evidence files relative to their source.
    # Prepare only empty output directories; never import previous run results.
    for area in ('ai-runtime', 'ai-snapshot-performance'):
        (target / 'engineering/acceptance' / area).mkdir(parents=True, exist_ok=True)
    manifest = {p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for area in ('engineering/ai/src', 'engineering/ai/web', 'engineering/ai/tests',
                     'engineering/backend/src', 'engineering/contracts', 'engineering/data-management')
        for p in (target / area).rglob('*') if p.is_file()}
    (HERE / (label + '-source.json')).write_text(json.dumps({'tree': str(target), 'engine': str(source), 'engineOverlays':list(overlays), 'ai': str(ai_root), 'files': manifest}, indent=2)+'\n', encoding='utf-8')
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--engine')
    parser.add_argument('--engine-overlay',action='append',default=[])
    parser.add_argument('--core', action='store_true')
    parser.add_argument('--ai-source')
    parser.add_argument('tests', nargs='*')
    args = parser.parse_args()
    target = snapshot(args.label, args.engine, args.ai_source,args.engine_overlay)
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
