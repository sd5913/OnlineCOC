"""The accepted snapshot end is already outbound; later revocation affects the next view."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'backend/src'),str(ROOT/'backend/tests'),str(ROOT/'data-management')]
from fastapi.testclient import TestClient
from starlette.websockets import WebSocket
from onlinecoc.server import create_app
from test_knowledge import host, install, observe, command
from test_knowledge_network import login


def test_k17_revocation_after_end_enqueue_cannot_retract(host,monkeypatch):
    install(host);grant=observe(host);fired=[]
    original=WebSocket.send_json
    async def send(ws,data,*args,**kwargs):
        if data['type']=='snapshot.end' and not fired:
            # send_json's coroutine starts only after create_task enqueues it,
            # following the lock-protected final authorization check.
            fired.append(True)
            result=command(host,'knowledge.revoke',{'grantId':grant['grantId'],'expectedRevision':1,'reason':'after enqueue'})
            assert result['status']=='committed'
        return await original(ws,data,*args,**kwargs)
    monkeypatch.setattr(WebSocket,'send_json',send)
    with TestClient(create_app(host),base_url='http://127.0.0.1:8765') as c:
        login(c,'player1')
        with c.websocket_connect('ws://127.0.0.1:8765/api/v1/connect',headers={'origin':'http://127.0.0.1:8765'}) as ws:
            views=[];parts=[]
            for _ in range(20):
                frame=ws.receive_json()
                if frame['type']=='snapshot.begin':parts=[]
                if frame['type']=='snapshot.part':parts.append(frame['data'])
                if frame['type']=='snapshot.end':
                    views.append(json.loads(''.join(parts)))
                    if len(views)==2:break
            assert len(views)==2 and fired
            assert views[0]['knowledge']['items']
            assert not views[1]['knowledge']['items']
