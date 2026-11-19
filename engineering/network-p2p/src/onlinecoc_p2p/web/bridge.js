const allowedGet=/^(me|view|contracts|catalog|chat\/members|knowledge\/capabilities|receipts\/[A-Za-z0-9_.-]+)$/;
const allowedPost=/^(commands|query|calculate|chat\/history|knowledge\/(preview|search|read|grants\/query))$/;

export async function mountPackage(container, packageData, transport, prepare) {
  const {manifest,files}=packageData;
  if(!manifest.entry)return null;
  const raw=files.get(manifest.entry);if(!raw)throw new Error("PACKAGE_ENTRY_MISSING");
  const decoder=new TextDecoder(),documentCopy=new DOMParser().parseFromString(decoder.decode(raw),"text/html");
  const urls=new Map();
  const mime=path=>path.endsWith(".js")?"text/javascript":path.endsWith(".css")?"text/css":path.endsWith(".svg")?"image/svg+xml":path.endsWith(".png")?"image/png":path.endsWith(".jpg")?"image/jpeg":"application/octet-stream";
  for(const [path,bytes]of files)urls.set(path,URL.createObjectURL(new Blob([bytes],{type:mime(path)})));
  for(const element of documentCopy.querySelectorAll("[src],[href]")){
    for(const attribute of ["src","href"]){
      const value=element.getAttribute(attribute);
      if(!value)continue;
      const base=manifest.entry.includes("/")?manifest.entry.slice(0,manifest.entry.lastIndexOf("/")+1):"";
      const path=new URL(value,"https://package.invalid/"+base).pathname.slice(1);
      if(urls.has(path)&&!value.includes(":")&&!value.startsWith("//"))element.setAttribute(attribute,urls.get(path));
      else if(!value.startsWith("#"))element.removeAttribute(attribute);
    }
  }
  for(const element of documentCopy.querySelectorAll("base,meta[http-equiv],iframe,object,embed,form"))element.remove();
  const policy=documentCopy.createElement("meta");policy.httpEquiv="Content-Security-Policy";
  policy.content="default-src 'none'; script-src 'unsafe-inline' blob:; style-src 'unsafe-inline' blob:; img-src blob: data:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'";
  documentCopy.head.prepend(policy);
  const iframe=document.createElement("iframe");iframe.title=manifest.packageId;iframe.setAttribute("sandbox","allow-scripts");iframe.referrerPolicy="no-referrer";
  const rendered=await prepare("<!doctype html>"+documentCopy.documentElement.outerHTML);
  iframe.src=rendered.url;
  let port,subscription,connected=false;let active=true;const pending=new Set();
  function hello(event){
    if(!active||connected||event.source!==iframe.contentWindow||event.data?.type!=="onlinecoc:connect")return;
    connected=true;const channel=new MessageChannel();port=channel.port1;
    port.onmessage=async event=>{
      const value=event.data;
      if(!active||!value||typeof value.id!=="string"||value.id.length>64||pending.size>=8)return;
      pending.add(value.id);
      try{
        let result;
        if(value.method==="request"){
          const {path,options={}}=value.params||{},method=options.method||"GET";
          if(!(method==="GET"?allowedGet.test(path):method==="POST"&&allowedPost.test(path)))throw new Error("ROUTE_NOT_EXPOSED");
          if(JSON.stringify(value).length>65536)throw new Error("LIMIT_EXCEEDED");
          result=await transport.request(path,options);
          if(path==="me")result={accountId:result.accountId};
        }else if(value.method==="subscribe"){
          subscription?.close();subscription=transport.open(message=>port.postMessage({event:"state",message}),()=>port.postMessage({event:"closed"}));result={subscribed:true};
        }else throw new Error("METHOD_NOT_EXPOSED");
        if(active)port.postMessage({id:value.id,ok:true,result});
      }catch(error){if(active)port.postMessage({id:value.id,ok:false,error:{code:error.code||error.message}});}
      finally{pending.delete(value.id);}
    };
    iframe.contentWindow.postMessage({type:"onlinecoc:port"},"*",[channel.port2]);
  }
  window.addEventListener("message",hello);container.replaceChildren(iframe);
  return ()=>{active=false;window.removeEventListener("message",hello);subscription?.close();port?.close();iframe.remove();for(const url of urls.values())URL.revokeObjectURL(url);};
}
