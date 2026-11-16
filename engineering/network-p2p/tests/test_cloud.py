import asyncio
import json
import os
from pathlib import Path

import pytest

from onlinecoc_p2p.client import Player
from onlinecoc_p2p.common import Fault, atomic_json
from onlinecoc_p2p.control import Control
from onlinecoc_p2p.host import Host

pytestmark=pytest.mark.skipif(os.environ.get("P2P_CLOUD_TEST")!="1",reason="Explicit live cloud acceptance")


@pytest.mark.parametrize("protocol",["udp","tcp"])
async def test_public_directory_and_forced_relay(upstream,tmp_path,protocol):
    config=json.loads(Path("local/client-config.json").read_text())
    _,upstream_url=upstream
    config.update(statePath=str(tmp_path/"host"),upstream=upstream_url,relayOnly=True,
                  settings={"title":"自动联调临时房间","visibility":"public","approvalRequired":False})
    host=Host(config)
    player=Player(config["directory"],config["caFile"],relay_only=True)
    original_host=host.control.request
    original_player=player.control.request
    def select(original):
        async def request(method,path,credential=None,data=None):
            value=await original(method,path,credential,data)
            if path=="/v1/turn-credentials":
                for server in value["iceServers"]:
                    server["urls"]=[url for url in server["urls"] if url.endswith("="+protocol)]
            return value
        return request
    host.control.request=select(original_host)
    player.control.request=select(original_player)
    try:
        health=await host.control.request("GET","/health")
        assert health["status"]=="ok"
        with pytest.raises(Fault,match="PUBLISHER_AUTH_REQUIRED"):
            await player.control.request("POST","/v1/rooms","invalid",{})
        with pytest.raises(Fault,match="TURN_NOT_AUTHORIZED"):
            await player.control.request("POST","/v1/turn-credentials","invalid",{"intentId":"missing"})
        await host.start()
        assert len(host.room["roomCode"]) == 8
        await player.join(room_code=host.room["roomCode"])
        await player.request("login","POST",{"loginName":"alice","password":"test-only"})
        await player.prepare(tmp_path/"cache")
        assert (await player.request("me"))["accountId"]=="alice"
        receipt=await player.request("commands","POST",{"commandId":"relay-test","op":"roll"})
        assert receipt["count"]==1
        await player.rpc("subscribe")
        assert (await asyncio.wait_for(player.states.get(),10))["type"]=="snapshot.begin"
        network=player.network()
        assert network["state"]=="connected" and network["pairs"]
        assert all(p["localType"]=="relay" and p["remoteType"]=="relay" for p in network["pairs"])
        atomic_json(Path("local/acceptance")/("cloud-"+protocol+".json"),
                    {"transport":protocol,"network":network,"health":health,"commands":"passed","shortCodeJoin":True,
                     "snapshot":"passed","certificateValidation":True,"unauthorizedRejected":True,
                     "topology":"two local endpoints forced through public CVM relay"})
    finally:
        await player.close()
        await host.close()


async def test_public_browser_relay_and_package(upstream,tmp_path):
    from test_browser import test_browser_room_login_download_sandbox_and_state
    config=json.loads(Path("local/client-config.json").read_text(encoding="utf-8"))
    await test_browser_room_login_download_sandbox_and_state((None,config["directory"],config["publisherToken"]),upstream,tmp_path)
