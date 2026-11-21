// Package-only transport/queue regression. No engine, browser or provider calls.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
import {webcrypto, randomUUID} from 'node:crypto';

const pack=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.join(pack,'tests/output','ai-recovery-'+randomUUID());
await fs.mkdir(output,{recursive:true});
const report={checkedAt:new Date().toISOString(),kind:'package-only mocked transport',realSaveChanged:false,realProviderCalls:0,checks:[]};
async function check(id,fn){try{await fn();report.checks.push({id,passed:true});}catch(e){report.checks.push({id,passed:false,error:e.message});}}
class Element{
  constructor(tag,all){this.tag=tag;this.children=[];this.selectors=new Map();this.dataset={};this.hidden=false;this.isConnected=true;if(tag==='template')this.content={firstElementChild:{childNodes:[]}};all.push(this);this.all=all;}
  append(...values){this.children.push(...values);}
  replaceChildren(...values){this.children=values;}
  remove(){this.isConnected=false;}
  replaceWith(){} focus(){} scrollIntoView(){} addEventListener(){} showModal(){}
  querySelector(q){if(!this.selectors.has(q))this.selectors.set(q,new Element(q,this.all));return this.selectors.get(q);}
  querySelectorAll(){return [];}
}
async function context(){
  const stored=new Map(),all=[],body=new Element('body',all);
  const ctx=vm.createContext({URL,console,crypto:webcrypto,setInterval:()=>1,clearInterval(){},setTimeout,
    document:{createElement:tag=>new Element(tag,all),body,hidden:false},
    localStorage:{getItem:key=>stored.get(key)??null,setItem:(key,value)=>stored.set(key,String(value)),removeItem:key=>stored.delete(key)},
    rulingCard:()=>'',mountPackageRulings:()=>({destroy(){},refresh(){},setHistory(){}}),t:key=>key,locale:()=> 'zh-CN',mountKeeperAIQueue:()=>({destroy(){},refresh(){},remember(){}})});
  // Imports are injected explicitly; execute the actual package modules unchanged otherwise.
  try{const helper=await fs.readFile(path.join(pack,'ui/ai-recovery.js'),'utf8');vm.runInContext(helper.replace(/\bexport /g,''),ctx);}catch(e){if(e.code!=='ENOENT')throw e;}
  const rulings=await fs.readFile(path.join(pack,'ui/keeper-rulings.js'),'utf8');
  vm.runInContext(rulings.replace(/^import .*?;\s*/gm,'').replace(/\bexport /g,'').replace('function mountPackageRulings(','function unusedRulingsFixture('),ctx);
  return {ctx,stored,all,body};
}
const pending='sv.desktop.aiQueue.room.kp';
const command=id=>({method:'POST',body:{requestId:id,authorityEpoch:1,op:'ai.session.create',args:{title:'隔离测试'}}});
await check('actual-http-transport-retains-status-outside-json',async()=>{
  const f=await context();f.ctx.location={href:'http://localhost/sessions/kp/',origin:'http://localhost'};
  f.ctx.fetch=async()=>({ok:false,status:403,json:async()=>({code:'PERMISSION_DENIED'})});
  const transport=f.ctx.packageAITransport('http://localhost/sessions/kp/api/v1/');
  await assert.rejects(transport.request('ai/commands',command('real-shape')),e=>e.code==='PERMISSION_DENIED'&&e.status===403&&f.ctx.definiteAIRejection(e));
});
await check('non-json-client-refusal-retains-status',async()=>{
  const f=await context();f.ctx.location={href:'http://localhost/',origin:'http://localhost'};
  f.ctx.fetch=async()=>({ok:false,status:413,json:async()=>{throw Error('not JSON');}});
  await assert.rejects(f.ctx.packageAITransport('http://localhost/api/v1/').request('ai/commands'),e=>e.status===413&&f.ctx.definiteAIRejection(e));
});
await check('null-json-client-refusal-retains-status',async()=>{
  const f=await context();f.ctx.location={href:'http://localhost/',origin:'http://localhost'};
  f.ctx.fetch=async()=>({ok:false,status:400,json:async()=>null});
  await assert.rejects(f.ctx.packageAITransport('http://localhost/api/v1/').request('ai/commands'),e=>e.status===400&&f.ctx.definiteAIRejection(e));
});
await check('package-service-httpStatus-is-a-definite-refusal',async()=>{
  const f=await context();assert.equal(f.ctx.definiteAIRejection({httpStatus:403,code:'PERMISSION_DENIED'}),true);
  assert.equal(f.ctx.definiteAIRejection({httpStatus:503}),false);
});
async function embedded(handler){
  const fixture=await context();let client;
  class AiClient{
    constructor(transport){this.transport=transport;this.connected=true;this.view={accountId:'kp',role:'kp',authorityEpoch:1};client=this;}
    async resume(){} subscribe(){return ()=>{};} destroy(){} aiReceipt(id){return this.transport.request('ai/receipts/'+id);}
  }
  fixture.ctx.stumpsvilleWeb={aiModules:{AiClient,mountAIConversation:()=>({destroy(){},refresh(){},select(){}})},
    api:async (route,options)=>route==='api/v1/capabilities'?{ai:{available:true}}:handler(options)};
  const code=await fs.readFile(path.join(pack,'ui/ai-embedded.js'),'utf8');
  vm.runInContext(code.replace(/^import .*?;\s*/gm,'').replace('export const embeddedAI=','globalThis.embeddedAI='),fixture.ctx);
  await fixture.ctx.embeddedAI.mount(new Element('target',fixture.all),{base:'http://localhost/',manager:true,account:'kp',scope:'room'});
  return {...fixture,client};
}
for(const status of [400,401,403,409,429])await check('http-'+status+'-does-not-poison-next-command',async()=>{
  let calls=0;const f=await embedded(async()=>{if(++calls===1)throw Object.assign(new Error('explicit refusal'),{status,code:'REQUEST_REJECTED'});return {status:'committed'};});
  await assert.rejects(f.client.transport.request('ai/commands',command('first')));
  assert.equal(f.stored.get(pending),undefined,'definite HTTP refusal retained an unknown command');
  assert.equal((await f.client.transport.request('ai/commands',command('next'))).status,'committed');
});
for(const status of [undefined,408,500,503])await check('uncertain-'+status+'-blocks-until-original-receipt',async()=>{
  let receipt=false;const f=await embedded(async o=>{if(o.path==='ai/receipts/lost'){receipt=true;return {status:'committed'};}if(!receipt)throw Object.assign(new Error('response lost'),status?{status}:{});return {status:'committed'};});
  await assert.rejects(f.client.transport.request('ai/commands',command('lost')));
  assert.equal(f.stored.get(pending),'lost');
  await assert.rejects(f.client.transport.request('ai/commands',command('new')));
  await f.client.transport.request('ai/receipts/lost');assert.equal(f.stored.get(pending),undefined);
  assert.equal((await f.client.transport.request('ai/commands',command('next'))).status,'committed');
});
await check('unknown-receipt-does-not-silently-retry',async()=>{
  const f=await embedded(async o=>{if(o.path.startsWith('ai/receipts/'))return {status:'unknown'};throw Error('network lost');});
  await assert.rejects(f.client.transport.request('ai/commands',command('lost')));
  await f.client.transport.request('ai/receipts/lost');assert.equal(f.stored.get(pending),'lost');
});
await check('queue-definite-http-refusal-clears-prewritten-marker',async()=>{
  const f=await context();const task={requestId:'request1',createdAt:1,status:'failed',initiator:'player1',text:'测试申请'};
  const client={connected:true,view:{role:'kp',accountId:'kp',authorityEpoch:1},subscribe:()=>()=>{},
    aiTasks:async()=>({items:[task]}),aiRulings:async()=>({items:[]}),
    aiCommand:async()=>{throw Object.assign(Error('forbidden'),{status:403,code:'PERMISSION_DENIED'});}};
  const code=await fs.readFile(path.join(pack,'ui/keeper-queue.js'),'utf8');
  vm.runInContext(code.replace(/^import .*?;\s*/gm,'').replace('export function mountKeeperAIQueue','function mountKeeperAIQueue'),f.ctx);
  f.ctx.mountKeeperAIQueue(new Element('target',f.all),client,{mountRulings:()=>({refresh(){},destroy(){}})},{scope:'room',account:'kp'});
  await new Promise(resolve=>setTimeout(resolve,0));
  const cancel=f.all.find(e=>e.tag==='button'&&e.textContent==='ai.cancel');assert.ok(cancel,'fixture did not render cancellation action');
  await cancel.onclick();assert.equal(f.stored.get(pending),undefined,'queue retained marker after definitive refusal');
});
report.passed=report.checks.every(c=>c.passed);report.passedCount=report.checks.filter(c=>c.passed).length;
report.evidenceDirectory=path.relative(pack,output).replaceAll('\\','/');
await fs.writeFile(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));process.exitCode=report.passed?0:1;
