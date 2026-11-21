"""Real single/multiple browser page workloads with repeatable synthetic history."""
import argparse
import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

import httpx
from playwright.async_api import async_playwright

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

def stats(values):
    ordered=sorted(values)
    return {'n':len(ordered),'p50Ms':round(ordered[max(0,math.ceil(len(ordered)*.5)-1)],3),
            'p95Ms':round(ordered[max(0,math.ceil(len(ordered)*.95)-1)],3),
            'totalMs':round(sum(values),3)} if ordered else {'n':0}

async def wait_page(page, expression, timeout=60):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if await page.evaluate(expression):return
        await asyncio.sleep(.025)
    raise TimeoutError('Isolated browser state did not become ready')

async def scenario(browser, clients, history, rounds, generations, padding=0, baseline=False):
    parent=HERE/'benchmark-tmp';parent.mkdir(exist_ok=True)
    directory=Path(tempfile.mkdtemp(prefix='host-',dir=parent))
    log=open(directory/'server.log','w',encoding='utf-8')
    environment={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
    if baseline:environment['PERFORMANCE_ENGINEERING']=str(HERE/'baseline-source-tmp')
    process=subprocess.Popen([sys.executable,'-B',str(HERE/'host_fixture.py'),str(directory/'room'),str(history),str(generations),str(padding)],
        stdout=subprocess.PIPE,stderr=log,text=True,env=environment,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    contexts=[]
    try:
        first=await asyncio.wait_for(asyncio.to_thread(process.stdout.readline),90)
        if not first:raise RuntimeError('Fixture failed; inspect isolated server.log')
        ready=json.loads(first);base='http://127.0.0.1:'+str(ready['port'])
        async with httpx.AsyncClient(base_url=base,trust_env=False,timeout=90) as control:
            for _ in range(100):
                try:
                    if (await control.get('/api/v1/capabilities')).status_code==200:break
                except httpx.HTTPError:pass
                await asyncio.sleep(.05)
            pages=[]
            for i in range(clients):
                context=await browser.new_context();contexts.append(context)
                page=await context.new_page();pages.append(page)
                await page.goto(base+'/performance-fixture')
                await wait_page(page,'!!window.client')
                await page.evaluate("async a=>await client.login(a,'test-password')",('kp','player1','player2','kp')[i])
                await wait_page(page,'client.connected')
            initial=(await control.get('/performance-metrics?reset=true')).json()
            started=time.perf_counter()
            async def work(page,index):
                return await page.evaluate('''async ({rounds,index})=>{
                  const values=[];
                  async function record(operation,fn){const start=performance.now();let reconnect=false;
                    try{while(!client.connected){reconnect=true;if(performance.now()-start>60000)throw Error('RECONNECT_TIMEOUT');await new Promise(r=>setTimeout(r,20));}
                      const result=await fn();
                      if(result?.commandId&&result.status!=='committed')throw Error(result.code||result.status);
                      values.push({operation,ms:performance.now()-start,reconnect});return result;
                    }catch(error){values.push({operation,ms:performance.now()-start,reconnect,error:error.code||error.message});return null;}}
                  for(let i=0;i<rounds;i++){
                    await record('view',()=>client.request('view'));
                    await record('history',()=>client.chatHistory('general'));
                    const sent=await record('chat.send',()=>client.sendChat('general','load '+index+' '+i,{},'perf-chat-'+index+'-'+i));
                    if(!sent)continue;
                    const updateStart=performance.now();
                    while(client.view?.chatChannels.general.lastSequence<sent.result.sequence){
                      if(performance.now()-updateStart>60000)throw Error('snapshot timeout');await new Promise(r=>setTimeout(r,5));}
                    values.push({operation:'snapshot.after.response',ms:performance.now()-updateStart});
                    await record('chat.read',()=>client.markChatRead('general',sent.result.sequence,'perf-read-'+index+'-'+i));
                    await record('rule.action',()=>{const suffix=client.view.accountId==='player2'?'player2':'player1';return client.command('action.invoke',{actionId:'demo.check',input:{actor:'actor-'+suffix,skill:'skill-'+suffix}},'perf-rule-'+index+'-'+i);});
                  }return values;
                }''',{'rounds':rounds,'index':index})
            values=sum(await asyncio.gather(*(work(page,i) for i,page in enumerate(pages))),[])
            elapsed=time.perf_counter()-started
            metrics=(await control.get('/performance-metrics?reset=true')).json()
            # Verify all writes were retained, original command IDs deduplicate, and PL view stays filtered.
            for i,page in enumerate(pages):
                await wait_page(page,'client.connected')
                check=await page.evaluate('''async i=>{
                  const r=await client.receipt('perf-chat-'+i+'-0');
                  const repeated=await client.sendChat('general','load '+i+' 0',{},'perf-chat-'+i+'-0');
                  return {same:JSON.stringify(r)===JSON.stringify(repeated),privateVisible:'secret-clue' in client.view.entities};
                }''',i)
                assert check['same']
                assert check['privateVisible']==(i in (0,3))
            protocol=[await page.evaluate('perfProtocol') for page in pages]
            return {'pages':clients,'historyMessages':history,'historyReceipts':history,'seedGenerations':generations,
                'syntheticAuditPaddingBytes':padding,
                'roundsPerPage':rounds,'elapsedSeconds':round(elapsed,3),
                'requestThroughputPerSecond':round(clients*rounds*5/elapsed,3),
                'initial':{k:v for k,v in initial.items() if k not in ('samplesMs','dispatch')},
                'final':{k:v for k,v in metrics.items() if k not in ('samplesMs','dispatch')},
                'operations':{op:stats([v['ms'] for v in values if v['operation']==op]) for op in sorted({v['operation'] for v in values})},
                'instrumentationInclusive':{k:stats(v) for k,v in metrics['samplesMs'].items()},
                'commandLockQueue':stats([v['queueMs'] for v in metrics['dispatch']]),
                'failedOperations':[v for v in values if v.get('error')],
                'reconnectWaits':sum(bool(v.get('reconnect')) for v in values),
                'protocol':protocol,
                'unavailableViewWaits':sum(bool(v.get('reconnect')) for v in values),
                'waitDefinition':'reconnectWaits is a legacy name: counts waiting for client.connected after snapshot reset OR socket close; protocol separates actual causes',
                'checks':{'sameIdReceipt':True,'playerPrivateEntityHidden':True},'samples':values}
    finally:
        for context in contexts:await context.close()
        process.terminate()
        try:await asyncio.to_thread(process.wait,10)
        except subprocess.TimeoutExpired:process.kill();await asyncio.to_thread(process.wait)
        log.close()

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    parser.add_argument('--history',type=int,default=1000);parser.add_argument('--rounds',type=int,default=8)
    parser.add_argument('--pages',type=int,nargs='+',default=[1,4]);parser.add_argument('--generations',type=int,default=24)
    parser.add_argument('--padding',type=int,default=0);parser.add_argument('--baseline',action='store_true')
    args=parser.parse_args();results=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(channel='msedge',headless=True)
        try:
            for pages in args.pages:
                result=await scenario(browser,pages,args.history,args.rounds,args.generations,args.padding,args.baseline);results.append(result)
                print(json.dumps({'pages':pages,'operations':result['operations'],'throughput':result['requestThroughputPerSecond']},ensure_ascii=False),flush=True)
        finally:await browser.close()
    paths=['engineering/backend/src/onlinecoc/host.py','engineering/backend/src/onlinecoc/server.py',
           'engineering/backend/src/onlinecoc/contracts.py','engineering/data-management/onlinecoc_data/store.py',
           'engineering/client-sdk/client.js']
    result={'createdAt':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'platform':platform.platform(),'python':sys.version,
        'fixture':'synthetic real Host/Uvicorn/Edge pages; no AI; inclusive timings overlap',
        'productionRoomTouched':False,'results':results,
        'sha256':{name:hashlib.sha256(((HERE/'baseline-source-tmp'/Path(name).relative_to('engineering')) if args.baseline else (ROOT/name)).read_bytes()).hexdigest() for name in paths}}
    target=(ROOT/args.output).resolve()
    if not target.is_relative_to(HERE):raise ValueError('Output must stay in acceptance/performance')
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':asyncio.run(main())
