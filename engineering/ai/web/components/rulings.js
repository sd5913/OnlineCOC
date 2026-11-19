import {mountStyle} from './styles.js';
import {guardedClient} from './guard.js';
import {mountMarkdown} from './markdown.js';
/** Host-authorized queue: a whole change set is one decision, never a model confirmation. */
export function mountRulings(target,rawClient,{onChange=()=>{}}={}){
 const shell=document.createElement('div');shell.className='ai-rulings';target.append(shell);const root=shell.attachShadow({mode:'open'});
 mountStyle(root,new URL('./rulings.css',import.meta.url));
 const heading=document.createElement('h3');heading.textContent='AI 修改裁决';const status=document.createElement('p');status.className='rulings-status';status.setAttribute('role','status');const list=document.createElement('div');root.append(heading,status,list);
 let dead=false,busy=false,seq=0;const rows=new Map(),client=guardedClient(rawClient,()=>dead);
 const labels={pending:'等待 KP 裁决',completed:'已执行',rejected:'已拒绝',cancelled:'已取消',blocked:'检查未通过／执行已停止',draft:'尚未检查',executing:'执行中／待核对',unknown:'结果待核对',partial:'部分完成，已停止'};
 function clear(){seq++;for(const row of rows.values())row.markdown.destroy();rows.clear();list.replaceChildren();status.textContent='';}
 function make(item){
  const card=document.createElement('article');card.className='batch-card';const title=document.createElement('h4');title.textContent=item.kind==='configuration'?'配置与规则修改':'运行时修改';const state=document.createElement('p');state.className='ruling-state';state.textContent=labels[item.status]||item.status;
  const summary=document.createElement('div');card.append(title,state,summary);const markdown=mountMarkdown(summary,item.summary,{resolveReferences:t=>client.aiResolve(t)});
  if(item.blockingReason==='CONSULTATION_ONLY'){const reason=document.createElement('p');reason.textContent='该版本引用了仅供咨询的包侧资料，不能发布；请基于宿主资料重新生成配置。';card.append(reason);}
  const details=document.createElement('details'),caption=document.createElement('summary'),pre=document.createElement('pre');caption.textContent='完整修改与检查结果';pre.textContent=JSON.stringify(item.kind==='runtime'?{actions:item.actions,receipts:item.receipts}:{changeSet:item.changeSet,reports:item.reports,receipts:item.receipts,publications:item.publications},null,2);details.append(caption,pre);card.append(details);
  const fields=new Map();if(item.status==='pending'&&item.canDecide){for(const risk of item.risks){const label=document.createElement('label'),input=document.createElement('textarea');label.textContent=risk.question;input.setAttribute('aria-label',risk.question);input.placeholder='填写风险判断后批准';label.append(input);card.append(label);fields.set(risk.id,input);}
   for(const [text,decision] of [['批准并执行','approve'],['拒绝','reject']]){const button=document.createElement('button');button.textContent=text;button.onclick=async()=>{if(dead||busy)return;busy=true;for(const b of list.querySelectorAll('button'))b.disabled=true;status.textContent='正在保存裁决…';try{
    const result=await client.aiCommand('ai.ruling.decide',{rulingId:item.rulingId,digest:item.digest,decision,riskDecisions:Object.fromEntries([...fields].map(([k,v])=>[k,v.value]))});if(result.status!=='committed')throw Error(result.code||result.status);
    status.textContent=labels[result.result.status]||result.result.status;await refresh();onChange(result.result);
   }catch(e){status.textContent=e.code||e.message;}finally{busy=false;if(!dead)for(const b of list.querySelectorAll('button'))b.disabled=false;}};card.append(button);}
  }
  if(item.kind==='runtime'&&['unknown','executing'].includes(item.status)){
   const recover=document.createElement('button');recover.textContent='核对原执行回执';recover.onclick=async()=>{if(dead||busy)return;busy=true;recover.disabled=true;
    try{const result=await client.aiCommand('ai.batch.reconcile',{batchId:item.rulingId.slice(6),digest:item.digest});if(result.status!=='committed')throw Error(result.code||result.status);await refresh();onChange(result.result);}
    catch(e){if(!dead)status.textContent=e.code||e.message;}finally{busy=false;if(!dead)recover.disabled=false;}};card.append(recover);
  }
  return {card,markdown,key:JSON.stringify(item)};
 }
 async function refresh(){if(dead)return;const stamp=++seq;try{const data=await client.aiRulings();if(dead||stamp!==seq)return;const retained=new Set();for(const item of data.items){retained.add(item.rulingId);let row=rows.get(item.rulingId);if(!row||row.key!==JSON.stringify(item)){row?.markdown.destroy();const next=make(item);if(row)row.card.replaceWith(next.card);else list.append(next.card);row=next;rows.set(item.rulingId,row);}}for(const [id,row] of rows)if(!retained.has(id)){row.markdown.destroy();row.card.remove();rows.delete(id);}heading.textContent='AI 修改裁决 · '+data.items.filter(i=>i.status==='pending').length+' 项待处理';if(!data.items.length)status.textContent='暂无 AI 修改';}
  catch(e){if(!dead&&stamp===seq){clear();status.textContent=e.code||e.message;}}
 }
 let identity=JSON.stringify([client.generation,client.connected,client.view?.accountId,client.view?.authorityEpoch]);const unsub=client.subscribe(()=>{const next=JSON.stringify([client.generation,client.connected,client.view?.accountId,client.view?.authorityEpoch]);if(next!==identity){identity=next;clear();}});
 const timer=setInterval(()=>{if(!busy&&!document.hidden)refresh();},2500);refresh();
 return {refresh,destroy(){dead=true;clearInterval(timer);unsub();clear();shell.remove();}};
}
