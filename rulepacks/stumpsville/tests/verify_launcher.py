"""Exercise the Windows entry point, including PowerShell 5.1 file decoding."""
from datetime import datetime
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
import urllib.request
import sys

PACK = Path(__file__).resolve().parents[1]


def main(integrated=False, web=False, ai=False):
    assert os.name == 'nt', 'This acceptance test targets Windows PowerShell.'
    script = PACK / 'start.ps1'
    assert script.read_bytes().startswith(b'\xef\xbb\xbf'), 'Chinese PowerShell script must retain its UTF-8 BOM.'
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'STUMPSVILLE_TEST_SCRIPT': str(script)}
    parser = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
        '$tokens=$null; $errors=$null; '
        '[System.Management.Automation.Language.Parser]::ParseFile($env:STUMPSVILLE_TEST_SCRIPT,[ref]$tokens,[ref]$errors) | Out-Null; '
        '@{version=$PSVersionTable.PSVersion.ToString(); errors=@($errors | ForEach-Object { $_.Message })} | ConvertTo-Json; '
        'if ($errors.Count) { exit 1 }'], env=env, capture_output=True, check=True, text=True)
    parsed = json.loads(parser.stdout)
    assert not parsed['errors'], parsed
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    # Spaces and Chinese exercise argument forwarding as well as script encoding.
    data = PACK / 'tests/output' / ('launcher-' + secrets.token_hex(4)) / '中文 存档'
    data.parent.mkdir(parents=True)
    log_path = data.parent / 'launcher.log'
    origin = f'http://127.0.0.1:{port}'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    entry = 'start.ps1'
    command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
               '-Port', str(port), '-DataDir', str(data), '-NoBrowser']
    if web: command += ['-Web', '-AI']
    elif integrated: command += ['-P2P', '-AI']
    elif ai: command += ['-AI']
    with log_path.open('wb') as log:
        process = subprocess.Popen(command, cwd=PACK.parents[1], env=env, stdout=log, stderr=log,
                                   stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            for _ in range(200):
                if process.poll() is not None:
                    raise AssertionError('Launcher exited before serving: ' + log_path.read_text(encoding='utf-8', errors='replace'))
                try:
                    with opener.open(origin + '/setup/status', timeout=.5) as response:
                        status = json.load(response)
                    break
                except OSError:
                    time.sleep(.1)
            else:
                raise AssertionError('Launcher did not start: ' + log_path.read_text(encoding='utf-8', errors='replace'))
            assert status == {'ready': False, 'canSetup': True}, status
            assert (data / 'package.lock').exists(), 'DataDir did not survive CMD and PowerShell forwarding.'
            with opener.open(origin + '/') as response:
                assert '树桩镇' in response.read().decode('utf-8')
            with opener.open(origin + '/app.js') as response:
                assert 'javascript' in response.headers['Content-Type']
        finally:
            # Only terminate the process tree that this test owns; leave real rooms alone.
            if process.poll() is None:
                subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
                               capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            process.wait(timeout=15)
    for _ in range(50):
        try:
            opener.open(origin + '/setup/status', timeout=.2).close()
        except OSError:
            break
        time.sleep(.1)
    else:
        raise AssertionError('Owned launcher server still running after cleanup')
    result = {'passed': True, 'checkedAt': datetime.now().astimezone().isoformat(), 'powershell': parsed['version'],
              'checks': ['UTF-8 BOM retained and Windows PowerShell parses without errors',
                         'actual '+entry+' launches the HTTP entry page',
                         'port, no-browser, and Chinese/space data path pass through the console launcher',
                         'isolated empty archive is served without initializing the real runtime',
                         'owned launcher process tree and listening port are cleaned up']}
    target = 'tests/output/web-launcher-results.json' if web else 'tests/output/integrated-launcher-results.json' if integrated else 'tests/output/ai-launcher-results.json' if ai else 'tests/launcher-results.json'
    (PACK / target).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main('--integrated' in sys.argv, '--web' in sys.argv, '--ai' in sys.argv)
