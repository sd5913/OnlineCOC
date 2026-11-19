"""Real Tk lifecycle, isolated host/AI/web services, and abrupt owner exit."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import tkinter as tk

from harness import PACK, Account
from launch import Runtime, free_port
from panel import PanelWindow, arguments
from verify_integrations import provider, directory
from verify_lan import pump, screenshot, test_cmd
import httpx


def port_closed(url):
    with socket.socket() as sock:
        return sock.connect_ex(('127.0.0.1', int(url.rsplit(':', 1)[1].rstrip('/')))) != 0


def close_window(window):
    window.close()
    deadline = time.monotonic()+40
    while window.service.active and time.monotonic() < deadline:
        window.root.update()
        time.sleep(.05)
    assert not window.service.active, 'service did not stop'
    try:
        window.destroy_window()
    except tk.TclError:
        pass


def crash_owner(data):
    runtime = Runtime(argparse.Namespace(data_dir=data, backend_port=0, port=free_port(), bind='127.0.0.1', no_browser=True))
    runtime.setup(secrets.token_urlsafe(18))
    (data.parent/'ready.json').write_text(json.dumps({'backend': runtime.backend}), encoding='utf-8')
    deadline = time.monotonic()+60
    while time.monotonic() < deadline and not (data.parent/'exit-now').exists():
        time.sleep(.1)
    # Intentionally bypass finally/atexit: only OS Job ownership can clean descendants.
    os._exit(0)


def main():
    output = PACK/'tests/output'/('panel-'+secrets.token_hex(4))
    output.mkdir(parents=True)
    checks = []
    args = arguments(['-DataDir', str(output/'中文 存档'), '-Port', '8898', '-NoBrowser', '-Web', '-AI'])
    assert args.mode == 'web' and args.ai and args.port == 8898 and args.no_browser
    with provider(output) as (config, calls):
        root = tk.Tk()
        window = PanelWindow(root, output/'中文 存档', False, ai=True, ai_config=config, port=free_port())
        try:
            pump(root, lambda: not window.scanning)
            window.slot_name.set('面板验收');window.slot_create.invoke()
            password = secrets.token_urlsafe(18)
            window.password.set(password); window.confirm.set('wrong')
            window.start_button.invoke()
            assert '不一致' in window.status.get() and not (window.data/'host').exists()
            window.confirm.set(password)
            window.start_button.invoke()
            pump(root, lambda: bool(window.url) or window.failed)
            assert window.url, window.status.get()
            origin, backend = window.url.rstrip('/'), window.service.runtime.backend
            account = Account(origin, 'player1', password)
            account.action('note', {'text': 'PANEL-PERSISTENCE'})
            assert account.request('/api/v1/capabilities')['ai']['available']
            checks.append('native panel validates input and prepares an isolated room with AI via public CLI; legacy argument aliases work')
            root.iconify(); root.update()
            assert root.state() == 'iconic'
            assert account.state()['note'] == 'PANEL-PERSISTENCE'
            root.deiconify(); root.update()
            window.copy_button.invoke()
            assert root.clipboard_get() == window.url
            window.diagnose_button.invoke()
            pump(root, lambda: hasattr(window, 'last_report'))
            assert '本机回环入口，只供本机访问' in window.last_report
            assert '所选IP已不在本机' not in window.last_report
            for child in root.winfo_children():
                if isinstance(child, tk.Toplevel): child.destroy()
            screenshot(root, output/'panel-running.png')
            checks.append('minimized window keeps room reachable; restore, address copy, loopback diagnostics and management controls work')
            close_window(window)
            assert port_closed(origin) and port_closed(backend)
            assert (window.data/'host').is_dir() and (window.data/'package.json').is_file()
            checks.append('closing panel releases adapter/backend ports and descendants while keeping the paired save')
        finally:
            close_window(window)

        with directory(output, web=True) as (network, directory_url):
            root = tk.Tk()
            window = PanelWindow(root, output/'中文 存档', False, mode='web', ai=True,
                                 ai_config=config, web_config=network, port=free_port())
            try:
                pump(root, lambda: not window.scanning)
                window.start_button.invoke()
                pump(root, lambda: bool(window.url) or window.failed, timeout=120)
                assert window.url, window.status.get()
                assert Account(window.url.rstrip('/'), 'player1', password).state()['note'] == 'PANEL-PERSISTENCE'
                status = window.service.runtime.modules.web_status()
                assert status['running'] and status['roomCode'], status
                root.update(); window.share_button.invoke()
                shared = root.clipboard_get()
                assert status['roomCode'] in shared and '/join' in shared
                assert 'claim' not in shared and 'creationString' not in shared
                host = window.service.runtime.process
                web = window.service.runtime.modules.web_process
                backend = window.service.runtime.backend
                screenshot(root, output/'panel-web.png')
                close_window(window)
                assert host.poll() is not None and web.poll() is not None and port_closed(backend)
                with httpx.Client(trust_env=False) as client:
                    assert not client.get(directory_url+'/v1/rooms').json()['items']
                checks.append('same save restarts in web mode; public join info excludes claims; close withdraws directory room and stops web/host processes')
            finally:
                close_window(window)
        assert not calls, 'launching a panel must not invoke a model'

    crash_data = output/'abrupt/room'
    crash_data.parent.mkdir()
    with (output/'abrupt/owner.log').open('wb') as log:
        owner = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--crash-owner', str(crash_data)],
            stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            ready = crash_data.parent/'ready.json'
            deadline = time.monotonic()+60
            while not ready.exists() and time.monotonic() < deadline:
                assert owner.poll() is None, 'abrupt-exit fixture failed to start'
                time.sleep(.1)
            assert ready.is_file()
            backend = json.loads(ready.read_text())['backend']
            assert not port_closed(backend)
            (crash_data.parent/'exit-now').touch()
            owner.wait(timeout=15)
            for _ in range(100):
                if port_closed(backend): break
                time.sleep(.1)
            assert port_closed(backend), 'orphan backend survived owner exit'
            runtime = Runtime(argparse.Namespace(data_dir=crash_data, backend_port=0, port=free_port(), bind='127.0.0.1', no_browser=True))
            try:
                runtime.start()
                assert runtime.process.poll() is None
            finally:
                runtime.close()
            checks.append('abrupt owner exit kills the venv launcher and backend subtree; the same archive reopens without STORE_LOCKED')
        finally:
            (crash_data.parent/'exit-now').touch()
            owner.wait(timeout=75)

    for entry in ('start-panel.cmd', 'start.cmd', 'start-ai.cmd', 'start-web.cmd', 'start-integrated.cmd', 'start-lan.cmd'):
        test_cmd(output/('entry-'+entry), entry)
    checks.append('all six double-click entries open the Python panel and close without initializing room data')
    report = {'checkedAt': datetime.now().astimezone().isoformat(), 'passed': len(checks), 'checks': checks,
              'provider': 'loopback only; no model calls', 'cloudTested': False, 'data': 'isolated test rooms'}
    (PACK/'tests/panel-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--crash-owner':
        crash_owner(Path(sys.argv[2]))
    else:
        main()
