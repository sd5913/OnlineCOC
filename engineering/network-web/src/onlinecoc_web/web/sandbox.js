import {scopedStorage} from './storage.js';
export async function mountGame(container,data,transport,loader,options={}){
  const {manifest,files}=data,raw=files.get(manifest.entry);if(!raw)throw new Error("PACKAGE_ENTRY_MISSING");
  const me=await transport.request('me');
  const storage=manifest.bridge?scopedStorage([loader.accountId,transport.intent.roomId,me.accountId,manifest.packageId,loader.version],manifest.bridge.storage):null;
  const doc=new DOMParser().parseFromString(new TextDecoder().decode(raw),"text/html"),urls=[];
  const mime=path=>path.endsWith(".js")?"text/javascript":path.endsWith(".css")?"text/css":path.endsWith(".svg")?"image/svg+xml":path.endsWith(".png")?"image/png":"application/octet-stream";
  const mappings=new Map();for(const [path,bytes]of files){const url=URL.createObjectURL(new Blob([bytes],{type:mime(path)}));urls.push(url);mappings.set(path,url);}
  for(const el of doc.querySelectorAll("[src],[href]"))for(const attr of ["src","href"]){const value=el.getAttribute(attr);if(!value)continue;const path=new URL(value,"https://package.invalid/"+manifest.entry).pathname.slice(1);if(mappings.has(path)&&!value.includes(":")&&!value.startsWith("//"))el.setAttribute(attr,mappings.get(path));else if(!value.startsWith("#"))el.removeAttribute(attr);}
  for(const el of doc.querySelectorAll("base,meta[http-equiv],iframe,object,embed,form"))el.remove();
  const html="<!doctype html>"+doc.documentElement.outerHTML;
  const frame=document.createElement("iframe");frame.title=manifest.packageId;frame.sandbox="allow-scripts";frame.referrerPolicy="no-referrer";frame.src="/sandbox.html";
  let connected=false,port,sub,active=true;const pending=new Set();
  const hello=event=>{
    if(!active||event.source!==frame.contentWindow)return;
    if(event.data?.type==="onlinecoc:sandbox-ready"){frame.contentWindow.postMessage({type:"onlinecoc:render",html},"*");return;}
    if(connected||event.data?.type!=="onlinecoc:connect")return;
    connected=true;const channel=new MessageChannel();port=channel.port1;
    port.onmessage=async event=>{
      const v=event.data;if(!active||!v||typeof v.id!=="string"||v.id.length>64||pending.size>=8||pending.has(v.id))return;
      pending.add(v.id);
      try{
        if(JSON.stringify(v).length>65536)throw new Error("LIMIT_EXCEEDED");let result;
        if(v.method==="request"){
          const {path,options={}}=v.params||{};
          if(["login","logout","capabilities"].includes(path))throw new Error("ROUTE_NOT_EXPOSED");
          result=await transport.request(path,options);if(path==="me")result={accountId:result.accountId};
        }else if(v.method==='service.request'){
          if(!manifest.bridge)throw Error('BRIDGE_NOT_DECLARED');
          result=await transport.rpc('service.request',v.params);
        }else if(v.method==='bridge.info'){
          result={version:manifest.bridge?.version||0,resourceVersion:loader.version,accountId:me.accountId};
        }else if(v.method.startsWith('storage.')){
          if(!storage)throw Error('BRIDGE_NOT_DECLARED');
          const current=await transport.request('me');if(current.accountId!==me.accountId)throw Error('SESSION_MISMATCH');
          if(v.method==='storage.snapshot')result=storage.snapshot();
          else if(v.method==='storage.write')result=storage.write(v.params?.key,v.params?.value);
          else throw Error('METHOD_NOT_EXPOSED');
        }else if(v.method==='session.leave'){
          options.onLeave?.();result={left:true};
        }else if(v.method==="resource.load"){
          const value=await loader.load(v.params?.group);
          // File bytes stay in the sandbox; no top-level same-origin navigation is provided.
          result={group:value.manifest.group,files:[...value.files].map(([path,bytes])=>({path,bytes}))};
        }else if(v.method==="subscribe"){
          sub?.close();sub=transport.open(message=>port.postMessage({event:"state",message}),()=>port.postMessage({event:"closed"}));result={subscribed:true};
        }else throw new Error("METHOD_NOT_EXPOSED");
        if(active)port.postMessage({id:v.id,ok:true,result});
      }catch(error){if(active)port.postMessage({id:v.id,ok:false,error:{code:error.code||error.message,status:error.status||503}});}finally{pending.delete(v.id);}
    };
    frame.contentWindow.postMessage({type:"onlinecoc:port"},"*",[channel.port2]);
  };
  window.addEventListener("message",hello);container.replaceChildren(frame);
  return ()=>{active=false;window.removeEventListener("message",hello);sub?.close();port?.close();frame.remove();urls.forEach(URL.revokeObjectURL);};
}
