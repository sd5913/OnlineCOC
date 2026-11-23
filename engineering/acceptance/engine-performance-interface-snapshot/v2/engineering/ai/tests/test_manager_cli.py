import os
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlsplit

import httpx


def test_actual_cli_start_and_one_use_bootstrap(tmp_path):
    root = Path(__file__).resolve().parents[2]
    config = tmp_path / 'profiles.json';config.write_bytes((root / 'ai/examples/ai-providers.json').read_bytes())
    with socket.socket() as sock:sock.bind(('127.0.0.1', 0));port = sock.getsockname()[1]
    origin = f'http://127.0.0.1:{port}'
    log_path = tmp_path / 'startup.log'
    with log_path.open('w', encoding='utf-8') as log:
        started = time.perf_counter()
        process = subprocess.Popen([sys.executable, '-B', str(root / 'ai/scripts/manager.py'), '--config', str(config),
            '--data-dir', str(tmp_path / 'manager'), '--port', str(port), '--no-browser'], stdout=log, stderr=log,
            creationflags=0x08000000 if os.name == 'nt' else 0)
        try:
            with httpx.Client(base_url=origin, trust_env=False, headers={'Origin': origin}, timeout=2) as client:
                for _ in range(100):
                    assert process.poll() is None, 'Manager exited during startup'
                    lines = log_path.read_text(encoding='utf-8').splitlines()
                    if any(line.startswith(origin + '/#unlock=') for line in lines):break
                    time.sleep(.1)
                else:raise AssertionError('Manager startup timed out')
                entry = next(line for line in lines if line.startswith(origin + '/#unlock='))
                assert client.get('/').status_code == 200
                startup_ms = round((time.perf_counter() - started) * 1000, 2)
                assert client.get('/manager/api/providers').status_code == 403
                secret = parse_qs(urlsplit(entry).fragment)['unlock'][0]
                opened = client.post('/manager/api/unlock', json={'key': secret})
                assert opened.status_code == 200
                assert client.post('/manager/api/unlock', json={'key': secret}).status_code == 403
                assert client.get('/manager/api/providers').status_code == 200
                assert client.post('/manager/api/lock', json={}, headers={'X-CSRF-Token': opened.json()['csrf']}).status_code == 200
                (root / 'acceptance/ai-runtime/chat-startup.json').write_text(json.dumps({
                    'passed': True, 'managerProcessToHttpReadyMs': startup_ms,
                    'samples': 1, 'includes': ['Python process and imports', 'manager construction', 'HTTP readiness'],
                    'excludes': ['browser startup', 'existing game save', 'model network call']
                }, indent=2) + '\n', encoding='utf-8')
        finally:process.terminate();process.wait(timeout=15)
