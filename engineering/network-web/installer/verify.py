"""Install the actual EXE into an isolated project copy without relying on system Python."""
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid
import argparse
import time

module = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=module / 'local/acceptance/installer.json')
args = parser.parse_args()
target = module / 'local/installer-smoke' / ('含 空格-' + uuid.uuid4().hex[:8])
for name in ('network-web', 'network-p2p'):
    source = module.parent / name
    destination = target / 'engineering' / name
    shutil.copytree(source / 'src', destination / 'src', ignore=shutil.ignore_patterns('__pycache__', '*.egg-info'))
    shutil.copy2(source / 'pyproject.toml', destination / 'pyproject.toml')
sentinel = target / 'engineering/network-p2p/local/config-preserve.json'
sentinel.parent.mkdir(parents=True)
sentinel.write_text('{"sentinel":"preserve"}')
exe = module / 'dist/OnlineCOC-Network-Setup.exe'
env = {**os.environ, 'PATH': os.environ['WINDIR'] + '/System32', 'PYTHONHOME':'Z:/not-installed', 'PYTHONPATH':'Z:/not-installed'}
steps = []
def run(*command_args, expected=0):
    started = time.monotonic()
    result = subprocess.run([str(exe), *map(str,command_args)], env=env, capture_output=True, text=True, encoding="utf-8", timeout=180)
    steps.append({'operation': command_args[0], 'exitCode': result.returncode,
                  'expectedExitCode': expected, 'seconds': round(time.monotonic()-started, 3)})
    assert result.returncode == expected, (result.returncode, result.stdout, result.stderr)
run('--install', target)
run('--verify', target)
runtime = target / 'engineering/network-p2p/.venv'
python = runtime / 'Scripts/python.exe'
for module_name in ('onlinecoc_p2p', 'onlinecoc_web'):
    result = subprocess.run([str(python), '-B', '-m', module_name, '--help'], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
# In-use environment is rejected without terminating it.
worker = subprocess.Popen([str(python), '-B', '-c', 'import time; time.sleep(90)'], env=env)
try:
    run('--install', target, expected=1)
    assert worker.poll() is None
finally:
    worker.terminate(); worker.wait(timeout=10)
run('--install', target)
run('--verify', target)
assert list((sentinel.parent / 'runtime-backups').iterdir())
assert sentinel.read_text() == '{"sentinel":"preserve"}'
run('--install', target / 'missing', expected=1)
result = {'freshInstall': True, 'repeatInstallAndBackup': True, 'unicodeAndSpaces': True,
    'systemPythonAbsentFromPATH': True, 'invalidPythonEnvironmentIgnored': True,
    'inUseRuntimeRejected': True, 'retryAfterRuntimeStopped': True, 'configurationPreserved': True, 'invalidTargetRejected': True,
    'bothCLIHelp': True, 'dependenciesAndWebRTCProbe': True,
    'exeSHA256': hashlib.sha256(exe.read_bytes()).hexdigest(),
    'checkedAt': datetime.now(timezone.utc).isoformat(), 'samePhysicalComputer': True,
    'guiClicked': False, 'steps': steps, 'isolatedProject': str(target)}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result))
