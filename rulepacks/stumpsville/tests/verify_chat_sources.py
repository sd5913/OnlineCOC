"""Package source projection: chat churn versus actual game facts, no model."""
import argparse,copy,json,secrets,sys
from datetime import datetime
from pathlib import Path
PACK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PACK/'tools'))
from ai_data import Adapter,fingerprint

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',action='store_true');args=parser.parse_args()
    output=PACK/'tests/output'/('chat-sources-'+secrets.token_hex(4));output.mkdir(parents=True)
    path=output/'package.json';checks=[]
    report={'at':datetime.now().astimezone().isoformat(),'externalApiCalls':0,'output':str(output),'baseline':args.baseline,'checks':checks}
    room={'members':{'kp':{'role':'kp'},'player1':{'role':'player'}},'entities':{
        'scene':{'configurationId':'sv.scene','lifecycle':'active','owner':'kp'},
        'character':{'configurationId':'sv.character','lifecycle':'active','owner':'player1','numbers':{'location':1}}},'chat':{'channels':{},'messages':{}},'commands':{}}
    state={'format':2,'sceneId':'scene','locations':{'1':{'name':'入口','secret':'奶酪机关'}},'doors':{'1-2':'open'},
        'ruleRevisions':{'active':{'data':{'item':'盾'}}},'activeRevision':'active','revision':1,'jobs':{},'requests':{},'events':{},'receipts':{},
        'scopedChat':{'messages':{},'reads':{}},'autoSceneQueue':{},'futureTransportCounter':0}
    adapter=Adapter(path)
    def read(account='kp',scope='kp-room'):
        path.write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8');return adapter.read_scoped(room,account,read_scope=scope)
    def configs(rows):return [x for x in rows if x['kind']=='config']
    try:
        original=fingerprint(configs(read()));observed=[]
        msg={'messageId':'message1','channelId':'sv-party','sequence':1,'revision':1,'senderAccountId':'player1','text':'普通聊天','deleted':False,'createdAt':1}
        state['scopedChat']['messages']['sv-party']=[msg];state['revision']+=1;state['jobs']['chat-1']={'result':'committed'};state['receipts']['player1']=[{'id':'chat-1'}]
        rows=read();observed.append(fingerprint(configs(rows))==original);selected=next(x for x in rows if x['kind']=='chat')
        msg.update(text='编辑聊天',revision=2);state['revision']+=1;rows=read();observed.append(fingerprint(configs(rows))==original)
        assert next(x for x in rows if x['kind']=='chat')['revision']!=selected['revision']
        msg.update(text='',deleted=True,revision=3);state['revision']+=1;rows=read();observed.append(fingerprint(configs(rows))==original)
        assert not [x for x in rows if x['kind']=='chat']
        state['scopedChat']['reads']['player1']={'sv-party':1};state['jobs']['failed']={'result':'failed'};state['futureTransportCounter']+=1
        observed.append(fingerprint(configs(read()))==original)
        report['configStableAcrossSendEditRetractReadAndRecovery']=observed
        if not args.baseline:assert all(observed),observed
        checks.append('explicit chat revision changes on edit and disappears on retract; default config stability measured separately')
        before=fingerprint(configs(read()));state['locations']['1']['secret']='改变了机关';after=fingerprint(configs(read()))
        assert before!=after;checks.append('actual location fact changes still alter config evidence')
        assert not configs(read('player1',None));assert not adapter.read_scoped({**room,'entities':{}},'kp',read_scope='kp-room')
        checks.append('player scope cannot read KP config rows; unrelated room binding exposes nothing')
        if not args.baseline:
            paths=[x['data']['path'] for x in configs(read())]
            assert all(not any(p=='/'+k or p.startswith('/'+k+'/') for k in ['scopedChat','jobs','requests','events','receipts','revision','autoSceneQueue','futureTransportCounter']) for p in paths),paths
            state['events']['player1']=[{'id':'event-1','status':'completed','operation':'resolve','mode':'auto','title':'明确裁决','time':2,'mechanical':False}]
            rows=read();assert {'event','ruling'}<={x['kind'] for x in rows};assert fingerprint(configs(rows))==after
            checks.append('business allowlist excludes chat/transport containers, while explicit event/ruling evidence remains available')
        report['passed']=True
    except Exception as e:report.update(passed=False,error=repr(e))
    report['passedCount']=len(checks)
    canonical=PACK/'tests'/('chat-sources-baseline-results.json' if args.baseline else 'chat-sources-results.json')
    if canonical.exists():
        old=json.loads(canonical.read_text(encoding='utf-8'));report['previousRuns']=old.get('previousRuns',[])+[{k:v for k,v in old.items() if k!='previousRuns'}]
    for p in [canonical,output/'results.json']:p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False));return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
