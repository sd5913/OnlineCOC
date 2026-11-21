// Read-only transport probe: synthetic fetch responses, no host process or room.
import {writeFile} from 'node:fs/promises';
import {HttpTransport,Client} from '../../client-sdk/client.js';

const transport=new HttpTransport();
const options={method:'POST',csrf:'synthetic-csrf',body:{requestId:'trace-request',payload:{commandId:'trace-command',op:'knowledge.observe',args:{}}}};
const cases=[
 ['json-denial',()=>Promise.resolve(new Response(JSON.stringify({code:'PERMISSION_DENIED'}),{status:403,headers:{'content-type':'application/json'}}))],
 ['plaintext-500',()=>Promise.resolve(new Response('Internal Server Error',{status:500}))],
 ['receipt-rejected',()=>Promise.resolve(new Response(JSON.stringify({status:'rejected',commandId:'trace-command',code:'KNOWLEDGE_UNAVAILABLE'}),{status:200}))],
 ['receipt-unknown',()=>Promise.resolve(new Response(JSON.stringify({status:'unknown',commandId:'trace-command'}),{status:200}))],
 ['no-response',()=>Promise.reject(new TypeError('Failed to fetch'))],
];
const output=[];const original=globalThis.fetch;
try {
 for(const [name,fetch] of cases){
  globalThis.fetch=fetch;
  try {output.push({name,returned:await transport.request('commands',options)});}
  catch(e){output.push({name,error:{name:e.name,message:e.message,code:e.code??null,status:e.status??null,operation:e.operation??null,requestId:e.requestId??null,commandId:e.commandId??null}});}
 }
 const client=new Client({request(){throw new Error('must not send');}});
 try{await client.command('knowledge.observe',{},'trace-command');}
 catch(e){output.push({name:'local-disconnected',error:{message:e.message,code:e.code??null,status:e.status??null,operation:e.operation??null,requestId:e.requestId??null,commandId:e.commandId??null}});}
}finally{globalThis.fetch=original;}
await writeFile(new URL('./initial-probe.json',import.meta.url),JSON.stringify(output,null,2)+'\n');
console.log(JSON.stringify(output,null,2));
