"""LAN uses the independent networking runtime; no AI implementation imports."""
import asyncio
from pathlib import Path
import sys

ENGINEERING=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ENGINEERING/'network-lan/src'))
from aiohttp import web,ClientSession,DummyCookieJar
from aiohttp.test_utils import TestServer
from onlinecoc_lan.gateway import Gateway,Config


def test_lan_debug_forwards_only_get_and_original_cookie_query():
    async def run():
        seen=[]
        async def upstream(request):
            seen.append({'method':request.method,'query':list(request.query.items()),'cookie':request.headers.get('Cookie')})
            return web.json_response({'forwarded':True})
        app=web.Application();app.router.add_route('*','/{tail:.*}',upstream)
        async with TestServer(app) as origin:
            gateway=Gateway(Config(upstream=str(origin.make_url('/')).rstrip('/'),port=8877))
            async with ClientSession(cookie_jar=DummyCookieJar(),trust_env=False) as session:
                gateway.session=session
                front=web.Application();front.router.add_route('*','/{tail:.*}',gateway.handle)
                async with TestServer(front) as server:
                    gateway.config=Config(upstream=str(origin.make_url('/')).rstrip('/'),port=server.port)
                    url=server.make_url('/api/v1/ai/debug?sessionId=s1&includeContent=true')
                    async with session.get(url,headers={'Cookie':'onlinecoc=original-player'}) as response:
                        assert response.status==200 and response.headers['Cache-Control']=='no-store'
                    assert seen==[{'method':'GET','query':[('sessionId','s1'),('includeContent','true')],'cookie':'onlinecoc=original-player'}]
                    for method,path in [('POST','/api/v1/ai/debug'),('GET','/api/v1/ai/commands'),('GET','/api/v1/host-control/debug')]:
                        async with session.request(method,server.make_url(path),headers={'Origin':gateway.config.url}) as response:
                            assert response.status==404
                    assert len(seen)==1
    asyncio.run(run())
