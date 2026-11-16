"""Verify the generated source bundle from a different working directory."""
import json
import os
import subprocess
import time
import urllib.request
import zipfile
from pathlib import Path

from onlinecoc_p2p.common import atomic_json

root=Path(__file__).resolve().parents[1]
target=root/"local/player-bundle-smoke"
target.mkdir(exist_ok=True)
with zipfile.ZipFile(root/"dist/onlinecoc-player.zip") as archive:
    for item in archive.infolist():
        assert not item.filename.startswith("/") and ".." not in Path(item.filename).parts
    archive.extractall(target)
entry=target/"local/player-session/local-entry.json"
if entry.exists():
    entry.unlink()
env={**os.environ,"PYTHONPATH":str(target/"src"),"PYTHONDONTWRITEBYTECODE":"1"}
log=(root/"local/player-bundle-smoke.log").open("w",encoding="utf-8")
process=subprocess.Popen([str(root/".venv/Scripts/python.exe"),"-m","onlinecoc_p2p","client",
    "--config",str(target/"local/client-config.json"),"--no-browser"],cwd=root.parents[1],env=env,stdout=log,stderr=log)
try:
    for _ in range(80):
        assert process.poll() is None,"Portable client exited"
        if entry.exists():break
        time.sleep(.1)
    assert entry.exists()
    url=json.loads(entry.read_text(encoding="utf-8"))["url"]
    origin,credential=url.split("/#token=")
    request=urllib.request.Request(origin+"/local/status",headers={"Authorization":"Bearer "+credential})
    with urllib.request.urlopen(request,timeout=5) as response:
        status=json.load(response)
    assert status["hostEnabled"] is False
    request=urllib.request.Request(origin+"/control/rooms",data=b"{}",method="POST",
        headers={"Authorization":"Bearer "+credential,"Origin":origin,"Content-Type":"application/json"})
    with urllib.request.urlopen(request,timeout=10) as response:
        assert "items" in json.load(response)
    atomic_json(root/"local/acceptance/player-smoke.json",{"relativeConfig":True,"directoryTls":True,
       "hostPublishingDisabled":True,"sourceBundleLaunched":True})
    print("Player source bundle: launch, relative CA, directory and publisher boundary passed")
finally:
    process.terminate()
    process.wait(timeout=10)
    log.close()
