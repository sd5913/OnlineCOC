"""Independent, loopback-only AI administration and authenticated room bridge."""
import asyncio
import copy
from contextlib import asynccontextmanager
import os
from pathlib import Path
import re
import secrets
import time
from urllib.parse import urlsplit
import uuid

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .contracts import canonical, loads
from .errors import AiError, require
from .profiles import AI_ROOT, DEFAULT_PATH, credential, delete_profile, load_profiles, save_profile
from .providers import create_provider
from .vault import Vault

ROOM_GET = re.compile(r'^(?:me|view|capabilities|ai/settings|ai/contracts|ai/access|ai/batches|ai/rulings(?:/[a-z]+:[a-f0-9]{32}|\?[\w.:=&%-]+)?|ai/debug(?:\?[\w.=&%-]+)?|ai/usage(?:\?[\w.=&%-]+)?|ai/tasks(?:\?(?:before|limit)=[\w.-]+(?:&(?:before|limit)=[\w.-]+)*)?|ai/sessions(?:\?archived=(?:true|false))?|ai/sessions/[\w-]+|ai/(?:receipts|proposals)/[\w.-]+|receipts/[\w.-]+)$')
ROOM_POST = {'ai/commands', 'ai/drafts', 'ai/references/resolve', 'ai/data/search', 'ai/data/read', 'ai/data/chat', 'ai/data/case', 'commands', 'logout'}


def local_url(value):
    require(type(value) is str, 'ROOM_URL_INVALID')
    try:
        url = urlsplit(value)
        valid = url.scheme == 'http' and url.hostname in ('127.0.0.1', 'localhost') and url.port and 1 <= url.port <= 65535
    except ValueError:valid = False
    require(valid and not url.username and not url.password and url.path in ('', '/') and not url.query and not url.fragment, 'ROOM_URL_INVALID')
    return f'http://127.0.0.1:{url.port}'


