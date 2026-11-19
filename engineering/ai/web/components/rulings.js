import {mountStyle} from './styles.js';
import {guardedClient} from './guard.js';
import {mountMarkdown} from './markdown.js';
/** Host-authorized queue: a whole change set is one decision, never a model confirmation. */
export function mountRulings(target,rawClient,{compact=false,onOpenSession=null,onKnowledgeRequest=null,onChange=()=>{}}={}){
 const shell=document.createElement('div');shell.className='ai-rulings';target.append(shell);const root=shell.attachShadow({mode:'open'});
 mountStyle(root,new URL('./rulings.css',import.meta.url));
 const heading=document.createElement('h3');heading.textContent='AI 修改裁决';const status=document.createElement('p');status.className='rulings-status';status.setAttribute('role','status');const list=document.createElement('div');root.append(heading,status,list);
 let dead=false,busy=false,seq=0;const rows=new Map(),client=guardedClient(rawClient,()=>dead);
 const labels={accepted:'已接收，方案另行审核',pending:'等待 KP 裁决',completed:'已执行',rejected:'已拒绝',cancelled:'已取消',blocked:'检查未通过／执行已停止',draft:'尚未检查',executing:'执行中／待核对',unknown:'结果待核对',partial:'部分完成，已停止'};
 function dispose(row){row.dialog?.close();row.markdown.destroy();}
 function clear(){seq++;for(const row of rows.values())dispose(row);rows.clear();list.replaceChildren();status.textContent='';}
 function makeDetail(item){
  const card=document.createElement('article');card.className='batch-card';const title=document.createElement('h4');title.textContent=item.kind==='player_request'?'玩家创作／配置申请':item.kind==='knowledge_request'?'玩家资料申请':item.kind==='configuration'?(item.highRisk?'高危配置与规则修改':'配置与规则修改'):'运行时修改';const state=document.createElement('p');state.className='ruling-state';state.textContent=labels[item.status]||item.status;
  const summary=document.createElement('div');card.append(title,state,summary);const markdown=mountMarkdown(summary,item.summary,{resolveReferences:t=>client.aiResolve(t)});
  if(item.blockingReason==='CONSULTATION_ONLY'){const reason=document.createElement('p');reason.textContent='该版本引用了仅供咨询的包侧资料，不能发布；请基于宿主资料重新生成配置。';card.append(reason);}
  const details=document.createElement('details'),caption=document.createElement('summary'),pre=document.createElement('pre');caption.textContent='完整修改与检查结果';pre.textContent=JSON.stringify(item.kind==='runtime'?{actions:item.actions,receipts:item.receipts}:{changeSet:item.changeSet,diff:item.diff,riskTags:item.riskTags,reports:item.reports,receipts:item.receipts,publications:item.publications},null,2);details.append(caption,pre);card.append(details);
  if(item.kind==='player_request'){details.hidden=true;const note=document.createElement('p');note.textContent='接收申请后在 KP 私有会话准备方案；不会向玩家披露新资料，也不会执行修改。生成的修改必须另行人工审核。';card.append(note);if(item.generationError){const error=document.createElement('p');error.textContent='方案生成未启动（'+item.generationError+'），可打开审核会话处理。';card.append(error);}if(!compact&&item.reviewSessionId&&onOpenSession){const open=document.createElement('button');open.textContent='打开审核会话';open.onclick=()=>onOpenSession(item.reviewSessionId);card.append(open);}}
  const fields=new Map();if(item.status==='pending'&&item.canDecide){for(const risk of item.risks){const label=document.createElement('label'),input=document.createElement('textarea');label.textContent=risk.question;input.setAttribute('aria-label',risk.question);input.placeholder='填写风险判断后批准';label.append(input);card.append(label);fields.set(risk.id,input);}
   for(const [text,decision] of [['批准并执行','approve'],['拒绝','reject']]){const button=document.createElement('button');button.textContent=item.kind==='player_request'&&decision==='approve'?'接收并生成方案':item.kind==='knowledge_request'&&decision==='approve'?'选择披露资料':text;if(item.kind==='knowledge_request'&&decision==='approve'&&!onKnowledgeRequest){button.disabled=true;button.dataset.unavailable='true';button.title='宿主需接入披露分面选择器';}button.onclick=async()=>{if(dead||busy)return;busy=true;for(const b of list.querySelectorAll('button'))b.disabled=true;status.textContent='正在保存裁决…';try{
    if(item.kind==='knowledge_request'&&decision==='approve'){if(onKnowledgeRequest){await onKnowledgeRequest(item);await refresh();}return;}
    const result=await client.aiCommand('ai.ruling.decide',{rulingId:item.rulingId,digest:item.digest,decision,...(item.highRisk&&decision==='approve'?{explicitHighRiskDigest:item.digest}:{}),riskDecisions:Object.fromEntries([...fields].map(([k,v])=>[k,v.value]))});if(result.status!=='committed')throw Error(result.code||result.status);
    status.textContent=labels[result.result.status]||result.result.status;await refresh();onChange(result.result);
   }catch(e){status.textContent=e.code||e.message;}finally{busy=false;if(!dead)for(const b of list.querySelectorAll('button'))b.disabled=b.dataset.unavailable==='true';}};card.append(button);}
  }
  if(['runtime','knowledge_request'].includes(item.kind)&&['unknown','executing'].includes(item.status)){
   const recover=document.createElement('button');recover.textContent='核对原执行回执';recover.onclick=async()=>{if(dead||busy)return;busy=true;recover.disabled=true;
    try{const result=await client.aiCommand(item.kind==='runtime'?'ai.batch.reconcile':'ai.knowledge.reconcile',item.kind==='runtime'?{batchId:item.rulingId.slice(6),digest:item.digest}:{rulingId:item.rulingId,digest:item.digest});if(result.status!=='committed')throw Error(result.code||result.status);await refresh();onChange(result.result);}
    catch(e){if(!dead)status.textContent=e.code||e.message;}finally{busy=false;if(!dead)recover.disabled=false;}};card.append(recover);
  }
  return {card,markdown,key:JSON.stringify(item)};
 }
 function make(item){
  const detail=makeDetail(item);if(!compact)return detail;
  const card=document.createElement('article');card.className='ruling-row';
  const time=document.createElement('time');time.textContent=new Date(item.createdAt*1000).toLocaleString();
  const source=document.createElement('span');source.className='ruling-source';source.textContent=(item.initiator||'AI')+' · '+(item.kind==='player_request'?'创作申请':item.kind==='knowledge_request'?'资料申请':item.kind==='configuration'?(item.highRisk?'高危配置':'配置'):'运行时');
  const summary=document.createElement('span');summary.className='ruling-summary';const excerpt=document.createElement('span');excerpt.className='ruling-excerpt';excerpt.textContent=(item.summary||'修改提案').replace(/\s+/g,' ').slice(0,140);summary.append(excerpt);
  const state=document.createElement('small');state.textContent=labels[item.status]||item.status;summary.append(state);
  const actions=document.createElement('div');actions.className='ruling-actions';
  const dialog=document.createElement('dialog');dialog.className='ruling-dialog';dialog.setAttribute('aria-label','AI 修改裁决详情');
  const close=document.createElement('button');close.textContent='关闭详情';close.className='ruling-close';close.onclick=()=>dialog.close();dialog.append(close,detail.card);
  const open=document.createElement('button');open.textContent=item.status==='pending'&&item.canDecide?'查看并裁决':'查看详情';open.onclick=()=>{if(!dead&&!busy&&!dialog.open)dialog.showModal();};actions.append(open);
  if(item.sessionId&&onOpenSession){const chat=document.createElement('button');chat.textContent=item.reviewSessionId?'打开审核会话':'打开对话';chat.onclick=async()=>{try{await onOpenSession(item.reviewSessionId||item.sessionId);}catch(e){if(!dead)status.textContent=e.code||e.message;}};actions.append(chat);}
  card.append(time,source,summary,actions,dialog);return {...detail,card,dialog};
 }
 async function refresh(){if(dead)return;const stamp=++seq;try{const data=await client.aiRulings();if(dead||stamp!==seq)return;const retained=new Set();for(const item of data.items){retained.add(item.rulingId);let row=rows.get(item.rulingId);if(!row||row.key!==JSON.stringify(item)){if(row)dispose(row);const next=make(item);if(row)row.card.replaceWith(next.card);else list.append(next.card);row=next;rows.set(item.rulingId,row);}}for(const [id,row] of rows)if(!retained.has(id)){dispose(row);row.card.remove();rows.delete(id);}heading.textContent='AI 修改裁决 · '+data.items.filter(i=>i.status==='pending').length+' 项待处理';if(!data.items.length)status.textContent='暂无 AI 修改';}
  catch(e){if(!dead&&stamp===seq){clear();status.textContent=e.code||e.message;}}
 }
 let identity=JSON.stringify([client.generation,client.connected,client.view?.accountId,client.view?.authorityEpoch]);const unsub=client.subscribe(()=>{const next=JSON.stringify([client.generation,client.connected,client.view?.accountId,client.view?.authorityEpoch]);if(next!==identity){identity=next;clear();}});
 const timer=setInterval(()=>{if(!busy&&!document.hidden)refresh();},2500);refresh();
 return {refresh,destroy(){dead=true;clearInterval(timer);unsub();clear();shell.remove();}};
}
