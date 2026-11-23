"""Public HTTP protocol client, used by pack tools and black-box tests."""
import http.cookiejar
import json
import urllib.error
import urllib.request
import uuid

import httpx


class RejectCookies(http.cookiejar.DefaultCookiePolicy):
    """A shared connection pool must never become a shared login session."""
    def set_ok(self, cookie, request):
        return False

    def return_ok(self, cookie, request):
        return False


def stateless_cookies():
    return http.cookiejar.CookieJar(policy=RejectCookies())


class HostError(RuntimeError):
    def __init__(self, response):
        self.response = response
        super().__init__(str(response))


class Client:
    def __init__(self, base, name, password):
        self.base, self.csrf = base.rstrip('/'), None
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.csrf = self.request('/login', {'loginName': name, 'password': password})['csrf']

    def request(self, path, body=None):
        if body is not None and not self.csrf and getattr(self, 'defer_csrf', False):
            self.csrf = self.request('/me')['csrf']
        headers = {'Origin': self.base, 'Content-Type': 'application/json'}
        if self.csrf:
            headers['X-CSRF-Token'] = self.csrf
        # Runtime requests reuse TCP connections, with credentials supplied for
        # this request only. Standalone CLI/test clients keep their private jar.
        transport = getattr(self, 'transport', None)
        if transport is not None:
            headers['Cookie'] = self.cookie
            try:
                response = transport.request('GET' if body is None else 'POST',
                    self.base + '/api/v1' + path, headers=headers,
                    content=None if body is None else json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
                try:
                    value = response.json()
                except (ValueError, UnicodeError) as error:
                    if response.is_success:
                        raise HostError({'code':'HOST_RESPONSE_INVALID','httpStatus':502,
                            'message':'主机响应格式异常，无法确认本次请求结果','operation':path}) from error
                    value = {}
                if not response.is_success:
                    value = value if isinstance(value, dict) else {}
                    raise HostError({**value,'httpStatus':response.status_code,'operation':path,
                        'code':value.get('code') or 'HOST_HTTP_ERROR',
                        'message':value.get('message') or ('主机返回 HTTP '+str(response.status_code))})
                return value
            except httpx.HTTPError as error:
                timeout = isinstance(error, httpx.TimeoutException)
                network = isinstance(error, httpx.NetworkError)
                raise HostError({'code':'HOST_TIMEOUT' if timeout else 'HOST_UNREACHABLE' if network else 'HOST_PROTOCOL_ERROR',
                    'httpStatus':503 if timeout or network else 502,
                    'message':'等待主机响应超时' if timeout else '无法连接本机主机服务' if network else '主机连接协议异常',
                    'operation':path,'errorKind':type(error).__name__}) from error
        req = urllib.request.Request(self.base + '/api/v1' + path,
                                     data=None if body is None else json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8'),
                                     headers=headers)
        try:
            with self.opener.open(req, timeout=25) as r:
                try:
                    return json.load(r)
                except (ValueError, UnicodeError) as error:
                    raise HostError({'code':'HOST_RESPONSE_INVALID', 'httpStatus':502,
                        'message':'主机响应格式异常，无法确认本次请求结果', 'operation':path}) from error
        except urllib.error.HTTPError as e:
            try:
                value = json.loads(e.read())
                if not isinstance(value, dict):
                    value = {}
            except (ValueError, UnicodeError):
                value = {}
            raise HostError({**value, 'httpStatus':e.code, 'operation':path,
                'code':value.get('code') or 'HOST_HTTP_ERROR',
                'message':value.get('message') or ('主机返回 HTTP ' + str(e.code))}) from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            timeout = isinstance(getattr(e, 'reason', e), TimeoutError)
            raise HostError({'code':'HOST_TIMEOUT' if timeout else 'HOST_UNREACHABLE', 'httpStatus':503,
                'message':'等待主机响应超时' if timeout else '无法连接本机主机服务', 'operation':path,
                'errorKind':type(getattr(e,'reason',e)).__name__, 'osError':getattr(getattr(e,'reason',e),'errno',None)}) from e

    def envelope(self, op, args, *, view=None):
        if view is None:
            view = self.request('/view')
        return {'protocolVersion': 1, 'type': 'command', 'requestId': str(uuid.uuid4()),
                'roomId': view['roomId'], 'payload': {
                    'commandId': str(uuid.uuid4()), 'authorityEpoch': view['authorityEpoch'],
                    'runId': view['runId'], 'catalogRevision': view['catalog']['revision'],
                    'rulesetRevision': view['catalog']['rulesetRevision'],
                    'expectedViews': {}, 'op': op, 'args': args}}

    def send(self, envelope):
        receipt = self.request('/commands', envelope)
        if receipt['status'] != 'committed':
            raise HostError(receipt)
        return receipt

    def command(self, op, args):
        return self.send(self.envelope(op, args))['result']

    def invoke(self, action, **inputs):
        return self.command('action.invoke', {'actionId': action, 'input': inputs})