class Manager:
    def __init__(self, config=DEFAULT_PATH, directory=None, *, vault=None, provider_factory=create_provider):
        self.config = Path(config).resolve()
        self.directory = Path(directory or AI_ROOT / '.manager')
        self.vault = vault or Vault()
        self.provider_factory = provider_factory
        self.bootstrap = secrets.token_urlsafe(32)
        self.bootstrap_deadline = time.monotonic() + 300
        self.sessions = {}
        self.clients = {}
        self.probe_lock = asyncio.Lock()
        self.rooms_path = self.directory / 'rooms.json'
        self.rooms = loads(self.rooms_path.read_bytes()) if self.rooms_path.exists() else {}
        require(type(self.rooms) is dict and len(self.rooms) <= 32, 'MANAGER_STATE_INVALID')
        for key, room in self.rooms.items():
            require(re.fullmatch(r'[a-f0-9]{32}', key) and set(room) == {'id', 'name', 'url'} and room['id'] == key, 'MANAGER_STATE_INVALID')
            room['url'] = local_url(room['url'])
        load_profiles(self.config)

    def profiles(self):
        profiles = load_profiles(self.config)
        return {'profiles': [{**p, 'credentialStatus': 'saved' if self.vault.has(p['credentialRef']) else 'environment' if self._environment(p) else 'missing'} for p in profiles.values()],
                'credentialStorage': 'windows-dpapi' if os.name == 'nt' else 'environment-only', 'configPath': str(self.config)}

    def _environment(self, profile):
        try:
            credential(profile, vault=self.vault)
            return True
        except AiError:return False

    def save_room(self, name, url):
        require(type(name) is str and 1 <= len(name.strip()) <= 80, 'INPUT_INVALID')
        url = local_url(url)
        require(all(r['url'] != url for r in self.rooms.values()), 'ROOM_ALREADY_REGISTERED')
        require(len(self.rooms) < 32, 'LIMIT_EXCEEDED')
        identifier = uuid.uuid4().hex
        room = {'id': identifier, 'name': name.strip(), 'url': url}
        candidate = {**self.rooms, identifier: room}
        self._save_rooms(candidate)
        return room

    def _save_rooms(self, value):
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = self.rooms_path.with_name('rooms.' + uuid.uuid4().hex + '.tmp')
        try:
            with temporary.open('xb') as stream:
                stream.write(canonical(value));stream.flush();os.fsync(stream.fileno())
            os.replace(temporary, self.rooms_path)
            self.rooms = value
        finally:temporary.unlink(missing_ok=True)

    async def close_session(self, token):
        self.sessions.pop(token, None)
        for key in [key for key in self.clients if key[0] == token]:
            record = self.clients.pop(key)
            try:await record['client'].post('/api/v1/logout', json={}, headers={'X-CSRF-Token': record['csrf']})
            except httpx.HTTPError:pass
            await record['client'].aclose()

    async def close(self):
        for token in list(self.sessions):await self.close_session(token)

    async def login_room(self, token, room_id, data):
        require(set(data) == {'loginName', 'password'} and all(isinstance(v, str) and len(v) <= 512 for v in data.values()), 'INPUT_INVALID')
        require(room_id in self.rooms, 'ROOM_NOT_FOUND')
        key = (token, room_id)
        if key in self.clients:
            previous = self.clients.pop(key)
            try:await previous['client'].post('/api/v1/logout', json={}, headers={'X-CSRF-Token': previous['csrf']})
            except httpx.HTTPError:pass
            finally:await previous['client'].aclose()
        url = self.rooms[room_id]['url']
        client = httpx.AsyncClient(base_url=url, headers={'Origin': url}, trust_env=False, follow_redirects=False, timeout=15)
        try:
            response = await client.post('/api/v1/login', json=data)
            require(response.status_code == 200, 'ROOM_LOGIN_FAILED')
            csrf = response.json()['csrf']
            require(token in self.sessions and time.monotonic() < self.sessions[token]['expires'], 'MANAGER_AUTH_REQUIRED')
            self.clients[key] = {'client': client, 'csrf': csrf}
            return {'connected': True}
        except BaseException:
            await client.aclose();raise

    async def room_request(self, token, room_id, data):
        require(type(data) is dict and set(data) <= {'path', 'method', 'body'} and 'path' in data, 'INPUT_INVALID')
        path, method = data['path'], data.get('method', 'GET')
        from urllib.parse import parse_qs
        reference_route = False
        if type(path) is str and path.startswith('ai/references?'):
            params = parse_qs(path.split('?', 1)[1], keep_blank_values=True)
            reference_route = set(params) <= {'kind', 'q'} and all(len(v) == 1 for v in params.values()) and len(path) <= 1600
        require(type(path) is str and ((method == 'GET' and (ROOM_GET.fullmatch(path) or reference_route)) or (method == 'POST' and path in ROOM_POST)), 'ROOM_ROUTE_FORBIDDEN')
        record = self.clients.get((token, room_id))
        require(record is not None, 'ROOM_LOGIN_REQUIRED')
        async with record['client'].stream(method, '/api/v1/' + path, json=data.get('body') if method == 'POST' else None,
            headers={'X-CSRF-Token': record['csrf']}) as response:
            require(response.status_code == 200 or response.status_code in (400, 401, 403, 404, 409, 413, 503), 'ROOM_RESPONSE_INVALID')
            raw = bytearray()
            async for chunk in response.aiter_bytes():
                raw.extend(chunk);require(len(raw) <= 8 * 1024 * 1024, 'ROOM_RESPONSE_INVALID')
            value = loads(bytes(raw))
        if response.status_code >= 400:
            raise AiError(value.get('code', 'ROOM_REQUEST_FAILED'))
        if path == 'logout':
            self.clients.pop((token, room_id), None);await record['client'].aclose()
        return value


