"""Version 2 fixtures: real isolated records, catalog namespaces and explicit intent.

Expected outputs and engine dice/oracles never enter generation inputs. Each
case's durable store permits an independent execution replay of model output.
"""
import copy
import importlib.util
import json
import shutil
import sys
import time
from pathlib import Path
from types import SimpleNamespace
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];ENG=ROOT/'engineering'
sys.path[:0]=[str(ENG/'ai/src'),str(ENG/'backend/src'),str(ENG/'data-management'),str(ENG/'ai/tests')]
from onlinecoc.host import Host
from onlinecoc.model import entity
from onlinecoc.registry import stage
from onlinecoc_ai.api import Application
from onlinecoc_ai.proposals import Proposals
from onlinecoc_ai.pack import Pack,fixture_state
from onlinecoc_ai.coordinator import Coordinator,SYSTEM
from onlinecoc_ai.context import Context,source
from onlinecoc_ai.contracts import canonical,digest
from onlinecoc_ai.data_queries import DataQueryService,NAMES
from onlinecoc_ai import data_edits
from test_entrypoints import command,committed
from test_access_batches import session,submit
from test_context import add_message,enable
from test_known_runtime import install,observe
from casebook import build,EMPTY

MATRIX=ENG/'acceptance/stumpsville-action-matrix'
NOW=1795182000


def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def application(folder,packpath,*,fresh=True):
    host=Host(folder/'host',bootstrap='synthetic-only-password',clock=lambda:NOW)
    pack=Pack(packpath)
    if fresh:
        artifact=stage(pack.sources,pack.data);state=host.state()
        world=fixture_state(pack.json(pack.scenarios[0]['fixtureRef']),pack.configurations)
        for key in ('entities','relations','configurations','members','progress','collectionRevision'):state[key]=world[key]
        state['artifacts'][artifact['revision']]=artifact;state['activeRuleset']=artifact['revision']
        state['aiControl']['settings'].update(enabled=True,profileId='deepseek-main',externalSources={'public':True,'private':True,'kp':True})
        host.commit(state)
    proposals=Proposals(host,pack)
    profile=json.loads((ENG/'ai/examples/ai-providers.json').read_text(encoding='utf-8'))['profiles'][0];profile['enabled']=True
    coordinator=Coordinator(proposals,{profile['profileId']:profile},context=Context(proposals))
    return Application(SimpleNamespace(proposals=proposals,coordinator=coordinator))


def close(app):app.proposals.close();app.host.close()


def host_command(app,op,args,cid):return app.rulings.host_command('kp',cid,op,args)


def setup_host(app,op):
    """Record only actual initialized objects; no invented stand-in references."""
    host=app.host;state=host.state();artifact=state['artifacts'][state['activeRuleset']]
    sources={**artifact['sources'],'inspect.lua':"return rule('fixture.inspect', {}, function(r) return {ok=true} end)",
        'wait.lua':"return flow('fixture.wait', {'actor'}, {ask('wait',{role='kp',seconds=3600,yes='end',no='end',timeout='end'})})",
        'retry.lua':"return flow('fixture.retry', {'actor'}, {step('fail',function(r,actor) assert(false,'FIXTURE_RETRY_FAILURE') end)})"}
    artifact=stage(sources,{**artifact['data'],'edits.json':{'title':'preserve','items':[{'id':'one','value':1}],'tuning':{'a':1,'b':2}}})
    state['artifacts'][artifact['revision']]=artifact;state['activeRuleset']=artifact['revision']
    state['entities']['actor-one']['rules']['inspect']={'ruleId':'fixture.inspect'}
    state['assets']['asset-one']={'assetId':'asset-one','name':'Synthetic image','digest':digest('synthetic-image'),'size':15,'visibility':'public','ready':True}
    config={'configurationId':'fixture.bag','revision':'1','typeRef':'bag','defaults':{},'behaviors':{}}
    state['configurations']['fixture.bag']=config
    bag=entity('bag-one','bag','合成容器','player1');bag.update(configurationId='fixture.bag',configurationRevision='1',components={'core.container':{'allowed':['item']}});state['entities']['bag-one']=bag
    if op=='relation.remove':state['relations']['relation-one']={'relationId':'relation-one','revision':1,'sourceId':'bag-one','targetId':'token-one','relationType':'contains','tags':[],'metadata':{}}
    host.commit(state)
    if op=='member.add':host.identity.create('new-player','synthetic-only-password')
    if op.startswith('flow.'):
        rule='fixture.retry' if op=='flow.retry' else 'fixture.wait'
        receipt=host_command(app,'action.invoke',{'actionId':rule,'input':{'actor':'actor-one'}},'seed-flow')
        assert receipt['status']=='committed',receipt
    if op.startswith('chat.message.'):
        add_message(host,'kp','原始合成消息')
        if op=='chat.message.share':assert host_command(app,'action.invoke',{'actionId':'fixture.inspect','input':{}},'command-one')['status']=='committed'


