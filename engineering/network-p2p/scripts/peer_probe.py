"""Remote client acceptance; read config from stdin, never from process args."""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

from onlinecoc_p2p.client import Player


async def main(config):
    relay_only=config.get("relayOnly",True)
    player=Player(config["directory"],config.get("caFile"),relay_only=relay_only)
    try:
        await player.join(config["roomId"],invitation=config.get("invitation",""))
        await player.request("login","POST",{"loginName":"alice","password":"test-only"})
        with tempfile.TemporaryDirectory(prefix="onlinecoc-probe-") as folder:
            await player.prepare(Path(folder))
        account=(await player.request("me"))["accountId"]
        receipt=await player.request("commands","POST",{"commandId":"cross-machine","op":"roll"})
        assert account=="alice" and receipt["count"]==1
        if relay_only:
            assert all(p["localType"]=="relay" for p in player.network()["pairs"])
        print(json.dumps({"accountIsolation":True,"command":True,"network":player.network(),
                          "endpoint":"Ubuntu CVM peer to Windows host","relayOnly":relay_only}),flush=True)
    finally:
        await player.close()


if __name__=="__main__":
    asyncio.run(main(json.load(sys.stdin)))
