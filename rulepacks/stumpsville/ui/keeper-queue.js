import {mountPackageRulings,rulingIsArchived} from './keeper-rulings.js';
import {rulingCard} from './ruling-card.js';
import {t,locale} from './i18n.js';
import {definiteAIRejection} from './ai-recovery.js';

// The engine remains authoritative; this panel combines its public queues.
export function mountKeeperAIQueue(target,client,module,{scope,account,archived=false,onCount=()=>{},onSettings=()=>{},onSession=()=>{},onReveal=()=>{},onKnowledgeRequest=()=>{},onOpenSource=()=>{},onNotice=()=>{},readBundle,renderReference,timeline=null,statusTarget=null}={}){
  const root=document.createElement('div');root.className='keeper-ai-queue';target.append(root);
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  root.innerHTML='<div class="queue-tools"><button type="button" data-refresh></button><button type="button" data-settings></button><label><input type="checkbox" data-history><span></span></label></div><div class="queue-status-line"><p class="queue-status" role="status"></p><div data-recovery hidden><span role="status"></span><button type="button"></button></div></div><div class="ai-assistance-list"></div><div class="ai-modifications-list"></div>';
  const find=q=>root.querySelector(q),status=find('.queue-status'),list=find('.ai-assistance-list'),recovery=find('[data-recovery]'),statusLine=find('.queue-status-line');
  function setStatusTarget(target){(target||root).prepend(statusLine);}
  setStatusTarget(statusTarget);
  let detail=null,detailMarkdown=null,historyDialog=null;
  function closeDetail(){detailMarkdown?.destroy();detailMarkdown=null;detail?.remove();detail=null;}
  function showDetail(item){
    closeDetail();detail=document.createElement('dialog');detail.className='ai-request-detail';
    detail.innerHTML='<header><h2>'+esc(t('queue.aiRequest'))+'</h2><button type="button" data-close>'+esc(t('ui.m058'))+'</button></header><p>'+esc(item.initiator)+' · '+esc(new Date(item.createdAt*1000).toLocaleString())+' · '+esc(label(item.status))+'</p><p class="full-request">'+esc(item.text||'')+'</p>';
    if(item.sourceState==='stale'||item.status==='stale'){detail.classList.add('ruling-stale');detail.title=item.sourceNotice||'依赖资料已过时，正文保留原申请。';}
    if(item.error){const error=document.createElement('p');error.className='notice error';error.textContent=typeof item.error==='string'?item.error:JSON.stringify(item.error);detail.append(error);}
    if(item.response){const replies=document.createElement('details'),summary=document.createElement('summary'),body=document.createElement('div');summary.textContent=t('queue.aiReply');replies.append(summary,body);detail.append(replies);detailMarkdown=module.mountMarkdown(body,item.response,{resolveReferences:tokens=>client.aiResolve(tokens),renderReference,audience:'administrator'});}
    if(item.sessionId)detail.append(button(t('queue.openSession'),async()=>{closeDetail();await locate(item);}));
    if(item.resolution?.targetId)detail.append(button('查看完成行动',()=>openSource({rulingId:item.resolution.targetId})));
    if(item.archiveReason){const p=document.createElement('p');p.className='notice';p.textContent='归档说明：'+item.archiveReason;detail.append(p);}
    if(item.supersededBy)detail.append(button('查看后续方案',()=>openSource(item.supersededBy.startsWith('request:')?{requestId:item.supersededBy.slice(8)}:{rulingId:item.supersededBy})));
    if(item.canArchive||item.canRestore)detail.append(button(item.canRestore?'恢复到裁决队列':'归档此项',()=>archiveTask(item,!item.canRestore),true));
    if(!item.archived&&!terminal.has(item.status))detail.append(button(t('ai.cancel'),()=>command('ai.request.cancel',{requestId:item.requestId}),true));
    const opened=detail;
    module.appendDebugTools?.(detail,client,{requestId:item.requestId},{valid:()=>authorized()&&detail===opened});
    if(item.reviewSource)module.appendReviewSource?.(detail,item.reviewSource,{onOpenSource,onOpenSession:onSession});
    detail.querySelector('[data-close]').onclick=closeDetail;detail.addEventListener('close',closeDetail,{once:true});document.body.append(detail);detail.showModal();
  }
  async function openSource(source){
    if(!authorized())throw Error('当前账户或房间权限已变化，请刷新');
    const stamp=epoch;
    if(source.rulingId){
      const item=client.aiRuling ? await client.aiRuling(source.rulingId) : (await client.aiRulings()).items.find(row=>row.rulingId===source.rulingId);
      if(!authorized()||stamp!==epoch)throw Error('当前账户或房间权限已变化，请刷新');
      if(!item)throw Error('原裁决不存在或当前不可读');
      closeDetail();detail=document.createElement('dialog');detail.className='ai-request-detail';
      detail.innerHTML='<header><h2>原 AI 裁决</h2><button type="button" data-close>'+esc(t('ui.m058'))+'</button></header><p>'+esc(item.initiator)+' · '+esc(label(item.status))+'</p>';
      const body=document.createElement('div');detail.append(body);detailMarkdown=module.mountMarkdown(body,item.summary||'',{resolveReferences:tokens=>client.aiResolve(tokens),renderReference,audience:'administrator'});
      const extra=document.createElement('details'),caption=document.createElement('summary'),pre=document.createElement('pre');caption.textContent='当前裁决记录';pre.textContent=JSON.stringify(item,null,2);extra.append(caption,pre);detail.append(extra);
      const opened=detail;module.appendDebugTools?.(detail,client,{rulingId:item.rulingId},{valid:()=>authorized()&&detail===opened});
      if(item.sessionId)detail.append(button('查看原对话',async()=>{closeDetail();await onSession(item.sessionId);}));
      detail.querySelector('[data-close]').onclick=closeDetail;detail.addEventListener('close',closeDetail,{once:true});document.body.append(detail);detail.showModal();
      return;
    }
    if(source.requestId){
      const cursors=new Set();let before,item;
      do{const page=await client.aiTasks({limit:100,before});if(!authorized()||stamp!==epoch)throw Error('当前账户或房间权限已变化，请刷新');item=page.items.find(row=>row.requestId===source.requestId);before=page.nextBefore;if(before&&cursors.has(before))throw Error('CURSOR_INVALID');cursors.add(before);}while(!item&&before);
      if(!item)throw Error('原请求不存在或当前不可读');
      showDetail(item);return;
    }
    throw Error('来源缺少有效定位');
  }
  const rows=new Map(),pendingKey='sv.desktop.aiQueue.'+scope+'.'+account;
  let activeRulings=null;
  let dead=false,busy=false,reading=false,readFailed=false,epoch=0,showHistory=archived,historyBeforeDialog=false,tasks=[],rulings=[],uncertain=localStorage.getItem(pendingKey);
  const authority=client.view?.authorityEpoch;
  const authorized=()=>!dead&&client.connected&&client.view?.role==='kp'&&client.view?.accountId===account&&client.view?.authorityEpoch===authority;
  const terminal=new Set(['completed','published','rejected','cancelled','accepted']);
  const queuedHistory=item=>item.archived===true||['history','superseded','archived'].includes(item.queueStatus);
  const needsTask=item=>!queuedHistory(item)&&!item.playerRequest&&['received','needs_input','blocked','failed','interrupted','stale'].includes(item.status)&&!item.proposalId&&!item.batchId;
  const archivedTask=item=>!item.playerRequest&&!item.proposalId&&!item.batchId&&(queuedHistory(item)||terminal.has(item.status)||item.status==='review_ready');
  const needsRuling=item=>!rulingIsArchived(item);
  const count=()=>onCount(tasks.filter(needsTask).length+(activeRulings??rulings.filter(needsRuling).length));
  const label=value=>t((['completed','rejected','partial','unknown'].includes(value)?'queue.':'ai.')+value,{},value);
  find('[data-refresh]').textContent=t('ai.refresh');find('[data-settings]').textContent=t('queue.aiSettings');
  find('[data-history]+span').textContent=t('queue.aiHistory');
  function recoverState(){
    uncertain=localStorage.getItem(pendingKey);
    recovery.hidden=!uncertain;status.hidden=!!uncertain;recovery.querySelector('span').textContent=t('ai.pending');recovery.querySelector('span').title=t('ai.pending');
    recovery.querySelector('button').textContent=t('ai.receipt');
    for(const b of [...root.querySelectorAll('[data-write]'),...[...rows.values()].flatMap(r=>[...r.card.querySelectorAll('[data-write]')])])b.disabled=busy||!!uncertain;
  }
  const button=(name,fn,write=false)=>{const b=document.createElement('button');b.type='button';b.textContent=name;if(write)b.dataset.write='';b.onclick=()=>run(fn);return b;};
  async function run(fn){
    if(!authorized()||busy)return;busy=true;recoverState();
    try{await fn();}catch(e){if(authorized()){status.textContent=e.message||e.code;onNotice({title:'AI 申请处理',status:e.aiOutcome||'failed',reason:e.message||e.code,locator:{commandRequestId:e.aiRequestId||e.requestId,traceId:e.traceId,operation:e.operation,httpStatus:e.status||e.httpStatus}});}}
    finally{busy=false;if(!dead)recoverState();}
  }
  async function command(op,args){
    closeDetail();
    if(uncertain)throw Object.assign(Error(t('ai.pending')),{aiRequestId:uncertain,aiOutcome:'unknown'});
    const bytes=crypto.getRandomValues(new Uint8Array(16));const id='queue-'+Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
    uncertain=id;localStorage.setItem(pendingKey,id);recoverState();
    let receipt;
    try{receipt=await client.aiCommand(op,args,id);}
    catch(error){error.aiRequestId=id;error.aiOutcome=definiteAIRejection(error)?'failed':'unknown';if(definiteAIRejection(error)){uncertain=null;localStorage.removeItem(pendingKey);}throw error;}
    if(['committed','rejected'].includes(receipt.status)){uncertain=null;localStorage.removeItem(pendingKey);}
    if(receipt.status!=='committed')throw Object.assign(Error(receipt.code||receipt.status),{aiRequestId:id,aiOutcome:receipt.status==='rejected'?'failed':'unknown'});
    status.textContent=t('queue.saved');if(args.requestId||args.source?.kind==='request')onNotice({title:'AI 申请处理',status:op==='ai.request.cancel'?'cancelled':'completed',reason:op==='ai.request.cancel'?'KP 已取消该请求':'已转交 AI，方案须另行审核',locator:{requestId:args.requestId||args.source?.requestId,commandRequestId:id}});await refresh();return receipt.result;
  }
  recovery.querySelector('button').onclick=()=>run(async()=>{
    const id=uncertain,receipt=await client.aiReceipt(id);
    if(authorized())onNotice({title:'原裁决回执',status:receipt.status==='committed'?(receipt.result?.status||'completed'):receipt.status==='rejected'?'rejected':'unknown',reason:receipt.result?.blockingReason||receipt.result?.generationError||receipt.code|| (receipt.status==='committed'?'已核对原执行结果':'原执行结果尚未确认'),locator:{commandRequestId:id,rulingId:receipt.result?.rulingId}});
    if(['committed','rejected'].includes(receipt.status)){uncertain=null;localStorage.removeItem(pendingKey);status.textContent=receipt.status==='committed'?t('queue.saved'):receipt.code||t('ui.m093');await refresh();}
    else status.textContent=t('ai.pending');
  });
  async function locate(item){
    if(!authorized())return;
    if(item.sessionId){await onSession(item.sessionId);return;}
    throw Error(t('queue.noSession'));
  }
  async function archiveTask(item,archived){
    const value=await command('ai.queue.archive',{targetId:item.queueTargetId,digest:item.queueDigest,archived,...(archived?{reason:'KP 将无需继续处理的中间请求归档'}:{})});
    onNotice({title:'AI 申请处理',status:'completed',reason:archived?'已归档，可在已归档标签查看或恢复':value.supersededBy?'已取消手动归档，原请求仍由后续方案替代':needsTask({...item,...value})?'已恢复到裁决队列':'已取消手动归档，可在已归档标签查看',locator:{requestId:item.requestId,sessionId:item.sessionId}});
  }
  function paint(){
    if(dead)return;const retained=new Set();
    for(const item of [...tasks].sort((a,b)=>a.createdAt-b.createdAt||a.requestId.localeCompare(b.requestId)).filter(i=>!i.playerRequest).filter(i=>showHistory?archivedTask(i):needsTask(i))){
      retained.add(item.requestId);const fingerprint=JSON.stringify([item,showHistory,locale()]);
      const previous=rows.get(item.requestId);if(previous?.fingerprint===fingerprint)continue;
      const card=document.createElement('article');card.className='queue-item ruling-card ai-assistance';card.classList.toggle('ruling-stale',item.sourceState==='stale'||item.status==='stale');card.dataset.aiRequest=item.requestId;card.dataset.queueTime=item.createdAt||0;card.dataset.queueKey='request:'+item.requestId;
      const markup=document.createElement('template');markup.innerHTML=rulingCard({time:new Date(item.createdAt*1000).toLocaleTimeString(locale(),{hour:'2-digit',minute:'2-digit'}),type:'AI 申请',source:item.initiator||t('queue.sourceUnavailable'),summary:'',actions:''});card.append(...markup.content.firstElementChild.childNodes);
      const summary=button(label(item.status)+' · '+(item.text||t('queue.sourceUnavailable')),()=>showDetail(item));summary.className='queue-summary quiet';card.querySelector('.ruling-card-summary').append(summary);
      if(item.sourceState==='stale'||item.status==='stale')card.title=item.sourceNotice||'依赖资料已过时，正文保留原申请。';
      if(item.resolution||item.supersededBy||item.archiveReason){const info=document.createElement('p');info.className='notice';info.textContent=item.resolution?'需求已完成，相关中间项已归档':item.supersededBy?'已由后续方案替代':item.archiveReason;card.querySelector('.ruling-card-summary').append(info);}
      const actions=card.querySelector('.ruling-card-actions');

      actions.append(button('转 AI 处理',async()=>{const result=await command('ai.review.create',{source:{kind:'request',requestId:item.requestId}});if(result.sessionId)await onSession(result.sessionId);},true));
      if(!showHistory&&!terminal.has(item.status)){
        actions.append(button(t('queue.disclose'),()=>onReveal(item.recipientAccountId)));
        actions.append(item.canArchive?button('归档此项',()=>archiveTask(item,true),true):button(t('ai.cancel'),()=>command('ai.request.cancel',{requestId:item.requestId}),true));
      }
      if(showHistory&&item.canRestore)actions.append(button('恢复到裁决队列',()=>archiveTask(item,false),true));
      if(previous){previous.card.replaceWith(card);}else list.append(card);rows.set(item.requestId,{card,fingerprint});
    }
    for(const [id,row] of rows)if(!retained.has(id)){row.card.remove();rows.delete(id);}
    if(timeline&&!historyDialog)timeline.set('tasks',[...rows.values()].map(r=>r.card));else for(const row of [...rows.values()].sort((a,b)=>Number(a.card.dataset.queueTime)-Number(b.card.dataset.queueTime)||a.card.dataset.queueKey.localeCompare(b.card.dataset.queueKey)))list.append(row.card);
    recoverState();count();
  }
  async function refresh(){
    if(!authorized()||reading)return;reading=true;const current=epoch;
    try{
      const collected=[],cursors=new Set();let before;
      do{const page=await client.aiTasks({limit:100,before});if(dead||current!==epoch)return;collected.push(...page.items);before=page.nextBefore;if(before&&cursors.has(before))throw Error('CURSOR_INVALID');cursors.add(before);}while(before);
      tasks=collected;if(readFailed){status.textContent='';readFailed=false;}paint();
    }catch(e){if(!dead&&current===epoch){tasks=[];readFailed=true;paint();status.textContent=e.message||e.code;}}
    finally{reading=false;}
  }
  const facade=new Proxy(client,{get(object,key){
    if(key==='aiRulings')return async options=>{if(!authorized())return {items:[]};const generation=epoch;let data;try{data=await client.aiRulings(options);}catch(e){if(!dead){rulings=[];activeRulings=null;count();}throw e;}if(!authorized()||generation!==epoch)return {items:[]};rulings=data.items;activeRulings=data.activeCount??null;count();return data;};
    const value=object[key];return typeof value==='function'?value.bind(object):value;
  }});
  const modifications=mountPackageRulings(find('.ai-modifications-list'),facade,module,{command,authorized,onNotice,onSession,onOpenSource,onKnowledgeRequest,readBundle,renderReference,timeline,onChange:item=>{refresh();if(item.kind==='player_request'&&item.status==='accepted'&&item.reviewSessionId)Promise.resolve(onSession(item.reviewSessionId)).catch(error=>onNotice({title:'打开审核会话',status:'failed',reason:error.message,locator:{rulingId:item.rulingId}}));}});
  function closeHistory(){if(!historyDialog)return;target.append(root);historyDialog.remove();historyDialog=null;showHistory=historyBeforeDialog;modifications.setTimeline(timeline);modifications.setHistory(showHistory);paint();modifications.refresh();}
  function openHistory(content=''){
    closeHistory();timeline?.remove('tasks');modifications.setTimeline(null);historyBeforeDialog=showHistory;showHistory=true;historyDialog=document.createElement('dialog');historyDialog.className='ai-request-detail ruling-history';
    historyDialog.innerHTML='<header><h2>处理记录</h2><button type="button" data-close-history>关闭</button></header><h3>裁决与行动记录</h3>'+content+'<h3>AI 处理记录</h3>';
    historyDialog.append(root);historyDialog.querySelector('[data-close-history]').onclick=closeHistory;historyDialog.addEventListener('cancel',e=>{e.preventDefault();closeHistory();});document.body.append(historyDialog);historyDialog.showModal();modifications.setHistory(true);paint();modifications.refresh();
  }
  function setArchived(value){if(showHistory===!!value)return;closeHistory();showHistory=!!value;find('[data-history]').checked=showHistory;modifications.setHistory(showHistory);paint();modifications.refresh();}
  modifications.setHistory(showHistory);
  find('[data-refresh]').onclick=()=>run(async()=>{await refresh();await modifications.refresh();});
  find('[data-settings]').onclick=onSettings;
  find('[data-history]').onchange=event=>{showHistory=event.target.checked;modifications.setHistory(showHistory);paint();modifications.refresh();};
  let identity=JSON.stringify([client.connected,client.view?.accountId,client.view?.authorityEpoch,client.view?.role]);
  const unsubscribe=client.subscribe(()=>{const next=JSON.stringify([client.connected,client.view?.accountId,client.view?.authorityEpoch,client.view?.role]);if(next!==identity){identity=next;epoch++;closeHistory();closeDetail();tasks=[];rulings=[];activeRulings=null;paint();}});
  const timer=setInterval(()=>{if(!busy&&!document.hidden&&root.isConnected)refresh();},4000);
  refresh();recoverState();
  return {setStatusTarget,setTimeline(value){timeline?.remove('tasks');timeline=value;modifications.setTimeline(historyDialog?null:value);paint();},setArchived,openHistory,openSource,relocalize(){find('[data-refresh]').textContent=t('ai.refresh');find('[data-settings]').textContent=t('queue.aiSettings');find('[data-history]+span').textContent=t('queue.aiHistory');paint();},remember(id){uncertain=id;localStorage.setItem(pendingKey,id);recoverState();},refresh:async()=>{await refresh();await modifications.refresh();},focus(){root.tabIndex=-1;root.focus({preventScroll:true});root.scrollIntoView({block:'nearest'});},destroy(){closeHistory();dead=true;epoch++;closeDetail();clearInterval(timer);unsubscribe();modifications.destroy();timeline?.remove('tasks');rows.clear();statusLine.remove();root.remove();onCount(0);}};
}

