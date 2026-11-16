const encoder = new TextEncoder(), decoder = new TextDecoder();
const BLOCK = 262144;
function fault(code) { return Object.assign(new Error(code), {code}); }
function check(value, code) { if (!value) throw fault(code); }
function deferred() { let resolve, reject; const promise = new Promise((a,b)=>{resolve=a;reject=b;}); return {promise,resolve,reject}; }
function bounded(promise, ms, code="TIMEOUT") { let timer; return Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(fault(code)),ms);})]).finally(()=>clearTimeout(timer)); }
export function canonical(value) {
  if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
  if (value !== null && typeof value === "object") return "{" + Object.keys(value).sort().map(k=>JSON.stringify(k)+":"+canonical(value[k])).join(",") + "}";
  return JSON.stringify(value);
}
export async function sha(bytes) { return [...new Uint8Array(await crypto.subtle.digest("SHA-256",bytes))].map(x=>x.toString(16).padStart(2,"0")).join(""); }
function base64(bytes) { let text=""; for(let i=0;i<bytes.length;i+=8192) text+=String.fromCharCode(...bytes.subarray(i,i+8192)); return btoa(text); }
function unbase64(text) { return Uint8Array.from(atob(text.replaceAll("-","+").replaceAll("_","/")), x=>x.charCodeAt(0)); }
async function verify(key, text, signature) {
  const publicKey=await crypto.subtle.importKey("jwk", key, {name:"ECDSA",namedCurve:"P-256"}, false, ["verify"]);
  check(await crypto.subtle.verify({name:"ECDSA",hash:"SHA-256"},publicKey,unbase64(signature),encoder.encode(text)),"HOST_IDENTITY_INVALID");
}
function fingerprint(sdp) {
  const values=[...sdp.matchAll(/^a=fingerprint:sha-256 ([0-9A-Fa-f:]+)\r?$/gm)].map(x=>x[1].toUpperCase());
  check(values.length && new Set(values).size===1, "DTLS_FINGERPRINT_INVALID");
  return values[0];
}
async function gather(pc) {
  if(pc.iceGatheringState==="complete") return;
  await bounded(new Promise(resolve=>{const listener=()=>{if(pc.iceGatheringState==="complete"){pc.removeEventListener("icegatheringstatechange",listener);resolve();}};pc.addEventListener("icegatheringstatechange",listener);listener();}),20000,"ICE_GATHER_TIMEOUT");
}
function frameReceiver(onMessage) {
  const pending=new Map();
  return raw=>{
    check(typeof raw==="string" && raw.length<=16384,"FRAME_INVALID");
    const f=JSON.parse(raw);
    check(typeof f.frame==="string" && /^[0-9a-f]{32}$/.test(f.frame) && Number.isInteger(f.index) &&
      Number.isInteger(f.count) && f.count>0 && f.count<=257 && f.index>=0 && f.index<f.count &&
      typeof f.data==="string" && f.data.length<=11000,"FRAME_INVALID");
    const now=performance.now();
    for(const [id,state] of pending) if(now-state.time>15000) pending.delete(id);
    check(pending.has(f.frame)||pending.size<8,"FRAME_LIMIT");
    const state=pending.get(f.frame)||{count:f.count,parts:new Map(),size:0,time:now};
    check(state.count===f.count&&!state.parts.has(f.index),"FRAME_INVALID");
    const chunk=unbase64(f.data);
    check(chunk.length<=8192,"FRAME_INVALID");
    state.size+=chunk.length;check(state.size<=2097152,"MESSAGE_LIMIT");
    state.parts.set(f.index,chunk);pending.set(f.frame,state);
    if(state.parts.size===state.count){
      const joined=new Uint8Array(state.size);let offset=0;
      for(let i=0;i<state.count;i++){joined.set(state.parts.get(i),offset);offset+=state.parts.get(i).length;}
      pending.delete(f.frame);onMessage(JSON.parse(decoder.decode(joined)));
    }
  };
}
function sender(channel) {
  let chain=Promise.resolve();
  return value=>{
    const job=chain.then(async()=>{
      const raw=encoder.encode(JSON.stringify(value));check(raw.length<=65536,"REQUEST_LIMIT");
      const frame=crypto.randomUUID().replaceAll("-",""),count=Math.max(1,Math.ceil(raw.length/8192));
      for(let index=0;index<count;index++){
        const deadline=performance.now()+10000;
        while(channel.bufferedAmount>262144){check(channel.readyState==="open"&&performance.now()<deadline,"BACKPRESSURE_TIMEOUT");await new Promise(r=>setTimeout(r,10));}
        check(channel.readyState==="open","DISCONNECTED");
        channel.send(JSON.stringify({frame,index,count,data:base64(raw.subarray(index*8192,(index+1)*8192))}));
      }
    });
    chain=job.catch(()=>{});return job;
  };
}