def create_manager_app(manager, port=8776):
    import mimetypes
    mimetypes.add_type('text/javascript', '.js');mimetypes.add_type('text/css', '.css')
    origins = {f'http://127.0.0.1:{port}', f'http://localhost:{port}'}
    hosts = {urlsplit(x).netloc for x in origins}
    @asynccontextmanager
    async def lifespan(app):
        try:yield
        finally:await manager.close()
    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.exception_handler(AiError)
    async def ai_error(request, exc):return JSONResponse({'code': exc.code}, status_code=403 if exc.code in ('MANAGER_AUTH_REQUIRED', 'PERMISSION_DENIED') else 409)

    @app.exception_handler(httpx.HTTPError)
    async def network_error(request, exc):return JSONResponse({'code': 'ROOM_UNAVAILABLE'}, status_code=503)

    @app.middleware('http')
    async def boundary(request, call_next):
        if request.headers.get('host') not in hosts:return JSONResponse({'code': 'HOST_REJECTED'}, status_code=403)
        if request.method != 'GET' and request.headers.get('origin') not in origins:return JSONResponse({'code': 'ORIGIN_REJECTED'}, status_code=403)
        if request.url.path.startswith('/manager/api/'):
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > 8 * 1024 * 1024:return JSONResponse({'code': 'LIMIT_EXCEEDED'}, status_code=413)
            request._body = bytes(raw)
        response = await call_next(request)
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer', 'Content-Security-Policy': "default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
        return response

    def auth(request, write=False):
        token = request.cookies.get('onlinecoc-ai-manager', '')
        session = manager.sessions.get(token)
        require(session and time.monotonic() < session['expires'], 'MANAGER_AUTH_REQUIRED')
        if write:require(secrets.compare_digest(request.headers.get('x-csrf-token', ''), session['csrf']), 'PERMISSION_DENIED')
        return token

    async def body(request):
        value = loads(await request.body())
        require(type(value) is dict, 'INPUT_INVALID')
        return value

    @app.post('/manager/api/unlock')
    async def unlock(request: Request):
        data = await body(request)
        require(set(data) == {'key'} and isinstance(data['key'], str) and manager.bootstrap and time.monotonic() < manager.bootstrap_deadline
                and secrets.compare_digest(data['key'], manager.bootstrap), 'MANAGER_AUTH_REQUIRED')
        manager.bootstrap = None
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        manager.sessions[token] = {'csrf': csrf, 'expires': time.monotonic() + 8 * 3600}
        response = JSONResponse({'csrf': csrf})
        response.set_cookie('onlinecoc-ai-manager', token, httponly=True, samesite='strict', max_age=8 * 3600)
        return response

    @app.get('/manager/api/session')
    def session(request: Request):
        token = auth(request)
        return {'csrf': manager.sessions[token]['csrf'], 'version': 1}

    @app.post('/manager/api/lock')
    async def lock(request: Request):
        await manager.close_session(auth(request, True))
        response = JSONResponse({'locked': True});response.delete_cookie('onlinecoc-ai-manager');return response

    @app.get('/manager/api/providers')
    def providers(request: Request):auth(request);return manager.profiles()

    @app.post('/manager/api/providers')
    async def put_provider(request: Request):
        auth(request, True);data = await body(request)
        require(set(data) == {'profile', 'expectedRevision'} and type(data['expectedRevision']) is int, 'INPUT_INVALID')
        return await asyncio.to_thread(save_profile, data['profile'], manager.config, expected_revision=data['expectedRevision'])

    @app.post('/manager/api/providers/{identifier}/delete')
    async def remove_provider(identifier: str, request: Request):
        auth(request, True);data = await body(request)
        require(set(data) == {'revision'} and type(data['revision']) is int, 'INPUT_INVALID')
        return delete_profile(identifier, data['revision'], manager.config)

    @app.post('/manager/api/providers/{identifier}/credential')
    async def key(identifier: str, request: Request):
        auth(request, True);data = await body(request)
        profile = load_profiles(manager.config).get(identifier);require(profile is not None, 'PROFILE_NOT_FOUND')
        require(set(data) == {'secret'}, 'INPUT_INVALID')
        if data['secret'] is None:manager.vault.remove(profile['credentialRef'])
        else:manager.vault.put(profile['credentialRef'], data['secret'])
        return {'saved': manager.vault.has(profile['credentialRef'])}

    @app.post('/manager/api/providers/{identifier}/probe')
    async def probe(identifier: str, request: Request):
        auth(request, True)
        require(not manager.probe_lock.locked(), 'PROBE_BUSY')
        async with manager.probe_lock:
            profile = load_profiles(manager.config).get(identifier);require(profile is not None, 'PROFILE_NOT_FOUND')
            provider = manager.provider_factory(profile, credential_loader=lambda p: credential(p, vault=manager.vault))
            try:return await provider.probe()
            finally:await provider.close()

    @app.get('/manager/api/rooms')
    def rooms(request: Request):
        token = auth(request)
        return {'items': [{**r, 'connected': (token, r['id']) in manager.clients} for r in manager.rooms.values()]}

    @app.post('/manager/api/rooms')
    async def add_room(request: Request):
        auth(request, True);data = await body(request);require(set(data) == {'name', 'url'}, 'INPUT_INVALID')
        require(local_url(data['url']) != f'http://127.0.0.1:{port}', 'ROOM_URL_INVALID')
        return manager.save_room(data['name'], data['url'])

    @app.post('/manager/api/rooms/{identifier}/login')
    async def login_room(identifier: str, request: Request):return await manager.login_room(auth(request, True), identifier, await body(request))

    @app.post('/manager/api/rooms/{identifier}/request')
    async def room_request(identifier: str, request: Request):return await manager.room_request(auth(request, True), identifier, await body(request))

    @app.post('/manager/api/rooms/{identifier}/delete')
    async def delete_room(identifier: str, request: Request):
        auth(request, True);require(identifier in manager.rooms, 'ROOM_NOT_FOUND')
        require(not any(key[1] == identifier for key in manager.clients), 'ROOM_MUST_BE_DISCONNECTED')
        manager._save_rooms({key: value for key, value in manager.rooms.items() if key != identifier})
        return {'deleted': identifier}

    app.mount('/components', StaticFiles(directory=AI_ROOT / 'web/components'), name='ai-components')
    app.mount('/', StaticFiles(directory=AI_ROOT / 'web/manager', html=True), name='ai-manager')
    return app


