import {t} from './i18n.js';
import {mountKeeperAIQueue} from './keeper-queue.js';
let current=null, epoch=0;
export const embeddedAI={
  close(){epoch++;const old=current;current=null;old?.queue?.destroy();old?.queueRoot?.remove();old?.settings?.destroy();old?.unsubscribe?.();old?.view?.destroy();old?.client?.destroy();old?.root.remove();},
  async mount(target,{base,manager=false,account='',scope='',onReview=()=>{},onQueueCount=()=>{},onSettings=()=>{},onReveal=()=>{},onKnowledgeRequest=()=>{},rulingsTarget=null,settings=false}={}){
    const key=JSON.stringify([String(base),manager,account,scope]);
    if(!target){if(manager&&current?.key===key){current.root.remove();current.queueRoot?.remove();current.rulingsTarget=null;}else this.close();return;}
    if(current?.key===key){current.mode=settings?'settings':'chat';current.queue?.relocalize();current.rulingsTarget=rulingsTarget;target.append(current.root);current.attach?.();return;}
    this.close();const generation=epoch,root=document.createElement('div');root.className='embedded-ai-root';
    target.append(root);current={key,root,rulingsTarget,mode:settings?'settings':'chat'};root.textContent=t('ai.loading');
    const live=()=>current?.root===root&&generation===epoch;
    try{
      const web=globalThis.stumpsvilleWeb;
      const modulePromise=web?Promise.resolve(web.aiModules):import(new URL('ai-ui/pack.js',base).href).catch(error=>({loadError:error}));
      const capabilities=web?await web.api('api/v1/capabilities'):await fetch(new URL('api/v1/capabilities',base),{credentials:'same-origin'}).then(response=>{if(!response.ok)throw Error(t('ai.offline'));return response.json();});
      if(!live())return;
      if(!capabilities.ai?.available){root.textContent=t('ai.disabled');if(current.rulingsTarget)current.rulingsTarget.replaceChildren();return;}
      const module=await modulePromise;if(module.loadError)throw module.loadError;
      if(!live())return;
      const http=web?null:new module.HttpTransport(new URL('api/v1/',base).href);
      let uncertain=manager?localStorage.getItem('sv.desktop.aiQueue.'+scope+'.'+account):null,notice=null;
      const transport={async request(path,options={}){
        if(uncertain&&path==='ai/commands')throw Error(t('ai.pending'));
        if(!manager&&path==='ai/commands'&&options.body?.op==='ai.session.create')options={...options,body:{...options.body,args:{...options.body.args,accessLevel:'player'}}};
        let result;
        try{
          if(web){
            result=path==='me'?{csrf:null}:path==='view'?await web.api('api/v1/view'):await web.api('package/ai',{path,method:options.method||'GET',...(options.body===undefined?{}:{body:options.body})});
          }else result=await http.request(path,options);
        }catch(error){
          if(live()&&path==='ai/commands'&&options.body?.requestId){uncertain=options.body.requestId;if(manager)localStorage.setItem('sv.desktop.aiQueue.'+scope+'.'+account,uncertain);if(manager&&current.queue)current.queue.remember(uncertain);if(notice&&(!current.queue||current.mode==='settings'))notice.hidden=false;}
          throw error;
        }
        if(uncertain&&path==='ai/receipts/'+encodeURIComponent(uncertain)&&['committed','rejected'].includes(result.status)){uncertain=null;if(manager)localStorage.removeItem('sv.desktop.aiQueue.'+scope+'.'+account);if(notice)notice.hidden=true;}
        // Replies are already filtered by the host's immutable session permission.
        if(!manager&&path.startsWith('ai/sessions/')&&result.items)result={...result,items:result.items.map(({proposalId,diagnostics,...item})=>item)};
        if(!manager&&path==='ai/access')result={...result,role:'player',defaultLevel:'player'};
        if(!manager&&path.startsWith('ai/sessions?'))result={...result,items:result.items.filter(s=>s.owner===account&&s.accessLevel==='player')};
        return path==='view'&&!manager?{...result,role:'player'}:result;
      }};
      const client=new module.AiClient(transport);current.client=client;await client.resume();
      if(!live()){client.destroy();return;}
      root.replaceChildren();
      notice=document.createElement('div');notice.className='native-ai-recovery';notice.hidden=!uncertain;
      const message=document.createElement('span');message.textContent=t('ai.pending');
      const recover=document.createElement('button');recover.type='button';recover.textContent=t('ai.receipt');notice.append(message,recover);root.append(notice);
      const body=document.createElement('div');body.className='native-ai-body';root.append(body);
      const guide=document.createElement('p');guide.className='notice';guide.hidden=true;root.append(guide);
      if(manager&&!web)http.request('../../package/integrations').then(data=>{if(live()&&(data.ai?.queryMode!=='demand'||!data.ai?.guideCurrent)){guide.textContent=t('ai.reloadGuide');guide.hidden=current.mode!=='settings';current.guideOutdated=true;}}).catch(()=>{});
      const settingsBody=document.createElement('div');settingsBody.className='native-ai-body native-ai-settings';root.append(settingsBody);
      const identity=JSON.stringify([client.view?.accountId,client.view?.role,client.view?.authorityEpoch]);
      current.unsubscribe=client.subscribe(()=>{if(live()&&(!client.connected||identity!==JSON.stringify([client.view?.accountId,client.view?.role,client.view?.authorityEpoch])))this.close();});
      current.attach=()=>{
        if(!live())return;
        guide.hidden=!(current.mode==='settings'&&current.guideOutdated);
        body.hidden=current.mode==='settings';settingsBody.hidden=current.mode!=='settings';
        if(current.mode==='settings'&&!current.settings)current.settings=module.mountAISettings(settingsBody,client);
        if(current.mode==='chat'&&!current.view)current.view=module.mountAIConversation(body,client,{title:t('ai.title'),review:manager,onReview:id=>{if(current?.queueRoot){current.queue.refresh();current.queue.focus();}else onReview(id);}});
        if(manager&&current.rulingsTarget){
          if(!current.queue){const queueRoot=document.createElement('div');current.queueRoot=queueRoot;current.queue=mountKeeperAIQueue(queueRoot,client,module,{scope,account,onCount:onQueueCount,onSettings,onReveal,onKnowledgeRequest,onSession:id=>current?.view?.resume({sessionId:id})});}
          current.rulingsTarget.append(current.queueRoot);
        }
        notice.hidden=!uncertain||(current.mode==='chat'&&!!current.queue);
      };
      current.attach();
      recover.onclick=async()=>{if(!uncertain)return;recover.disabled=true;try{
        const receipt=await client.aiReceipt(uncertain);if(!live())return;
        if(['committed','rejected'].includes(receipt.status)){uncertain=null;notice.hidden=true;await current.queue?.refresh();await current.view?.refresh();if(current.view&&receipt.result?.sessionId&&!receipt.result.deleted)await current.view.select(receipt.result.sessionId);}
        else message.textContent=t('ai.pending');
      }catch(error){if(live())message.textContent=error.code||error.message;}finally{if(live())recover.disabled=false;}};
    }catch(error){if(live())root.textContent=error.code||error.message;}
  }
};
