"""Versioned package service declaration, with bounded query parameters."""
import re
from onlinecoc_p2p.common import require, loopback_url


def validate_bridge(value):
    require(isinstance(value, dict) and set(value) == {'version', 'service', 'storage'}, 'BRIDGE_INVALID')
    require(value['version'] == 1, 'BRIDGE_VERSION_UNSUPPORTED')
    routes = value['service']
    require(isinstance(routes, list) and 1 <= len(routes) <= 16, 'BRIDGE_INVALID')
    seen = set()
    for route in routes:
        require(set(route) == {'path', 'method', 'query'}, 'BRIDGE_INVALID')
        require(route['method'] in {'GET', 'POST'} and re.fullmatch(r'package/[a-z/-]{1,60}', route['path']), 'BRIDGE_INVALID')
        key = (route['path'], route['method'])
        require(key not in seen and isinstance(route['query'], dict) and len(route['query']) <= 8, 'BRIDGE_INVALID'); seen.add(key)
        for name, values in route['query'].items():
            require(re.fullmatch(r'[a-z]{1,24}', name) and isinstance(values, list) and 1 <= len(values) <= 16, 'BRIDGE_INVALID')
            require(all(isinstance(v, str) and len(v) <= 64 for v in values), 'BRIDGE_INVALID')
    storage = value['storage']
    require(isinstance(storage, list) and len(storage) <= 16 and all(re.fullmatch(r'[a-zA-Z0-9_.-]{1,64}\*?', k) for k in storage), 'BRIDGE_INVALID')
    return value


def service_config(config, descriptor):
    declared = descriptor.get('bridge')
    endpoint = config.get('packageService')
    if not declared:
        require(not endpoint, 'BRIDGE_NOT_DECLARED'); return None
    validate_bridge(declared)
    require(isinstance(endpoint, dict) and set(endpoint) == {'version', 'url', 'packageId', 'packageVersion'}, 'PACKAGE_SERVICE_REQUIRED')
    require(endpoint['version'] == 1 and endpoint['packageId'] == descriptor['package']['id'] and endpoint['packageVersion'] == descriptor['package']['version'], 'PACKAGE_SERVICE_MISMATCH')
    return loopback_url(endpoint['url'])


def service_call(descriptor, params):
    require(isinstance(params, dict) and set(params) <= {'path', 'method', 'query', 'body'}, 'REQUEST_INVALID')
    method, path, query = params.get('method', 'GET'), params.get('path'), params.get('query', {})
    route = next((r for r in descriptor['bridge']['service'] if r['path'] == path and r['method'] == method), None)
    require(route is not None, 'ROUTE_NOT_EXPOSED', 404)
    require(isinstance(query, dict) and set(query) <= set(route['query']), 'QUERY_NOT_EXPOSED', 400)
    require(all(isinstance(v, str) and v in route['query'][k] for k,v in query.items()), 'QUERY_NOT_EXPOSED', 400)
    body = params.get('body')
    require((body is None if method == 'GET' else isinstance(body, dict)), 'REQUEST_INVALID')
    return path, method, query, body
