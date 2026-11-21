"""Paired real-model requests on equivalent synthetic long conversations."""
import argparse,asyncio,copy,hashlib,json,sys,time,traceback
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('--tree',required=True)
parser.add_argument('--variant',required=True,choices=['baseline','adapted'])
parser.add_argument('--run',action='store_true')
parser.add_argument('--phases',default='accepted,replace,cancel')
ARGS=parser.parse_args()
ENG=Path(ARGS.tree)/'engineering'
sys.path[:0]=[str(ENG/'ai/src'),str(ENG/'backend/src'),str(ENG/'data-management'),str(ENG/'ai/tests'),str(ROOT/'rulepacks/stumpsville/tools')]
from onlinecoc_ai.profiles import load_profiles
from onlinecoc_ai.contracts import canonical,digest
from onlinecoc_ai.local_lock import file_lock
from test_access_batches import session,submit
from test_coordinator import Fake,completion,wait_task
from live_support import setup_case,business,approve,artifact,command,committed
from bounded_provider import BoundedProvider,save

PLAN='两步方案：先新增NPC模板sv.ext.npc.official_a，沿用当前sv.npc完整结构及默认值，我建议hp和maxHp均为3，按作者要求补isNpc=1；发布后再另行讨论实例。现在仅是建议，尚未批准执行。'
ACCEPT='同意你提出的模板方案和建议HP值；同意方案不等于批准执行。'
CORRECT='更正：最终hp和maxHp在你提议、我同意的数值上增加1，其他已同意参数不变；仍未批准执行。'
REPLACE='撤回旧目标作为后续新增目标。接下来改为新模板sv.ext.npc.official_b，hp和maxHp都用7，不再沿用旧的HP建议。不要新增旧目标的第二份，也不要修改已发布模板；其余结构和默认字段沿用当前sv.npc，保留isNpc=1。尚未批准执行。'
REQUESTS={
    'accepted':'按之前你提出、我同意并更正后的全部参数准备新增NPC模板草稿。不要再问已经确认的数值；查询当前模板，保留其他全部内容。尚未批准执行。',
    'replace':'按我最后替换的目标和参数准备新增NPC模板草稿，其余现有配置完全不变。尚未批准执行。',
    'cancel':'我撤回继续新增模板的计划。现在不要创建、修改或删除任何配置，仅用一句话确认停止准备新增方案。'}


async def settled(app,tid):
    task=await wait_task(app.coordinator,tid,timeout=660)
    for _ in range(250):
        task=app.repository.state()['tasks'][tid]
        if 'diagnostics' in task:break
        await asyncio.sleep(.02)
    return task


