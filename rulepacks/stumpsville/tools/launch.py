"""Local package server. Uses only public host CLI and HTTP/WebSocket APIs."""
import argparse
from collections import deque
import hashlib
import threading
import asyncio
from contextlib import asynccontextmanager
from http.cookies import SimpleCookie
import ipaddress
import json
import logging
import os
import re
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
import webbrowser
import uuid

sys.dont_write_bytecode = True
import httpx
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import Response
import uvicorn
import websockets

from client import Client, HostError, stateless_cookies
from package import PACK, Package, PackageError, bundle
from chat import ScopedChat
from localization import localize_projection, localize_result
from integrations import Modules
from ai_bridge import consultation
from processes import OwnedProcess, run_owned, stop_process

ROOT = PACK.parents[1]
SLOTS = re.compile(r'[a-zA-Z0-9_-]{1,40}')
STATIC = {'': ('ui/index.html', 'text/html; charset=utf-8'),
          'app.js': ('ui/app.js', 'text/javascript; charset=utf-8'),
          'chat.js': ('ui/chat.js', 'text/javascript; charset=utf-8'),
          'ruling-card.js': ('ui/ruling-card.js', 'text/javascript; charset=utf-8'),
          'batch-details.js': ('ui/batch-details.js', 'text/javascript; charset=utf-8'),
          'reference-view.js': ('ui/reference-view.js', 'text/javascript; charset=utf-8'),
          'keeper-rulings.js': ('ui/keeper-rulings.js', 'text/javascript; charset=utf-8'),
          'keeper-queue.js': ('ui/keeper-queue.js', 'text/javascript; charset=utf-8'),
          'dice.js': ('ui/dice.js', 'text/javascript; charset=utf-8'),
          'effects.js': ('ui/effects.js', 'text/javascript; charset=utf-8'),
          'map.js': ('ui/map.js', 'text/javascript; charset=utf-8'),
          'ai.js': ('ui/ai.js', 'text/javascript; charset=utf-8'),
          'ai-embedded.js': ('ui/ai-embedded.js', 'text/javascript; charset=utf-8'),
          'ai-recovery.js': ('ui/ai-recovery.js', 'text/javascript; charset=utf-8'),
          'i18n.js': ('ui/i18n.js', 'text/javascript; charset=utf-8'),
          'messageformat.js': ('ui/messageformat.js', 'text/javascript; charset=utf-8'),
          'locales/zh-CN/ui.json': ('locales/zh-CN/ui.json', 'application/json'),
          'locales/en/ui.json': ('locales/en/ui.json', 'application/json'),
          'locales/meta/catalog/ui.json': ('locales/meta/catalog/ui.json', 'application/json'),
          'styles.css': ('ui/styles.css', 'text/css; charset=utf-8')}


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def slot_path(path):
    if path.startswith('sessions/'):
        parts = path.split('/', 2)
        if len(parts) != 3 or not SLOTS.fullmatch(parts[1]):
            raise PackageError('入口不存在')
        return parts[1], parts[2]
    return None, path


def forwarded_cookie(header, slot):
    cookies = SimpleCookie()
    cookies.load(header)
    prefix = 'sv_' + slot + '__' if slot else ''
    values = []
    for name, morsel in cookies.items():
        if slot and name.startswith(prefix):
            values.append(name[len(prefix):] + '=' + morsel.coded_value)
        elif slot is None and not name.startswith('sv_'):
            values.append(name + '=' + morsel.coded_value)
    return '; '.join(values)


