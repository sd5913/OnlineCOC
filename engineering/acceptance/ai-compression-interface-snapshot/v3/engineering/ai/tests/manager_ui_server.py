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
from onlinecoc.knowledge import HostStateProvider
descriptor=host.register_knowledge_provider({'policyId':'ui-personal','namespace':'ui','providerId':'ui-provider',
    'contractVersion':1,'mode':'required-personal','selectors':[{'kind':'entity','configurationPrefix':'demo.'}],
    'facetSchemas':{'identity':{'schema':{'type':'object'},'modes':['observed_snapshot'],'labelField':'name'}},
    'egress':{k:'filtered' for k in ('view','query','rules','receipts','assets','export','ai')}},HostStateProvider({'identity':{'name':'name'}}))
bound=host.command('kp',{'protocolVersion':1,'type':'command','requestId':'ui-knowledge','roomId':host.state()['roomId'],
    'payload':{'commandId':'ui-knowledge','authorityEpoch':host.epoch,'op':'knowledge.policy.bind',
        'args':{'policyId':descriptor['policyId'],'descriptorDigest':descriptor['descriptorDigest'],'expectedRevision':0}}})
assert bound['status']=='committed',bound
entity=next(iter(host.state()['entities'].values()))
disclosed=host.command('kp',{'protocolVersion':1,'type':'command','requestId':'ui-observe','roomId':host.state()['roomId'],
    'payload':{'commandId':'ui-observe','authorityEpoch':host.epoch,'op':'knowledge.observe','args':{
        'policyId':descriptor['policyId'],'expectedPolicyRevision':1,'subjectMemberId':host.state()['members']['player1']['memberId'],
        'resource':{'namespace':'ui','kind':'entity','id':entity['instanceId']},'facetIds':['identity'],
        'expectedSourceRevision':str(entity['revision']),'reason':'UI fixture explicitly disclosed identity'}}})
assert disclosed['status']=='committed',disclosed
class OfflineProvider:
    async def complete(self,messages,tools):
        output={'kind':'draft','text':'离线验收：新技能默认值 15；已有技能保持 60，需要 KP 判断。','changeSet':loads((ROOT/'rulepacks/demo/ai/examples/skill-15.json').read_bytes())}
        request=json.loads(messages[1]['content'])['request']
        if '批次验收' in request:output={'kind':'batch','text':'将首个对象改名为批次验收名称','actions':[{'target':'host','op':'entity.patch','args':{'id':next(iter(host.state()['entities'])),'name':'批次验收名称'}}]}
        if '玩家咨询验收' in request:output={'kind':'plan','text':'玩家咨询验收回答'}
        if '选项验收' in request:
            output={'kind':'clarification','text':'可以设计一位友好医师。请选择风格。','choices':{'prompt':'NPC 风格',
                'options':[{'id':'friendly','label':'友好医师','text':'采用友好医师方案'},
                           {'id':'mysterious','label':'神秘访客','text':'采用神秘访客方案'}]}}
            refs=json.loads(messages[1]['content']).get('selectedReferences',[])
            if refs:
                ref=refs[0];output['text']=f"参考 {ref['token']}，设计一位友好医师。"
        if request.startswith('采用'):output={'kind':'plan','text':'已按你的选择继续设计。'}
        if json.loads(messages[1]['content']).get('dataAccess',{}).get('mode')=='strict-known':
            output={'kind':'known','evidence':[],'next':'none'}
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
