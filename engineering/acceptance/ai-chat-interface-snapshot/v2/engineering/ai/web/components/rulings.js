import {appendDebugTools} from './debug.js';
import {mountStyle} from './styles.js';
import {guardedClient} from './guard.js';
import {mountMarkdown} from './markdown.js';
function appendBatchDetails(target,item){
 const names={passed:'预检通过',blocked:'预检阻塞',unsupported:'不支持此事务组合',runtime_required:'执行时检查',committed:'已提交',rolled_back:'已撤销暂存修改',failed:'失败',not_executed:'未执行',unknown:'结果待核对',pending:'结果待核对',rejected:'被拒绝'};
 const negative=r=>r===false||!!r&&typeof r==='object'&&(r.passed===false||['blocked','failure','failed'].includes(r.outcome)||['public','result'].some(k=>k in r&&negative(r[k])));
 const info=document.createElement('p');info.className='batch-result-summary';
 if(item.execution){const e=item.execution;info.textContent=e.status==='unknown'?'结果尚未确定，请核对原回执，不要重新执行。':`提交 ${e.committedCount||0} 项 · 撤销 ${e.rolledBackCount||0} 项 · 失败 ${e.failedCount||0} 项 · 未执行 ${e.notExecutedCount||0} 项`;}
 else if(item.status==='partial'){const n=(item.receipts||[]).filter(r=>r.receipt?.status==='committed').length;info.textContent=n?`旧批次实际提交 ${n} 项；其余结果见下方回执。`:'旧批次没有成功提交项；无法从旧记录证明事务回滚。';}
 else info.textContent='预检不会执行修改；批准时重新核对当前条件。';
 target.append(info);const list=document.createElement('ol');list.className='batch-steps';
 for(const [i,a] of (item.actions||[]).entries()){
  const row=document.createElement('li'),title=document.createElement('strong');title.textContent=`第 ${i+1} 步 · ${a.op}`;row.append(title);
  const pre=item.preflight?.items?.find(r=>r.index===i),done=item.execution?.items?.find(r=>r.index===i);
  for(const [label,value] of [['预检',pre],['执行',done]]){if(!value)continue;const line=document.createElement('p');line.textContent=label+'：'+(names[value.status]||value.status)+(value.ruleCode||value.code?' · '+(value.ruleCode||value.code):'')+(value.reason?' · '+value.reason:'')+(value.path?'（'+value.path+'）':'');row.append(line);if(value.result!==undefined){const result=document.createElement('pre');result.textContent=(negative(value.result)?'业务结果未达成；不会自动重试。\n':'')+JSON.stringify(value.result,null,2);row.append(result);}}
  if(!done&&item.receipts?.[i]){const r=item.receipts[i].receipt||item.receipts[i],line=document.createElement('p');line.textContent='旧回执：'+(names[r.status]||r.status)+(r.code?' · '+r.code:'');row.append(line);}
  const args=document.createElement('details'),caption=document.createElement('summary'),value=document.createElement('pre');caption.textContent='查看该步参数';value.textContent=JSON.stringify(a.args,null,2);args.append(caption,value);row.append(args);list.append(row);
 }
 target.append(list);
}
/** Host-authorized queue: a whole change set is one decision, never a model confirmation. */
export function mountRulings(target,rawClient,{compact=false,onOpenSession=null,onOpenSource=null,onKnowledgeRequest=null,onChange=()=>{}}={}){
 const shell=document.createElement('div');shell.className='ai-rulings';target.append(shell);const root=shell.attachShadow({mode:'open'});
 mountStyle(root,new URL('./rulings.css',import.meta.url));
 const heading=document.createElement('h3');heading.textContent='AI 修改裁决';const status=document.createElement('p');status.className='rulings-status';status.setAttribute('role','status');const list=document.createElement('div');root.append(heading,status,list);
 let dead=false,busy=false,seq=0;const rows=new Map(),client=guardedClient(rawClient,()=>dead);
 const labels={accepted:'已接收，方案另行审核',pending:'等待 KP 裁决',completed:'已执行',rejected:'已拒绝',cancelled:'已取消',blocked:'预检未通过',failed:'执行失败，未提交修改',rolled_back:'批次失败，暂存修改已撤销',draft:'尚未检查',executing:'执行中／待核对',unknown:'结果待核对',partial:'旧批次未全部完成，请核对逐项记录'};
 function dispose(row){row.dialog?.close();row.markdown.destroy();}
 function clear(){seq++;for(const row of rows.values())dispose(row);rows.clear();list.replaceChildren();status.textContent='';}
 function makeDetail(item){
  const card=document.createElement('article');card.className='batch-card';const title=document.createElement('h4');title.textContent=item.kind==='player_request'?'玩家创作／配置申请':item.kind==='knowledge_request'?'玩家资料申请':item.kind==='configuration'?(item.highRisk?'高危配置与规则修改':'配置与规则修改'):'运行时修改';const state=document.createElement('p');state.className='ruling-state';state.textContent=item.kind==='runtime'&&item.status==='completed'?'指令已提交':labels[item.status]||item.status;
  const summary=document.createElement('div');card.append(title,state,summary);const markdown=mountMarkdown(summary,item.summary,{resolveReferences:t=>client.aiResolve(t)});
  if(item.sourceNotice){const notice=document.createElement('p');notice.className='history-source-notice';notice.textContent=item.sourceNotice;card.append(notice);}
  if(item.queueStatus==='superseded'||item.queueStatus==='archived'){const note=document.createElement('p');note.textContent=item.queueStatus==='superseded'?'已由后继方案替代，原内容与回执保留。':'已归档：'+(item.archiveReason||'');card.append(note);}
  if(item.canArchive||item.canRestore){const reason=document.createElement('textarea');reason.setAttribute('aria-label','归档理由');reason.placeholder='说明为何归档这条旧申请';reason.maxLength=500;reason.hidden=!!item.archived;const organize=document.createElement('button');organize.textContent=item.archived?'恢复记录':'归档记录';organize.onclick=async()=>{if(dead||busy)return;if(!item.archived&&!reason.value.trim()){status.textContent='请填写归档理由';reason.focus();return;}busy=true;organize.disabled=true;try{const result=await client.aiCommand('ai.queue.archive',{targetId:item.queueTargetId,digest:item.queueDigest,archived:!item.archived,...(!item.archived?{reason:reason.value.trim()}:{})});if(result.status!=='committed')throw Error(result.code||result.status);await refresh();onChange(result.result);}catch(e){if(!dead)status.textContent=e.code||e.message;}finally{busy=false;if(!dead)organize.disabled=false;}};card.append(reason,organize);}
  if(item.blockingReason==='CONSULTATION_ONLY'){const reason=document.createElement('p');reason.textContent='该版本引用了仅供咨询的包侧资料，不能发布；请基于宿主资料重新生成配置。';card.append(reason);}
  if(item.cAssessment){const assessment=document.createElement('section'),heading=document.createElement('h4'),note=document.createElement('p');heading.textContent='C 类游戏性评估 · 依据版本 '+item.cAssessment.basisRevision;note.textContent=item.cAssessment.stale?'评估依据已更新，请重新检测后裁决。':item.cAssessment.requiresAcceptance?'以下是评估结果与未覆盖范围。采纳会记录你的决定并尝试发布，保留原始检测结果。':'声明场景的评估已完成；结果不保证所有游戏情境。';assessment.append(heading,note);for(const f of item.cAssessment.findings||[]){const p=document.createElement('p');p.textContent=f.code+'：'+f.message+(f.path?'（'+f.path+'）':'');assessment.append(p);}for(const limit of item.cAssessment.limitations||[]){const p=document.createElement('small');p.textContent=limit;assessment.append(p,document.createElement('br'));}card.append(assessment);if(item.cAssessment.stale&&item.canRevalidate){const retry=document.createElement('button');retry.textContent='按当前依据重新检测';retry.onclick=async()=>{if(busy||dead)return;busy=true;retry.disabled=true;try{const r=await client.aiCommand('ai.proposal.validate',{proposalId:item.rulingId.slice(9),revision:item.revision});if(r.status!=='committed')throw Error(r.code||r.status);await refresh();}catch(e){status.textContent=e.code||e.message;}finally{busy=false;retry.disabled=false;}};card.append(retry);}}
  if(item.kind==='runtime')appendBatchDetails(card,item);
  const details=document.createElement('details'),caption=document.createElement('summary'),pre=document.createElement('pre');caption.textContent='完整修改与检查结果';pre.textContent=JSON.stringify(item.kind==='runtime'?{actions:item.actions,preflight:item.preflight,execution:item.execution,receipts:item.receipts}:{changeSet:item.changeSet,diff:item.diff,riskTags:item.riskTags,reports:item.reports,receipts:item.receipts,publications:item.publications},null,2);details.append(caption,pre);card.append(details);
  if(item.kind==='player_request'){details.hidden=true;const note=document.createElement('p');note.textContent='接收申请后在 KP 私有会话准备方案；不会向玩家披露新资料，也不会执行修改。生成的修改必须另行人工审核。';card.append(note);if(item.generationError){const error=document.createElement('p');error.textContent='方案生成未启动（'+item.generationError+'），可打开审核会话处理。';card.append(error);}if(!compact&&item.reviewSessionId&&onOpenSession){const open=document.createElement('button');open.textContent='打开审核会话';open.onclick=()=>onOpenSession(item.reviewSessionId);card.append(open);}}
  if(item.kind==='runtime'){for(const [index,action] of (item.actions||[]).entries()){if(action.op!=='notification.send')continue;const note=document.createElement('p');note.className='notification-plan';const source=action.args.sourceActionIndex;note.textContent='通知步骤 '+(index+1)+'：'+action.args.recipientAccountIds.join('、')+'；绑定第 '+(source+1)+' 步 '+(item.actions[source]?.op||'无效动作')+'。仅原动作成功且流程完成后投递。消息：'+action.args.text;card.append(note);}}
  if(item.status==='pending'&&item.canDecide){for(const risk of item.risks){const label=document.createElement('p');label.textContent=risk.question.replace('填写接受理由','确认是否采用');card.append(label);}const note=document.createElement('textarea');note.setAttribute('aria-label','裁决备注（可选）');note.placeholder='裁决备注（可选）';note.maxLength=800;card.append(note);
   for(const [text,decision] of [['批准并执行','approve'],['拒绝','reject']]){const button=document.createElement('button');button.textContent=item.kind==='player_request'&&decision==='approve'?'接收并生成方案':item.kind==='knowledge_request'&&decision==='approve'?'选择披露资料':text;if(item.kind==='knowledge_request'&&decision==='approve'&&!onKnowledgeRequest){button.disabled=true;button.dataset.unavailable='true';button.title='宿主需接入披露分面选择器';}button.onclick=async()=>{if(dead||busy)return;busy=true;for(const b of list.querySelectorAll('button'))b.disabled=true;status.textContent='正在保存裁决…';try{
    if(item.kind==='knowledge_request'&&decision==='approve'){if(onKnowledgeRequest){await onKnowledgeRequest(item);await refresh();}return;}
    const adopting=decision==='approve'&&item.cAssessment?.requiresAcceptance;const cReview=adopting?Object.fromEntries(['basisRevision','basisDigest','reportDigest'].map(k=>[k,item.cAssessment[k]])):null;
    const result=await client.aiCommand('ai.ruling.decide',{rulingId:item.rulingId,digest:item.digest,decision,...(item.highRisk&&decision==='approve'?{explicitHighRiskDigest:item.digest}:{}),...(cReview?{cReview}:{}),riskDecisions:decision==='approve'?Object.fromEntries((item.risks||[]).map(r=>[r.id,(adopting?'KP 点击“采纳评估并发布”':'KP 点击“批准并执行”')+'，确认采用本次所列风险。'+(note.value.trim()?' 备注：'+note.value.trim():'（未填写备注）')])):{}});if(result.status!=='committed')throw Error(result.code||result.status);
    status.textContent=labels[result.result.status]||result.result.status;await refresh();onChange(result.result);
   }catch(e){status.textContent=e.code||e.message;}finally{busy=false;if(!dead)for(const b of list.querySelectorAll('button'))b.disabled=b.dataset.unavailable==='true';}};if(decision==='approve'&&item.cAssessment?.requiresAcceptance)button.textContent='采纳评估并发布';card.append(button);}
  }
  if(['runtime','knowledge_request'].includes(item.kind)&&['unknown','executing'].includes(item.status)){
   const recover=document.createElement('button');recover.textContent='核对原执行回执';recover.onclick=async()=>{if(dead||busy)return;busy=true;recover.disabled=true;
    try{const result=await client.aiCommand(item.kind==='runtime'?'ai.batch.reconcile':'ai.knowledge.reconcile',item.kind==='runtime'?{batchId:item.rulingId.slice(6),digest:item.digest}:{rulingId:item.rulingId,digest:item.digest});if(result.status!=='committed')throw Error(result.code||result.status);await refresh();onChange(result.result);}
    catch(e){if(!dead)status.textContent=e.code||e.message;}finally{busy=false;if(!dead)recover.disabled=false;}};card.append(recover);
  }
  const forward=document.createElement('button');forward.textContent='转 AI 处理';forward.disabled=!!item.sourceUnavailable;if(item.sourceUnavailable)forward.dataset.unavailable='true';forward.onclick=async()=>{if(dead||busy)return;busy=true;forward.disabled=true;try{const r=await client.aiCommand('ai.review.create',{source:{kind:'ruling',rulingId:item.rulingId,digest:item.digest}});if(r.status!=='committed')throw Error(r.code||r.status);status.textContent='已创建审核会话，修改另行批准。';if(onOpenSession)await onOpenSession(r.result.sessionId);}catch(e){if(!dead)status.textContent=e.code||e.message;}finally{busy=false;if(!dead)forward.disabled=false;}};card.append(forward);
  appendDebugTools(card,client,{rulingId:item.rulingId},{valid:()=>!dead&&card.isConnected});
  return {card,markdown,key:JSON.stringify(item)};
 }
 function make(item){
  const detail=makeDetail(item);if(!compact)return detail;
  const card=document.createElement('article');card.className='ruling-row';
  const time=document.createElement('time');time.textContent=new Date(item.createdAt*1000).toLocaleString();
  const source=document.createElement('span');source.className='ruling-source';source.textContent=(item.initiator||'AI')+' · '+(item.kind==='player_request'?'创作申请':item.kind==='knowledge_request'?'资料申请':item.kind==='configuration'?(item.highRisk?'高危配置':'配置'):'运行时');
  const summary=document.createElement('span');summary.className='ruling-summary';const excerpt=document.createElement('span');excerpt.className='ruling-excerpt';excerpt.textContent=(item.summary||'修改提案').replace(/\s+/g,' ').slice(0,140);summary.append(excerpt);
  const state=document.createElement('small');state.textContent=item.kind==='runtime'&&item.status==='completed'?'指令已提交':labels[item.status]||item.status;summary.append(state);
  const actions=document.createElement('div');actions.className='ruling-actions';
  const dialog=document.createElement('dialog');dialog.className='ruling-dialog';dialog.setAttribute('aria-label','AI 修改裁决详情');
  const close=document.createElement('button');close.textContent='关闭详情';close.className='ruling-close';close.onclick=()=>dialog.close();dialog.append(close,detail.card);
  const open=document.createElement('button');open.textContent=item.status==='pending'&&item.canDecide?'查看并裁决':'查看详情';open.onclick=()=>{if(!dead&&!busy&&!dialog.open)dialog.showModal();};actions.append(open);
  if(item.sessionId&&onOpenSession){const chat=document.createElement('button');chat.textContent=item.reviewSessionId?'打开审核会话':'打开对话';chat.onclick=async()=>{try{await onOpenSession(item.reviewSessionId||item.sessionId);}catch(e){if(!dead)status.textContent=e.code||e.message;}};actions.append(chat);}
  card.append(time,source,summary,actions,dialog);return {...detail,card,dialog};
 }
 async function refresh(){if(dead)return;const stamp=++seq;try{const data=await client.aiRulings();if(dead||stamp!==seq)return;const retained=new Set();for(const item of data.items){retained.add(item.rulingId);let row=rows.get(item.rulingId);if(!row||row.key!==JSON.stringify(item)){if(row)dispose(row);const next=make(item);if(row)row.card.replaceWith(next.card);else list.append(next.card);row=next;rows.set(item.rulingId,row);}}for(const [id,row] of rows)if(!retained.has(id)){dispose(row);row.card.remove();rows.delete(id);}heading.textContent='AI 修改裁决 · '+data.items.filter(i=>i.status==='pending'&&(!i.queueStatus||i.queueStatus==='active')).length+' 项待处理';if(!data.items.length)status.textContent='暂无 AI 修改';}
  catch(e){if(!dead&&stamp===seq){clear();status.textContent=e.code||e.message;}}
 }
 let identity=JSON.stringify([client.generation,client.connected,client.view?.accountId,client.view?.authorityEpoch]);const unsub=client.subscribe(()=>{const next=JSON.stringify([client.generation,client.connected,client.view?.accountId,client.view?.authorityEpoch]);if(next!==identity){identity=next;clear();}});
 const timer=setInterval(()=>{if(!busy&&!document.hidden)refresh();},2500);refresh();
 return {refresh,destroy(){dead=true;clearInterval(timer);unsub();clear();shell.remove();}};
}