class Runtime:
    def __init__(self, args):
        self.args = args
        self.data = args.data_dir.resolve()
        if self.data.is_relative_to(ROOT / 'engineering'):
            raise ValueError('运行存档应位于 engineering 目录外')
        self.data.mkdir(parents=True, exist_ok=True)
        self.lock = (self.data / 'package.lock').open('a+b')
        self.lock.seek(0)
        if os.name == 'nt':
            import msvcrt
            if self.lock.read(1) == b'':
                self.lock.write(b'0')
                self.lock.flush()
            self.lock.seek(0)
            msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.package = Package(self.data / 'package.json')
        self.host_data = self.data / 'host'
        self.backend = 'http://127.0.0.1:' + str(args.backend_port or free_port())
        self.origin = f'http://{args.bind}:{args.port}'
        self.process = None
        self.log = None
        self.setup_lock = asyncio.Lock()
        python = Path(sys.executable)
        if python.name.lower() == 'pythonw.exe':
            python = python.with_name('python.exe')
        self.command = [str(python), '-B', str(ROOT / 'engineering/backend/scripts/run.py'), '--data-dir', str(self.host_data)]
        self.env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1'}
        self.opened_at = time.time()
        self.pack_version = json.loads((PACK/'manifest.json').read_text(encoding='utf-8'))['version']
        self.net_lock = threading.RLock()
        self.connections, self.seen_accounts = {}, {}
        self.visits = deque(maxlen=60)
        self.modules = Modules(self)
        self.bootstrap_ai = None

    def observe_request(self, peer, path, status):
        try:
            _, path = slot_path(path.lstrip('/'))
        except PackageError:
            path = 'invalid'
        kind = '打开页面' if path == '' else ('登录成功' if status == 200 else '登录失败') if path == 'api/v1/login' else '请求被拒绝' if status >= 400 else None
        if kind:
            with self.net_lock:
                self.visits.append({'time': time.time(), 'ip': peer, 'kind': kind, 'status': status,
                                    'local': peer in {self.args.bind, '127.0.0.1', '::1'}})

    def heartbeat(self, projection, cookie, page, peer):
        now = time.time()
        token = hashlib.sha256(cookie.encode()).hexdigest()
        page = page if re.fullmatch(r'[a-zA-Z0-9-]{1,64}', page or '') else 'api'
        with self.net_lock:
            self.connections = {k: v for k, v in self.connections.items() if now-v['lastSeen'] < 600}
            self.connections[(token, page)] = {'accountId': projection['accountId'], 'ip': peer, 'lastSeen': now}
            self.seen_accounts[projection['accountId']] = now
            while len(self.connections) > 256:
                del self.connections[min(self.connections, key=lambda k: self.connections[k]['lastSeen'])]

    def forget_connection(self, cookie):
        token = hashlib.sha256(cookie.encode()).hexdigest()
        with self.net_lock:
            self.connections = {k:v for k,v in self.connections.items() if k[0] != token}

    def network_snapshot(self, members=(), characters=()):
        now = time.time()
        with self.net_lock:
            players = []
            for member in members:
                account = member['accountId']
                connections = [c for c in self.connections.values() if c['accountId'] == account]
                live = [c for c in connections if now-c['lastSeen'] < 30]
                recent = [c for c in connections if now-c['lastSeen'] < 120]
                actor = next((c for c in characters if c['owner'] == account), None)
                players.append({'accountId': account, 'name': member.get('displayName', account), 'role': member['role'],
                    'character': actor['name'] if actor else None, 'status': 'online' if live else 'stale' if recent else 'offline',
                    'pages': len(live), 'ips': sorted({c['ip'] for c in recent}), 'lastSeen': self.seen_accounts.get(account)})
            return {'url': self.origin+'/', 'bind': self.args.bind, 'port': self.args.port, 'startedAt': self.opened_at,
                    'version': self.pack_version, 'players': players, 'visits': list(self.visits)}

    def start(self):
        if self.process and self.process.poll() is None:
            return
        stop_process(self.process)
        if not self.host_data.exists():
            return
        if self.log:
            self.log.close()
        self.log = (self.data / 'host.log').open('a', encoding='utf-8')
        log_offset = self.log.tell()
        control_dir = getattr(self.args, 'host_control_dir', None)
        control_args = ['--host-control-dir', str(control_dir)] if control_dir else []
        self.process = OwnedProcess(self.command + ['serve', '--port', self.backend.rsplit(':', 1)[1]] + control_args + self.modules.host_args(),
                                        env=self.env, stdout=self.log, stderr=self.log,
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        for _ in range(150):
            if self.process.poll() is not None:
                self.log.flush()
                with (self.data/'host.log').open('rb') as file:
                    file.seek(max(log_offset, (self.data/'host.log').stat().st_size-6000))
                    tail = file.read().decode('utf-8', errors='replace')
                if 'STORE_LOCKED' in tail:
                    raise RuntimeError('宿主存档被其他进程占用（STORE_LOCKED）。请关闭原房间面板；不要删除锁文件。详情见 host.log。')
                if 'SCHEMA_UNSUPPORTED' in tail:
                    raise RuntimeError('房间存档版本与当前引擎不兼容（SCHEMA_UNSUPPORTED）。请在房间数据区创建新槽位，或先离线处理旧档。详情见所选槽位 host.log。')
                raise RuntimeError('宿主启动失败，请在面板查看 host.log')
            try:
                with urllib.request.urlopen(self.backend + '/api/v1/capabilities', timeout=.5):
                    self.modules.start()
                    return
            except OSError:
                time.sleep(.1)
        raise RuntimeError('宿主连接超时')

    def close(self):
        try:
            self.modules.close()
        finally:
            try:
                stop_process(self.process)
            finally:
                if self.log:
                    self.log.close()
                self.lock.close()

    def setup(self, password):
        if self.host_data.exists():
            raise PackageError('存档已经存在')
        if not isinstance(password, str) or not 8 <= len(password) <= 128:
            raise PackageError('密码应为8至128位')
        run_owned(self.command + ['init'], env={**self.env, 'ONLINECOC_BOOTSTRAP_PASSWORD': password},
                       check=True, capture_output=True, timeout=45,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.start()
        client = Client(self.backend, 'kp', password)
        try:
            self.package.action(client, {'id': 'initial-install-0001', 'operation': 'initialize', 'args': {}})
            if self.modules.ai_config:
                self.initialize_new_room_ai(client)
        finally:
            client.request('/logout', {})

    def initialize_new_room_ai(self, client):
        """Explicit first-room setup only; ordinary starts preserve chosen policy."""
        try:
            settings = client.request('/ai/settings')
            scope = settings['scopeId']
            view = client.request('/view')
            receipt = client.request('/ai/commands', {
                'requestId': str(uuid.uuid5(uuid.NAMESPACE_URL, 'stumpsville-ai-initialize:'+scope)),
                'authorityEpoch': view['authorityEpoch'], 'op': 'ai.room.initialize',
                'args': {'scopeId': scope, 'profileId': None}})
            if receipt.get('status') != 'committed':
                raise HostError({'code': receipt.get('code', 'AI_INITIALIZATION_INCOMPLETE')})
            self.bootstrap_ai = receipt['result']
        except (HostError, KeyError, OSError, ValueError) as error:
            # The room was created successfully. Surface AI setup separately,
            # without retrying or overriding policy during a later restart.
            self.bootstrap_ai = {'serviceStatus': 'initialization_failed',
                'code': getattr(error, 'response', {}).get('code', 'AI_INITIALIZATION_INCOMPLETE')}

    def client(self, cookie, *, defer_csrf=False):
        client = Client.__new__(Client)
        client.base = self.backend
        client.csrf = None
        client.transport = getattr(self, 'http_client', None)
        client.cookie = cookie
        if client.transport is None:
            client.opener = urllib.request.build_opener()
            client.opener.addheaders = [('Cookie', cookie)]
        client.defer_csrf = defer_csrf
        if not defer_csrf:
            client.csrf = client.request('/me')['csrf']
        return client


def projection_delta(value, previous):
    # Compare authorized, localized domains. An empty domain removes old fields.
    catalog = {'items', 'presets', 'rules', 'locations', 'sourceStatus', 'allLocations',
               'npcTemplates', 'sceneDefinitions', 'catalog', 'published'}
    activity = {'events', 'receipts', 'requests', 'notifications', 'keeperWaits'}
    domains = [{}, {}, {}, {}, {}]
    for key, item in value.items():
        index = 1 if key in catalog else 2 if key in activity else 3 if key == 'channels' else 4 if key in ('network', 'revision') else 0
        domains[index][key] = item
    versions = [hashlib.sha256(json.dumps(domain, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
                for domain in domains]
    prior = previous.split(',') if len(previous) <= 324 else []
    return {'versions': versions, 'domains': {str(i): domain for i, domain in enumerate(domains)
            if len(prior) != len(domains) or prior[i] != versions[i]}}


def create_app(runtime):
    @asynccontextmanager
    async def lifespan(app):
        try:
            await asyncio.to_thread(runtime.start)
            # Pools carry connections, never account state. Each call supplies
            # its own Cookie/CSRF; even login Set-Cookie cannot populate a jar.
            with httpx.Client(timeout=25, trust_env=False, follow_redirects=False,
                              cookies=stateless_cookies()) as client:
                runtime.http_client = client
                async with httpx.AsyncClient(timeout=30, trust_env=False, follow_redirects=False,
                                             cookies=stateless_cookies()) as upstream:
                    app.state.upstream = upstream
                    app.state.ai_resources = upstream
                    yield
        finally:
            runtime.http_client = None
            await asyncio.to_thread(runtime.close)

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def track_reachability(request, call_next):
        started = time.perf_counter()
        result = await call_next(request)
        result.headers['Server-Timing'] = 'package;dur=' + str(round((time.perf_counter()-started)*1000, 2))
        runtime.observe_request(request.client.host if request.client else 'unknown', request.url.path, result.status_code)
        return result

    def response(value, status=200, mime='application/json'):
        body = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
        return Response(body, status_code=status, media_type=mime, headers={
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"})

    def static_response(file, mime, request):
        # Browser storage is limited to public assets. Compare the actual bytes
        # so replacing a same-sized file with an unchanged timestamp is detected.
        raw = file.read_bytes()
        etag = '"' + hashlib.sha256(raw).hexdigest() + '"'
        match = request.headers.get('if-none-match') == etag
        result = response(b'' if match else raw, 304 if match else 200, mime)
        result.headers.update({'ETag': etag, 'Cache-Control': 'private, no-cache'})
        return result

    def check_origin(headers, write=False):
        if headers.get('host') != runtime.origin.split('//')[1]:
            raise PackageError('HOST_REJECTED')
        origin = headers.get('origin')
        if (origin and origin != runtime.origin) or (write and origin != runtime.origin):
            raise PackageError('ORIGIN_REJECTED')

    chat_change = asyncio.Event()

    @app.api_route('/{path:path}', methods=['GET', 'POST'])
    async def handle(path, request: Request):
        nonlocal chat_change
        trace_id = uuid.uuid4().hex
        body = b''
        def error_response(data, status):
            # Only routing/receipt identifiers are exposed; never body text, cookies or URLs.
            try:
                submitted = json.loads(body) if body else {}
            except (ValueError, UnicodeError):
                submitted = {}
            submitted = submitted if isinstance(submitted, dict) else {}
            payload = submitted.get('payload', submitted)
            payload = payload if isinstance(payload, dict) else {}
            def identifier(value):
                return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.:/-]{1,200}', value) else None
            details = {'traceId':trace_id, 'method':request.method,
                       'operation':identifier(payload.get('op') or submitted.get('operation')) or identifier(path) or 'unknown-route',
                       'requestId':identifier(submitted.get('requestId') or submitted.get('id')) or trace_id,
                       'httpStatus':status}
            command_id = identifier(payload.get('commandId'))
            if command_id:
                details['commandId'] = command_id
            upstream_operation = identifier(data.get('operation'))
            if upstream_operation and upstream_operation != details['operation']:
                details['upstreamOperation'] = upstream_operation
            data = {**data, **details}
            message = data.get('message') or data.get('code') or '请求失败'
            action = '。请核对原行动回执后恢复' if request.method=='POST' and path in {'package/action','api/v1/commands','api/v1/ai/commands'} and status>=500 else '。请稍后刷新或重试查询' if request.method=='GET' and status>=500 else ''
            data['message'] = message + action + '（' + str(data.get('code') or 'REQUEST_FAILED') + '；定位：' + trace_id + '）'
            logging.getLogger('stumpsville').error('request_failed trace=%s method=%s operation=%s request=%s status=%s code=%s', trace_id, request.method, details['operation'], details['requestId'], status, data.get('code'))
            try:
                with (runtime.data / 'request-errors.log').open('a', encoding='utf-8') as log:
                    log.write(json.dumps({'time':time.time(), **details, 'code':data.get('code'),
                        **{key:data[key] for key in ('errorKind','osError') if key in data}}, ensure_ascii=False)+'\n')
            except OSError:
                logging.getLogger('stumpsville').error('Cannot persist request diagnostic trace=%s',trace_id)
            return response(data, status)
        try:
            check_origin(request.headers, request.method == 'POST')
            slot, path = slot_path(path)
            if '%' in path or '..' in path or '\\' in path:
                return response({'code': 'NOT_FOUND'}, 404)
            cookie = forwarded_cookie(request.headers.get('cookie', ''), slot)
            body = await request.body()
            if len(body) > 10 * 1024 * 1024:
                return response({'code': 'REQUEST_TOO_LARGE'}, 413)
            if path == 'setup/status':
                return response({'ready': bool(runtime.process and runtime.process.poll() is None), 'canSetup': not runtime.host_data.exists()})
            if path == 'setup' and request.method == 'POST':
                if request.client.host not in {'127.0.0.1', '::1'}:
                    return response({'code': '首次准备请在本机完成'}, 403)
                async with runtime.setup_lock:
                    await asyncio.to_thread(runtime.setup, json.loads(body).get('password'))
                return response({'ready': True})
            if path.startswith('api/v1/'):
                if path.startswith('api/v1/host-control'):
                    return response({'code': 'NOT_FOUND'}, 404)
                headers = {'Origin': runtime.backend, 'Cookie': cookie}
                for key in ('content-type', 'x-csrf-token'):
                    if request.headers.get(key):
                        headers[key] = request.headers[key]
                result = await request.app.state.upstream.request(request.method, runtime.backend + '/' + path,
                    params=request.query_params, content=body, headers=headers)
                if path == 'api/v1/logout' and result.is_success:
                    runtime.forget_connection(cookie)
                if not result.is_success:
                    try:
                        value = result.json()
                        if not isinstance(value, dict):
                            value = {}
                    except ValueError:
                        value = {}
                    return error_response({**value, 'code':value.get('code') or 'HOST_HTTP_ERROR',
                        'message':value.get('message') or value.get('code') or ('主机返回 HTTP ' + str(result.status_code))}, result.status_code)
                output = response(result.content, result.status_code, result.headers.get('content-type', 'application/json'))
                for raw in result.headers.get_list('set-cookie'):
                    if not slot:
                        output.headers.append('set-cookie', raw)
                        continue
                    cookies = SimpleCookie()
                    cookies.load(raw)
                    for name, morsel in cookies.items():
                        scoped = SimpleCookie()
                        scoped['sv_' + slot + '__' + name] = morsel.value
                        target = scoped['sv_' + slot + '__' + name]
                        for key, value in morsel.items():
                            if value and key not in {'path', 'domain'}:
                                target[key] = value
                        target['path'] = '/sessions/' + slot + '/'
                        output.headers.append('set-cookie', target.OutputString())
                return output
            if path.startswith('package/'):
                client = await asyncio.to_thread(runtime.client, cookie, defer_csrf=request.method == 'GET' and path in {'package/state', 'package/chat/state'})
                # Authenticated host reads always verify the session. A token
                # supplied on a GET can be forwarded for nested host queries.
                if getattr(client, 'defer_csrf', False):
                    client.csrf = request.headers.get('x-csrf-token')
                if request.method == 'POST' and request.headers.get('x-csrf-token') != client.csrf:
                    return response({'code': 'CSRF_REQUIRED'}, 403)
                if path in {'package/web/status','package/web/stop'}:
                    view=await asyncio.to_thread(client.request,'/view')
                    if view['role']!='kp' or request.client.host not in {'127.0.0.1','::1'}:
                        return response({'code':'LOCAL_KP_REQUIRED'},403)
                    if path=='package/web/stop':
                        if request.method!='POST':return response({'code':'METHOD_NOT_ALLOWED'},405)
                        await asyncio.to_thread(runtime.modules.stop_web)
                    return response(runtime.modules.web_status(private=True))
                if path == 'package/state' and request.method == 'GET':
                    result = await asyncio.to_thread(runtime.package.projection, client, request.query_params.get('preview'), request.query_params.get('player') == '1')
                    if not result['preview']:
                        runtime.heartbeat(result, cookie, request.query_params.get('page'), request.client.host)
                        if result['role'] == 'kp':
                            result['network'] = runtime.network_snapshot(result['members'], result['characters'])
                    localized = localize_projection(result, request.query_params.get('locale', 'zh-CN'), detached=True)
                    previous = request.headers.get('x-projection-versions')
                    return response(projection_delta(localized, previous) if previous is not None else localized)
                if path == 'package/integrations' and request.method == 'GET':
                    view = await asyncio.to_thread(client.request, '/view')
                    if view['role'] != 'kp':
                        return response({'code': 'KP_REQUIRED'}, 403)
                    return response(runtime.modules.status())
                if path == 'package/chat/state' and request.method == 'GET':
                    previous = request.headers.get('x-chat-version')
                    deadline = time.monotonic() + 2
                    while True:
                        signal = chat_change
                        chat = await asyncio.to_thread(ScopedChat(runtime.package).projection, client, request.query_params.get('player') == '1')
                        if previous is None:
                            return response(chat)
                        version = hashlib.sha256(json.dumps(chat, separators=(',', ':')).encode()).hexdigest()
                        if version != previous:
                            return response({**chat, 'version': version})
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            return response({'accountId': chat['accountId'], 'version': version})
                        try:
                            await asyncio.wait_for(signal.wait(), remaining)
                        except asyncio.TimeoutError:
                            pass
                if path == 'package/chat/history' and request.method == 'POST':
                    return response(await asyncio.to_thread(ScopedChat(runtime.package).history, client, json.loads(body)))
                if path == 'package/ai-source' and request.method == 'POST':
                    return response(await asyncio.to_thread(runtime.package.review_source, client, json.loads(body)))
                if path == 'package/ai' and request.method == 'POST':
                    if len(body) > 65536:
                        return response({'code': 'REQUEST_TOO_LARGE'}, 413)
                    return response(await asyncio.to_thread(consultation, client, json.loads(body)))
                if path == 'package/scene-executor' and request.method == 'POST':
                    return response(await asyncio.to_thread(runtime.package.scene_executor, client))
                if path == 'package/action' and request.method == 'POST':
                    if len(body) > 512 * 1024:
                        return response({'code': 'REQUEST_TOO_LARGE'}, 413)
                    submitted = json.loads(body)
                    if len(body) > 65536:
                        if not isinstance(submitted, dict) or submitted.get('operation') != 'rules.stage':
                            return response({'code': 'REQUEST_TOO_LARGE'}, 413)
                        view = await asyncio.to_thread(client.request, '/view')
                        if view.get('role') != 'kp':
                            return response({'code': 'KP_REQUIRED'}, 403)
                    result = await asyncio.to_thread(runtime.package.action, client, submitted)
                    if submitted['operation'] == 'chat':
                        signal, chat_change = chat_change, asyncio.Event()
                        signal.set()
                    return response(localize_result(result, request.query_params.get('locale', 'zh-CN')))
                if path == 'package/bundle' and request.method == 'GET':
                    view = await asyncio.to_thread(client.request, '/view')
                    if view['role'] != 'kp':
                        return response({'code': 'KP_REQUIRED'}, 403)
                    await asyncio.to_thread(runtime.package.sync_rules,client,view)
                    if request.query_params.get('form') == 'active':
                        revision = view['catalog']['rulesetRevision']
                        artifact = (await asyncio.to_thread(client.request, '/admin/artifacts/' + revision))['artifact']
                        configs = (await asyncio.to_thread(client.request, '/admin'))['configurations']
                        return response({'sources': artifact['sources'], 'data': artifact['data'], 'configurations': list(configs.values())})
                    content = bundle()
                    content['configurations']=list((await asyncio.to_thread(client.request,'/admin'))['configurations'].values())
                    active = runtime.package.state.get('activeRevision')
                    if active in runtime.package.state['ruleRevisions']:
                        content.update(runtime.package.state['ruleRevisions'][active])
                    return response(content)
                return response({'code': 'NOT_FOUND'}, 404)
            if request.method != 'GET':
                return response({'code': 'METHOD_NOT_ALLOWED'}, 405)
            if path.startswith('ai-ui/') and not path.endswith('.html') and runtime.modules.ai_config:
                ai_files = json.loads((ROOT/'engineering/ai/web/components/pack-manifest.json').read_text(encoding='utf-8'))['runtimeFiles']
                if path[6:] in ai_files:
                    result = await request.app.state.ai_resources.get(runtime.backend + '/' + path, timeout=10)
                    return response(result.content, result.status_code, 'text/css; charset=utf-8' if path.endswith('.css') else 'text/javascript; charset=utf-8')
            if path in STATIC:
                filename, mime = STATIC[path]
                return static_response(PACK / filename, mime, request)
            if path.startswith('art/') and path[4:] in {'welcome.png', 'courtyard.png', 'mouse.png'}:
                file = PACK / 'assets/runtime' / path[4:]
                if file.is_file():
                    return static_response(file, 'image/png', request)
            return response({'code': 'NOT_FOUND'}, 404)
        except urllib.error.HTTPError as error:
            return error_response({'code':'HOST_HTTP_ERROR','message':'主机返回 HTTP '+str(error.code)}, error.code)
        except HostError as error:
            if path == 'package/action' and error.response.get('failure'):
                # A domain rejection is a result, so the web service bridge also
                # preserves its explanation instead of reducing it to a code.
                return response(error.response)
            return error_response(error.response, error.response.get('httpStatus', 409))
        except (PackageError, ValueError, KeyError, TypeError) as error:
            return error_response({'code':str(error)}, 400)
        except (OSError, httpx.HTTPError) as error:
            code, message = ('HOST_TIMEOUT','等待主机响应超时') if isinstance(error, (TimeoutError,httpx.TimeoutException)) else ('HOST_UNREACHABLE','无法连接本机主机服务') if isinstance(error, (ConnectionError,urllib.error.URLError,httpx.NetworkError)) else ('HOST_PROTOCOL_ERROR','主机连接协议异常') if isinstance(error,httpx.HTTPError) else ('LOCAL_IO_ERROR','本机文件或资源读取失败')
            logging.getLogger('stumpsville').exception('Local request failed trace=%s kind=%s', trace_id, type(error).__name__)
            return error_response({'code':code,'message':message,'errorKind':type(error).__name__,'osError':getattr(error,'errno',None)}, 503 if code in {'HOST_TIMEOUT','HOST_UNREACHABLE'} else 502 if code=='HOST_PROTOCOL_ERROR' else 500)

    @app.websocket('/{path:path}')
    async def websocket_proxy(socket: WebSocket, path):
        try:
            check_origin(socket.headers, True)
            slot, path = slot_path(path)
            if path != 'api/v1/connect':
                await socket.close(code=1008)
                return
            cookie = forwarded_cookie(socket.headers.get('cookie', ''), slot)
            uri = runtime.backend.replace('http://', 'ws://') + '/api/v1/connect'
            async with websockets.connect(uri, origin=runtime.backend, additional_headers={'Cookie': cookie}, max_size=2**21) as upstream:
                await socket.accept()

                async def incoming():
                    while True:
                        await upstream.send(await socket.receive_text())

                async def outgoing():
                    async for message in upstream:
                        await socket.send_text(message)

                tasks = {asyncio.create_task(incoming()), asyncio.create_task(outgoing())}
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception:
            try:
                await socket.close(code=1011)
            except RuntimeError:
                pass

    return app


def main():
    parser = argparse.ArgumentParser(description='树桩镇配置包')
    parser.add_argument('--data-dir', type=Path, default=PACK / 'runtime')
    parser.add_argument('--port', type=int, default=8899)
    parser.add_argument('--backend-port', type=int, default=0)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--ai-config', type=Path, help='启用咨询模块；不自动启用模型调用')
    parser.add_argument('--p2p-config', type=Path, help='打开 P2P 基础联机入口；不自动发布房间')
    parser.add_argument('--web-config', type=Path, help='网页玩家分享；与旧P2P入口互斥')
    args = parser.parse_args()
    address = ipaddress.ip_address(args.bind)
    if address.version != 4 or not (address.is_loopback or (address.is_private and not address.is_unspecified)):
        parser.error('绑定地址应为明确的本机或可信局域网 IPv4')
    runtime = Runtime(args)
    print('树桩镇 ' + runtime.origin, flush=True)
    if not args.no_browser:
        import threading
        timer = threading.Timer(1.5, webbrowser.open, args=(runtime.origin,))
        timer.daemon = True
        timer.start()
    try:
        uvicorn.run(create_app(runtime), host=args.bind, port=args.port, log_level='warning', proxy_headers=False)
    finally:
        runtime.close()


if __name__ == '__main__':
    main()
