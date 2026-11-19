import {t} from './i18n.js';
import {mountKeeperAIQueue} from './keeper-queue.js';
let current=null, epoch=0;
export const embeddedAI={
  close(){epoch++;const old=current;current=null;old?.queue?.destroy();old?.queueRoot?.remove();old?.view?.destroy();old?.client?.destroy();old?.root.remove();},
  async mount(target,{base,manager=false,account='',scope='',onReview=()=>{},onQueueCount=()=>{},onSettings=()=>{},onReveal=()=>{},rulingsTarget=null}={}){
    const key=JSON.stringify([String(base),manager,account,scope]);
    if(!target){this.close();return;}
    if(current?.key===key){current.queue?.relocalize();current.rulingsTarget=rulingsTarget;target.append(current.root);if(rulingsTarget&&current.queueRoot)rulingsTarget.append(current.queueRoot);return;}
    this.close();const generation=epoch,root=document.createElement('div');root.className='embedded-ai-root';
    target.append(root);current={key,root,rulingsTarget};root.textContent=t('ai.loading');
    const live=()=>current?.root===root&&generation===epoch;
    try{
      const web=globalThis.stumpsvilleWeb;
      const module=web?web.aiModules:await import(new URL('ai-ui/pack.js',base).href);
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
          if(live()&&path==='ai/commands'&&options.body?.requestId){uncertain=options.body.requestId;if(manager&&current.queue)current.queue.remember(uncertain);else if(notice)notice.hidden=false;}
          throw error;
        }
        if(uncertain&&path==='ai/receipts/'+encodeURIComponent(uncertain)&&['committed','rejected'].includes(result.status)){uncertain=null;if(notice)notice.hidden=true;}
        // Replies are already filtered by the host's immutable session permission.
        if(!manager&&path.startsWith('ai/sessions/')&&result.items)result={...result,items:result.items.map(({proposalId,diagnostics,...item})=>item)};
        if(!manager&&path==='ai/access')result={...result,role:'player',defaultLevel:'player'};
        if(!manager&&path.startsWith('ai/sessions?'))result={...result,items:result.items.filter(s=>s.owner===account&&s.accessLevel==='player')};
        return path==='view'&&!manager?{...result,role:'player'}:result;
      }};
      const caps=await transport.request('capabilities');if(!live())return;
      if(!caps.ai?.available){root.textContent=t('ai.disabled');if(current.rulingsTarget)current.rulingsTarget.textContent=t('ai.disabled');return;}
      const client=new module.AiClient(transport);current.client=client;await client.resume();
      if(!live()){client.destroy();return;}
      root.replaceChildren();
      notice=document.createElement('div');notice.className='native-ai-recovery';notice.hidden=true;
      const message=document.createElement('span');message.textContent=t('ai.pending');
      const recover=document.createElement('button');recover.type='button';recover.textContent=t('ai.receipt');notice.append(message,recover);root.append(notice);
      const body=document.createElement('div');body.className='native-ai-body';root.append(body);
      if(manager&&current.rulingsTarget){const queueRoot=document.createElement('div');current.rulingsTarget.replaceChildren(queueRoot);current.queueRoot=queueRoot;current.queue=mountKeeperAIQueue(queueRoot,client,module,{scope,account,onCount:onQueueCount,onSettings,onReveal,onSession:id=>current?.view?.select(id)});}
      current.view=module.mountAIConversation(body,client,{title:t('ai.title'),review:manager,onReview:id=>{
        if(current?.queueRoot){current.queue.refresh();current.queue.focus();}
        else onReview(id);
      }});
      recover.onclick=async()=>{if(!uncertain)return;recover.disabled=true;try{
        const receipt=await client.aiReceipt(uncertain);if(!live())return;
        if(['committed','rejected'].includes(receipt.status)){uncertain=null;notice.hidden=true;await current.view.refresh();if(receipt.result?.sessionId&&!receipt.result.deleted)await current.view.select(receipt.result.sessionId);}
        else message.textContent=t('ai.pending');
      }catch(error){if(live())message.textContent=error.code||error.message;}finally{if(live())recover.disabled=false;}};
    }catch(error){if(live())root.textContent=error.code||error.message;}
  }
};
