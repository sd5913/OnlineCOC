"""Public stdin/JSON client for the running Windows host's local control port."""
import base64
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, quote
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from uuid import UUID
from .errors import DomainError, require
from .host_control import protect


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        raise DomainError('HOST_CONTROL_REDIRECT_DENIED')


def _path(value):
    return os.path.normcase(str(Path(value).resolve()))


def _request(record, route, data=None):
    parsed = urlsplit(record['url'])
    require(parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', '::1') and parsed.port
            and not parsed.username and not parsed.password and parsed.path in ('', '/')
            and not parsed.query and not parsed.fragment, 'HOST_CONTROL_DISCOVERY_INVALID')
    key = protect(base64.b64decode(record['protectedKey'], validate=True), decrypt=True).decode('utf-8')
    headers = {'X-OnlineCOC-Instance': record['instanceId'], 'X-OnlineCOC-Host-Key': key}
    body = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=True).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    request = Request(record['url'].rstrip('/') + route, data=body, headers=headers)
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=5) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            require(len(raw) <= 2 * 1024 * 1024, 'LIMIT_EXCEEDED')
            result = json.loads(raw)
            require(isinstance(result, dict), 'HOST_CONTROL_RESPONSE_INVALID')
            return result
    except HTTPError as exc:
        # Preserve sanitized host receipts on rejection/pending, including legacy
        # HTTP status behavior. Never echo arbitrary error bodies or headers.
        try:
            failure = json.loads(exc.read(16384))
            if failure.get('status') in ('pending','rejected') and 'requestId' in failure:
                fields = {'requestId','operation','accountId','status','actor','time','code','requestedRole',
                          'revokedSessions','roomRole','roomActive','disabled','deleted'}
                return {key:value for key,value in failure.items() if key in fields}
            code = failure.get('code','')
            if code and all(char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789' for char in code):
                raise DomainError(code)
        except (ValueError, AttributeError):
            pass
        raise DomainError('HOST_CONTROL_HTTP_' + str(exc.code)) from None
    except (URLError, TimeoutError, OSError):
        raise DomainError('HOST_CONTROL_OUTCOME_UNKNOWN' if data is not None else 'HOST_NOT_RUNNING') from None


def request(data_directory, data, discovery_directory=None):
    require(isinstance(data, dict))
    operation = data.get('operation')
    if operation == 'list':
        require(set(data) == {'operation'})
    elif operation == 'receipt':
        require(set(data) == {'operation', 'requestId'})
        try: UUID(data['requestId'])
        except (ValueError, TypeError, AttributeError): raise DomainError('INPUT_INVALID')
    else:
        require(operation in ('create', 'delete', 'password'))
    directory = Path(discovery_directory) if discovery_directory else Path(os.environ['LOCALAPPDATA']) / 'OnlineCOC/HostControl'
    matched = []
    for file in sorted(directory.glob('*.json')):
        try:
            require(file.stat().st_size <= 16384)
            record = json.loads(file.read_text(encoding='utf-8'))
            if record.get('version') != 1 or _path(record['dataDirectory']) != _path(data_directory):
                continue
            listing = _request(record, '/api/v1/host-control/accounts')
            require(listing.get('instanceId') == record['instanceId'] and listing.get('pid') == record['pid']
                    and _path(listing['dataDirectory']) == _path(data_directory), 'HOST_CONTROL_INSTANCE_MISMATCH')
            matched.append((record, listing))
        except (DomainError, ValueError, KeyError, TypeError, OSError):
            continue  # Stale, partial or foreign discovery records are not hosts.
    require(matched, 'HOST_NOT_RUNNING')
    require(len(matched) == 1, 'HOST_CONTROL_INSTANCE_AMBIGUOUS')
    record, listing = matched[0]
    if operation == 'list':
        return listing
    if operation == 'receipt':
        return _request(record, '/api/v1/host-control/receipts/' + quote(data['requestId'], safe=''))
    return _request(record, '/api/v1/host-control/accounts', data)


def run(data_directory, discovery_directory=None):
    import sys
    try:
        raw = sys.stdin.buffer.read(16385)
        require(len(raw) <= 16384, 'LIMIT_EXCEEDED')
        result = request(data_directory, json.loads(raw.decode('utf-8')), discovery_directory)
    except DomainError as exc:
        print(json.dumps({'status': 'error', 'code': exc.code}))
        return 2
    except Exception:
        print(json.dumps({'status': 'error', 'code': 'HOST_CONTROL_REQUEST_FAILED'}))
        return 2
    print(json.dumps(result, ensure_ascii=True))
    return 2 if result.get('status') in ('rejected', 'pending') else 0