export class WebRtcTransport {
  constructor(api, appToken, onStatus=()=>{}, options={}) {
    this.options=options;
    this.api=api;this.appToken=appToken;this.onStatus=onStatus;
    this.pending=new Map();this.listeners=new Set();this.senders={};this.closed=false;this.ready=false;
    this.events=[];this.waiters=[];this.challenge=deferred();this.latestState=[];this.stateBuilding=null;
  }
  emitEvent(data) {
    const index=this.waiters.findIndex(w=>w.type===data.type || ["error","cancelled"].includes(data.type));
    if(index>=0){const [waiter]=this.waiters.splice(index,1);if(["error","cancelled"].includes(data.type)) waiter.reject(fault(data.code||"JOIN_CANCELLED"));else waiter.resolve(data);}
    else {check(this.events.length<128,"SIGNAL_LIMIT");this.events.push(data);}
  }
  wait(type,ms=60000) {
    const at=this.events.findIndex(e=>e.type===type||["error","cancelled"].includes(e.type));
    if(at>=0){const [e]=this.events.splice(at,1);return ["error","cancelled"].includes(e.type)?Promise.reject(fault(e.code||"JOIN_CANCELLED")):Promise.resolve(e);}
    const task=deferred(),entry={type,...task};this.waiters.push(entry);
    return bounded(task.promise,ms).finally(()=>{this.waiters=this.waiters.filter(w=>w!==entry);});
  }
  async connect({roomId,roomCode,password="",invitation="",relayOnly=false}) {
    try {
      check(Boolean(roomId)!==Boolean(roomCode),"INPUT_INVALID");
      this.onStatus("正在申请加入");
      this.identity=await crypto.subtle.generateKey({name:"ECDSA",namedCurve:"P-256"},true,["sign","verify"]);
      this.session=await this.api("session",{publicKey:await crypto.subtle.exportKey("jwk",this.identity.publicKey)});
      this.socket=new WebSocket(location.origin.replace("http","ws")+(this.options.signalPath||"/signal"));
      this.socket.onmessage=e=>{try{this.emitEvent(JSON.parse(e.data));}catch{this.close();}};
      this.socket.onclose=()=>{this.onStatus(this.ready?"信令暂时离线，已有连接继续":"信令连接已断开");};
      await bounded(new Promise((resolve,reject)=>{this.socket.onopen=resolve;this.socket.onerror=()=>reject(fault("SIGNAL_UNAVAILABLE"));}),15000);
      this.socket.send(JSON.stringify(this.options.auth?this.options.auth(this.session):{appToken:this.appToken,clientToken:this.session.clientToken}));
      await this.wait("authenticated",15000);
      await this.api("join",{...(roomCode?{roomCode}:{roomId}),password,invitation},this.session.clientToken);
      this.intent=(await this.wait("decision")).intent;
      check(this.intent.status==="approved","JOIN_REJECTED");
      const ice=await this.api("turn",{intentId:this.intent.intentId,role:"client"},this.session.clientToken);
      check(!relayOnly || ice.iceServers.length,"TURN_REQUIRED");
      this.pc=new RTCPeerConnection({iceServers:ice.iceServers,iceTransportPolicy:relayOnly?"relay":"all"});
      this.pc.onconnectionstatechange=()=>{
        this.onStatus(({connected:"已连接",failed:"连接失败，请重新加入",disconnected:"连接中断",closed:"已断开"})[this.pc.connectionState]||"正在建立连接");
        if(["failed","closed"].includes(this.pc.connectionState)) this.failPending("DISCONNECTED");
      };
      for(const name of ["control","state","package"]){
        const channel=this.pc.createDataChannel(name,{ordered:true});
        this.senders[name]=sender(channel);
        channel.onmessage=e=>{try{frameReceiverForChannel(e.data);}catch{this.close();}};
        const frameReceiverForChannel=frameReceiver(value=>this.receive(value));
      }
      this.onStatus(relayOnly?"正在建立中继连接":"正在协商直连或中继");
      await this.pc.setLocalDescription(await this.pc.createOffer());await gather(this.pc);
      const description={type:"offer",sdp:this.pc.localDescription.sdp},offerFp=fingerprint(description.sdp);
      this.socket.send(JSON.stringify({type:"signal",intentId:this.intent.intentId,description}));
      const answer=await this.wait("signal",45000);
      check(answer.intentId===this.intent.intentId,"SIGNAL_MISMATCH");
      await verify(this.intent.hostKey,answer.intentId+"|"+offerFp+"|"+fingerprint(answer.description.sdp)+"|"+this.intent.connectionEpoch,answer.signature);
      await this.pc.setRemoteDescription(answer.description);
      const challenge=await bounded(this.challenge.promise,30000,"CONNECT_TIMEOUT");
      const signature=base64(new Uint8Array(await crypto.subtle.sign({name:"ECDSA",hash:"SHA-256"},this.identity.privateKey,encoder.encode(challenge)))).replaceAll("+","-").replaceAll("/","_").replaceAll("=","");
      return await this.rpc("admit",{ticket:this.intent.ticket,signature});
    } catch(error) {this.close();throw error;}
  }
  receive(value) {
    if(value.event==="challenge") this.challenge.resolve(value.challenge);
    else if(value.event==="state") {
      const message=value.message;
      if(message.type==="reset"){this.latestState=[];this.stateBuilding=null;}
      if(message.type==="snapshot.begin")this.stateBuilding=[];
      if(this.stateBuilding&&["snapshot.begin","snapshot.part","snapshot.end"].includes(message.type)){
        check(this.stateBuilding.length<130,"SNAPSHOT_LIMIT");this.stateBuilding.push(message);
        if(message.type==="snapshot.end"){this.latestState=this.stateBuilding;this.stateBuilding=null;}
      }
      for(const listener of [...this.listeners])listener.onMessage(message);
    }
    else if(this.pending.has(value.id)){
      const p=this.pending.get(value.id);this.pending.delete(value.id);
      if(value.ok)p.resolve(value.result);else p.reject(Object.assign(fault(value.error.code),value.error));
    }
  }
  async rpc(method,params={},channel="control") {
    check(!this.closed && this.senders[channel],"DISCONNECTED");check(this.pending.size<32,"CLIENT_BUSY");
    const id=crypto.randomUUID().replaceAll("-",""),task=deferred();this.pending.set(id,task);
    try {await this.senders[channel]({id,method,params});return await bounded(task.promise,30000);}
    finally {this.pending.delete(id);}
  }
  request(path,options={}) {return this.rpc("request",{path,options});}
  open(onMessage,onClose) {
    const first=!this.listeners.size,listener={onMessage,onClose};this.listeners.add(listener);
    if(first)this.rpc("subscribe").catch(()=>onClose?.());
    else for(const message of this.latestState)queueMicrotask(()=>{if(this.listeners.has(listener))onMessage(message);});
    return {close:()=>{this.listeners.delete(listener);if(!this.listeners.size&&!this.closed){this.latestState=[];this.rpc("unsubscribe").catch(()=>{});}}};
  }
  failPending(code) {
    this.latestState=[];this.stateBuilding=null;
    for(const p of this.pending.values())p.reject(fault(code));this.pending.clear();
    for(const listener of this.listeners)listener.onClose?.();
  }
  close() {
    if(this.closed)return;this.closed=true;this.ready=false;this.failPending("DISCONNECTED");
    this.socket?.close();this.pc?.close();
  }
  async manifest() {
    const signed=await this.rpc("package.manifest");
    check(await sha(encoder.encode(canonical(signed.manifest)))===signed.digest,"MANIFEST_CORRUPTED");
    await verify(this.intent.hostKey,signed.digest,signed.signature);
    return signed;
  }
  async sync(signed,onProgress=()=>{}) {
    const manifest=signed.manifest,cache=await openCache();
    check(manifest.protocolVersion===1&&Array.isArray(manifest.files)&&manifest.files.length<=10000,"MANIFEST_INVALID");
    const paths=new Set();let total=0;
    for(const file of manifest.files){
      check(typeof file.path==="string"&&!file.path.startsWith("/")&&!/[\\:\x00-\x1f]/.test(file.path)&&file.path.split("/").every(p=>p&&p!==".."&&p!==".")&&!paths.has(file.path.toLowerCase()),"PACKAGE_PATH_INVALID");
      paths.add(file.path.toLowerCase());
      check(/^[0-9a-f]{64}$/.test(file.digest)&&Number.isInteger(file.size)&&file.size>=0&&file.size<=67108864&&file.blocks.length===Math.ceil(file.size/BLOCK),"MANIFEST_INVALID");
      total+=file.size;
    }
    check(total<=536870912,"PACKAGE_LIMIT");
    const estimate=await navigator.storage?.estimate?.();
    if(estimate?.quota)check(estimate.quota-(estimate.usage||0)>total*2,"CACHE_SPACE");
    let complete=0,downloaded=0;const files=new Map();
    try {
      for(const file of manifest.files){
        let raw=await cache.get("blob:"+file.digest);
        if(!raw||await sha(raw)!==file.digest){
          const parts=[];
          for(let index=0;index<file.blocks.length;index++){
            const partKey="partial:"+file.digest+":"+index;
            let part=await cache.get(partKey);
            if(!part||await sha(part)!==file.blocks[index]){
              const chunk=await this.rpc("package.chunk",{manifestDigest:signed.digest,fileDigest:file.digest,index},"package");
              part=unbase64(chunk.data);
              check(part.length<=BLOCK&&await sha(part)===file.blocks[index],"CHUNK_CORRUPTED");
              await cache.put(partKey,part);downloaded+=part.length;
            }
            parts.push(part);
          }
          raw=new Uint8Array(file.size);let offset=0;
          for(const part of parts){check(offset+part.length<=raw.length,"FILE_CORRUPTED");raw.set(part,offset);offset+=part.length;}
          check(offset===file.size&&await sha(raw)===file.digest,"FILE_CORRUPTED");
          await cache.put("blob:"+file.digest,raw);
        }
        files.set(file.path,raw);complete+=file.size;onProgress(complete,total);
      }
      await cache.put("room:"+this.intent.roomId,{digest:signed.digest,manifest});
      await this.rpc("ready",{manifestDigest:signed.digest});this.ready=true;
      return {files,manifest,downloadedBytes:downloaded};
    } finally {cache.close();}
  }
  async stats() {
    const report=await this.pc.getStats();let pair;
    for(const item of report.values()) if(item.type==="transport"&&item.selectedCandidatePairId)pair=report.get(item.selectedCandidatePairId);
    if(!pair)for(const item of report.values())if(item.type==="candidate-pair"&&item.nominated&&item.state==="succeeded")pair=item;
    return {state:this.pc.connectionState,localType:pair?report.get(pair.localCandidateId)?.candidateType:null,
      remoteType:pair?report.get(pair.remoteCandidateId)?.candidateType:null,rttMs:pair?.currentRoundTripTime?Math.round(pair.currentRoundTripTime*1000):null};
  }
}

export function openCache(name="onlinecoc-p2p-cache-v1") {
  return new Promise((resolve,reject)=>{
    const request=indexedDB.open(name,1);
    request.onupgradeneeded=()=>request.result.createObjectStore("content");
    request.onerror=()=>reject(fault("CACHE_UNAVAILABLE"));
    request.onsuccess=()=>{
      const db=request.result;
      function operation(mode,fn){return new Promise((done,fail)=>{const tx=db.transaction("content",mode),r=fn(tx.objectStore("content"));let result;r.onsuccess=()=>{result=r.result;};tx.oncomplete=()=>done(result);tx.onerror=()=>fail(fault("CACHE_WRITE_FAILED"));tx.onabort=()=>fail(fault("CACHE_WRITE_FAILED"));});}
      resolve({get:key=>operation("readonly",s=>s.get(key)),put:(key,value)=>operation("readwrite",s=>s.put(value,key)),close:()=>db.close()});
    };
  });
}
