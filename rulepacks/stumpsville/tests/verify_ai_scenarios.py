"""Public-API regression for high-risk publications and package projection recovery."""
import copy
from datetime import datetime
import json
import secrets
from harness import PACK, running, provision, Account
from integrations import write_json
from verify_integrations import provider, ai, result
import publication_sync
from client import Client
from unittest.mock import patch


def main():
    output=PACK/'tests/output'/('ai-scenarios-'+secrets.token_hex(4));output.mkdir(parents=True)
    report={'checkedAt':datetime.now().astimezone().isoformat(),'checks':[], 'realSaveChanged':False,
            'evidenceDirectory':str(output.relative_to(PACK)).replace('\\','/')}
    def check(label):
        report['checks'].append(label);print(label,flush=True)
        write_json(output/'progress.json',report)
    try:
        with provider(output) as (config,calls):
            with running('ai-scenarios',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
                kp,p1,p2=provision(runtime,password)
                original=kp.request('/package/bundle')
                game=copy.deepcopy(original['data']['game.json'])
                game['items'].append({'id':'test-lantern','name':'验收提灯','kind':'item','slots':1,'uses':3,'description':'隔离测试用提灯'})
                place={'index':len(game['locations'])+1,'name':'验收侧门','description':'新建侧门入口。','truth':'仅供测试的隐藏信息',
                       'exits':[1],'features':[],'stock':[{'item':len(game['items']),'count':2}],'clues':[]}
                game['locations'].append(place);game['locations'][0]['exits'].append(place['index'])
                access=kp.request('/api/v1/ai/access')
                result(ai(kp,'ai.access.update',{'revision':access['revision'],'allowPlayerChat':True,'autoApproveBatches':True,'autoApproveConfigurations':True}))
                def propose(delta,text):
                    proposal=result(ai(kp,'ai.draft.create',{'text':text,'changeSet':{'schemaVersion':1,'configurations':[],'sources':{},'data':{},'suggestions':[],**delta}}))
                    checked=result(ai(kp,'ai.proposal.validate',{'proposalId':proposal['proposalId'],'revision':1}))
                    write_json(output/('validation-'+proposal['proposalId']+'.json'),checked)
                    return proposal,checked
                proposal,checked=propose({'data':{'game.json':game}},'新增提灯及侧门入口')
                assert checked['proposal']['status']=='review_ready',[(r['level'],r['status'],r['findings']) for r in checked['reports']]
                row=next(i for i in kp.request('/api/v1/ai/rulings')['items'] if i['rulingId']=='proposal:'+proposal['proposalId'])
                assert row['highRisk'] and row['status']=='pending'
                assert kp.request('/package/bundle')['data']['game.json']==original['data']['game.json']
                check('开启普通自动审批仍不能执行高危物品与地图修改')
                decision={'rulingId':row['rulingId'],'digest':row['digest'],'decision':'approve',
                          'riskDecisions':{r['id']:'隔离验收接受已显示的风险与覆盖限制' for r in row['risks']}}
                refused=ai(kp,'ai.ruling.decide',decision,allow_error=True)
                assert refused.get('status')=='rejected' or refused.get('code'),refused
                decision['explicitHighRiskDigest']=row['digest']
                first=result(ai(kp,'ai.ruling.decide',decision));second=result(ai(kp,'ai.ruling.decide',decision))
                assert first['status']==second['status']=='completed'
                check('高危裁决必须显式绑定完整指纹；重复批准不重复发布')
                original_send=Client.send
                def lose_map_response(client,envelope):
                    receipt=original_send(client,envelope)
                    if envelope['payload']['op']=='entity.create' and envelope['payload']['args'].get('configurationId')=='sv.location':
                        raise OSError('isolated lost map creation response')
                    return receipt
                with patch.object(Client,'send',lose_map_response):
                    pending=kp.state()['publicationSync']
                    assert pending['status']=='pending' and pending['hostCommitted']
                state=kp.state()
                assert state['publicationSync']['status']=='completed',state['publicationSync']
                assert state['allLocations']['11']['name']=='验收侧门' and state['doors']['1-11']=='closed'
                assert '11' not in state['published']
                view=kp.request('/api/v1/view')
                assert sum(e['configurationId']=='sv.location' and e['numbers']['index']==11 for e in view['entities'].values())==1
                actor=state['characters'][0]
                result(kp.command('action.invoke',{'actionId':'sv.travel','input':{'actor':actor['instanceId'],'location':11}}))
                check('批准后地图、物品同步；新地点默认未公开；新入口可实际传送')
                assert all('result' in step for job in runtime.package.state['jobs'].values() if job.get('requestKey','').startswith('publication-sync:') for step in job['steps'].values())
                check('地点创建响应丢失时显示已发布待同步，按原回执恢复且不重复创建')
                reordered=copy.deepcopy(game);reordered['items'][0],reordered['items'][1]=reordered['items'][1],reordered['items'][0]
                _,invalid=propose({'data':{'game.json':reordered}},'错误重排库存编号')
                assert invalid['proposal']['status']=='blocked'
                badmap=copy.deepcopy(game);badmap['locations'][0]['exits'].append(999)
                _,invalid=propose({'data':{'game.json':badmap}},'错误悬空出口')
                assert invalid['proposal']['status']=='blocked'
                check('物品编号重排和悬空出口在批准前被校验拦截')
                source=kp.request('/package/bundle')['sources']['check-core.lua'].replace('rolled <= target','rolled < target')
                proposal,checked=propose({'sources':{'check-core.lua':source}},'检定阈值高危变更')
                assert checked['proposal']['status']=='review_ready',[(r['level'],r['status'],r['findings']) for r in checked['reports']]
                core=next(i for i in kp.request('/api/v1/ai/rulings')['items'] if i['rulingId']=='proposal:'+proposal['proposalId'])
                assert core['highRisk'] and core['status']=='pending'
                result(ai(kp,'ai.ruling.decide',{'rulingId':core['rulingId'],'digest':core['digest'],'decision':'reject'}))
                assert 'rolled <= target' in kp.request('/package/bundle')['sources']['check-core.lua']
                check('核心检定修改进入高危裁决，拒绝后活动规则保持原样')
                unused=copy.deepcopy(kp.request('/api/v1/admin')['configurations']['sv.npc'])
                unused.update(configurationId='sv.ext.npc.removable',revision='1');unused['defaults']['isNpc']=1
                added,checked=propose({'configurations':[{'kind':'add','id':unused['configurationId'],'expectedRevision':None,'value':unused}]},'新增未使用的测试模板')
                assert checked['proposal']['status']=='review_ready',[(r['level'],r['status'],r['findings']) for r in checked['reports']]
                # Ordinary NPC templates still use the previously enabled ordinary auto approval.
                assert unused['configurationId'] in kp.request('/api/v1/admin')['configurations']
                removed,checked=propose({'configurations':[{'kind':'remove','id':unused['configurationId'],'expectedRevision':'1','value':None}]},'删除未使用模板')
                assert checked['proposal']['status']=='review_ready',[(r['level'],r['status'],r['findings']) for r in checked['reports']]
                removal=next(i for i in kp.request('/api/v1/ai/rulings')['items'] if i['rulingId']=='proposal:'+removed['proposalId'])
                assert removal['highRisk'] and removal['status']=='pending'
                result(ai(kp,'ai.ruling.decide',{'rulingId':removal['rulingId'],'digest':removal['digest'],'explicitHighRiskDigest':removal['digest'],'decision':'approve','riskDecisions':{r['id']:'隔离验收确认没有引用' for r in removal['risks']}}))
                assert unused['configurationId'] not in kp.request('/api/v1/admin')['configurations']
                check('普通NPC创建沿用普通策略，未使用模板删除必须高危确认后实际移除')
                local=copy.deepcopy(runtime.package.state);local['locations']['1']['description']='KP 未发布草稿'
                proposed=copy.deepcopy(game);proposed['locations'][0]['description']='批准的另一版本'
                try:publication_sync.projection(local,game,proposed)
                except publication_sync.SyncConflict:pass
                else:raise AssertionError('must retain concurrent local edit')
                assert local['locations']['1']['description']=='KP 未发布草稿'
                check('已发布工件与包侧并发草稿冲突不会覆盖本地数据')
            with running('ai-scenarios-restart',data=output/'game',ai_config=config,no_browser=True) as (runtime,_):
                kp=Account(runtime.origin,'kp',password,'restart')
                assert kp.state()['allLocations']['11']['name']=='验收侧门'
                view=kp.request('/api/v1/view')
                assert sum(e['configurationId']=='sv.location' and e['numbers']['index']==11 for e in view['entities'].values())==1
                check('重启保留已批准地图与物品，不重复建立地点实体')
            assert not calls
        report['passed']=True
    except Exception as error:
        report.update(passed=False,error=repr(error))
        raise
    finally:
        report['passedCount']=len(report['checks']);write_json(output/'report.json',report)
        write_json(PACK/'tests/ai-scenarios-results.json',report)
        print(json.dumps({k:report.get(k) for k in ('passed','passedCount','evidenceDirectory')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
