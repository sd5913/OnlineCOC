import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {mkdir,mkdtemp} from 'node:fs/promises';
import net from 'node:net';
import {fileURLToPath} from 'node:url';
import {createInterface} from 'node:readline';
import test,{before,after} from 'node:test';
import {HttpTransport,Client} from '../../client-sdk/client.js';

const nativeFetch=globalThis.fetch;
let child,base,cookie,csrf,view,stderr='';
const transport=new HttpTransport();
const trace={requestId:'trace-request',payload:{commandId:'trace-command',op:'knowledge.observe',args:{}}};
const request={method:'POST',body:trace};
const routedFetch=(path,options={})=>nativeFetch(new URL(path,base),{...options,headers:{Origin:base,...(cookie?{Cookie:cookie}:{}),...options.headers}});

before(async()=>{
 const parent=fileURLToPath(new URL('./sdk-live-tmp/',import.meta.url));await mkdir(parent,{recursive:true});
 const directory=await mkdtemp(parent+'host-');
 child=spawn(fileURLToPath(new URL('../../.venv/Scripts/python.exe',import.meta.url)),['-B',fileURLToPath(new URL('./serve_fixture.py',import.meta.url)),directory],
  {windowsHide:true,env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'},stdio:['ignore','pipe','pipe']});
 child.stderr.on('data',chunk=>{stderr=(stderr+chunk).slice(-2000);});
 const lines=createInterface({input:child.stdout});
 const first=await Promise.race([once(lines,'line'),once(child,'exit').then(([code])=>{throw new Error('Fixture exited '+code+': '+stderr);})]);
 base='http://127.0.0.1:'+JSON.parse(first[0]).port;lines.close();
 const deadline=Date.now()+15000;
 while(true){try{const r=await nativeFetch(base+'/api/v1/capabilities');if(r.ok)break;}catch{}if(Date.now()>deadline)throw new Error('Fixture startup timed out');await new Promise(r=>setTimeout(r,50));}
 const login=await routedFetch('/api/v1/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({loginName:'player1',password:'test-password'})});
 assert.equal(login.status,200);cookie=login.headers.get('set-cookie').split(';')[0];csrf=(await login.json()).csrf;
 globalThis.fetch=routedFetch;view=await transport.request('view');
});
after(async()=>{globalThis.fetch=nativeFetch;if(child&&child.exitCode===null){const stopped=once(child,'exit');child.kill();await stopped;}});

async function failure(promise,expected){
 await assert.rejects(promise,error=>{
  for(const [key,value] of Object.entries(expected))assert.deepEqual(error[key],value,key);
  assert.equal(error.message,error.code);
  assert.ok(!JSON.stringify(error).includes('synthetic-private'));
  assert.ok(!error.message.includes('synthetic-private'));
  return true;
 });
}

test('real non-JSON HTTP 500 retains status and command identity without retry',async()=>{
 await failure(transport.request('probe/plain',request),{code:'HTTP_ERROR',status:500,errorKind:'http',operation:'knowledge.observe',requestId:'trace-request',commandId:'trace-command'});
 assert.equal((await transport.request('probe/counts')).plain,1);
});
test('real default host exception remains an HTTP failure',async()=>{
 await failure(transport.request('probe/unexpected'),{code:'HTTP_ERROR',status:500,errorKind:'http',operation:'GET probe/unexpected',requestId:null,commandId:null});
});
test('real storage refusal preserves its machine code',async()=>{
 await failure(transport.request('probe/storage'),{code:'STORAGE_UNAVAILABLE',status:503,errorKind:'http'});
});
test('real malformed success is a response failure, not network failure',async()=>{
 await failure(transport.request('probe/invalid-success',request),{code:'INVALID_RESPONSE',status:200,errorKind:'response',operation:'knowledge.observe',requestId:'trace-request'});
});
test('HTTP error payload cannot overwrite trace or leak detail',async()=>{
 await failure(transport.request('probe/json-error',request),{code:'INPUT_INVALID',status:409,errorKind:'http',operation:'knowledge.observe',requestId:'trace-request'});
});
test('non-machine error code is replaced without echoing response content',async()=>{
 await failure(transport.request('probe/unsafe-code'),{code:'HTTP_ERROR',status:400,errorKind:'http'});
});
test('real command admission rejection retains request metadata',async()=>{
 const body={protocolVersion:1,type:'command',requestId:'schema-request',roomId:view.roomId,payload:{commandId:'schema-command',authorityEpoch:view.authorityEpoch,op:'entity.update',args:{bad:true}}};
 await failure(transport.request('commands',{method:'POST',csrf,body}),{code:'INPUT_INVALID',status:409,operation:'entity.update',requestId:'schema-request',commandId:'schema-command'});
 assert.equal((await transport.request('receipts/schema-command')).status,'unknown');
});
test('real business rejection stays a queryable receipt',async()=>{
 const client=new Client(transport);client.connected=true;client.csrf=csrf;client.view=view;
 const result=await client.command('entity.update',{id:'actor-player1',numbers:{hp:7}},'business-denial');
 assert.equal(result.status,'rejected');assert.equal(result.code,'PERMISSION_DENIED');
 assert.deepEqual(await client.receipt('business-denial'),result);
 assert.deepEqual(await client.command('entity.update',{id:'actor-player1',numbers:{hp:7}},'business-denial'),result);
 assert.equal((await transport.request('view')).entities['actor-player1'].numbers.hp,9);
 await failure(client.command('entity.update',{id:'actor-player1',numbers:{hp:6}},'business-denial'),{code:'COMMAND_ID_CONFLICT',errorKind:'client',status:null,commandId:'business-denial'});
});
test('unknown receipt remains unknown and is not converted to a rejection',async()=>{
 assert.deepEqual(await transport.request('probe/unknown',request),{status:'unknown',commandId:'trace-command'});
});
test('real connection refusal has no HTTP response status',async(t)=>{
 const server=net.createServer();server.listen(0,'127.0.0.1');await once(server,'listening');const port=server.address().port;
 await new Promise(resolve=>server.close(resolve));
 globalThis.fetch=(path,options)=>nativeFetch('http://127.0.0.1:'+port+path,options);t.after(()=>{globalThis.fetch=routedFetch;});
 await failure(transport.request('commands',request),{code:'NETWORK_ERROR',errorKind:'network',status:null,operation:'knowledge.observe',requestId:'trace-request',commandId:'trace-command'});
});
test('invalid serialization is a local request error and never sends',async(t)=>{
 globalThis.fetch=()=>assert.fail('must not send');t.after(()=>{globalThis.fetch=routedFetch;});
 const body=structuredClone(trace);body.payload.args.self=body;
 await failure(transport.request('commands',{method:'POST',body}),{code:'INVALID_REQUEST',errorKind:'client',status:null,operation:'knowledge.observe'});
});
test('local disconnected host and AI commands have structured identity',async()=>{
 const client=new Client({request(){assert.fail('must not send');}});
 await failure(client.command('knowledge.observe',{},'offline-host'),{code:'DISCONNECTED',status:null,errorKind:'client',operation:'knowledge.observe',commandId:'offline-host'});
 await failure(client.aiCommand('ai.ruling.decide',{},'offline-ai'),{code:'DISCONNECTED',status:null,errorKind:'client',operation:'ai.ruling.decide',requestId:'offline-ai'});
});
test('late failure after account reset cannot expose old request metadata',async()=>{
 let reject;const client=new Client({request:()=>new Promise((_,r)=>{reject=r;})});client.connected=true;client.view=view;
 const result=client.command('entity.update',{id:'actor-player1',numbers:{hp:7}},'old-account-command');
 const checked=failure(result,{code:'SESSION_CHANGED',status:null,errorKind:'session',operation:null,requestId:null,commandId:null});
 client.resetSession();reject(new Error('synthetic-private-old-account'));await checked;
});
test('read diagnostic operation omits query content',async()=>{
 await failure(transport.request('probe/unexpected?private=synthetic-private-query'),{operation:'GET probe/unexpected',code:'HTTP_ERROR',status:500});
});
test('client cannot reattach unsafe identifier text to a transport failure',async()=>{
 const client=new Client({request:(path,options)=>transport.request('probe/plain',options)});client.connected=true;client.view=view;
 await failure(client.command('entity.update',{},'synthetic-private\nidentifier'),{code:'HTTP_ERROR',status:500,commandId:null});
 await failure(client.aiCommand('ai.ruling.decide',{},'synthetic-private\nidentifier'),{code:'HTTP_ERROR',status:500,requestId:null,aiRequestId:null});
});