def main(argv=None):
    import argparse
    import webbrowser
    import uvicorn
    parser = argparse.ArgumentParser(description='OnlineCOC AI manager (local administrator)')
    parser.add_argument('--config', default=str(DEFAULT_PATH))
    parser.add_argument('--data-dir', default=str(AI_ROOT / '.manager'))
    parser.add_argument('--port', type=int, default=8776)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args(argv)
    require(1 <= args.port <= 65535, 'INPUT_INVALID')
    manager = Manager(args.config, args.data_dir)
    url = f'http://127.0.0.1:{args.port}/#unlock={manager.bootstrap}'
    # Reserve the port before revealing the bootstrap or opening the browser.
    import socket
    with socket.socket() as listener:
        if os.name == 'nt':listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(('127.0.0.1', args.port));listener.listen(128)
        server = uvicorn.Server(uvicorn.Config(create_manager_app(manager, args.port), log_level='warning', access_log=False))
        async def serve():
            async def launch():
                while not server.started and not server.should_exit:await asyncio.sleep(.05)
                if not server.started:return
                # Fragments never enter HTTP request/access logs.
                if args.no_browser:print(url, flush=True)
                else:
                    await asyncio.to_thread(webbrowser.open, url)
                    print(f'AI manager: http://127.0.0.1:{args.port}/', flush=True)
            opener = asyncio.create_task(launch())
            try:await server.serve(sockets=[listener])
            finally:
                opener.cancel()
                await asyncio.gather(opener, return_exceptions=True)
        asyncio.run(serve())
