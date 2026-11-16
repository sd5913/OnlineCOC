export function requestId(){
 const a=crypto.getRandomValues(new Uint8Array(16));a[6]=(a[6]&15)|64;a[8]=(a[8]&63)|128;
 const s=Array.from(a,x=>x.toString(16).padStart(2,'0')).join('');return `${s.slice(0,8)}-${s.slice(8,12)}-${s.slice(12,16)}-${s.slice(16,20)}-${s.slice(20)}`;
}

export class HttpTransport{
 constructor(base='/api/v1/'){this.base=new URL(base,location.href);if(this.base.origin!==location.origin)throw new Error('CUSTOM_TRANSPORT_REQUIRED');}
 async request(path,{method='GET',body,csrf}={}){
  const r=await fetch(new URL(path,this.base),{method,credentials:'same-origin',headers:{...(body!==undefined?{'Content-Type':'application/json'}:{}),...(csrf?{'X-CSRF-Token':csrf}:{})},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await r.json();if(!r.ok)throw Object.assign(new Error(data.code||'REQUEST_FAILED'),data);return data;
 }
}

/** Headless room API. Custom transports implement request(path, options). */
export class AiClient{
 constructor(transport=new HttpTransport()){this.transport=transport;this.view=null;this.connected=false;this.pending=new Map();this.aiPending=new Map();this.listeners=new Set();this.generation=0;this.syncSequence=0;this.appliedSequence=0;}
 subscribe(listener){this.listeners.add(listener);return ()=>this.listeners.delete(listener);}
 changed(){this.onChange?.();for(const fn of this.listeners)fn(this);}
 async login(loginName,password){this.csrf=(await this.transport.request('login',{method:'POST',body:{loginName,password}})).csrf;await this.start();}
 async resume(){this.csrf=(await this.transport.request('me')).csrf;await this.start();}
 async start(){this.stop();const epoch=++this.generation;await this.sync();this.timer=setInterval(()=>{if(epoch===this.generation)this.sync().catch(()=>{});},2000);}
 async sync(){const epoch=this.generation,sequence=++this.syncSequence;try{const view=await this.transport.request('view');if(epoch!==this.generation||sequence<this.appliedSequence)return;this.appliedSequence=sequence;this.view=view;this.connected=true;this.changed();}catch(e){if(epoch===this.generation&&sequence>=this.appliedSequence){this.appliedSequence=sequence;this.view=null;this.connected=false;this.changed();}throw e;}}
 stop(){this.generation++;clearInterval(this.timer);this.timer=null;}
 destroy(){this.stop();this.view=null;this.connected=false;this.csrf=null;this.pending.clear();this.aiPending.clear();this.changed();this.listeners.clear();}
 async logout(){try{return await this.transport.request('logout',{method:'POST',body:{},csrf:this.csrf});}finally{this.destroy();}}
 async aiCommand(op,args,id=requestId()){
  if(!this.connected)throw new Error('DISCONNECTED');let e=this.aiPending.get(id);
  if(e&&(e.op!==op||JSON.stringify(e.args)!==JSON.stringify(args)))throw new Error('COMMAND_ID_CONFLICT');
  if(!e){e={requestId:id,authorityEpoch:this.view.authorityEpoch,op,args:structuredClone(args)};this.aiPending.set(id,e);}
  try{return await this.transport.request(['ai.draft.create','ai.proposal.revise'].includes(op)?'ai/drafts':'ai/commands',{method:'POST',body:e,csrf:this.csrf});}catch(error){error.aiRequestId=id;throw error;}
 }
 aiReceipt(id){return this.transport.request('ai/receipts/'+encodeURIComponent(id));}
 aiTasks({before,limit=30}={}){return this.transport.request('ai/tasks?'+new URLSearchParams({limit,...(before?{before}:{})}));}
 aiProposal(id){return this.transport.request('ai/proposals/'+encodeURIComponent(id));}
 aiUsage(options={}){const query=new URLSearchParams(options).toString();return this.transport.request('ai/usage'+(query?'?'+query:''));}
 aiSettings(){return this.transport.request('ai/settings');}
 aiContracts(){return this.transport.request('ai/contracts');}
 aiReferences(kind='config',q=''){return this.transport.request('ai/references?'+new URLSearchParams({kind,q}));}
 aiResolve(tokens){return this.transport.request('ai/references/resolve',{method:'POST',body:{tokens},csrf:this.csrf});}
 aiData(operation,args){if(!['search','read','chat','case'].includes(operation))throw new Error('INPUT_INVALID');return this.transport.request('ai/data/'+operation,{method:'POST',body:args,csrf:this.csrf});}
 aiSessions(archived=false){return this.transport.request('ai/sessions?archived='+archived);}
 aiSession(id){return this.transport.request('ai/sessions/'+encodeURIComponent(id));}
 async command(op,args,id=requestId()){
  if(!this.connected)throw new Error('DISCONNECTED');let envelope=this.pending.get(id);
  if(envelope&&(envelope.payload.op!==op||JSON.stringify(envelope.payload.args)!==JSON.stringify(args)))throw new Error('COMMAND_ID_CONFLICT');
  if(!envelope){const v=this.view;envelope={protocolVersion:1,type:'command',requestId:requestId(),roomId:v.roomId,payload:{commandId:id,runId:v.runId,authorityEpoch:v.authorityEpoch,catalogRevision:v.catalog.revision,rulesetRevision:v.catalog.rulesetRevision,expectedViews:{},op,args:structuredClone(args)}};this.pending.set(id,envelope);}
  try{return await this.transport.request('commands',{method:'POST',body:envelope,csrf:this.csrf});}catch(error){error.commandId=id;throw error;}
 }
 receipt(id){return this.transport.request('receipts/'+encodeURIComponent(id));}
}
