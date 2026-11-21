"""Actual C findings, publication proof, and an Edge click against real Application."""
import copy
import importlib.util
import json
import sys
import time
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from threading import Thread

HERE=Path(__file__).resolve().parent
tree=json.loads((HERE/'active-tree.json').read_text())['tree']
sys.argv=[str(HERE/'coordinator_live.py'),'--tree',tree]
spec=importlib.util.spec_from_file_location('natural_test',HERE/'coordinator_live.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
from playwright.sync_api import sync_playwright,expect

profile=json.loads((Path(tree)/'engineering/ai/examples/ai-providers.json').read_text())['profiles'][0];profile['enabled']=True
pack=Path(json.loads((HERE/'strict-pack-source.json').read_text())['path'])
work=HERE/'work'/('c-publication-'+str(time.time_ns()));work.mkdir(parents=True)
rows=[]


def candidate(app,kind):
    delta={'schemaVersion':1,'configurations':[],'sources':{},'data':{},'suggestions':[]}
    if kind=='EXTENSION_FORBIDDEN':
        value=copy.deepcopy(app.host.state()['configurations']['sv.character']);value.update(revision='2');value['defaults'].update(hp=5,maxHp=5)
        delta['configurations']=[{'kind':'replace','id':'sv.character','expectedRevision':'1','value':value}]
    else:delta['sources']['rest.lua']=app.proposals.pack.sources['rest.lua'].replace('r.roll(6) + 1','r.roll(6) + 2')
    p=h.committed(h.command(app,'ai.draft.create',{'text':'实际C风险隔离验收','changeSet':delta}))
    result=h.committed(h.command(app,'ai.proposal.validate',{'proposalId':p['proposalId'],'revision':1}))
    item=app.rulings.list('kp')['items'][0]
    assert [r['status'] for r in result['reports']]==['pass','pass','unknown'],result
    assert any(f['code']==kind for f in result['reports'][2]['findings']),result['reports'][2]
    assert item['status']=='pending' and item['canDecide'] and item['cAssessment']['requiresAcceptance']
    return p,item


def main():
    for kind,identifier in [('EXTENSION_FORBIDDEN','c-extension-adopt'),('LIVE_SCENARIO_COVERAGE_MISSING','c-coverage-adopt')]:
        case=next(c for c in h.CASES if c['id']==identifier);app=h.setup_case(work/identifier,pack,case,profile)
        try:
            before=h.business(app);p,item=candidate(app,kind)
            params={'proposalId':p['proposalId'],'proposalRevision':1,'explicitHighRiskDigest':item['digest'],'riskDecisions':{r['id']:'Isolated explicit acceptance' for r in item['risks']}}
            missing=app.rulings.host_command('kp','missing-proof','ai.proposal.approve',params)
            assert missing['status']=='rejected' and missing['code']=='C_REVIEW_REQUIRED',missing
            proof={k:item['cAssessment'][k] for k in ('basisRevision','basisDigest','reportDigest')}
            tampered=app.rulings.host_command('kp','tampered-proof','ai.proposal.approve',{**params,'cReview':{**proof,'reportDigest':'0'*64}})
            assert tampered['status']=='rejected' and not app.host.state()['aiControl']['publications']
            if kind=='EXTENSION_FORBIDDEN':
                SimpleHTTPRequestHandler.extensions_map={**SimpleHTTPRequestHandler.extensions_map,'.js':'text/javascript','.css':'text/css'}
                server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(Path(tree)/'engineering/ai/web/components')))
                thread=Thread(target=server.serve_forever,daemon=True);thread.start()
                try:
                    with sync_playwright() as playwright:
                        browser=playwright.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1100,'height':850});calls=[];errors=[]
                        page.on('pageerror',lambda e:errors.append(str(e)))
                        page.expose_function('readRulings',lambda:app.rulings.list('kp'))
                        def decide(op,args):
                            calls.append({'op':op,'args':args});return h.command(app,op,args)
                        page.expose_function('decideRuling',decide)
                        page.goto(f'http://127.0.0.1:{server.server_port}/')
                        page.evaluate('''async()=>{document.body.replaceChildren();const {mountRulings}=await import('./rulings.js');window.panel=mountRulings(document.body,{connected:true,generation:1,view:{accountId:'kp',role:'kp',authorityEpoch:'e'},subscribe:()=>()=>{},aiResolve:async()=>({items:[]}),aiRulings:()=>readRulings(),aiCommand:(op,args)=>decideRuling(op,args)},{compact:true});}''')
                        page.get_by_role('button',name='查看并裁决').click()
                        expect(page.get_by_text('C 类游戏性评估 · 依据版本 1',exact=True)).to_be_visible()
                        page.screenshot(path=str(HERE/'actual-c-review-before.png'),full_page=True)
                        page.get_by_role('button',name='采纳评估并发布',exact=True).click()
                        expect(page.locator('.ruling-state')).to_have_text('已执行',timeout=20000)
                        assert len(calls)==1 and calls[0]['args']['cReview']==proof and not errors
                        page.get_by_role('button',name='查看详情').click();page.screenshot(path=str(HERE/'actual-c-review-after.png'),full_page=True)
                        browser.close()
                finally:server.shutdown();server.server_close();thread.join()
                approval={'realEdgeClick':True,'command':calls[0]}
            else:approval=h.approval(app,item,'manual-adopt')
            after=h.business(app);h.verify(case,app,before,after)
            rows.append({'caseId':identifier,'status':'passed','findings':item['cAssessment']['findings'],'originalStatuses':['pass','pass','unknown'],
                'missingProof':missing,'tamperedProof':tampered,'approval':approval,'publications':list(app.host.state()['aiControl']['publications'].values()),'consumed':True})
        finally:app.proposals.close();app.host.close()
    case=next(c for c in h.CASES if c['id']=='c-coverage-adopt');app=h.setup_case(work/'basis-stale',pack,case,profile)
    try:
        p,item=candidate(app,'LIVE_SCENARIO_COVERAGE_MISSING');proof={k:item['cAssessment'][k] for k in ('basisRevision','basisDigest','reportDigest')}
        approved=h.committed(app.rulings.host_command('kp','approve-before-edit','ai.proposal.approve',{'proposalId':p['proposalId'],'proposalRevision':1,
            'explicitHighRiskDigest':item['digest'],'riskDecisions':{r['id']:'Test acceptance' for r in item['risks']},'cReview':proof}))
        h.committed(h.command(app,'ai.c_basis.update',{'revision':1,'metricOverrides':{},'liveScenarios':[],'notes':'New basis'}))
        stale=app.rulings.host_command('kp','apply-old-basis','publication.apply',{'approvalId':approved['approvalId']})
        assert stale['status']=='rejected' and stale['code']=='C_BASIS_STALE' and not app.host.state()['aiControl']['publications'],stale
        rows.append({'caseId':'approved-then-basis-changed','status':'passed','result':stale,'published':False})
    finally:app.proposals.close();app.host.close()


try:main()
except Exception as exc:
    import traceback
    rows.append({'status':'failed','code':getattr(exc,'code',type(exc).__name__),'reason':str(exc),'traceback':traceback.format_exc()})
finally:
    h.save(HERE/('actual-c-publication-'+str(time.time_ns())+'.json'),{'tree':tree,'realProvider':False,'cases':rows})
    print(json.dumps(rows,ensure_ascii=False,default=str),flush=True)
if any(r['status']=='failed' for r in rows):raise SystemExit(1)
