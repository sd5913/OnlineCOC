import {canonical,sha,openCache} from "./transport.js";
const encoder=new TextEncoder();
const check=(value,code)=>{if(!value)throw Object.assign(new Error(code),{code});};
const decode=text=>Uint8Array.from(atob(text.replaceAll("-","+").replaceAll("_","/")),x=>x.charCodeAt(0));
export class ResourceLoader{
  constructor(transport,accountId,version){this.transport=transport;this.accountId=accountId;this.version=version;this.cacheName="onlinecoc-web:"+accountId+":"+transport.intent.roomId;this.loaded=new Map();this.downloaded=0;this.pending=new Map();}
  async load(group,onProgress=()=>{}){
    if(this.pending.has(group))return this.pending.get(group);
    const task=this.fetchGroup(group,onProgress);this.pending.set(group,task);
    try{return await task;}finally{this.pending.delete(group);}
  }
  async fetchGroup(group,onProgress){
    const t=this.transport;
    // Always reauthorize, including a cache hit. Unknown groups/hashes are never probed locally first.
    const signed=await t.rpc("resource.manifest",{resourceVersion:this.version,group});
    const m=signed.manifest;
    check(m.protocolVersion===2&&m.resourceVersion===this.version&&m.group===group&&Array.isArray(m.files)&&m.files.length<=10000,"MANIFEST_INVALID");
    check(await sha(encoder.encode(canonical(m)))===signed.digest,"MANIFEST_CORRUPTED");
    const key=await crypto.subtle.importKey("jwk",t.intent.hostKey,{name:"ECDSA",namedCurve:"P-256"},false,["verify"]);
    check(await crypto.subtle.verify({name:"ECDSA",hash:"SHA-256"},key,decode(signed.signature),encoder.encode(signed.digest)),"HOST_IDENTITY_INVALID");
    let total=0,done=0;const paths=new Set();
    for(const f of m.files){check(typeof f.path==="string"&&!/[\\:\x00-\x1f]/.test(f.path)&&f.path.split("/").every(p=>p&&p!==".."&&p!==".")&&!paths.has(f.path.toLowerCase()),"PACKAGE_PATH_INVALID");paths.add(f.path.toLowerCase());check(/^[a-f0-9]{64}$/.test(f.digest)&&Number.isInteger(f.size)&&f.size>=0&&f.size<=67108864&&Array.isArray(f.blocks)&&f.blocks.length===Math.ceil(f.size/262144),"MANIFEST_INVALID");total+=f.size;}
    check(total<=536870912,"PACKAGE_LIMIT");
    const files=new Map(),cache=await openCache(this.cacheName);
    try{
      for(const file of m.files){
        let raw=await cache.get("blob:"+file.digest);
        if(!raw||raw.length!==file.size||await sha(raw)!==file.digest){
          const parts=[];
          for(let index=0;index<file.blocks.length;index++){
            const partKey="partial:"+file.digest+":"+index;let part=await cache.get(partKey);
            if(!part||await sha(part)!==file.blocks[index]){
              const result=await t.rpc("resource.chunk",{resourceVersion:this.version,group,manifestDigest:signed.digest,fileDigest:file.digest,index},"package");
              part=decode(result.data);check(part.length<=262144&&await sha(part)===file.blocks[index],"CHUNK_CORRUPTED");await cache.put(partKey,part);this.downloaded+=part.length;
            }parts.push(part);
          }
          raw=new Uint8Array(file.size);let offset=0;for(const part of parts){check(offset+part.length<=raw.length,"FILE_CORRUPTED");raw.set(part,offset);offset+=part.length;}
          check(offset===file.size&&await sha(raw)===file.digest,"FILE_CORRUPTED");await cache.put("blob:"+file.digest,raw);
        }
        files.set(file.path,raw);done+=file.size;onProgress(done,total);
      }
      await t.rpc("resource.ready",{resourceVersion:this.version,group,manifestDigest:signed.digest});
      if(group==="startup")t.ready=true;
      const result={manifest:m,files};this.loaded.set(group,result);return result;
    }finally{cache.close();}
  }
  clear(){this.loaded.clear();indexedDB.deleteDatabase(this.cacheName);}
}
