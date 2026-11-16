import asyncio
import time

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from onlinecoc_p2p.client import Player
from onlinecoc_p2p.common import Fault
from onlinecoc_p2p.host import Host
from onlinecoc_p2p.rooms import PASSWORDS


async def until(predicate):
    for _ in range(100):
        if predicate():return
        await asyncio.sleep(.02)
    raise AssertionError("State did not arrive")


async def test_approval_reject_and_password(hosted):
    host,_,url,_=hosted
    config=dict(host.settings,approvalRequired=True,passwordVerifier=PASSWORDS.hash("room-test"))
    await host.patch(config,host.room["revision"])
    a=Player(url)
    try:
        with pytest.raises(Fault,match="ROOM_UNAVAILABLE"):
            await a.join(host.room_id,password="bad")
        assert not host.pending
        task=asyncio.create_task(a.join(host.room_id,password="room-test"))
        await until(lambda: bool(host.pending))
        assert not task.done()
        await host.decide(next(iter(host.pending)),False)
        with pytest.raises(Fault,match="JOIN_REJECTED"):await task
    finally:
        await a.close()


async def test_ticket_requires_original_client_private_key(hosted):
    host,_,url,_=hosted
    player=Player(url)
    try:
        await player.start()
        player.identity=ec.generate_private_key(ec.SECP256R1())
        with pytest.raises(Fault):await player.join(host.room_id)
        assert not any(p.proved for p in host.peers.values())
    finally:
        await player.close()


async def test_account_ban_persists_across_host_restart(hosted,tmp_path):
    host,_,url,_=hosted
    a=Player(url)
    try:
        await a.join(host.room_id)
        await a.request("login","POST",{"loginName":"alice","password":"test-only"})
        await a.prepare(tmp_path/"a")
        await host.kick(next(iter(host.peers)),True)
        await host.close()
        restarted=Host(host.config)
        await restarted.start()
        b=Player(url)
        try:
            await b.join(restarted.room_id)
            with pytest.raises(Fault,match="MEMBER_BANNED"):
                await b.request("login","POST",{"loginName":"alice","password":"test-only"})
            assert not any(p.account for p in restarted.peers.values())
        finally:
            await b.close()
            await restarted.close()
    finally:
        await a.close()


async def test_new_lease_epoch_and_old_token_rejected(hosted):
    host,service,url,_=hosted
    old_token,old_epoch=host.lease_token,host.room["connectionEpoch"]
    service.store.leases[host.room_id]["expires"]=time.time()-1
    await host.republish()
    await until(lambda: service.store.leases[host.room_id]["connected"])
    assert host.room["connectionEpoch"]==old_epoch+1
    with pytest.raises(Fault,match="LEASE_INVALID"):
        await host.control.request("POST","/v1/rooms/"+host.room_id+"/heartbeat",old_token)
