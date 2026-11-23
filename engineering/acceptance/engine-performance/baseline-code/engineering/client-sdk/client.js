function safeId(value){return typeof value==='string'&&value.length>0&&value.length<=200&&!/[^A-Za-z0-9_.:-]/.test(value)?value:null;}
function requestContext(path,method,body){
 const payload=body?.payload??body;
 const route=typeof path==='string'?path.split('?')[0]:'';
 return {operation:safeId(payload?.op)??(typeof method==='string'&&method.length>0&&!/[^A-Z]/.test(method)&&route.length<=200&&!/[^A-Za-z0-9_./:-]/.test(route)?method+' '+route:null),requestId:safeId(body?.requestId),commandId:safeId(body?.payload?.commandId)};
}
function failure(code,errorKind,context={},status=null){return Object.assign(new Error(code),{code,errorKind,status,operation:null,requestId:null,commandId:null,...context});}
function serverCode(value){return typeof value==='string'&&value.length>0&&value.length<=200&&/^[A-Z]/.test(value)&&!/[^A-Z0-9_]/.test(value)?value:'HTTP_ERROR';}
export class HttpTransport {
 async request(path,{method='GET',body,csrf}={}){
  const context=requestContext(path,method,body);let serialized,response,value;
  try{serialized=body===undefined?undefined:JSON.stringify(body);}catch{throw failure('INVALID_REQUEST','client',context);}
  try{response=await fetch('/api/v1/'+path,{method,credentials:'same-origin',headers:{...(serialized!==undefined?{'Content-Type':'application/json'}:{}),...(csrf?{'X-CSRF-Token':csrf}:{})},body:serialized});}
  catch{throw failure('NETWORK_ERROR','network',context);}
  try{value=await response.json();}
  catch{throw failure(response.ok?'INVALID_RESPONSE':'HTTP_ERROR',response.ok?'response':'http',context,response.status);}
  if(!response.ok)throw failure(serverCode(value?.code),'http',context,response.status);
  return value;
 }
 open(onMessage,onClose){const ws=new WebSocket(location.origin.replace('http','ws')+'/api/v1/connect');ws.onmessage=e=>onMessage(JSON.parse(e.data));ws.onclose=onClose;return ws;}
}
export class Client {
 constructor(transport=new HttpTransport()){this.transport=transport;this.view=null;this.connected=false;this.pending=new Map();this.listeners=new Set();this.sessionGeneration=0;this.connectionGeneration=0;this.authTail=Promise.resolve();}
 subscribe(listener){this.listeners.add(listener);return ()=>this.listeners.delete(listener);}
 changed(){this.onChange?.();for(const listener of this.listeners)listener(this);}
 resetSession(){this.sessionGeneration++;this.connectionGeneration++;this.stopped=true;clearTimeout(this.timer);this.socket?.close();this.socket=null;this.csrf=null;this.view=null;this.parts=null;this.connected=false;this.pending.clear();this.aiPending?.clear();this.changed();return this.sessionGeneration;}
 async request(path,options){const generation=this.sessionGeneration;try{const value=await this.transport.request(path,options);if(generation!==this.sessionGeneration)throw failure('SESSION_CHANGED','session');return value;}catch(error){if(generation!==this.sessionGeneration)throw failure('SESSION_CHANGED','session');throw error;}}
 authenticate(path,options){const generation=this.resetSession();const run=this.authTail.catch(()=>{}).then(async()=>{if(generation!==this.sessionGeneration)throw failure('SESSION_CHANGED','session');const value=await this.request(path,options);this.csrf=value.csrf;this.connect();});this.authTail=run;return run;}
 async login(loginName,password){return this.authenticate('login',{method:'POST',body:{loginName,password}});}
 async resume(){return this.authenticate('me');}
 connect(){const generation=++this.connectionGeneration;clearTimeout(this.timer);this.socket?.close();this.stopped=false;this.view=null;this.connected=false;this.parts=null;this.socket=this.transport.open(m=>{
  if(generation!==this.connectionGeneration)return;
  if(m.type==='reset'){this.view=null;this.parts=null;this.connected=false;this.changed();}
  if(m.type==='snapshot.begin'&&Number.isInteger(m.parts)&&m.parts>0&&m.parts<=128)this.parts={id:m.id,count:m.parts,values:Array(m.parts).fill(null)};
  if(m.type==='snapshot.part'&&this.parts?.id===m.id&&Number.isInteger(m.index)&&m.index>=0&&m.index<this.parts.count)this.parts.values[m.index]=m.data;
  if(m.type==='snapshot.end'&&this.parts?.id===m.id){if(this.parts.values.length===this.parts.count&&this.parts.values.every(x=>typeof x==='string')){this.view=JSON.parse(this.parts.values.join(''));this.connected=true;this.changed();}this.parts=null;}
 },()=>{if(generation!==this.connectionGeneration)return;this.connected=false;this.view=null;this.parts=null;this.changed();if(!this.stopped)this.timer=setTimeout(()=>{if(generation===this.connectionGeneration)this.connect();},1500);});}
 async command(op,args,id=crypto.randomUUID()){
  if(!this.connected)throw failure('DISCONNECTED','client',{operation:safeId(op),commandId:safeId(id)});const v=this.view;let m=this.pending.get(id);
  if(m&&(m.payload.op!==op||JSON.stringify(m.payload.args)!==JSON.stringify(args)))throw failure('COMMAND_ID_CONFLICT','client',requestContext('commands','POST',m));if(!m){m={protocolVersion:1,type:'command',requestId:crypto.randomUUID(),roomId:v.roomId,payload:{commandId:id,runId:v.runId,authorityEpoch:v.authorityEpoch,catalogRevision:v.catalog.revision,rulesetRevision:v.catalog.rulesetRevision,expectedViews:op.startsWith('chat.')||op.startsWith('notification.')?{}:Object.fromEntries(Object.values(v.entities).filter(e=>JSON.stringify(args).includes(JSON.stringify(e.instanceId))).map(e=>[e.instanceId,e.viewToken])),op,args:structuredClone(args)}};this.pending.set(id,m);}
  try{const r=await this.request('commands',{method:'POST',csrf:this.csrf,body:m});return r;}catch(e){if(e.code!=='SESSION_CHANGED')e.commandId=safeId(id);throw e;}
 }
 async receipt(id){return this.request('receipts/'+encodeURIComponent(id));}
 async notifications({after=0,limit=50}={}){return this.request('notifications?'+new URLSearchParams({after,limit}));}
 async ackNotification(notificationId,id=crypto.randomUUID()){return this.command('notification.ack',{notificationId},id);}
 async knowledgeCapabilities(){return this.request('knowledge/capabilities');}
 async knowledgePreview(args){return this.request('knowledge/preview',{method:'POST',csrf:this.csrf,body:args});}
 async knowledgeSearch(args={}){return this.request('knowledge/search',{method:'POST',csrf:this.csrf,body:args});}
 async knowledgeRead(refs){return this.request('knowledge/read',{method:'POST',csrf:this.csrf,body:{refs}});}
 async knowledgeGrants(args={}){return this.request('knowledge/grants/query',{method:'POST',csrf:this.csrf,body:args});}
 async aiCommand(op,args,id=crypto.randomUUID()){
  if(!this.connected)throw failure('DISCONNECTED','client',{operation:safeId(op),requestId:safeId(id)});this.aiPending??=new Map();let envelope=this.aiPending.get(id);
  if(envelope&&(envelope.op!==op||JSON.stringify(envelope.args)!==JSON.stringify(args)))throw failure('COMMAND_ID_CONFLICT','client',requestContext('ai/commands','POST',envelope));
  if(!envelope){envelope={requestId:id,authorityEpoch:this.view.authorityEpoch,op,args:structuredClone(args)};this.aiPending.set(id,envelope);}
  try{return await this.request(op==='ai.draft.create'||op==='ai.proposal.revise'?'ai/drafts':'ai/commands',{method:'POST',csrf:this.csrf,body:envelope});}
  catch(e){if(e.code!=='SESSION_CHANGED')e.aiRequestId=safeId(id);throw e;}
 }
 async aiReceipt(id){return this.request('ai/receipts/'+encodeURIComponent(id));}
 async aiTasks({before,limit=30}={}){return this.request('ai/tasks?'+new URLSearchParams({limit,...(before?{before}:{})}));}
 async aiProposal(id){return this.request('ai/proposals/'+encodeURIComponent(id));}
 async aiAccess(){return this.request('ai/access');}
 async aiRulings(){return this.request('ai/rulings');}
 async aiResolve(tokens){return this.request('ai/references/resolve',{method:'POST',csrf:this.csrf,body:{tokens}});}
 async aiBatches(){return this.request('ai/batches');}
 async aiSettings(){return this.request('ai/settings');}
 async aiDebug(options={}){
  const allowed=['sessionId','requestId','rulingId','includeContent'];
  if(!options||typeof options!=='object'||Array.isArray(options)||Object.keys(options).some(key=>!allowed.includes(key)))throw new Error('INPUT_INVALID');
  if(!allowed.slice(0,3).some(key=>key in options))throw new Error('INPUT_INVALID');
  const includeContent=options.includeContent??false;
  if(typeof includeContent!=='boolean'||('includeContent' in options&&options.includeContent===null))throw new Error('INPUT_INVALID');
  const query=new URLSearchParams({includeContent:String(includeContent)});
  for(const key of allowed.slice(0,3))if(key in options){const value=options[key];if(typeof value!=='string'||value.length<1||value.length>200)throw new Error('INPUT_INVALID');query.set(key,value);}
  return this.request('ai/debug?'+query);
 }
 async chatMembers(){return this.request('chat/members');}
 async chatHistory(channelId,{before,limit=50}={}){return this.request('chat/history',{method:'POST',csrf:this.csrf,body:{channelId,...(before!==undefined?{before}:{}),limit}});}
 async sendChat(channelId,text,options={},id=crypto.randomUUID()){return this.command('chat.message.send',{...options,channelId,text},id);}
 async openDirect(accountId,id=crypto.randomUUID()){return this.command('chat.direct.open',{accountId},id);}
 async markChatRead(channelId,sequence,id=crypto.randomUUID()){return this.command('chat.read',{channelId,sequence},id);}
 async calculate(rule,input){return this.request('calculate',{method:'POST',csrf:this.csrf,body:{rule,input}});}
 async logout(){const csrf=this.csrf;const generation=this.resetSession();const run=this.authTail.catch(()=>{}).then(async()=>{if(generation!==this.sessionGeneration)throw failure('SESSION_CHANGED','session');return this.request('logout',{method:'POST',csrf});});this.authTail=run;return run;}
}
