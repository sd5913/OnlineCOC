import {t,locale} from './i18n.js';

// The engine remains authoritative; this panel combines its public queues.
export function mountKeeperAIQueue(target,client,module,{scope,account,onCount=()=>{},onSettings=()=>{},onSession=()=>{},onReveal=()=>{}}={}){
  const root=document.createElement('div');root.className='keeper-ai-queue';target.append(root);
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  root.innerHTML='<div class="queue-tools"><button type="button" data-refresh></button><button type="button" data-settings></button><label><input type="checkbox" data-history><span></span></label></div><p class="queue-status" role="status"></p><div data-recovery hidden><span></span><button type="button"></button></div><div class="ai-assistance-list"></div><div class="ai-modifications-list"></div>';
  const find=q=>root.querySelector(q),status=find('.queue-status'),list=find('.ai-assistance-list'),recovery=find('[data-recovery]');
  const rows=new Map(),pendingKey='sv.desktop.aiQueue.'+scope+'.'+account;
  let dead=false,busy=false,reading=false,epoch=0,showHistory=false,tasks=[],rulings=[],uncertain=localStorage.getItem(pendingKey);
  const authority=client.view?.authorityEpoch;
  const authorized=()=>!dead&&client.connected&&client.view?.role==='kp'&&client.view?.accountId===account&&client.view?.authorityEpoch===authority;
  const terminal=new Set(['completed','published','rejected','cancelled']);
  const needsTask=item=>['received','needs_input','blocked','failed','interrupted','stale'].includes(item.status)&&!item.proposalId&&!item.batchId;
  const needsRuling=item=>!terminal.has(item.status);
  const count=()=>onCount(tasks.filter(needsTask).length+rulings.filter(needsRuling).length);
  const label=value=>t((['completed','rejected','partial','unknown'].includes(value)?'queue.':'ai.')+value,{},value);
  find('[data-refresh]').textContent=t('ai.refresh');find('[data-settings]').textContent=t('queue.aiSettings');
  find('[data-history]+span').textContent=t('queue.aiHistory');
  function recoverState(){
    recovery.hidden=!uncertain;recovery.querySelector('span').textContent=t('ai.pending');
    recovery.querySelector('button').textContent=t('ai.receipt');
    for(const b of root.querySelectorAll('[data-write]'))b.disabled=busy||!!uncertain;
  }
  const button=(name,fn,write=false)=>{const b=document.createElement('button');b.type='button';b.textContent=name;if(write)b.dataset.write='';b.onclick=()=>run(fn);return b;};
  async function run(fn){
    if(!authorized()||busy)return;busy=true;recoverState();
    try{await fn();}catch(e){if(!dead)status.textContent=e.code||e.message;}
    finally{busy=false;if(!dead)recoverState();}
  }
  async function command(op,args){
    if(uncertain)throw Error(t('ai.pending'));
    const bytes=crypto.getRandomValues(new Uint8Array(16));const id='queue-'+Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
    uncertain=id;localStorage.setItem(pendingKey,id);recoverState();
    const receipt=await client.aiCommand(op,args,id);
    if(['committed','rejected'].includes(receipt.status)){uncertain=null;localStorage.removeItem(pendingKey);}
    if(receipt.status!=='committed')throw Error(receipt.code||receipt.status);
    status.textContent=t('queue.saved');await refresh();return receipt.result;
  }
  recovery.querySelector('button').onclick=()=>run(async()=>{
    const receipt=await client.aiReceipt(uncertain);
    if(['committed','rejected'].includes(receipt.status)){uncertain=null;localStorage.removeItem(pendingKey);status.textContent=receipt.status==='committed'?t('queue.saved'):receipt.code||t('ui.m093');await refresh();}
    else status.textContent=t('ai.pending');
  });
  async function locate(item){
    const generation=epoch;
    const summaries=(await Promise.all([client.aiSessions(false),client.aiSessions(true)])).flatMap(p=>p.items);
    if(!authorized()||generation!==epoch)return;
    for(const summary of summaries.filter(s=>!item.initiator||s.owner===item.initiator)){
      const session=await client.aiSession(summary.sessionId);
      if(!authorized()||generation!==epoch)return;
      if(session.items.some(i=>i.requestId===item.requestId)){await onSession(summary.sessionId);return;}
    }
    throw Error(t('queue.noSession'));
  }
  function paint(){
    if(dead)return;const retained=new Set();
    for(const item of tasks.filter(i=>showHistory?!needsTask(i)&&!i.proposalId&&!i.batchId:needsTask(i))){
      retained.add(item.requestId);const fingerprint=JSON.stringify([item,showHistory,locale()]);
      const previous=rows.get(item.requestId);if(previous?.fingerprint===fingerprint)continue;
      const card=document.createElement('article');card.className='queue-item ai-assistance';card.dataset.aiRequest=item.requestId;
      card.innerHTML='<small>'+esc(item.initiator||t('queue.sourceUnavailable'))+' · '+esc(new Date(item.createdAt*1000).toLocaleString())+'</small><strong>'+esc(t(needsTask(item)?'queue.aiRequest':'ai.title'))+'</strong><span class="tag">'+esc(label(item.status))+'</span><p class="queue-text">'+esc(item.text||t('queue.sourceUnavailable'))+'</p>';
      let markdown=null;if(item.response){const details=document.createElement('details'),summary=document.createElement('summary'),body=document.createElement('div');summary.textContent=t('queue.aiReply');details.append(summary,body);card.append(details);markdown=module.mountMarkdown(body,item.response,{resolveReferences:tokens=>client.aiResolve(tokens)});}
      if(item.error){const p=document.createElement('p');p.className='notice error';p.textContent=typeof item.error==='string'?item.error:JSON.stringify(item.error);card.append(p);}
      const actions=document.createElement('div');actions.className='actions';card.append(actions);
      actions.append(button(t('queue.openSession'),()=>locate(item)));
      if(item.status==='received')actions.append(button(t('ai.dispatch'),()=>command('ai.request.dispatch',{requestId:item.requestId}),true));
      if(!terminal.has(item.status)){
        actions.append(button(t('queue.disclose'),()=>onReveal(item.initiator)));
        actions.append(button(t('ai.cancel'),()=>command('ai.request.cancel',{requestId:item.requestId}),true));
      }
      if(previous){previous.markdown?.destroy();previous.card.replaceWith(card);}else list.append(card);rows.set(item.requestId,{card,fingerprint,markdown});
    }
    for(const [id,row] of rows)if(!retained.has(id)){row.markdown?.destroy();row.card.remove();rows.delete(id);}
    recoverState();count();
  }
  async function refresh(){
    if(!authorized()||reading)return;reading=true;const current=epoch;
    try{
      const collected=[],cursors=new Set();let before;
      do{const page=await client.aiTasks({limit:100,before});if(dead||current!==epoch)return;collected.push(...page.items);before=page.nextBefore;if(before&&cursors.has(before))throw Error('CURSOR_INVALID');cursors.add(before);}while(before);
      tasks=collected;paint();
    }catch(e){if(!dead&&current===epoch){tasks=[];paint();status.textContent=e.code||e.message;}}
    finally{reading=false;}
  }
  const facade=new Proxy(client,{get(object,key){
    if(key==='aiRulings')return async()=>{if(!authorized())return {items:[]};const generation=epoch;let data;try{data=await client.aiRulings();}catch(e){if(!dead){rulings=[];count();}throw e;}if(!authorized()||generation!==epoch)return {items:[]};rulings=data.items;count();return {items:rulings.filter(i=>showHistory?!needsRuling(i):needsRuling(i))};};
    const value=object[key];return typeof value==='function'?value.bind(object):value;
  }});
  const modifications=module.mountRulings(find('.ai-modifications-list'),facade,{onChange:()=>{refresh();}});
  find('[data-refresh]').onclick=()=>run(async()=>{await refresh();await modifications.refresh();});
  find('[data-settings]').onclick=onSettings;
  find('[data-history]').onchange=event=>{showHistory=event.target.checked;paint();modifications.refresh();};
  let identity=JSON.stringify([client.connected,client.view?.accountId,client.view?.authorityEpoch,client.view?.role]);
  const unsubscribe=client.subscribe(()=>{const next=JSON.stringify([client.connected,client.view?.accountId,client.view?.authorityEpoch,client.view?.role]);if(next!==identity){identity=next;epoch++;tasks=[];rulings=[];paint();}});
  const timer=setInterval(()=>{if(!busy&&!document.hidden)refresh();},4000);
  refresh();recoverState();
  return {relocalize(){find('[data-refresh]').textContent=t('ai.refresh');find('[data-settings]').textContent=t('queue.aiSettings');find('[data-history]+span').textContent=t('queue.aiHistory');paint();},remember(id){uncertain=id;localStorage.setItem(pendingKey,id);recoverState();},refresh:async()=>{await refresh();await modifications.refresh();},focus(){root.tabIndex=-1;root.focus({preventScroll:true});root.scrollIntoView({block:'nearest'});},destroy(){dead=true;epoch++;clearInterval(timer);unsubscribe();modifications.destroy();for(const row of rows.values())row.markdown?.destroy();rows.clear();root.remove();onCount(0);}};
}

