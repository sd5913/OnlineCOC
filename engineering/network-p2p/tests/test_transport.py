import asyncio

import pytest

from onlinecoc_p2p.client import Player
from onlinecoc_p2p.common import Fault
from onlinecoc_p2p.control import Control


async def enter(host, url, path, login):
    player = Player(url)
    await player.join(host.room_id)
    await player.request("login", "POST", {"loginName": login, "password": "test-only"})
    await player.prepare(path)
    return player


async def test_real_webrtc_two_players_isolated_and_replay(hosted, tmp_path):
    host, service, url, fixture = hosted
    alice, bob = None, None
    try:
        alice = await enter(host, url, tmp_path / "a", "alice")
        bob = await enter(host, url, tmp_path / "b", "bob")
        assert (await alice.request("me"))["accountId"] == "alice"
        assert (await bob.request("me"))["accountId"] == "bob"
        first = await alice.request("commands", "POST", {"commandId": "same", "op": "roll"})
        again = await alice.request("commands", "POST", {"commandId": "same", "op": "roll"})
        assert first == again and fixture.count == 1
        other = await bob.request("commands", "POST", {"commandId": "same", "op": "roll"})
        assert other["count"] == 2
        with pytest.raises(Fault, match="PERMISSION_DENIED"):
            await alice.request("commands", "POST", {"commandId": "kp", "op": "kp-only"})
        with pytest.raises(Fault, match="ROUTE_NOT_EXPOSED"):
            await alice.request("host-control/accounts")
        with pytest.raises(Fault, match="ROUTE_NOT_EXPOSED"):
            await alice.request("../admin")
        assert alice.network()["state"] == "connected"
        assert all(p["localType"] == "host" for p in alice.network()["pairs"])
        await alice.rpc("subscribe")
        assert (await asyncio.wait_for(alice.states.get(), 5))["type"] == "snapshot.begin"
    finally:
        for player in (alice, bob):
            if player:
                await player.close()


async def test_ready_required_before_commands(hosted, tmp_path):
    host, service, url, _ = hosted
    player = Player(url)
    try:
        await player.join(host.room_id)
        with pytest.raises(Fault, match="CONTENT_NOT_READY"):
            await player.request("view")
        await player.request("login", "POST", {"loginName": "alice", "password": "test-only"})
        with pytest.raises(Fault, match="CONTENT_NOT_READY"):
            await player.request("commands", "POST", {"commandId": "early"})
        await player.prepare(tmp_path / "cache")
        assert (await player.request("view"))["accountId"] == "alice"
    finally:
        await player.close()


async def test_unauthorized_turn_and_publish(directory):
    _, url, _ = directory
    client = Control(url)
    try:
        with pytest.raises(Fault, match="PUBLISHER_AUTH_REQUIRED"):
            await client.request("POST", "/v1/rooms", "bad", {})
        with pytest.raises(Fault, match="TURN_NOT_AUTHORIZED"):
            await client.request("POST", "/v1/turn-credentials", "bad", {"intentId": "missing"})
    finally:
        await client.close()


async def test_real_datachannel_multiblock_package_and_cached_rejoin(directory, upstream, tmp_path):
    from onlinecoc_p2p.common import atomic_json, digest
    from onlinecoc_p2p.host import Host
    from onlinecoc_p2p.packages import Package
    source=tmp_path/"public"
    source.mkdir()
    raw=bytes(range(256))*2500
    (source/"map.dat").write_bytes(raw)
    atomic_json(source/"distribution.json",{"packageId":"multiblock","version":"1","entry":None,"files":["map.dat"]})
    exported=Package.export(source,source/"distribution.json",tmp_path/"export")
    _,url,publisher=directory
    host=Host({"directory":url,"publisherToken":publisher,"upstream":upstream[1],"statePath":str(tmp_path/"host"),
               "packagePath":str(exported),"settings":{"visibility":"public","approvalRequired":False}})
    player=Player(url)
    try:
        await host.start()
        await player.join(host.room_id)
        await player.request("login","POST",{"loginName":"alice","password":"test-only"})
        first=await player.prepare(tmp_path/"cache")
        assert first["downloadedBytes"]==len(raw)
        assert (tmp_path/"cache/blobs"/digest(raw)).read_bytes()==raw
        assert (await player.prepare(tmp_path/"cache"))["downloadedBytes"]==0
    finally:
        await player.close()
        await host.close()
