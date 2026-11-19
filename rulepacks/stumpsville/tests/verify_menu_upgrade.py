"""v1 -> v2 disclosure upgrade over public HTTP; old data never silently refreshed."""
import json
import secrets
from datetime import datetime
from unittest.mock import patch
from harness import PACK, Account, provision, running
from integrations import Modules
from processes import stop_process
from verify_integrations import provider, ai, result
from verify_menu_knowledge import answer, ask, scene, choices
from verify_strict_known import known


def restart(runtime):
    stop_process(runtime.process)
    runtime.start()


def main():
    output=PACK/'tests/output'/('menu-upgrade-'+secrets.token_hex(4));output.mkdir(parents=True)
    legacy=output/'old-provider.py'
    legacy.write_text('''import importlib.util, copy
from pathlib import Path
spec=importlib.util.spec_from_file_location('new_provider', Path('''+repr(str(PACK/'tools/knowledge_provider.py'))+'''))
current=importlib.util.module_from_spec(spec);spec.loader.exec_module(current)
def descriptor():
 d=current.descriptor();d['providerId']='stumpsville-known-v1'
 for f in d['facetSchemas'].values():f['schema']={'type':'object'}
 return d
class Provider(current.Provider):
 def pin(self,resource,facets,context):
  out=super().pin(resource,facets,context)
  if 'scene' in facets:
   value=out['facets']['scene'];artifact=context['state']['artifacts'][context['state']['activeRuleset']]
   value['actions']=[current.scene_knowledge.plain_definition(a) for a in artifact['data']['scene-actions.json']['actions'] if a['location']==value['index']]
  out['sourceGuard']={k:v for k,v in out['sourceGuard'].items() if k in ('entityId','configurationId')}
  return out
 def check_guard(self,guard,context):
  value=context['state']['entities'].get(guard.get('entityId'))
  return bool(value and not value['metadata'].get('knowledgeRevoked'))
def install(host,path=None):return host.register_knowledge_provider(descriptor(),Provider(path))
''',encoding='utf-8')
    original=Modules.host_args
    def old_args(modules):
        args=original(modules);args[args.index('--knowledge-provider')+1]=str(legacy);return args
    checks=[]
    with provider(output,answer) as (config,calls), patch.object(Modules,'host_args',old_args):
        with running('menu-upgrade',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
            kp,p1,_=provision(runtime,password)
            kp.action('location.publish',{'index':3,'clues':[]})
            kp.command('entity.update',{'id':p1.state()['character']['instanceId'],'numbers':{'location':3}})
            old=scene(p1,3)
            assert 'money' in choices(old['data']['actions'],'courtyard-pool')
            result(ai(kp,'ai.access.update',{'revision':1,'allowPlayerChat':True,'autoApproveBatches':False}))
            result(ai(kp,'ai.settings.update',{'enabled':True,'profileId':'offline','externalSources':{'public':True,'private':True,'kp':True},'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}))
            session,reply=ask(p1)
            assert '钱袋' in reply['response']
            checks.append('isolated stock-v1 fixture reproduces unsafe raw menu evidence and AI reply before upgrade')
            runtime.modules.host_args=lambda:original(runtime.modules)
            restart(runtime)
            kp=Account(runtime.origin,'kp',password,'up-kp');p1=Account(runtime.origin,'player1',password,'up-p1')
            assert p1.request('/api/v1/knowledge/capabilities')['status']=='blocked'
            assert not p1.state()['sceneActions']
            assert 'items' not in p1.request('/api/v1/knowledge/read',{'refs':[old['ref']]},allow_error=True)
            assert not p1.request('/api/v1/ai/sessions/'+session['sessionId'])['items'][-1].get('response')
            checks.append('new provider before explicit bind blocks old references, UI menus and prior AI answers')
            kp.action('knowledge.enable')
            assert p1.request('/api/v1/knowledge/capabilities')['status']=='ready'
            assert not any(i['facetId']=='scene' for i in known(p1))
            assert p1.state()['character']['owner']=='player1' and p1.state()['session']
            assert not any(i['facetId']=='scene' for i in p1.request('/api/v1/knowledge/search',{'includeHistory':True,'limit':50})['items'])
            assert 'items' not in p1.request('/api/v1/knowledge/read',{'refs':[old['ref']]},allow_error=True)
            assert not p1.request('/api/v1/ai/sessions/'+session['sessionId'])['items'][-1].get('response')
            checks.append('explicit bind preserves safe live sheet/play, invalidates all old fixed observations without automatically redisclosing any scene')
            kp.action('location.reveal',{'index':3,'accounts':['player1']})
            safe=scene(p1,3)
            assert safe['ref']!=old['ref'] and safe['observedAt']>=old['observedAt']
            assert choices(safe['data']['actions'],'courtyard-pool')==['inspect']
            assert '钱袋' not in json.dumps(safe,ensure_ascii=False)
            checks.append('explicit reveal produces a new safe snapshot; old knowledge handles and history remain unusable')
            restart(runtime)
            p1=Account(runtime.origin,'player1',password,'up-restart')
            assert p1.request('/api/v1/knowledge/read',{'refs':[safe['ref']]})['items'][0]==safe
            checks.append('new observation is byte-identical after restart')
            runtime.modules.host_args=lambda:old_args(runtime.modules);restart(runtime)
            p1=Account(runtime.origin,'player1',password,'up-rollback')
            assert p1.request('/api/v1/knowledge/capabilities')['status']=='blocked'
            assert 'items' not in p1.request('/api/v1/knowledge/read',{'refs':[old['ref']]},allow_error=True)
            checks.append('reinstalling the old provider without an explicit rebind cannot reopen old observations')
    report={'checkedAt':datetime.now().astimezone().isoformat(),'passed':len(checks),'checks':checks,
        'output':str(output),'realSaveChanged':False,'realProviderCalls':0}
    (PACK/'tests/menu-upgrade-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
