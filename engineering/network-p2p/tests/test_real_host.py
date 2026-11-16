import asyncio
import json
import os
import socket
import subprocess
import uuid
from pathlib import Path

import aiohttp
import pytest

from onlinecoc_p2p.client import Player
from onlinecoc_p2p.common import Fault, atomic_json
from onlinecoc_p2p.host import Host
from onlinecoc_p2p.upstream import Upstream

MODULE=Path(__file__).resolve().parents[1]
pytestmark=pytest.mark.skipif(os.environ.get("P2P_REAL_HOST_TEST")!="1",reason="Explicit real backend acceptance")


@pytest.fixture
async def real_upstream(tmp_path):
    snapshot=Path(os.environ.get("P2P_BACKEND_ROOT",str(MODULE.parent)))
    assert snapshot.exists(), "Create a pinned git archive for the real backend first."
    python=MODULE.parent/".venv/Scripts/python.exe"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1",0));port=probe.getsockname()[1]
    log=(tmp_path/"real-host.log").open("w",encoding="utf-8")
    process=subprocess.Popen([str(python),str(MODULE/"scripts/real_host_fixture.py"),"--snapshot",str(snapshot),
                              "--data-dir",str(tmp_path/"data"),"--port",str(port),
                              "--host-control-dir",str(tmp_path/"discovery")],stdout=log,stderr=log,
                              env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"})
    url=f"http://127.0.0.1:{port}"
    try:
        async with aiohttp.ClientSession() as http:
            for _ in range(100):
                assert process.poll() is None, "Real backend exited; inspect isolated log"
                try:
                    async with http.get(url+"/api/v1/capabilities") as response:
                        if response.status==200:break
                except aiohttp.ClientError:pass
                await asyncio.sleep(.1)
            else:raise AssertionError("Real backend startup timeout")
        yield url,process
    finally:
        process.terminate()
        await asyncio.to_thread(process.wait,10)
        log.close()


def command(view,op,args,cid=None):
    return {"protocolVersion":1,"type":"command","requestId":str(uuid.uuid4()),"roomId":view["roomId"],
            "payload":{"commandId":cid or str(uuid.uuid4()),"runId":view["runId"],
             "authorityEpoch":view["authorityEpoch"],"catalogRevision":view["catalog"]["revision"],
             "rulesetRevision":view["catalog"]["rulesetRevision"],"expectedViews":{},"op":op,"args":args}}


async def test_real_backend_two_players_via_public_relay(real_upstream,tmp_path):
    assert os.environ.get("P2P_CLOUD_TEST")=="1","This acceptance requires the configured cloud relay"
    config=json.loads((MODULE/"local/client-config.json").read_text())
    upstream_url,process=real_upstream
    config.update(statePath=str(tmp_path/"host"),upstream=upstream_url,relayOnly=True,
                  settings={"title":"真实宿主自动验收","visibility":"private","approvalRequired":False})
    # Private membership uses a single-use capability per joining player.
    from onlinecoc_p2p.common import digest
    import time
    invite="acceptance-"+uuid.uuid4().hex
    config["settings"]["invites"]={digest(invite.encode()):{"expires":time.time()+600,"remaining":2}}
    host=Host(config)
    players=[Player(config["directory"],config["caFile"],relay_only=True) for _ in range(2)]
    kp=Upstream(upstream_url)
    try:
        await host.start()
        listing=await host.control.request("GET","/v1/rooms")
        assert host.room_id not in [r["roomId"] for r in listing["items"]]
        for index,player in enumerate(players,1):
            await player.join(host.room_id,invitation=invite)
            await player.request("login","POST",{"loginName":"player"+str(index),"password":"p2p-test-only-password"})
            await player.prepare(tmp_path/("cache"+str(index)))
        a,b=players
        view=await a.request("view")
        assert view["accountId"]=="player1" and "secret-clue" not in view["entities"]
        assert "passwordHash" not in json.dumps(view)
        assert (await b.request("view"))["accountId"]=="player2"
        payload=command(view,"action.invoke",{"actionId":"demo.damage","input":{"actor":"actor-player1","amount":7}})
        first=await a.request("commands","POST",payload)
        assert first["status"]=="committed",first
        assert await a.request("commands","POST",payload)==first
        assert (await b.request("view"))["entities"]["actor-player1"]["numbers"]["hp"]==4
        sent=await a.request("commands","POST",command(await a.request("view"),"chat.message.send",{"channelId":"general","text":"P2P real-host acceptance"}))
        assert sent["status"]=="committed"
        assert (await b.request("chat/history","POST",{"channelId":"general","limit":10}))["items"][0]["text"]=="P2P real-host acceptance"
        with pytest.raises(Fault,match="ROUTE_NOT_EXPOSED"):
            await a.request("host-control/accounts")
        await a.rpc("subscribe")
        assert (await asyncio.wait_for(a.states.get(),10))["type"]=="snapshot.begin"
        await kp.request("login",{"method":"POST","body":{"loginName":"kp","password":"p2p-test-only-password"}})
        await kp.request("commands",{"method":"POST","body":command(await kp.request("view"),"member.update",{"accountId":"player1","active":False})})
        for _ in range(50):
            event=await asyncio.wait_for(a.states.get(),10)
            if event["type"]=="reset":break
        else:raise AssertionError("Revocation did not clear the projection")
        with pytest.raises(Fault):
            await a.request("view")
        atomic_json(MODULE/"local/acceptance/real-host.json",{"backend":"current working tree; source hashes in acceptance report",
          "players":2,"privateRoomHidden":True,"accountIsolation":True,"hiddenEntityAbsent":True,"idempotence":True,
          "sharedState":True,"chat":True,"hostControlDenied":True,"revocationReset":True,
          "networks":[p.network() for p in players]})
        await host.close()
        assert process.poll() is None,"Borrowed game host must survive adapter shutdown"
        assert (await kp.request("me"))["accountId"]=="kp"
    finally:
        for p in players:await p.close()
        await host.close()
        await kp.close()


async def test_real_backend_registered_host_discovery(real_upstream, tmp_path):
    from onlinecoc_p2p.discovery import discover
    upstream_url, process = real_upstream
    items = await discover({"hostDiscoveryPath": str(tmp_path / "discovery"), "upstream": upstream_url})
    assert len(items) == 1
    assert items[0]["url"] == upstream_url and items[0]["source"] == "registered"
    assert items[0]["dataDirectory"] == str((tmp_path / "data").resolve())
    assert "protectedKey" not in json.dumps(items)
    assert process.poll() is None
