"""Two real local services with deterministic model results and no WAN."""
import copy
import json
from pathlib import Path
import sys
import threading

from ui_server import ROOT  # Installs the WAN denial audit hook.
import uvicorn
from onlinecoc.host import Host
from onlinecoc.server import create_app
from onlinecoc_ai.runtime import Runtime
from onlinecoc_ai.manager import Manager, create_manager_app
from onlinecoc_ai.vault import Vault
from onlinecoc_ai.contracts import loads, canonical, digest
from onlinecoc_ai.providers.base import Completion

directory=Path(sys.argv[1]);room_port=int(sys.argv[2]);manager_port=int(sys.argv[3])
directory.mkdir(parents=True,exist_ok=True)
config=directory/'profiles.json';value=loads((ROOT/'ai/examples/ai-providers.json').read_bytes());value['profiles'][0]['enabled']=True;config.write_bytes(canonical(value))
host=Host(directory/'host',bootstrap='test-password')
runtime=Runtime(host,config,ROOT/'rulepacks/demo')
class OfflineProvider:
    async def complete(self,messages,tools):
        output={'kind':'draft','text':'离线验收：新技能默认值 15；已有技能保持 60，需要 KP 判断。','changeSet':loads((ROOT/'rulepacks/demo/ai/examples/skill-15.json').read_bytes())}
        return Completion({'role':'assistant','content':canonical(output).decode()},{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20},'stop',digest(output))
    async def probe(self):return {'jsonProbe':'passed','toolProbe':'passed','usage':{'total_tokens':20}}
    async def close(self):pass
runtime.coordinator.provider_factory=lambda profile:OfflineProvider()
room_server=uvicorn.Server(uvicorn.Config(create_app(host,room_port,ai_runtime=runtime),host='127.0.0.1',port=room_port,log_level='warning',access_log=False))
thread=threading.Thread(target=room_server.run,daemon=True);thread.start()
manager=Manager(config,directory/'manager',vault=Vault(directory/'keys.json'),provider_factory=lambda *a,**k:OfflineProvider())
(directory/'entry.json').write_text(json.dumps({'key':manager.bootstrap,'roomPort':room_port,'managerPort':manager_port}),encoding='utf-8')
try:uvicorn.run(create_manager_app(manager,manager_port),host='127.0.0.1',port=manager_port,log_level='warning',access_log=False)
finally:room_server.should_exit=True;thread.join(timeout=10);host.close()
