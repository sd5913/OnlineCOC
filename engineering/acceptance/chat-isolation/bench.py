import json,os,socket,subprocess,sys,time,uuid,statistics
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright
HERE=Path(__file__).resolve().parent;label=sys.argv[1];mode=sys.argv[2] if len(sys.argv)>2 else 'isolation';output=label+('-control' if mode=='control' else '');work=HERE/'work'/('run-'+output+'-'+uuid.uuid4().hex[:6]);work.mkdir(parents=True)
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
url=f'http://127.0.0.1:{port}';log=(work/'server.log').open('w')
proc=subprocess.Popen([sys.executable,'-B',str(HERE/'serve.py'),label,str(work/'data'),str(work/'ready.json'),str(port),mode],stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
def stats(values):
 ordered=sorted(values);return {'p50':statistics.median(values),'p95':ordered[min(len(ordered)-1,int(len(ordered)*.95))],'max':max(values)}
def wait(page,expression,arg=None):
 deadline=time.monotonic()+20
 while time.monotonic()<deadline:
  if page.evaluate(expression,arg):return
  page.wait_for_timeout(25)
 raise AssertionError('Browser state timeout: '+expression)
try:
 with httpx.Client(trust_env=False) as client:
  for _ in range(400):
   if proc.poll() is not None:raise RuntimeError((work/'server.log').read_text())
   try:
    if client.get(url+'/api/v1/capabilities',timeout=.2).status_code==200:break
   except httpx.HTTPError:pass
   time.sleep(.1)
  else:raise RuntimeError('startup timeout')
 meta=json.loads((work/'ready.json').read_text());sends=[];sync=[];approval=[];receipts=[]
 with sync_playwright() as pw:
  browser=pw.chromium.launch(channel='msedge',headless=True)
  contexts=[browser.new_context() for _ in range(3)];pages=[c.new_page() for c in contexts]
  for page,account in zip(pages,['kp','player1','player2']):
   page.goto(url);page.evaluate("async a=>{await playtest.login(a,'synthetic-password');window.seenSequence=0;}",account)
   wait(page,'playtest.connected')
  # Round-robin sends originate in three real independent browser sessions.
  # Approval starts from a separate HTTP connection concurrently with traffic.
  def approve():
   with httpx.Client(base_url=url,trust_env=False,headers={'Origin':url},timeout=40) as c:
    login=c.post('/api/v1/login',json={'loginName':'kp','password':'synthetic-password'}).json();c.headers['X-CSRF-Token']=login['csrf']
    out=[]
    for i in range(4):
     time.sleep(.15);rid='approve-'+str(i);payload={'protocolVersion':1,'type':'command','requestId':rid,'roomId':meta['roomId'],'payload':{'commandId':rid,'authorityEpoch':meta['epoch'],'op':'ai.proposal.approve','args':meta['approval']}}
     start=time.perf_counter();r=c.post('/api/v1/commands',json=payload).json();out.append({'ms':(time.perf_counter()-start)*1000,'receipt':r})
    return out
  with ThreadPoolExecutor(max_workers=1) as pool:
   for i in range(30):
    if i==1:future=pool.submit(approve)
    page=pages[i%3];rid='chat-'+str(i);start=time.perf_counter()
    result=page.evaluate("async x=>{const t=performance.now();const r=await playtest.command('chat.message.send',{channelId:'general',text:x.text},x.id);return {ms:performance.now()-t,receipt:r};}",{'text':'concurrent '+str(i),'id':rid})
    sends.append(result['ms']);receipts.append(result['receipt'])
    if result['receipt']['status']=='committed':
     seq=result['receipt']['result']['sequence']
     for p in pages:wait(p,'(s)=>playtest.view?.chatChannels.general.lastSequence>=s',seq)
     sync.append((time.perf_counter()-start)*1000)
   approval=future.result()
  for c in contexts:c.close()
  browser.close()
 failures=[r for r in receipts if r['status']!='committed'];af=[r for r in approval if r['receipt']['status']!='committed']
 result={'label':label,'mode':mode,'fixture':{'extraActors':120,'existingMessages':1200,'browsers':3,'chatSends':30,'concurrentApprovals':4},'sendMs':stats(sends),'allPagesSyncedMs':stats(sync),
  'chatFailureRate':len(failures)/len(receipts),'approvalFailureRate':len(af)/len(approval),'approvals':approval,'receipts':receipts,
  'sequenceUnique':len({r.get('result',{}).get('sequence') for r in receipts if r['status']=='committed'})==len(receipts),'sendSamples':sends,'syncSamples':sync}
 (HERE/(output+'.json')).write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ('receipts','sendSamples','syncSamples')}))
finally:proc.terminate();proc.wait(timeout=10);log.close()
