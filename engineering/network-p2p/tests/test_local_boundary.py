import pytest
from aiohttp import ClientSession

from onlinecoc_p2p.common import Fault
from onlinecoc_p2p.local_app import start_local
from onlinecoc_p2p.ownership import SessionLock


def test_session_lock_is_exclusive_and_released(tmp_path):
    a,b=SessionLock(tmp_path/"lock"),SessionLock(tmp_path/"lock")
    a.acquire()
    with pytest.raises(Fault,match="SESSION_ALREADY_OWNED"):
        b.acquire()
    a.close()
    b.acquire()
    b.close()


async def test_local_capability_origin_and_one_use_sandbox(directory,tmp_path):
    _,url,_=directory
    shell,runner,_=await start_local({"directory":url,"statePath":str(tmp_path)})
    try:
        async with ClientSession() as client:
            async with client.get(shell.origin+"/local/status") as response:
                assert response.status==401
            headers={"Authorization":"Bearer "+shell.capability,"Origin":"https://untrusted.invalid"}
            async with client.post(shell.origin+"/local/package-view",headers=headers,json={"html":"test"}) as response:
                assert response.status==403
            headers["Origin"]=shell.origin
            async with client.post(shell.origin+"/local/package-view",headers=headers,json={"html":"<script>1</script>"}) as response:
                assert response.status==200
                view=await response.json()
            async with client.get(shell.origin+view["url"]) as response:
                assert response.status==200
                assert "sandbox allow-scripts" in response.headers["Content-Security-Policy"]
                assert "allow-same-origin" not in response.headers["Content-Security-Policy"]
            async with client.get(shell.origin+view["url"]) as response:
                assert response.status==404
    finally:
        await runner.cleanup()
