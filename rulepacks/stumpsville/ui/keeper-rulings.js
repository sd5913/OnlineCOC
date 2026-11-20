import {rulingCard,rulingEscape as esc} from './ruling-card.js';
import {explainAIError} from './ai-recovery.js';

function staleApproval(item){
  const receipts=item.receipts||[];
  return item.kind==='configuration'&&item.highRisk&&item.canDecide&&item.status==='blocked'&&!(item.publications||[]).length&&receipts.length===1&&receipts[0].status==='rejected'&&receipts[0].code==='STALE_AUTHORITY'&&receipts[0].commandId==='ai-ruling:'+item.rulingId.slice('proposal:'.length)+':'+item.revision+':approve';
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
export function mountPackageRulings(target,client,module,{command,authorized,onSession,onOpenSource,onKnowledgeRequest,onNotice,readBundle,renderReference,onChange=()=>{}}){
  const labels={pending:'等待 KP 裁决',completed:'已执行',published:'已发布',accepted:'已接收，方案另行审核',rejected:'已拒绝',cancelled:'已取消',blocked:'检查未通过',draft:'尚未检查',executing:'执行中／待核对',unknown:'结果待核对',partial:'部分完成'};
  const terminal=new Set(['completed','published','accepted','rejected','cancelled']);
  let dead=false,busy=false,seq=0,items=[],dialog=null,markdown=null,history=false;
  const root=document.createElement('div');root.className='package-rulings';target.append(root);
  const type=i=>i.kind==='player_request'?'玩家创作申请':i.kind==='knowledge_request'?'玩家资料申请':i.kind==='configuration'?(i.highRisk?'AI 高危配置':'AI 配置'):'AI 行动';
  function close(){const old=dialog;dialog=null;markdown?.destroy();markdown=null;old?.close();old?.remove();}
  function notice(item,status,reason,extra={}){if(!authorized())return;onNotice({title:type(item),status,reason:explainAIError(reason),locator:{rulingId:item.rulingId,sessionId:item.sessionId,digest:item.digest,proposalRevision:item.revision,hostCommandId:item.receipts?.find(r=>r.status==='rejected')?.commandId,...extra}});}
  function reasonOf(value){return value.blockingReason||value.generationError||value.error||value.receipts?.find(r=>r.status!=='committed')?.code||value.reports?.flatMap(r=>r.findings||[]).filter(f=>f.severity==='error').map(f=>f.message||f.code).join('；');}
  function stateLabel(item){return reasonOf(item)==='STALE_AUTHORITY'?'审批依据已失效':labels[item.status]||item.status;}
  async function act(item,decision,note=''){
    if(dead||busy||!authorized())return;
    close();busy=true;paint();notice(item,'processing','正在提交裁决');
    try{
      let value;
      if(decision==='recheck'){
        const latest=(await client.aiRulings()).items.find(i=>i.rulingId===item.rulingId);
        if(!authorized()||!latest||latest.digest!==item.digest||latest.revision!==item.revision)throw Error('RULING_STALE');
        const proposalId=item.rulingId.slice('proposal:'.length);let revision=item.revision;
        if(staleApproval(latest)){
          const changes=recheckDelta(latest,await readBundle());
          if(!authorized())return;
          value=await command('ai.proposal.revise',{proposalId,revision,changeSet:changes,summary:(item.summary||'重新检查配置方案').slice(0,2000)});
          revision=value.revision;
        }else if(!(latest.kind==='configuration'&&latest.highRisk&&latest.canDecide&&latest.status==='draft'))throw Error('RULING_STALE');
        if(!authorized())return;
        value=await command('ai.proposal.validate',{proposalId,revision});
        const current=(await client.aiRulings()).items.find(i=>i.rulingId===item.rulingId);
        const ready=value.proposal?.status==='review_ready'&&current?.status==='pending'&&current.revision===revision;
        notice(item,ready?'pending':'blocked',ready?'重新检查通过，尚未执行。请重新打开详情核对方案，再点击接受并执行。':reasonOf(value)||(value.proposal?.status==='review_ready'?'RECHECK_STATE_BLOCKED':'重新检查未通过，请查看检查结果'),{digest:value.proposal?.candidateDigest,proposalRevision:revision});
      }else if(decision==='forward'){
        value=await command('ai.review.create',{source:{kind:'ruling',rulingId:item.rulingId,digest:item.digest}});
        notice(item,'completed','已转交 AI；方案须另行审核', {sessionId:value.sessionId});await onSession?.(value.sessionId);
      }else if(decision==='recover'){
        value=await command(item.kind==='runtime'?'ai.batch.reconcile':'ai.knowledge.reconcile',item.kind==='runtime'?{batchId:item.rulingId.slice(6),digest:item.digest}:{rulingId:item.rulingId,digest:item.digest});
        notice(item,value.status,reasonOf(value)||labels[value.status]||value.status);
      }else if(item.kind==='knowledge_request'&&decision==='approve'){
        await onKnowledgeRequest(item,async disclosures=>{
          let result;try{result=await command('ai.ruling.decide',{rulingId:item.rulingId,digest:item.digest,decision,disclosures});}catch(error){notice(item,error.aiOutcome||'failed',error.code||error.message,{commandRequestId:error.aiRequestId});throw error;}
          notice(item,result.status,reasonOf(result)||'已处理资料披露');await refresh();return result;
        });return;
      }else{
        const confirmation='KP 点击接受并执行，确认本次整包风险。'+(note?'备注：'+note:'');
        value=await command('ai.ruling.decide',{rulingId:item.rulingId,digest:item.digest,decision,
          ...(decision==='approve'?{riskDecisions:Object.fromEntries((item.risks||[]).map(r=>[r.id,confirmation])),...(item.highRisk?{explicitHighRiskDigest:item.digest}:{})}:{})});
        notice(item,value.status,reasonOf(value)||(decision==='reject'?(note||'KP 拒绝本次方案（未填写备注）'):(note||labels[value.status]||value.status)));
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
    dialog.querySelector('pre').textContent=JSON.stringify({changeSet:item.changeSet,diff:item.diff,actions:item.actions,riskTags:item.riskTags,reports:item.reports,receipts:item.receipts,publications:item.publications},null,2);
    if(reasonOf(item)){const p=document.createElement('p');p.className='notice error';p.textContent=explainAIError(reasonOf(item));dialog.append(p);}
    const controls=document.createElement('div');controls.className='ruling-decision-actions';
    if(item.status==='pending'&&item.canDecide){
      const label=document.createElement('label');label.textContent='备注（可选）';const note=document.createElement('textarea');note.maxLength=800;note.rows=2;note.setAttribute('aria-label','备注（可选）');label.append(note);dialog.append(label);
      for(const [name,decision] of [[item.kind==='player_request'?'接收并生成方案':item.kind==='knowledge_request'?'选择披露资料':'接受并执行','approve'],['拒绝','reject'],['转 AI 处理','forward']]){
        const b=document.createElement('button');b.type='button';b.textContent=name;b.onclick=()=>act(item,decision,note.value.trim());controls.append(b);
      }
    }else{
      if(readBundle&&(staleApproval(item)||item.kind==='configuration'&&item.highRisk&&item.canDecide&&item.status==='draft')){const b=document.createElement('button');b.textContent='重新检查';b.onclick=()=>act(item,'recheck');controls.append(b);}
      if(['unknown','executing'].includes(item.status)&&['runtime','knowledge_request'].includes(item.kind)){const b=document.createElement('button');b.textContent='核对原执行回执';b.onclick=()=>act(item,'recover');controls.append(b);}
      const b=document.createElement('button');b.textContent='转 AI 处理';b.onclick=()=>act(item,'forward');controls.append(b);
    }
    dialog.append(controls);const opened=dialog;module.appendDebugTools?.(dialog,client,{rulingId:item.rulingId},{valid:()=>authorized()&&dialog===opened});
    dialog.querySelector('[data-close]').onclick=close;dialog.addEventListener('cancel',e=>{e.preventDefault();close();});document.body.append(dialog);dialog.showModal();
  }
  function paint(){
    root.innerHTML=items.filter(i=>history?terminal.has(i.status):!terminal.has(i.status)).map(i=>rulingCard({time:new Date(i.createdAt*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}),type:type(i),source:i.initiator||'KP',summary:esc((i.summary||'修改提案').replace(/\s+/g,' ')),state:stateLabel(i),attrs:'data-ruling-id="'+esc(i.rulingId)+'"',actions:'<button type="button" data-open>查看并裁决</button><button type="button" data-session '+(!(i.reviewSessionId||i.sessionId)?'disabled':'')+'>查看对话</button><button type="button" data-forward>转 AI 处理</button>'})).join('');
    for(const card of root.children){const item=items.find(i=>i.rulingId===card.dataset.rulingId);card.querySelector('[data-open]').onclick=()=>open(item);card.querySelector('[data-forward]').onclick=()=>act(item,'forward');card.querySelector('[data-session]').onclick=()=>Promise.resolve(onSession?.(item.reviewSessionId||item.sessionId)).catch(e=>notice(item,'failed',e.message));if(busy)for(const button of card.querySelectorAll('button'))button.disabled=true;}
  }
  async function refresh(){if(dead||!authorized())return;const ticket=++seq;try{const data=await client.aiRulings();if(dead||ticket!==seq||!authorized())return;items=data.items;paint();}catch(e){if(!dead){root.textContent=e.code||e.message;}}}
  const timer=setInterval(()=>{if(!busy&&!document.hidden&&root.isConnected)refresh();},4000);refresh();
  return {refresh,setHistory(value){history=value;paint();},destroy(){dead=true;seq++;close();clearInterval(timer);root.remove();}};
}
