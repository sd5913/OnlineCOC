"""Player consultation over the authenticated package service bridge.

Never accept an account, upstream URL, credential or arbitrary host route.
The host checks ownership, authority epoch, request identity and arguments.
"""
import re
from urllib.parse import urlsplit, parse_qs
from client import HostError


def consultation(client, payload):
    def reject():
        raise HostError({'httpStatus': 403, 'code': 'AI_ROUTE_NOT_EXPOSED'})

    if not isinstance(payload, dict) or set(payload) - {'path', 'method', 'body'}:
        reject()
    path, method = payload.get('path'), payload.get('method')
    if not isinstance(path, str):
        reject()
    if method == 'GET' and 'body' not in payload:
        if path == 'ai/access':return client.request('/' + path)
        if path == 'capabilities':
            return {'ai': client.request('/capabilities').get('ai', {'available': False})}
        url = urlsplit(path)
        if url.path == 'ai/usage' and not url.scheme and not url.netloc and not url.fragment:
            query = parse_qs(url.query, keep_blank_values=True)
            if set(query) <= {'from','to','scope','profileId','sessionId','before','limit'} and all(len(v)==1 and 1<=len(v[0])<=200 for v in query.values()):
                return client.request('/' + path)
        if url.path == 'ai/references' and not url.scheme and not url.netloc and not url.fragment:
            query = parse_qs(url.query, keep_blank_values=True)
            if set(query) == {'kind', 'q'} and all(len(v) == 1 for v in query.values()) and query['kind'][0] in {'knowledge'} and len(query['q'][0]) <= 120:
                return client.request('/' + path)
        if path in {'ai/sessions?archived=false', 'ai/sessions?archived=true'} or re.fullmatch(r'ai/(?:sessions|receipts)/[a-zA-Z0-9_-]{1,128}', path):
            return client.request('/' + path)
    if method == 'POST' and path == 'ai/references/resolve':
        body = payload.get('body')
        if isinstance(body, dict) and set(body) == {'tokens'} and isinstance(body['tokens'], list) and len(body['tokens']) <= 12 and all(isinstance(t, str) and len(t) <= 1700 for t in body['tokens']):
            return client.request('/ai/references/resolve', body)
    if method == 'POST' and path in {'ai/data/search','ai/data/read','ai/data/chat','ai/data/case'}:
        body=payload.get('body')
        if isinstance(body,dict):return client.request('/'+path,body)
    if method == 'POST' and path == 'ai/commands':
        body = payload.get('body')
        if not isinstance(body, dict) or set(body) != {'requestId', 'authorityEpoch', 'op', 'args'}:
            reject()
        if body['op'] in {'ai.session.create', 'ai.session.update', 'ai.session.submit', 'ai.session.delete', 'ai.request.cancel', 'ai.knowledge.request', 'ai.player.request'}:
            return client.request('/ai/commands', body)
    reject()