def context_state(app,sections):return {key:app.host.state()[key] for key in sections}


def build_valid():
    work=HERE/'work'/('valid-'+str(time.time_ns()));work.mkdir(parents=True)
    packpath=work/'pack';shutil.copytree(ENG/'ai/tests/fixtures/pack',packpath)
    contract_path=packpath/'ai/contract.json';contract=json.loads(contract_path.read_text(encoding='utf-8'))
    contract['highRisk']={'configurationIds':['fixture.ext.extra'],'configurationPrefixes':[],'ruleFiles':[],'dataFiles':['edits.json'],'allowRemove':True};save(contract_path,contract)
    cases=build();built=[];fixture_checks=[]
    for case in cases:
        if case['category']=='pack-action':continue
        c=copy.deepcopy(case);c['caseVersion']=2;c['originProbeCaseId']=c['caseId'];folder=work/c['caseId'].replace(':','-');folder.mkdir()
        app=application(folder,packpath)
        try:
            op=c['coverage'];setup_host(app,op);catalog=app.batches.catalog('kp')
            if c['category']=='whitelist':
                actions=c['expected']['actions'];args=actions[-1]['args'];state=app.host.state()
                if op=='entity.create':args['configurationId']='fixture.actor';c['request']='按当前 fixture.actor 模板创建角色小栗，归 player1 所有、公开可见。'
                if op=='entity.update':args['numbers']={'target':11};c['request']='仅将 actor-one 的 target 设为11，其他数值不变。'
                if op=='relation.set':args.update(sourceId='bag-one',targetId='token-one');c['request']='将 item token-one 放入 bag-one，建立 contains 关系。'
                if op=='member.add':args['accountId']='new-player';c['request']='将已注册但不在房间的 new-player 作为普通玩家加入。'
                if op.startswith('flow.'):
                    flow=next(iter(state['flows'].values()))
                    if op=='flow.respond':
                        wait=next(iter(state['waits'].values()));args.update(waitId=wait['id'],revision=wait['revision']);c['request']='明确同意当前唯一的等待问题。'
                    else:args['flowId']=flow['id'];c['request']='重试当前 needs_attention 流程。' if op=='flow.retry' else '取消当前唯一等待中的流程。'
                if op=='chat.channel.update':args['revision']=state['chat']['channels']['general']['revision'];c['request']='只将 general 频道名称改为大厅。'
                if op in ('chat.message.edit','chat.message.retract'):
                    message=state['chat']['messages']['general'][-1];args.update(messageId=message['messageId'],revision=message['revision']);c['request']='将 general 中 KP 发出的唯一文本消息改成“稍后开始”。' if op.endswith('edit') else '撤回 general 中 KP 发出的唯一文本消息。'
                if op in ('ai.session.update','ai.session.delete'):
                    value=session(app,title='被测试会话');args.update(sessionId=value['sessionId'],revision=value['revision']);c['request']='把被测试会话的标题改为“线索”。' if op.endswith('update') else '删除“被测试会话”。'
                if op.startswith('ai.memory.'):
                    ref=source('entity','actor-one',app.host.state()['entities']['actor-one'],'public')
                    if op=='ai.memory.create':args['sourceRefs']=[ref]
                    else:
                        memory=app.memory.create('kp','角色仍在入口',[ref])
                        if op=='ai.memory.revoke':memory=app.memory.confirm('kp',memory['memoryId'],1)
                        args.update(memoryId=memory['memoryId'],revision=memory['revision']);c['request']='确认我创建的唯一记忆草稿。' if op.endswith('confirm') else '撤销我已确认的唯一记忆。'
                c['context']={'synthetic':True,'state':context_state(app,('roomId','status','entities','configurations','members','relations','progress','assets','flows','waits','chat')),
                    'sessions':app.sessions.list('kp')['items'],'memory':app.repository.state()['memory'],
                    'suppliedSourceRef':args.get('sourceRefs',[None])[0],
                    'registeredOutsideRoom':['new-player'] if op=='member.add' else []}
                if op=='chat.message.share':c['context']['sourceReceipt']=app.host.receipt('kp','command-one')
                c['catalog']={'host':{a['op']:catalog['host'][a['op']] for a in actions if a['target']=='host'},
                    'ai':{a['op']:catalog['ai'][a['op']] for a in actions if a['target']=='ai'},'actions':catalog['actions']}
                c['schemas']={a['op']:catalog[a['target']][a['op']] for a in actions}
                c['schemas']['notification.send']=catalog['host']['notification.send']
                c['catalog']['host']['notification.send']=catalog['host']['notification.send']
                c['allowNotifications']=True
                app.batches.validate_actions('kp',actions);pre=app.batches.preflight('kp',actions)
                assert pre['status'] in ('passed','runtime_required','unsupported'),(c['caseId'],pre)
                fixture_checks.append({'caseId':c['caseId'],'schema':'passed','preflight':pre})
            elif c['category']=='configuration':
                config=copy.deepcopy(app.host.state()['configurations']['fixture.token']);config['defaults']['bonus']=2
                kind=c['coverage'];identifier='fixture.ext.extra' if kind in ('add','remove') else config['configurationId']
                config.update(configurationId=identifier,revision='2' if kind=='replace' else '1')
                if kind=='remove':
                    state=app.host.state();state['configurations'][identifier]=copy.deepcopy(config);app.host.commit(state)
                c['request']={'add':'新增 fixture.ext.extra 道具模板，默认 bonus=2、charges=2，修订1，其余字段沿用给出的模板。',
                    'replace':'把 fixture.token 模板的 bonus 改为2，修订1升2，其他字段完整保留。',
                    'remove':'删除未被任何实例引用的 fixture.ext.extra 模板，当前修订1；保留其他模板。'}[kind]
                c['expected']['changeSet']['configurations']=[{'kind':kind,'id':identifier,'expectedRevision':None if kind=='add' else '1','value':None if kind=='remove' else config}]
                c['context']={'configurations':app.host.state()['configurations'],'pack':copy.deepcopy(app.proposals.pack.contract),
                    'fixtureAuthorPolicy':{'allowRemove':True,'allowedConfigurationIds':[identifier]},'entities':app.host.state()['entities']}
            elif c['category']=='data-edit':
                s=session(app);r=submit(app,s);snapshot,_=app.coordinator.context.capture('kp',app.repository.state()['requests'][r['requestId']]);pool={}
                path={'append':['items'],'add':['tuning'],'replace':['tuning','a'],'remove':['tuning','b']}[op]
                read=data_edits.read(app,'kp',snapshot,{'file':'edits.json','path':path},pool)
                c['expected']['dataEdits'][0]['ref']=read['editRef'];c['context']={'read':read,'untouchedSiblingPolicy':'Preserve all fields not explicitly targeted.'}
                c['replay']={'snapshot':snapshot,'editPool':pool}
                data_edits.compile_edits(EMPTY,c['expected']['dataEdits'],snapshot[2],pool)
                fixture_checks.append({'caseId':c['caseId'],'compile':'passed'})
            elif c['category']=='query':
                name=c['coverage'];args=copy.deepcopy(c['expected']['arguments'])
                if name.startswith('room_') and name.endswith('knowledge'):
                    install(app);observe(app);account='player1';page=app.host.knowledge.search(account,{'query':'','limit':5},player=True)
                    args={'query':'','limit':5} if name=='room_search_knowledge' else {'refs':[page['items'][0]['ref']]}
                    result=app.host.knowledge.search(account,args,player=True) if name=='room_search_knowledge' else app.host.knowledge.read(account,args,player=True)
                    c['principal']=account;c['knowledgeFixture']=True
                else:
                    account='kp'
                    if name=='room_read_sessions':
                        s=session(app,title='实际会话');args={'sessionId':s['sessionId']};result=app.sessions.get('kp',s['sessionId'])
                    elif name in ('room_read_data','room_read_case'):
                        service=DataQueryService(app.host)
                        if name=='room_read_case':
                            add_message(app.host,'kp','合成事件说明')
                            receipt=host_command(app,'action.invoke',{'actionId':'fixture.inspect','input':{}},'case-event');assert receipt['status']=='committed'
                            assert host_command(app,'chat.message.share',{'channelId':'general','commandId':'case-event'},'share-case')['status']=='committed'
                            page=service.execute('kp','search',{'types':['event'],'query':''},initiator='kp',read_scope='kp-room')
                        else:page=service.execute('kp','search',{'types':['entity'],'query':'测试角色'},initiator='kp',read_scope='kp-room')
                        assert page['items'],name
                        args={'refs':[page['items'][0]['ref']]};result=service.execute('kp',NAMES[name],args,initiator='kp',read_scope='kp-room')
                    elif name in NAMES:
                        if name=='room_search_data':args={'types':['entity'],'query':'测试角色'}
                        if name=='room_read_chat':add_message(app.host,'kp','现在开始');args={'channelId':'general','limit':5}
                        result=DataQueryService(app.host).execute('kp',NAMES[name],args,initiator='kp',read_scope='kp-room')
                    elif name=='room_manage_catalog':result=app.batches.catalog_query('kp',args['operations'])
                    elif name=='room_read_management':result=app.batches.read('kp','configurations')
                    elif name=='pack_read_config_data':
                        args={'file':'edits.json','path':['tuning','a']};s=session(app);r=submit(app,s);snapshot,_=app.coordinator.context.capture('kp',app.repository.state()['requests'][r['requestId']]);result=data_edits.read(app,'kp',snapshot,args,{})
                    else:
                        s=session(app);r=submit(app,s);snapshot,payload=app.coordinator.context.capture('kp',app.repository.state()['requests'][r['requestId']]);result=payload if name=='room_read_context' else payload['pack']
                c['expected']['arguments']=args;c['request']='只调用 '+name+' 查询，参数要求：'+json.dumps(args,ensure_ascii=False)+'。不生成修改，也不以文字代替工具调用。'
                c['context']={'synthetic':True,'resolvedArguments':args,'principal':account};fixture_checks.append({'caseId':c['caseId'],'toolExecution':'passed','resultDigest':digest(result)})
            elif c['caseId']=='lua:valid':c['context']['example']='return rule("example.id", {"actor"}, function(r, actor) return {ok=true} end)'
            c['fixturePath']=str(folder.relative_to(HERE));c['packPath']=str(packpath.relative_to(HERE));built.append(c)
            print(json.dumps({'fixture':c['caseId'],'status':'ready'},ensure_ascii=False),flush=True)
        finally:close(app)
    # Reuse independently checked game states, never send their expected args,
    # scripted dice or oracle. Explicit user decisions are in request text.
    engine=json.loads((MATRIX/'cases.json').read_text(encoding='utf-8'));contexts={x['caseId']:x for x in json.loads((MATRIX/'contexts.json').read_text(encoding='utf-8'))['contexts']}
    spec=importlib.util.spec_from_file_location('matrix_fixture',MATRIX/'run_matrix.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    sources={p.name:p.read_text(encoding='utf-8') for p in (ROOT/'rulepacks/stumpsville/rules').glob('*.lua')}
    data={p.name:json.loads(p.read_text(encoding='utf-8')) for p in (ROOT/'rulepacks/stumpsville/config').glob('*.json') if p.name!='configurations.json'};artifact=stage(sources,data)
    configs={c['configurationId']:c for c in engine['configurations']}
    for row in engine['cases']:
        if row['category']!='positive':continue
        ctx=copy.deepcopy(contexts[row['caseId']]);op=row['actionId'];folder=work/('pack-'+op);folder.mkdir();app=application(folder,packpath)
        try:
            module.fixture(app.host,row,configs,artifact);catalog=app.batches.catalog('kp')
            request='KP 按以下明确需求准备待审核指令：'+ctx['request']
            if op=='sv.profile':request+=' 初始力量8、敏捷9、意志10、HP5、钱币3。'
            if op=='sv.damage':request+=' 若有溢出，影响力量（str）。'
            publicrule=next(a for a in catalog['actions']['actions'] if a['id']==op)
            relevant={name:body for name,body in sources.items() if "return rule('"+op+"'" in body}
            c={'caseId':'pack:'+op,'caseVersion':2,'originProbeCaseId':'pack:'+op,'category':'pack-action','coverage':op,'positive':True,'live':True,
                'request':request,'context':{'synthetic':True,'state':ctx['state'],'inventorySlots':ctx['inventorySlots'],'referenceData':ctx['referenceData'],'ruleSources':relevant},
                'schemas':{'action.invoke':catalog['host']['action.invoke'],'notification.send':catalog['host']['notification.send'],'input:'+op:publicrule['schema']},
                'catalog':{'host':{'action.invoke':catalog['host']['action.invoke'],'notification.send':catalog['host']['notification.send']},'ai':{},'actions':{'actions':[publicrule]}},
                'expected':{'kind':'batch','actions':[row['action']]},'allowNotifications':True,
                'fixturePath':str(folder.relative_to(HERE)),'packPath':str(packpath.relative_to(HERE)),'matrixCaseId':row['caseId']}
            app.batches.validate_actions('kp',c['expected']['actions']);pre=app.batches.preflight('kp',c['expected']['actions']);assert pre['status'] in ('passed','runtime_required'),(op,pre)
            fixture_checks.append({'caseId':c['caseId'],'preflight':pre,'matrixCaseId':row['caseId']});built.append(c)
        finally:close(app)
    assert len(built)==71 and len({c['caseId'] for c in built})==71
    save(HERE/'valid-cases.json',built);save(HERE/'valid-fixture-checks.json',fixture_checks)
    (HERE/'improved-system.txt').write_text(SYSTEM,encoding='utf-8')
    return built


if __name__=='__main__':
    try:print(json.dumps({'validCases':len(build_valid())}))
    except Exception as exc:
        path=HERE/'setup-attempts.json';attempts=json.loads(path.read_text(encoding='utf-8'));attempts.append({'attempt':len(attempts)+1,'stage':'valid-fixture-v2','status':'failed','reason':str(exc)[:3000],'realApiRequests':0});save(path,attempts);raise
