import {rulingCard,rulingEscape as esc} from './ruling-card.js';
import {explainAIError} from './ai-recovery.js';
import {batchDetailsHTML,batchNoticeSnapshot} from './batch-details.js';

export function rulingIsArchived(item){
  if(['executing','unknown','partial'].includes(item.status))return false;
  return item.archived===true||['history','superseded','archived'].includes(item.queueStatus)||['completed','published','accepted','rejected','cancelled','failed','rolled_back'].includes(item.status);
}

function staleApproval(item){
  const receipts=item.receipts||[];
  return item.kind==='configuration'&&item.highRisk&&item.canDecide&&item.status==='blocked'&&!(item.publications||[]).length&&receipts.length===1&&receipts[0].status==='rejected'&&receipts[0].code==='STALE_AUTHORITY'&&receipts[0].commandId==='ai-ruling:'+item.rulingId.slice('proposal:'.length)+':'+item.revision+':approve';
}
function cReviewHTML(item){
  const c=item.cAssessment;
  if(!c)return '';
  const title=c.stale?'C 类评估依据已更新':c.requiresAcceptance?'C 类风险评估 · 由 KP 决定采用':c.adoptable?'C 类评估':'C 类检查未通过';
  const findings=(c.findings||[]).map(f=>'<li><strong>'+esc(f.message||f.code||'检测项')+'</strong>'+(f.code?'<small> '+esc(f.code)+'</small>':'')+(f.path?'<p>位置：'+esc(f.path)+'</p>':'')+(f.suggestion?'<p>'+esc(f.suggestion)+'</p>':'')+(f.evidence?'<details><summary>查看依据</summary><pre class="data-detail">'+esc(JSON.stringify(f.evidence,null,2))+'</pre></details>':'')+'</li>').join('');
  return '<section class="c-review-assessment notice" aria-label="C 类风险评估"><h3>'+esc(title)+'</h3><p>判断依据版本 '+esc(c.basisRevision)+(c.stale?' · 请重新检测后裁决。':c.requiresAcceptance?' · 此评估包含尚未覆盖或超出既定范围的内容，采用后仍按实际发布结果确认。':'')+'</p>'+(findings?'<ol>'+findings+'</ol>':'')+((c.limitations||[]).length?'<ul>'+c.limitations.map(s=>'<li>'+esc(s)+'</li>').join('')+'</ul>':'')+'</section>';
}
function consultationReady(item){
  const assessment=item.consultationAssessment;
  return !assessment?.requiresAcceptance||typeof assessment.sourceDigest==='string'&&assessment.sourceDigest.length>0;
}
function consultationHTML(item){
  const assessment=item.consultationAssessment;
  if(!assessment)return '';
  const notice=assessment.notice||'方案使用了独立来源资料作为参考。请核对与当前执行目标的关系，再决定是否采用。';
  return '<section class="consultation-assessment notice" aria-label="参考资料评估"><h3>参考资料评估 · 由 KP 决定</h3><p>'+esc(notice)+'</p>'+(Number.isInteger(assessment.sourceCount)?'<small>涉及 '+esc(assessment.sourceCount)+' 项参考来源</small>':'')+(!consultationReady(item)?'<p>评估信息不完整，请重新检查方案。</p>':'')+'</section>';
}
function recheckDelta(item,bundle){
  // Reuse only the intended changes. Never replay unchanged old files over newer work.
  const canonical=value=>JSON.stringify(value,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
  if(!item.changeSet||!Array.isArray(item.diff)||!item.diff.length)throw Error('RECHECK_BASELINE_CHANGED');
  const configurations=Object.fromEntries((bundle.configurations||[]).map(c=>[c.configurationId,c]));
  const delta={schemaVersion:1,configurations:item.changeSet.configurations,sources:{},data:{},suggestions:item.changeSet.suggestions||[]};
  for(const change of item.diff){
    if(!['configuration','sources','data'].includes(change.target))throw Error('RECHECK_BASELINE_CHANGED');
    const current=change.target==='configuration'?configurations[change.id]:bundle[change.target]?.[change.id];
    if(canonical(current??null)!==canonical(change.before??null))throw Error('RECHECK_BASELINE_CHANGED');
    if(change.target!=='configuration'){
      if(change.after==null)throw Error('RECHECK_BASELINE_CHANGED');
      delta[change.target][change.id]=change.after;
    }
  }
  return delta;
}

// Package presentation only. Commands keep the host digest, risk IDs and receipt path.
export function mountPackageRulings(target,client,module,{command,authorized,onSession,onOpenSource,onKnowledgeRequest,onNotice,readBundle,renderReference,timeline=null,onChange=()=>{}}){
  const labels={pending:'等待 KP 裁决',completed:'已执行',published:'已发布',accepted:'已接收，方案另行审核',rejected:'已拒绝',cancelled:'已取消',blocked:'检查未通过',draft:'尚未检查',executing:'执行中／待核对',unknown:'结果待核对',partial:'部分完成（请核对逐项结果）',failed:'执行失败',rolled_back:'整批已撤销，未生效'};
  let dead=false,busy=false,seq=0,items=[],dialog=null,markdown=null,history=false,reading=null,readAgain=false;
  const root=document.createElement('div');root.className='package-rulings';target.append(root);
  const type=i=>i.kind==='player_request'?'玩家创作申请':i.kind==='knowledge_request'?'玩家资料申请':i.kind==='configuration'?(i.highRisk?'AI 高危配置':'AI 配置'):'AI 行动';
  function close(){const old=dialog;dialog=null;markdown?.destroy();markdown=null;old?.close();old?.remove();}
  function notice(item,status,reason,extra={},result=item){if(!authorized())return;const outcome={...item,...result,status},failedReceipt=outcome.receipts?.find(r=>(r.receipt||r).status==='rejected');onNotice({title:type(item),status,reason:explainAIError(reason),batch:batchNoticeSnapshot(outcome),locator:{rulingId:item.rulingId,sessionId:item.sessionId,digest:item.digest,proposalRevision:item.revision,hostCommandId:outcome.execution?.items?.find(r=>r.status==='failed')?.commandId||failedReceipt?.commandId||failedReceipt?.id,...extra}});}
  function reasonOf(value){const failed=value.execution?.items?.find(r=>['failed','unknown'].includes(r.status)),check=value.preflight?.items?.find(r=>['blocked','unsupported'].includes(r.status)),receipt=value.receipts?.find(r=>(r.receipt||r).status!=='committed');return value.blockingReason||value.generationError||(typeof value.error==='string'?value.error:value.error?.message||value.error?.code)||failed?.reason||failed?.code||check?.reason||check?.code||(receipt?.receipt||receipt)?.code||value.reports?.flatMap(r=>r.findings||[]).filter(f=>f.severity==='error').map(f=>f.message||f.code).join('；');}
  function stateLabel(item){const reason=reasonOf(item),state=reason==='STALE_AUTHORITY'?'审批依据已失效':reason==='CONSULTATION_ONLY'?'参考资料需要重新评估':labels[item.status]||item.status;return (item.resolution?'需求已完成 · ':item.supersededBy?'已由后续方案替代 · ':item.archived?'已归档 · ':'')+state;}
  async function act(item,decision,note=''){
    if(dead||busy||!authorized())return;
    close();busy=true;paint();notice(item,'processing','正在提交裁决');
    try{
      let value;
      if(decision==='archive'||decision==='restore'){
        value=await command('ai.queue.archive',{targetId:item.queueTargetId,digest:item.queueDigest,archived:decision==='archive',...(decision==='archive'?{reason:'KP 将无需继续处理的中间方案归档'}:{})});
        notice(item,'completed',decision==='archive'?'已归档，可在已归档标签查看或恢复':value.supersededBy?'已取消手动归档，原方案仍由后续方案替代':rulingIsArchived({...item,...value})?'已取消手动归档，可在已归档标签查看':'已恢复到裁决队列');onChange(value);
      }else if(decision==='recheck'){
        const latest=(await client.aiRulings()).items.find(i=>i.rulingId===item.rulingId);
        if(!authorized()||!latest||latest.digest!==item.digest||latest.revision!==item.revision)throw Error('RULING_STALE');
        const proposalId=item.rulingId.slice('proposal:'.length);let revision=item.revision;
        if(staleApproval(latest)){
          const changes=recheckDelta(latest,await readBundle());
          if(!authorized())return;
          value=await command('ai.proposal.revise',{proposalId,revision,changeSet:changes,summary:(item.summary||'重新检查配置方案').slice(0,2000)});
          revision=value.revision;
        }else if(!(latest.kind==='configuration'&&(latest.canRevalidate||latest.highRisk&&latest.canDecide&&latest.status==='draft')))throw Error('RULING_STALE');
        if(!authorized())return;
        value=await command('ai.proposal.validate',{proposalId,revision});
        const current=(await client.aiRulings()).items.find(i=>i.rulingId===item.rulingId);
        const ready=value.proposal?.status==='review_ready'&&current?.status==='pending'&&current.revision===revision;
        notice(item,ready?'pending':'blocked',ready?'重新检查完成，尚未执行。请重新打开详情核对方案与评估，再作裁决。':reasonOf(value)||(value.proposal?.status==='review_ready'?'RECHECK_STATE_BLOCKED':'重新检查未通过，请查看检查结果'),{digest:value.proposal?.candidateDigest,proposalRevision:revision});
      }else if(decision==='forward'){
        value=await command('ai.review.create',{source:{kind:'ruling',rulingId:item.rulingId,digest:item.digest}});
        notice(item,'completed','已转交 AI；方案须另行审核', {sessionId:value.sessionId});await onSession?.(value.sessionId);
      }else if(decision==='recover'){
        value=await command(item.kind==='runtime'?'ai.batch.reconcile':'ai.knowledge.reconcile',item.kind==='runtime'?{batchId:item.rulingId.slice(6),digest:item.digest}:{rulingId:item.rulingId,digest:item.digest});
        notice(item,value.status,reasonOf(value)||labels[value.status]||value.status,{},value);
      }else if(item.kind==='knowledge_request'&&decision==='approve'){
        await onKnowledgeRequest(item,async disclosures=>{
          let result;try{result=await command('ai.ruling.decide',{rulingId:item.rulingId,digest:item.digest,decision,disclosures});}catch(error){notice(item,error.aiOutcome||'failed',error.code||error.message,{commandRequestId:error.aiRequestId});throw error;}
          notice(item,result.status,reasonOf(result)||'已处理资料披露');await refresh();return result;
        });return;
      }else{
        const confirmation='KP 点击接受并执行，确认本次整包风险。'+(note?'备注：'+note:'');
        const c=item.cAssessment;
        if(decision==='approve'&&c&&(c.stale||!c.adoptable))throw Error(c.stale?'C_BASIS_STALE':'C_REVIEW_NOT_ADOPTABLE');
        if(decision==='approve'&&!consultationReady(item))throw Error('CONSULTATION_REVIEW_REQUIRED');
        value=await command('ai.ruling.decide',{rulingId:item.rulingId,digest:item.digest,decision,
          ...(decision==='approve'?{riskDecisions:Object.fromEntries((item.risks||[]).map(r=>[r.id,confirmation])),...(item.highRisk?{explicitHighRiskDigest:item.digest}:{}),...(c?.requiresAcceptance?{cReview:{basisRevision:c.basisRevision,basisDigest:c.basisDigest,reportDigest:c.reportDigest}}:{}),...(item.consultationAssessment?.requiresAcceptance?{consultationReview:{sourceDigest:item.consultationAssessment.sourceDigest}}:{})}:{})});
        const resultReason=decision==='reject'?(note||'KP 拒绝本次方案（未填写备注）'):['published','completed'].includes(value.status)&&item.consultationAssessment?.requiresAcceptance?'已采纳参考资料评估，'+(labels[value.status]||value.status)+'；可在原裁决核对结果。':value.status==='published'&&c?.requiresAcceptance?'已采纳本次 C 类评估并发布；风险与依据可在原裁决查看。':reasonOf(value)||(note||labels[value.status]||value.status);
        notice(item,value.status,resultReason,{},value);
        onChange(value);
      }
      await refresh();
    }catch(error){notice(item,error.aiOutcome||'failed',error.code||error.message,{commandRequestId:error.aiRequestId||error.requestId});await refresh();}
    finally{busy=false;if(!dead)paint();}
  }
  function open(item){
    if(dead||busy||!authorized())return;close();dialog=document.createElement('dialog');dialog.className='ai-request-detail ruling-dialog';dialog.setAttribute('aria-label','裁决详情');
    dialog.innerHTML='<header><h2>'+esc(type(item))+'</h2><button type="button" data-close>关闭详情</button></header><p>'+esc(stateLabel(item))+'</p><div data-summary></div><details><summary>完整修改与检查结果</summary><pre class="data-detail"></pre></details>';
    markdown=module.mountMarkdown(dialog.querySelector('[data-summary]'),item.summary||'',{resolveReferences:tokens=>client.aiResolve(tokens),renderReference,audience:'administrator'});
    if(item.sourceState==='stale'||item.status==='stale'){dialog.classList.add('ruling-stale');dialog.title=item.sourceNotice||'依赖资料已过时，正文保留原方案。';}
    dialog.querySelector('pre').textContent=JSON.stringify({changeSet:item.changeSet,diff:item.diff,actions:item.actions,preflight:item.preflight,execution:item.execution,riskTags:item.riskTags,reports:item.reports,consultationAssessment:item.consultationAssessment,receipts:item.receipts,publications:item.publications},null,2);
    dialog.querySelector('details').insertAdjacentHTML('beforebegin',batchDetailsHTML(item));
    dialog.querySelector('details').insertAdjacentHTML('beforebegin',cReviewHTML(item));
    dialog.querySelector('details').insertAdjacentHTML('beforebegin',consultationHTML(item));
    if(reasonOf(item)&&!(item.cAssessment?.requiresAcceptance&&item.cAssessment.adoptable&&!item.cAssessment.stale)){const p=document.createElement('p');p.className='notice error';p.textContent=explainAIError(reasonOf(item));dialog.append(p);}
    const controls=document.createElement('div');controls.className='ruling-decision-actions';
    if(item.status==='pending'&&item.canDecide&&consultationReady(item)&&!['blocked','unsupported'].includes(item.preflight?.status)&&!rulingIsArchived(item)&&(!item.cAssessment||item.cAssessment.adoptable&&!item.cAssessment.stale)){
      const label=document.createElement('label');label.textContent='备注（可选）';const note=document.createElement('textarea');note.maxLength=800;note.rows=2;note.setAttribute('aria-label','备注（可选）');label.append(note);dialog.append(label);
      for(const [name,decision] of [[item.kind==='player_request'?'接收并生成方案':item.kind==='knowledge_request'?'选择披露资料':item.consultationAssessment?.requiresAcceptance?(item.kind==='configuration'?'采纳评估并发布':'采纳评估并执行'):item.cAssessment?.requiresAcceptance?'采纳评估并发布':'接受并执行','approve'],['拒绝','reject'],['转 AI 处理','forward']]){
        const b=document.createElement('button');b.type='button';b.textContent=name;b.onclick=()=>act(item,decision,note.value.trim());controls.append(b);
      }
    }else{
      if(item.kind==='configuration'&&item.canRevalidate||readBundle&&(staleApproval(item)||item.kind==='configuration'&&item.highRisk&&item.canDecide&&item.status==='draft')){const b=document.createElement('button');b.textContent='重新检查';b.onclick=()=>act(item,'recheck');controls.append(b);}
      if(['unknown','executing'].includes(item.status)&&['runtime','knowledge_request'].includes(item.kind)){const b=document.createElement('button');b.textContent='核对原执行回执';b.onclick=()=>act(item,'recover');controls.append(b);}
      const b=document.createElement('button');b.textContent='转 AI 处理';b.onclick=()=>act(item,'forward');controls.append(b);
    }
    dialog.append(controls);
    if(item.archiveReason){const reason=document.createElement('p');reason.className='notice';reason.textContent='归档说明：'+item.archiveReason;dialog.append(reason);}
    const related=[...(item.resolution?.targetId?[['查看完成行动',item.resolution.targetId]]:[]),...(item.supersededBy?[['查看后续方案',item.supersededBy]]:[]),...(item.supersedes||[]).map(id=>['查看旧方案',id])];
    for(const [text,id] of related){const b=document.createElement('button');b.type='button';b.textContent=text;b.onclick=()=>{close();Promise.resolve(onOpenSource?.(id.startsWith('request:')?{kind:'request',requestId:id.slice(8)}:{kind:'ruling',rulingId:id})).catch(error=>notice(item,'failed',error.message));};dialog.append(b);}
    if(item.canArchive||item.canRestore){const b=document.createElement('button');b.type='button';b.dataset.queueArchive='';b.textContent=item.canRestore?'恢复到裁决队列':'归档此项';b.onclick=()=>act(item,item.canRestore?'restore':'archive');dialog.append(b);}
    const opened=dialog;module.appendDebugTools?.(dialog,client,{rulingId:item.rulingId},{valid:()=>authorized()&&dialog===opened});
    dialog.querySelector('[data-close]').onclick=close;dialog.addEventListener('cancel',e=>{e.preventDefault();close();});document.body.append(dialog);dialog.showModal();
  }
  function paint(){
    root.innerHTML=items.filter(i=>history?rulingIsArchived(i):!rulingIsArchived(i)).map(i=>rulingCard({stale:i.sourceState==='stale'||i.status==='stale',timestamp:i.createdAt,key:i.rulingId,time:new Date(i.createdAt*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}),type:type(i),source:i.initiator||'KP',summary:esc((i.summary||'修改提案').replace(/\s+/g,' ')),state:stateLabel(i),attrs:'data-ruling-id="'+esc(i.rulingId)+'"',actions:'<button type="button" data-open>查看并裁决</button><button type="button" data-session '+(!(i.reviewSessionId||i.sessionId)?'disabled':'')+'>查看对话</button><button type="button" data-forward>转 AI 处理</button>'})).join('');
    for(const card of root.children){const item=items.find(i=>i.rulingId===card.dataset.rulingId);card.querySelector('[data-open]').onclick=()=>open(item);card.querySelector('[data-forward]').onclick=()=>act(item,'forward');card.querySelector('[data-session]').onclick=()=>Promise.resolve(onSession?.(item.reviewSessionId||item.sessionId)).catch(e=>notice(item,'failed',e.message));if(busy)for(const button of card.querySelectorAll('button'))button.disabled=true;}
    timeline?.set('rulings',[...root.children]);
  }
  async function refresh(){
    if(dead||!authorized())return;
    if(reading){readAgain=true;return reading;}
    reading=(async()=>{
      do{
        readAgain=false;const ticket=++seq;
        try{const data=await client.aiRulings();if(dead||ticket!==seq||!authorized())return;items=data.items;paint();}
        catch(e){if(!dead){timeline?.remove('rulings');root.textContent=e.message||e.code;}}
      }while(readAgain&&!dead&&authorized());
    })();
    try{return await reading;}finally{reading=null;}
  }
  const timer=setInterval(()=>{if(!busy&&!document.hidden&&root.isConnected)refresh();},4000);refresh();
  return {refresh,setTimeline(value){timeline?.remove('rulings');timeline=value;paint();},setHistory(value){history=value;paint();},destroy(){dead=true;seq++;close();clearInterval(timer);timeline?.remove('rulings');root.remove();}};
}
