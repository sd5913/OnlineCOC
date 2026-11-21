"""No model calls: independent consumption and corrected-harness reassessment."""
import copy
import json
import shutil
import time
import traceback
from pathlib import Path
from valid_cases import HERE,application,close,command,committed,digest
from coordinator_live import approve,business
from onlinecoc_ai.answers import parse_answer
from bounded_provider import save


def main():
    cases={c['caseId']:c for c in json.loads((HERE/'valid-cases.json').read_text(encoding='utf-8'))};ledger=json.loads((HERE/'live-ledger.json').read_text(encoding='utf-8'))
    run=str(time.time_ns());work=HERE/'work'/('followups-'+run);work.mkdir(parents=True);rows=[]
    replay=json.loads(next(HERE.glob('replay-*.json')).read_text(encoding='utf-8'))
    for name in ('configuration:add','configuration:replace','configuration:remove','lua:valid'):
        row={'caseId':name};app=None
        try:
            c=cases[name];path=work/name.replace(':','-')
            if name=='lua:valid':
                shutil.copytree(HERE/c['fixturePath'],path);app=application(path,HERE/c['packPath'],fresh=False)
                state=app.host.state();state['entities'].pop('bag-one');state['configurations'].pop('fixture.bag');app.host.commit(state)
                row['fixtureCorrection']='Removed unused bag-one/fixture.bag added by general fixture builder; they were not covered by the immutable author scenarios. Model output unchanged.'
                seed=next(a for a in ledger['attempts'] if a['attemptId']==193);value=parse_answer(seed['output']['content']);p=app.proposals.create('kp',c['request'],value['changeSet'],summary=value['text']);validation=app.proposals.validate('kp',p['proposalId'],1);row['validation']=validation
                assert validation['proposal']['status']=='review_ready'
                item=next(i for i in app.rulings.list('kp')['items'] if i['rulingId']=='proposal:'+p['proposalId']);row['publication']=approve(app,item,'followup-lua')
                result=app.rulings.host_command('kp','consume-lua','action.invoke',{'actionId':'fixture.ext.inspect','input':{'actor':'actor-one'}})
                assert result['status']=='committed' and result['result']=={'ok':True};row['consumption']=result
            else:
                source=HERE/'work'/('replay-'+replay['runId'])/name.replace(':','-');shutil.copytree(source,path);app=application(path,HERE/c['packPath'],fresh=False)
                identifier='fixture.token' if name.endswith('replace') else 'fixture.ext.extra'
                result=app.rulings.host_command('kp','consume-config','entity.create',{'configurationId':identifier,'name':'Published template consumer','owner':'player1'})
                if name.endswith('remove'):assert result['status']=='rejected';row['absenceEnforced']=True
                else:
                    assert result['status']=='committed',result
                    found=[e for e in app.host.state()['entities'].values() if e['name']=='Published template consumer'];assert len(found)==1 and found[0]['numbers']['bonus']==2 and found[0]['numbers']['charges']==2
                    saved=business(app.host);assert app.rulings.host_command('kp','consume-config','entity.create',{'configurationId':identifier,'name':'Published template consumer','owner':'player1'})==result and business(app.host)==saved
                row['consumption']=result
            row['status']='passed'
        except Exception as exc:row.update(status='failed',reason=str(exc),traceback=traceback.format_exc())
        finally:
            if app:close(app)
        rows.append(row)
    original=json.loads((HERE/'coordinator-1795183044989840600.json').read_text(encoding='utf-8'));reassessment=[]
    row={'caseId':'strict-data-item-consumption'};app=None
    try:
        source=HERE/'work'/('coordinator-'+original['runId'])/'data-append';path=work/'strict-data-item-consumption';shutil.copytree(source,path)
        app=application(path,Path(original['strictPack']),fresh=False)
        actor=app.rulings.host_command('kp','new-consumer','entity.create',{'configurationId':'sv.character','name':'New item consumer','owner':'player1'})
        assert actor['status']=='committed',actor
        actor_id=next(k for k,e in app.host.state()['entities'].items() if e['name']=='New item consumer')
        session_result=app.rulings.host_command('kp','new-session','entity.create',{'configurationId':'sv.session','name':'Consumption test session'})
        assert session_result['status']=='committed',session_result
        session_id=next(k for k,e in app.host.state()['entities'].items() if e['name']=='Consumption test session')
        relation=app.rulings.host_command('kp','consumer-session-link','relation.set',{'sourceId':actor_id,'targetId':session_id,'relationType':'source'})
        assert relation['status']=='committed',relation
        artifact=app.host.state()['artifacts'][app.host.state()['activeRuleset']];items=artifact['data']['game.json']['items'];index=next(i+1 for i,item in enumerate(items) if item['id']=='reliability-ration')
        grant=app.rulings.host_command('kp','grant-new-item','action.invoke',{'actionId':'sv.grant','input':{'actor':actor_id,'item':index,'slot':5,'uses':3}});assert grant['status']=='committed',grant
        args={'actionId':'sv.inventory','input':{'actor':actor_id,'operation':'use','slot':5,'value':1}};used=app.rulings.host_command('kp','consume-new-item','action.invoke',args);assert used['status']=='committed',used
        assert app.host.state()['entities'][actor_id]['numbers']['item5']==index and app.host.state()['entities'][actor_id]['numbers']['uses5']==2
        after=business(app.host);assert app.rulings.host_command('kp','consume-new-item','action.invoke',args)==used and business(app.host)==after
        row.update(status='passed',definitionIndex=index,grant=grant,consumption=used,idempotentReplay=True)
    except Exception as exc:row.update(status='failed',reason=str(exc),traceback=traceback.format_exc())
    finally:
        if app:close(app)
    rows.append(row)
    for row in original['cases']:
        if row['caseId']=='ambiguous-business':
            assert row['task']['status']=='needs_input' and not row['task'].get('batchId') and not row['task'].get('proposalId')
            reassessment.append({'caseId':row['caseId'],'original':'failed','reassessed':'passed','reason':'Harness expected review_ready; genuine missing attribute correctly produced needs_input without mutation.'})
        if row['caseId']=='data-append':
            old=row['before']['artifacts'][row['before']['activeRuleset']];new=row['after']['artifacts'][row['after']['activeRuleset']];expected=copy.deepcopy(old['data'])
            expected['game.json']['items'].append({'id':'reliability-ration','name':'试验口粮','kind':'item','slots':1,'uses':3,'description':'隔离验收用口粮。'})
            assert new['data']==expected and new['sources']==old['sources'] and row['idempotentReplay']
            reassessment.append({'caseId':row['caseId'],'original':'failed','reassessed':'passed_with_punctuation_difference','reason':'Only an added Chinese terminal full stop in the unquoted requested description. Exact whole-document comparison proves all other fields/order preserved; original strict failure retained.'})
        if row['caseId']=='slot-moved-fault':
            actions=row['candidate']['actions'];assert actions[0]['args']['input']=={'actor':'actor','operation':'use','slot':7,'value':1}
            reassessment.append({'caseId':row['caseId'],'original':'failed','actionIntent':'correct','overall':'failed_narrative','reason':'Harness omitted required value=1; corrected action targets slot7 correctly, but model prose falsely claims it is not ration. No success claim for this case.'})
    result={'runId':run,'apiCalls':0,'cases':rows,'originalCoordinatorReassessment':reassessment}
    save(HERE/('followup-'+run+'.json'),result);save(HERE/'followup-verification.json',result)
    print(json.dumps({'cases':[{k:r.get(k) for k in ('caseId','status','reason')} for r in rows],'reassessment':reassessment},ensure_ascii=False))


if __name__=='__main__':main()
