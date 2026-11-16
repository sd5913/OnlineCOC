import asyncio
import json
import os
from pathlib import Path

import pytest

from onlinecoc_p2p.common import atomic_json
from onlinecoc_p2p.host import Host

pytestmark=pytest.mark.skipif(os.environ.get("P2P_CLOUD_TEST")!="1",reason="Explicit cross-machine cloud acceptance")


@pytest.mark.parametrize("relay_only",[True,False])
async def test_windows_host_and_ubuntu_player(upstream,tmp_path,relay_only):
    module=Path(__file__).resolve().parents[1]
    config=json.loads((module/"local/client-config.json").read_text(encoding="utf-8"))
    server=json.loads((module/"local/server.json").read_text(encoding="utf-8"))
    config.update(statePath=str(tmp_path/"cross-host"),upstream=upstream[1],relayOnly=relay_only,
                  settings={"title":"跨机器自动联调","visibility":"private","approvalRequired":False})
    import time
    from onlinecoc_p2p.common import digest,token
    invite=token()
    config["settings"]["invites"]={digest(invite.encode()):{"expires":time.time()+300,"remaining":1}}
    host=Host(config)
    common=["-F","none","-i",str(module/server["keyFile"]),"-o","BatchMode=yes","-o","IdentitiesOnly=yes",
            "-o","StrictHostKeyChecking=yes","-o",'UserKnownHostsFile="'+str(module/"local/ssh-known-hosts").replace("\\","/")+'"',
            "-o","GlobalKnownHostsFile=NUL","-o","ConnectTimeout=10"]
    target=server["user"]+"@"+server["host"]
    async def run(*args,input=None):
        process=await asyncio.create_subprocess_exec(*args,stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try:
            stdout,stderr=await asyncio.wait_for(process.communicate(input),75)
        except BaseException:
            process.kill()
            await process.wait()
            raise
        assert process.returncode==0,stderr.decode(errors="replace")
        return stdout
    try:
        await host.start()
        for source,destination in [("scripts/peer_probe.py","peer_probe.py"),("local/test-ca.pem","test-ca.pem")]:
            await run("scp",*common,"-P",str(server["port"]),str(module/source),
                      target+":/home/ubuntu/onlinecoc-network-deploy/"+destination)
        payload={"directory":config["directory"],"caFile":"/home/ubuntu/onlinecoc-network-deploy/test-ca.pem",
                 "roomId":host.room_id,"invitation":invite,"relayOnly":relay_only}
        result=await run("ssh",*common,"-p",str(server["port"]),target,
            "/opt/onlinecoc-network/venv/bin/python /home/ubuntu/onlinecoc-network-deploy/peer_probe.py",
            input=json.dumps(payload).encode())
        report=json.loads(result)
        assert report["command"] and report["network"]["state"]=="connected"
        atomic_json(module/("local/acceptance/cross-machine-relay.json" if relay_only else "local/acceptance/cross-machine-auto.json"),report)
    finally:
        await host.close()