async def main():
    run=str(time.time_ns());folder=HERE/'work'/('live-'+ARGS.variant+'-'+run);folder.mkdir(parents=True)
    profile=copy.deepcopy(load_profiles(ROOT/'engineering/ai/config/ai-providers.json')['deepseek-main'])
    # Same deliberately smaller declared window for both variants; the real
    # endpoint/model remains identical. This forces compaction in bounded input.
    profile['request']['contextWindowTokens']=131072
    profile['limits']['taskTimeoutMs']=600000
    from integrations import ai_snapshot
    packpath=ai_snapshot(folder/'author-pack')
    pack_hashes={p.relative_to(packpath).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in packpath.rglob('*') if p.is_file()}
    app=setup_case(folder,packpath,{'id':'paired'},profile)
    s=session(app);rows=[];providers=[];path=HERE/(ARGS.variant+'-'+run+'.json')
    # The proposal text is a disclosed synthetic fixture, not counted as a real
    # model success. Routing it through a fake completion creates valid history
    # provenance equally for both variants, without leaking execution authority.
    async def seeded(*_):return completion({'kind':'plan','text':PLAN})
    app.coordinator.provider_factory=lambda p:Fake(seeded)
    report={'variant':ARGS.variant,'work':str(folder),'tree':ARGS.tree,'profile':profile,'packHashes':pack_hashes,
            'syntheticHistory':{'assistantPlan':PLAN,'userAcceptance':ACCEPT,'userCorrection':CORRECT,'replacement':REPLACE,
                                'externalSeedCalls':0,'fixtureDigest':digest([PLAN,ACCEPT,CORRECT,REPLACE])},'rows':rows}
    save(path,report)
    try:
        await app.coordinator.start()
        req=submit(app,s,'先建议NPC模板方案，只讨论，不生成草稿。')
        tid=committed(command(app,'ai.request.dispatch',{'requestId':req['requestId']}))['taskId']
        task=await settled(app,tid);assert task['status']=='review_ready' and task['text']==PLAN
        submit(app,s,ACCEPT)
        for n in range(18):submit(app,s,'合成背景'+str(n)+'：'+('走过树林与河岸，没有增加新的数值约定，先前明确选择继续有效。'*130))
        submit(app,s,CORRECT)
        for n in range(5):submit(app,s,'仅补充背景编号'+str(n)+'；保留前述最终更正，没有新增参数。')
        def factory(p):
            provider=BoundedProvider(p,'paired',ARGS.variant,'real-stumpsville');providers.append(provider);return provider
        app.coordinator.provider_factory=factory
        for phase in ARGS.phases.split(','):
            if phase=='replace':
                submit(app,s,REPLACE)
                for n in range(5):submit(app,s,'继续保留最新替换决定；背景编号'+str(n)+'，没有新参数。')
            before=business(app);initial=len(providers);started=time.perf_counter()
            row={'phase':phase,'request':REQUESTS[phase],'status':'running'};rows.append(row)
            try:
                req=submit(app,s,REQUESTS[phase]);tid=committed(command(app,'ai.request.dispatch',{'requestId':req['requestId']}))['taskId']
                task=await settled(app,tid);row['task']=task
                assert business(app)==before,'Generation mutated business state'
                assert task['status']=='review_ready',task.get('error') or task['status']
                if phase=='cancel':
                    assert not task.get('proposalId') and not task.get('batchId'),'Withdrawn request still produced a candidate'
                    row.update(noCandidate=True,noBusinessMutation=True)
                else:
                    assert task.get('proposalId') and not task.get('batchId'),'Missing configuration candidate'
                    item=next(r for r in app.rulings.list('kp')['items'] if r['rulingId']=='proposal:'+task['proposalId'])
                    row['ruling']=item
                    assert item['status']!='blocked',item
                    result=approve(app,item,ARGS.variant+'-'+phase+'-'+run);row['approval']=result
                    after=business(app);expected=copy.deepcopy(before['configurations'])
                    name='sv.ext.npc.official_a' if phase=='accepted' else 'sv.ext.npc.official_b';hp=4 if phase=='accepted' else 7
                    value=copy.deepcopy(expected['sv.npc']);value.update(configurationId=name,revision='1');value['defaults'].update(hp=hp,maxHp=hp,isNpc=1);expected[name]=value
                    assert after['configurations']==expected,'Unexpected target, parameter, or extra configuration'
                    assert before['entities']==after['entities'] and before['relations']==after['relations']
                    old=before['artifacts'][before['activeRuleset']];new=artifact(app)
                    assert old['data']==new['data'] and old['sources']==new['sources'],'Unrequested data/rule edit'
                    row.update(actualExecution=True,idempotent=True,target=name,hp=hp)
                row['status']='passed'
            except Exception as exc:
                row.update(status='failed',code=getattr(exc,'code',type(exc).__name__),reason=str(exc)[:2000],traceback=traceback.format_exc())
            finally:
                row['seconds']=round(time.perf_counter()-started,3)
                row['attemptIds']=[i for p in providers[initial:] for i in p.calls]
                save(path,report)
            if row['status']!='passed':break
    finally:
        await app.coordinator.close();app.proposals.close();app.host.close()
    print(json.dumps({'report':str(path),'rows':[{'phase':r['phase'],'status':r['status'],'seconds':r['seconds']} for r in rows]},ensure_ascii=False),flush=True)
    return all(r['status']=='passed' for r in rows)


if not ARGS.run:raise SystemExit('Explicit --run required; independent test budget applies')
with file_lock(HERE/'live-run'):
    if not asyncio.run(main()):raise SystemExit(1)
