"""Optional modules via public CLIs only; never write into engineering/."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import socket
import ssl
import time
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from processes import OwnedProcess, run_owned, stop_process

PACK = Path(__file__).resolve().parents[1]
ROOT = PACK.parents[1]


WEB_ERRORS = {
    'WEB_PLATFORM_REQUIRED': ('目录服务器缺少新版开房能力。', '更新联网平台至 network-web 0.3.0 或兼容版本，然后重启网页分享。'),
    'WEB_CONFIG_MISSING': ('找不到联网配置文件。', '检查启动参数 --web-config 或联网模块 local/client-config.json。'),
    'WEB_CONFIG_INVALID': ('联网配置格式或必填字段不正确。', '检查 directory、publisherToken 及 caFile；不要把配置文件发给玩家。'),
    'WEB_RUNTIME_MISSING': ('未找到独立联网 Python 运行环境。', '先按联网模块说明准备运行环境，再启动网页分享。'),
    'WEB_MODULE_MISSING': ('独立联网运行环境尚未安装 network-web 模块。', '按网页模块说明安装本地模块；这不会自动更新云端。'),
    'WEB_CA_MISSING': ('找不到配置指定的 CA 公钥证书。', '检查 caFile 路径；不要关闭证书校验或使用服务器私钥。'),
    'WEB_TLS_FAILED': ('目录服务器的 HTTPS 证书校验失败。', '检查服务器证书与本机 CA 配置是否匹配。'),
    'WEB_DIRECTORY_UNAVAILABLE': ('无法连接目录服务器。', '检查房主网络、目录地址及服务器是否在线，然后重启网页入口。'),
    'WEB_DIRECTORY_TIMEOUT': ('连接目录服务器超时。', '检查网络和服务器状态，然后重试。'),
    'WEB_BRIDGE_REQUIRED': ('目录服务器尚未提供网页包服务桥与存储桥版本 1。', '需要将云端 network-web 更新到 0.2.0 或兼容版本；仅重启本机或修改游戏端口不能补齐云端接口。'),
    'WEB_DIRECTORY_REDIRECT': ('目录地址返回了重定向。', '将 directory 配置为正确的 HTTPS 服务地址。'),
    'WEB_DIRECTORY_HTTP_ERROR': ('目录服务器拒绝了能力检查或发生服务错误。', '检查服务器网关和网页服务状态；具体 HTTP 状态见日志。'),
    'WEB_DIRECTORY_RESPONSE_INVALID': ('目录能力接口返回了无效内容。', '检查 directory 是否指向网页目录服务，排除错误页面或网关拦截。'),
    'WEB_EXPORT_FAILED': ('网页发行包构建或导出失败。', '检查 web.log 中的构建阶段记录；本机游戏仍可使用。'),
    'WEB_EXPORT_CACHE_INVALID': ('已有网页发行缓存未通过完整性校验。', '检查 web.log；缓存内容与本次导出不一致，已保留原文件并停止分享。'),
    'WEB_START_TIMEOUT': ('网页适配器未在规定时间内完成发布。', '检查 web.log 中的目录连接和房间发布错误。'),
    'WEB_START_FAILED': ('网页适配器启动后退出。', '检查 web.log 中的具体错误；可能涉及发布权限、房间占用或模块版本。'),
}


class WebStartError(Exception):
    def __init__(self, code, detail=''):
        self.code, self.detail = code, detail
        super().__init__(code)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def check_web_directory(config):
    """Read-only, credential-free preflight; never interpret an HTTP error as JSON."""
    address = config.get('directory', '')
    try:
        parsed = urllib.parse.urlsplit(address)
        if parsed.port == 0:raise ValueError('invalid port')
    except (ValueError, TypeError):
        raise WebStartError('WEB_CONFIG_INVALID') from None
    if (parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.username or
            parsed.password or parsed.query or parsed.fragment or parsed.path not in {'', '/'} or
            parsed.scheme == 'http' and parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}):
        raise WebStartError('WEB_CONFIG_INVALID')
    try:
        context = ssl.create_default_context(cafile=config.get('caFile'))
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPSHandler(context=context))
        request = urllib.request.Request(address.rstrip('/')+'/v1/web/capabilities', headers={'Accept': 'application/json'})
        with opener.open(request, timeout=10) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise WebStartError('WEB_DIRECTORY_RESPONSE_INVALID')
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise WebStartError('WEB_DIRECTORY_RESPONSE_INVALID')
        if value.get('packageBridge') != 1 or value.get('storageBridge') != 1:
            raise WebStartError('WEB_BRIDGE_REQUIRED')
        if value.get('roomCreation') != 1 or value.get('publicRooms') != 1:
            raise WebStartError('WEB_PLATFORM_REQUIRED')
    except urllib.error.HTTPError as error:
        code = 'WEB_BRIDGE_REQUIRED' if error.code in {404, 405} else 'WEB_DIRECTORY_REDIRECT' if 300 <= error.code < 400 else 'WEB_DIRECTORY_HTTP_ERROR'
        raise WebStartError(code, 'HTTP '+str(error.code)) from None
    except urllib.error.URLError as error:
        code = 'WEB_TLS_FAILED' if isinstance(error.reason, ssl.SSLError) else 'WEB_DIRECTORY_TIMEOUT' if isinstance(error.reason, (TimeoutError, socket.timeout)) else 'WEB_DIRECTORY_UNAVAILABLE'
        raise WebStartError(code) from None
    except ssl.SSLError:
        raise WebStartError('WEB_TLS_FAILED') from None
    except (TimeoutError, socket.timeout):
        raise WebStartError('WEB_DIRECTORY_TIMEOUT') from None
    except FileNotFoundError:
        raise WebStartError('WEB_CA_MISSING') from None
    except (ValueError, UnicodeError):
        raise WebStartError('WEB_DIRECTORY_RESPONSE_INVALID') from None


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def export_tree(path):
    """Fingerprint only regular files; never traverse cache links or junctions."""
    if path.is_symlink() or path.is_junction() or not path.is_dir():
        raise WebStartError('WEB_EXPORT_CACHE_INVALID')
    result = {}
    for directory, dirs, files in os.walk(path, followlinks=False):
        for name in dirs + files:
            child = Path(directory) / name
            if child.is_symlink() or child.is_junction():
                raise WebStartError('WEB_EXPORT_CACHE_INVALID')
        for name in files:
            child = Path(directory) / name
            if not child.is_file() or child.stat().st_nlink != 1:
                raise WebStartError('WEB_EXPORT_CACHE_INVALID')
            result[child.relative_to(path).as_posix()] = hashlib.sha256(child.read_bytes()).hexdigest()
    return result


def export_web_package(root, prefix, options):
    """The CLI requires an empty output; publish a complete immutable export only."""
    root = Path(root).resolve()
    cache = root / 'exports'
    if cache.is_symlink() or cache.is_junction():
        raise WebStartError('WEB_EXPORT_CACHE_INVALID')
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.export-', dir=root) as temporary_name:
        temporary = Path(temporary_name).resolve()
        # Both the rename and TemporaryDirectory cleanup stay inside this room's
        # generated-resource root, never the host archive or another export.
        if temporary.parent != root:
            raise WebStartError('WEB_EXPORT_FAILED')
        exported = run_owned(prefix + ['export', '--source', str(root/'source'),
            '--descriptor', str(root/'source/web.json'), '--output', str(temporary)],
            capture_output=True, text=True, encoding='utf-8', timeout=30, check=True, **options)
        package = Path(exported.stdout.strip()).resolve(strict=True)
        if package.parent != temporary or not re.fullmatch(r'web-[0-9a-f]{64}', package.name):
            raise WebStartError('WEB_EXPORT_FAILED')
        destination = cache / package.name
        if destination.exists() or destination.is_symlink():
            if export_tree(destination) != export_tree(package):
                raise WebStartError('WEB_EXPORT_CACHE_INVALID')
        else:
            package.rename(destination)
        return destination


def ai_snapshot(data):
    """Explicit companion manifest, bound to all author-owned executable files.

    The host's strict AI manifest cannot consume the package's UI metadata.
    No runtime save, credential, or package-private player record is copied.
    """
    manifest = json.loads((PACK / 'manifest.json').read_text(encoding='utf-8'))
    files = {manifest['configurations']: (PACK / manifest['configurations']).read_bytes()}
    for folder, names in (('rules', manifest['rules']), ('config', manifest['data'])):
        for name in names:
            if Path(name).name != name or '/' in name or '\\' in name:
                raise ValueError('Invalid author manifest path')
            files[folder + '/' + name] = (PACK / folder / name).read_bytes()
    files['ai/guide.md'] = (PACK / 'ai/guide.md').read_bytes()
    files['ai/player-guide.md'] = (PACK / 'ai/player-guide.md').read_bytes()
    files['ai/game-terms.json'] = (PACK / 'ai/game-terms.json').read_bytes()
    contract = {
        'schemaVersion': 1, 'packId': manifest['id'], 'packVersion': manifest['version'],
        'hostProtocolRange': {'min': 1, 'max': 1},
        'sources': [{'id': 'stumpsville-guide', 'path': 'ai/guide.md', 'visibility': 'kp'}, {'id':'stumpsville-player-guide','path':'ai/player-guide.md','visibility':'public'}],
        'schemas': {f'config/{name}': f'ai/{name}.schema.json' for name in manifest['data']},
        'checks': 'ai/checks.json', 'scenarios': [], 'metrics': 'ai/metrics.json',
        'reviewChecklist': 'ai/guide.md', 'extensionPoints': [], 'requiredChecks': [], 'requiredMetrics': [],
        'reviewPolicy': {'approvalTtlSeconds': 900, 'items': [], 'allowUnmeasuredOptional': False},
        'contextMapping': {},
    }
    strict = {k: manifest[k] for k in ('id', 'version', 'protocolVersion', 'configurations', 'rules', 'data')}
    strict['ai'] = 'ai/contract.json'
    values = {'manifest.json': strict, 'ai/contract.json': contract, 'ai/checks.json': [], 'ai/metrics.json': []}
    from ai_extensions import materials
    values.update(materials(contract,json.loads(files[manifest['configurations']])))
    from ai_gameplay import materials as gameplay_materials
    values.update(gameplay_materials(contract, json.loads(files[manifest['configurations']]),
        {name: json.loads(files['config/' + name]) for name in manifest['data']}, manifest['rules']))
    files.update({name: (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode('utf-8') for name, value in values.items()})
    digest = hashlib.sha256()
    for name, raw in sorted(files.items()):
        digest.update(name.encode()); digest.update(b'\0'); digest.update(raw)
    target = data / 'integrations' / ('ai-pack-' + digest.hexdigest()[:20])
    for name, raw in files.items():
        path = target / name
        if not path.exists() or path.read_bytes() != raw:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    return target


class Modules:
    def __init__(self, runtime):
        self.runtime = runtime
        self.ai_config = getattr(runtime.args, 'ai_config', None)
        self.ai_pack = None
        self.p2p_config = getattr(runtime.args, 'p2p_config', None)
        self.web_config = getattr(runtime.args, 'web_config', None)
        if self.web_config and self.p2p_config:
            raise ValueError('网页和旧P2P入口只能选择一种')
        if self.web_config and runtime.args.bind != '127.0.0.1':
            raise ValueError('网页分享模式的本机管理页须绑定127.0.0.1')
        self.web_process = self.web_log = self.web_entry = self.web_stop = None
        self.web_error = None
        self.web_error_code = None
        self.web_stage = None
        self.process = self.log = self.entry = None
        self.p2p_error = None
        self.started = False

    def host_args(self):
        knowledge=['--knowledge-provider',str(PACK/'tools/knowledge_provider.py'),
                   '--knowledge-data-path',str(self.runtime.data/'package.json')]
        if not self.ai_config:
            return knowledge
        config = Path(self.ai_config).resolve(strict=True)
        self.ai_pack = ai_snapshot(self.runtime.data)
        return knowledge + ['--ai-config', str(config), '--ai-pack', str(self.ai_pack),
                '--ai-data-adapter', str(PACK / 'tools/ai_data.py'), '--ai-data-path', str(self.runtime.data / 'package.json')]

    def start(self):
        if self.web_config:
            if not self.started:
                self.started = True
                self.start_web()
            return
        if not self.p2p_config or self.started:
            return
        self.started = True
        try:
            source = Path(self.p2p_config).resolve(strict=True)
            original = json.loads(source.read_text(encoding='utf-8-sig'))
            # Explicit settings only. In particular, never reuse another room's
            # identity or export the complete (secret-bearing) Stumpsville pack.
            config = {k: original[k] for k in ('directory', 'publisherToken', 'caFile', 'relayOnly', 'packageBytesPerSecond') if k in original}
            if config.get('caFile'):
                config['caFile'] = str((source.parent / config['caFile']).resolve())
            state = self.runtime.data / 'integrations/p2p-state'
            config.update(upstream=self.runtime.backend, statePath=str(state))
            path = self.runtime.data / 'integrations/p2p-client.json'
            write_json(path, config)
            entry_file = state / 'local-entry.json'
            if entry_file.exists():
                entry_file.unlink()
            python = ROOT / 'engineering/network-p2p/.venv/Scripts/python.exe'
            self.log = (self.runtime.data / 'p2p.log').open('a', encoding='utf-8')
            self.process = OwnedProcess([str(python), '-B', '-m', 'onlinecoc_p2p', 'client', '--config', str(path), '--no-browser'],
                cwd=ROOT / 'engineering/network-p2p', env=self.runtime.env, stdout=self.log, stderr=self.log,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            for _ in range(100):
                if self.process.poll() is not None:
                    raise RuntimeError('P2P_START_FAILED')
                if entry_file.is_file():
                    self.entry = json.loads(entry_file.read_text(encoding='utf-8'))['url']
                    if not getattr(self.runtime.args, 'no_browser', False):
                        webbrowser.open(self.entry)
                    return
                time.sleep(.1)
            raise RuntimeError('P2P_START_TIMEOUT')
        except (OSError, ValueError, KeyError, RuntimeError):
            # Log no credentials or capability URLs; keep the game available.
            self.p2p_error = 'P2P_START_FAILED'
            self.close()

    def status(self):
        try:
            guide_current = bool(self.ai_pack and all((self.ai_pack/name).read_bytes() == (PACK/name).read_bytes() for name in ('ai/guide.md','ai/player-guide.md','ai/game-terms.json')))
        except OSError:
            guide_current = False
        return {'ai': {'available': bool(self.ai_config), 'mode': 'consultation', 'queryMode': 'demand', 'guideCurrent': guide_current},
                'p2p': {'requested': bool(self.p2p_config), 'running': bool(self.process and self.process.poll() is None),
                        'error': self.p2p_error, 'mode': 'basic-host-only'}, 'web': self.web_status()}

    def web_status(self, private=False):
        value={'requested':bool(self.web_config),'running':bool(self.web_process and self.web_process.poll() is None),'error':self.web_error}
        if private and self.web_error_code:
            value.update(errorCode=self.web_error_code,stage=self.web_stage,
                         hint=WEB_ERRORS[self.web_error_code][1],logPath=str(self.runtime.data/'web.log'))
        if self.web_entry and self.web_entry.is_file() and value['running']:
            entry=json.loads(self.web_entry.read_text(encoding='utf-8'))
            value.update(entry if private else {k:v for k,v in entry.items() if k in {'url','roomCode'}})
        return value

    def start_web(self):
        from build_web import build
        self.web_error = self.web_error_code = None
        self.web_stage = '读取联网配置'
        try:
            self.web_log=(self.runtime.data/'web.log').open('a',encoding='utf-8')
            self.web_log.write('\n['+datetime.now().astimezone().isoformat()+'] 网页分享启动检查\n');self.web_log.flush()
            source=Path(self.web_config).resolve()
            if not source.is_file():raise WebStartError('WEB_CONFIG_MISSING')
            try:original=json.loads(source.read_text(encoding='utf-8-sig'))
            except ValueError:raise WebStartError('WEB_CONFIG_INVALID') from None
            if not isinstance(original,dict) or any(not isinstance(original.get(k),str) or not original[k].strip() for k in ('directory','publisherToken')):
                raise WebStartError('WEB_CONFIG_INVALID')
            config={k:original[k] for k in ('directory','publisherToken','caFile','relayOnly') if k in original}
            if config.get('caFile'):
                if not isinstance(config['caFile'],str):raise WebStartError('WEB_CONFIG_INVALID')
                config['caFile']=str((source.parent/config['caFile']).resolve())
                if not Path(config['caFile']).is_file():raise WebStartError('WEB_CA_MISSING')
            python=ROOT/'engineering/network-p2p/.venv/Scripts/python.exe'
            if not python.is_file():raise WebStartError('WEB_RUNTIME_MISSING')
            self.web_stage='检查目录服务器能力'
            check_web_directory(config)
            self.web_stage='构建与导出玩家资源'
            root=self.runtime.data/'integrations/web'
            build(root/'source')
            prefix=[str(python),'-B','-m','onlinecoc_web']
            options={'cwd':ROOT/'engineering/network-web','env':self.runtime.env,'creationflags':getattr(subprocess,'CREATE_NO_WINDOW',0)}
            package=export_web_package(root,prefix,options);state=root/package.name
            state.mkdir(parents=True,exist_ok=True)
            self.web_stop=state/'stop';self.web_stop.unlink(missing_ok=True)
            self.web_entry=state/'web-entry.json';self.web_entry.unlink(missing_ok=True)
            config.update(upstream=self.runtime.backend,statePath=str(state),webPackagePath=str(package),
                settings={'title':'树桩镇 · Stumpsville','maxPlayers':8},webPolicy={'approvalRequired':False},fileBytesPerSecond=1048576,
                packageService={'version':1,'url':self.runtime.origin,'packageId':'stumpsville','packageVersion':self.runtime.pack_version})
            path=root/'host.json';write_json(path,config)
            self.web_stage='启动适配器并发布房间'
            self.web_process=OwnedProcess(prefix+['host','--config',str(path),'--stop-file',str(self.web_stop)],stdout=self.web_log,stderr=self.web_log,**options)
            for _ in range(150):
                if self.web_process.poll() is not None:raise RuntimeError('WEB_START_FAILED')
                if self.web_entry.is_file():
                    self.web_stage='网页分享已启动'
                    if not getattr(self.runtime.args,'no_browser',False):webbrowser.open(config['directory'])
                    return
                time.sleep(.1)
            raise RuntimeError('WEB_START_TIMEOUT')
        except (OSError,ValueError,KeyError,RuntimeError,subprocess.SubprocessError,WebStartError) as error:
            code=error.code if isinstance(error,WebStartError) else 'WEB_START_TIMEOUT' if str(error)=='WEB_START_TIMEOUT' else 'WEB_EXPORT_FAILED' if self.web_stage=='构建与导出玩家资源' else 'WEB_START_FAILED'
            if isinstance(error,subprocess.CalledProcessError):
                if 'No module named onlinecoc_web' in (error.stderr or ''):code='WEB_MODULE_MISSING'
                if self.web_log:self.web_log.write((error.stderr or '')[-8192:]+'\n')
            self.web_error_code=code
            self.web_error=WEB_ERRORS[code][0]
            if self.web_log:
                detail=error.detail if isinstance(error,WebStartError) else type(error).__name__
                self.web_log.write(self.web_stage+' · '+code+' · '+detail+'\n');self.web_log.flush()
            self.stop_web()

    def stop_web(self):
        if self.web_process and self.web_process.poll() is None:
            if self.web_stop:self.web_stop.touch()
            try:self.web_process.wait(timeout=8)
            except subprocess.TimeoutExpired:pass
        stop_process(self.web_process)
        if self.web_log:self.web_log.close()

    def close(self):
        self.stop_web()
        if self.process and self.process.poll() is None:
            if self.entry:
                url = urllib.parse.urlsplit(self.entry)
                origin = url.scheme + '://' + url.netloc
                capability = urllib.parse.parse_qs(url.fragment).get('token', [''])[0]
                try:
                    request = urllib.request.Request(origin + '/local/host/stop', data=b'{}', headers={
                        'Origin': origin, 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + capability})
                    with urllib.request.urlopen(request, timeout=5):
                        pass
                except OSError:
                    pass
        stop_process(self.process)
        if self.log:
            self.log.close()
        self.entry = None
