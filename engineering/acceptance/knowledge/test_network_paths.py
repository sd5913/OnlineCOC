"""Actual HTTP host behind LAN and P2P upstream, with isolated credentials."""
import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if __name__=='__main__':sys.path.append(str(ROOT/'network-p2p/.venv/Lib/site-packages'))
import pytest
import aiohttp

sys.path[:0]=[str(ROOT/'network-lan/src'),str(ROOT/'network-p2p/src'),str(ROOT/'network-web/src')]

def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));return sock.getsockname()[1]

@pytest.fixture
async def live(tmp_path):
    selected=port();url=f'http://127.0.0.1:{selected}'
    log=(tmp_path/'host.log').open('w',encoding='utf-8')
    process=subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'),'-B',str(Path(__file__)),'--serve',str(tmp_path/'host'),str(selected)],stdout=log,stderr=log)
    try:
        async with aiohttp.ClientSession() as client:
            for _ in range(100):
                assert process.poll() is None,(tmp_path/'host.log').read_text(encoding='utf-8')
                try:
                    async with client.get(url+'/api/v1/capabilities') as r:
                        if r.status==200:break
                except aiohttp.ClientError:pass
                await asyncio.sleep(.05)
            else:raise AssertionError('Host startup timeout')
        yield url
    finally:process.terminate();await asyncio.to_thread(process.wait,10);log.close()

async def test_p2p_upstream_knowledge_routes_and_isolated_peers(live):
    from onlinecoc_p2p.upstream import Upstream
    from onlinecoc_p2p.common import Fault
    one=Upstream(live);two=Upstream(live)
    try:
        for client,name in [(one,'player1'),(two,'player2')]:await client.request('login',{'method':'POST','body':{'loginName':name,'password':'test-password'}})
        assert (await one.request('knowledge/capabilities'))['status']=='ready'
        page=await one.request('knowledge/search',{'method':'POST','body':{}})
        ref=page['items'][0]['ref']
        assert (await one.request('knowledge/read',{'method':'POST','body':{'refs':[ref]}}))['items']
        with pytest.raises(Fault,match='NOT_VISIBLE'):await two.request('knowledge/read',{'method':'POST','body':{'refs':[ref]}})
        with pytest.raises(Fault,match='ROUTE_NOT_EXPOSED'):await one.request('knowledge/provider/install',{'method':'POST','body':{}})
    finally:await one.close();await two.close()

async def test_lan_gateway_knowledge_and_csrf(live):
    from onlinecoc_lan import Config,Gateway
    gateway=Gateway(Config(upstream=live,port=port()));gateway.start()
    try:
        for _ in range(100):
            if gateway.running:break
            await asyncio.sleep(.02)
        assert gateway.running,gateway.error
        url=gateway.config.url
        async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True),headers={'Origin':url}) as client:
            async with client.post(url+'/api/v1/login',json={'loginName':'player1','password':'test-password'}) as r:csrf=(await r.json())['csrf']
            async with client.post(url+'/api/v1/knowledge/search',json={}) as r:assert r.status==403
            async with client.post(url+'/api/v1/knowledge/search',headers={'X-CSRF-Token':csrf},json={}) as r:
                assert r.status==200;ref=(await r.json())['items'][0]['ref']
            async with client.post(url+'/api/v1/knowledge/read',headers={'X-CSRF-Token':csrf},json={'refs':[ref]}) as r:assert (await r.json())['items']
            async with client.post(url+'/api/v1/knowledge/provider/install',headers={'X-CSRF-Token':csrf},json={}) as r:assert r.status==404
    finally:await asyncio.to_thread(gateway.stop)

def test_web_export_has_exact_knowledge_routes(tmp_path):
    from onlinecoc_web.resources import Resources
    source=ROOT/'network-web/examples/core-table';target=Resources.export(source,source/'web.json',tmp_path/'exports')
    routes=Resources(target).descriptor['routes']
    assert {r['path'] for r in routes if r['path'].startswith('knowledge/')}=={'knowledge/capabilities','knowledge/preview','knowledge/search','knowledge/read','knowledge/grants/query'}

if __name__=='__main__':
    sys.path[:0]=[str(ROOT/'backend/src'),str(ROOT/'backend/tests'),str(ROOT/'data-management'),str(ROOT/'network-p2p/.venv/Lib/site-packages')]
    from onlinecoc.host import Host
    from onlinecoc.server import create_app
    from test_knowledge import install,observe
    import uvicorn
    h=Host(sys.argv[2],bootstrap='test-password');install(h);observe(h)
    try:uvicorn.run(create_app(h,int(sys.argv[3])),host='127.0.0.1',port=int(sys.argv[3]),log_level='warning')
    finally:h.close()
