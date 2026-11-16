// Executed before the bundled modules, inside the opaque player sandbox.
async function connectStumpsville(){
  // The sandbox forbids native form navigation. Keep local form semantics by
  // dispatching only a cancellable DOM event to the existing package handlers.
  const submit=(form,button)=>{if(form.reportValidity())form.dispatchEvent(new SubmitEvent('submit',{bubbles:true,cancelable:true,submitter:button||null}));};
  HTMLFormElement.prototype.requestSubmit=function(button){submit(this,button);};
  // Shadow DOM retargets event.target to the host; use the composed path for embedded forms.
  document.addEventListener('click',event=>{const button=event.composedPath().find(node=>node instanceof HTMLElement&&node.matches('button,input[type=submit]'));if(button?.form&&button.type==='submit'){event.preventDefault();submit(button.form,button);}},true);
  document.addEventListener('keydown',event=>{const input=event.composedPath().find(node=>node instanceof HTMLInputElement);if(event.key==='Enter'&&input?.form){event.preventDefault();submit(input.form);}},true);
  const pending=new Map();let port,serial=0;
  const ready=new Promise(resolve=>window.addEventListener('message',function receive(event){
    if(event.source!==parent||event.data?.type!=='onlinecoc:port'||port)return;
    port=event.ports[0];window.removeEventListener('message',receive);
    port.onmessage=event=>{const v=event.data,p=pending.get(v.id);if(!p)return;pending.delete(v.id);clearTimeout(p.timer);v.ok?p.resolve(v.result):p.reject(Object.assign(Error(v.error.code),v.error));};resolve();
  }));
  parent.postMessage({type:'onlinecoc:connect'},'*');await ready;
  const call=(method,params={})=>new Promise((resolve,reject)=>{const id=String(++serial),timer=setTimeout(()=>{pending.delete(id);reject(Error('BRIDGE_TIMEOUT'));},25000);pending.set(id,{resolve,reject,timer});port.postMessage({id,method,params});});
  const info=await call('bridge.info');if(info.version!==1)throw Error('BRIDGE_VERSION_UNSUPPORTED');
  const saved=await call('storage.snapshot');let writing=Promise.resolve();
  const storage={getItem:k=>saved[k]??null,setItem(k,v){saved[k]=String(v);writing=writing.then(()=>call('storage.write',{key:k,value:String(v)}));writing.catch(()=>{});},removeItem(k){delete saved[k];writing=writing.then(()=>call('storage.write',{key:k,value:null}));writing.catch(()=>{});}};
  const groups=new Map();
  const load=async group=>{if(!groups.has(group))groups.set(group,call('resource.load',{group}));return groups.get(group);};
  const json=async path=>{if(path in STUMPSVILLE_STARTUP)return STUMPSVILLE_STARTUP[path];const group=await load('locale-en'),file=group.files.find(f=>f.path===path);if(!file)throw Error('RESOURCE_NOT_EXPOSED');return JSON.parse(new TextDecoder().decode(file.bytes));};
  let mouse;
  const images=()=>{for(const img of document.querySelectorAll('img[data-web-image="mouse"]')){img.removeAttribute('data-web-image');(mouse??=load('portraits').then(g=>URL.createObjectURL(new Blob([g.files.find(f=>f.path==='art/mouse.png').bytes],{type:'image/png'})))).then(url=>img.src=url).catch(()=>{});}};
  new MutationObserver(images).observe(document.body,{childList:true,subtree:true});
  return {info,storage,json,flush:()=>writing,leave:()=>call('session.leave'),
    async api(path,body){
      if(path==='setup/status')return {ready:true,canSetup:false};
      if(path==='api/v1/logout'){call('session.leave');return {};}
      const u=new URL(path,'https://package.invalid/'),method=body===undefined?'GET':'POST';
      if(u.pathname.startsWith('/package/')){
        // Page heartbeat identifiers are local UI bookkeeping, not remote authority.
        u.searchParams.delete('page');
        return call('service.request',{path:u.pathname.slice(1),method,query:Object.fromEntries(u.searchParams),...(body===undefined?{}:{body})});
      }
      if(!u.pathname.startsWith('/api/v1/'))throw Error('ROUTE_NOT_EXPOSED');
      return call('request',{path:u.pathname.slice(8),options:{method,...(body===undefined?{}:{body})}});
    }
  };
}
