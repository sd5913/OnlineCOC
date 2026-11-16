import {guardedClient} from './guard.js';

/** Owner-scoped session directory and settings; does not own the supplied client. */
export function mountSessionManager(target,rawClient,{onOpen=null,onChange=()=>{},title='会话管理'}={}){
 const element=document.createElement('div');target.append(element);const root=element.attachShadow({mode:'open'});
 const css=document.createElement('link');css.rel='stylesheet';css.href=new URL('./session-manager.css',import.meta.url);root.append(css);
 const panel=document.createElement('section');panel.className='session-manager';root.append(panel);
 panel.innerHTML=`<header><h2></h2><span class="owner"></span><button class="refresh" type="button">刷新</button></header><form class="create"><input aria-label="新会话名称" maxlength="120" placeholder="新会话名称"><button>新建会话</button></form><div class="filters"><input class="search" type="search" aria-label="搜索会话" placeholder="搜索会话名称"><select class="filter" aria-label="会话范围"><option value="active">使用中</option><option value="archived">已归档</option><option value="all">全部</option></select><select class="sort" aria-label="会话排序"><option value="recent">最近更新</option><option value="title">名称</option></select></div><div class="workspace"><nav class="list" aria-label="会话目录"></nav><form class="settings" hidden><h3>会话设置</h3><label>名称<input name="title" required maxlength="120"></label><label><input name="pinned" type="checkbox">置顶会话</label><label>携带的历史需求<select name="historyTurns"><option value="0">不携带</option><option value="1">最近 1 轮</option><option value="2">最近 2 轮</option><option value="3">最近 3 轮</option><option value="4">最近 4 轮（默认）</option></select></label><small>仅影响后续生成；原记录仍保留，来源权限和总输入限制继续生效。</small><label>回答显示<select name="renderMode"><option value="formatted">格式化文本</option><option value="plain">原始文本</option></select></label><label class="diagnostics"><input name="showDiagnostics" type="checkbox">显示查询诊断（KP）</label><div class="actions"><button class="save">保存设置</button><button class="open" type="button">打开对话</button><button class="archive" type="button">归档</button></div><p class="details"></p></form></div><p class="status" role="status"></p>`;
 const $=s=>panel.querySelector(s),form=$('.settings');$('h2').textContent=title;
 let dead=false,paused=false,busy=false,uncertain=null,sequence=0,selectionSequence=0,current=null,items=[],identity='';
 const client=guardedClient(rawClient,()=>dead);const checked=r=>{if(r.status!=='committed')throw Object.assign(new Error(r.code||r.status),{code:r.code,...(['pending','unknown'].includes(r.status)?{aiRequestId:r.requestId}:{})});return r.result;};
 async function write(op,args){if(uncertain)throw new Error('请先查询原操作结果');return checked(await client.aiCommand(op,args));}
 function state(text){if(!dead)$('.status').textContent=text;}
 const recovery=document.createElement('button');recovery.type='button';recovery.className='receipt';recovery.hidden=true;recovery.textContent='查询操作结果';panel.append(recovery);
 function locks(){for(const el of panel.querySelectorAll('button,input,select'))el.disabled=busy||!client.connected;for(const el of panel.querySelectorAll('.create button,.save,.archive'))el.disabled||=!!uncertain;recovery.hidden=!uncertain;}
 async function run(fn){if(dead||busy||!client.connected)return;busy=true;locks();try{await fn();}catch(e){if(e.aiRequestId){uncertain=e.aiRequestId;state('操作结果尚未确认，请查询原操作回执：'+uncertain);}else state(e.code==='SESSION_VERSION_CONFLICT'?'会话已在其他页面修改，请重新选择后再保存。':e.code||e.message);}finally{busy=false;if(!dead)locks();}}
 function paint(){
  const q=$('.search').value.trim().toLocaleLowerCase();const list=items.filter(s=>s.title.toLocaleLowerCase().includes(q));
  list.sort((a,b)=>Number(b.pinned)-Number(a.pinned)||($('.sort').value==='title'?a.title.localeCompare(b.title):b.updatedAt-a.updatedAt));$('.list').replaceChildren();
  for(const s of list){const b=document.createElement('button');b.type='button';b.className='session-link';b.setAttribute('aria-current',String(current?.sessionId===s.sessionId));b.textContent=(s.pinned?'★ ':'')+s.title;const small=document.createElement('small');small.textContent=(s.archived?'已归档 · ':'')+s.requestCount+' 条 · '+new Date(s.updatedAt*1000).toLocaleString();b.append(small);b.onclick=()=>run(()=>select(s.sessionId));$('.list').append(b);}
  if(!list.length)$('.list').textContent=q?'没有匹配的会话':'暂无会话';
 }
 function show(session){current=session;form.hidden=false;for(const key of ['title','historyTurns','renderMode'])form.elements[key].value=session[key]??({historyTurns:4,renderMode:'formatted'}[key]||'');for(const key of ['pinned','showDiagnostics'])form.elements[key].checked=session[key]??(key==='showDiagnostics');$('.diagnostics').hidden=client.view?.role!=='kp';$('.archive').textContent=session.archived?'恢复会话':'归档';$('.open').hidden=!onOpen;$('.details').textContent=session.archived?'已归档，恢复后可继续发送需求。':'设置保存在本房间，仅本人可管理。';paint();}
 async function select(id){const seq=++selectionSequence;const result=await client.aiSession(id);if(dead||seq!==selectionSequence)return;show(result.session);state('');}
 async function refresh(){
  if(dead||paused||!client.connected)return;const seq=++sequence,filter=$('.filter').value;
  const pages=await Promise.all(filter==='all'?[client.aiSessions(false),client.aiSessions(true)]:[client.aiSessions(filter==='archived')]);
  if(dead||paused||seq!==sequence)return;items=pages.flatMap(p=>p.items);paint();
 }
 $('.create').onsubmit=e=>{e.preventDefault();run(async()=>{const input=$('.create input');const session=await write('ai.session.create',{title:input.value.trim()||'新会话'});input.value='';$('.filter').value='active';await refresh();show(session);state('会话已创建');onChange(session);});};
 form.onsubmit=e=>{e.preventDefault();run(async()=>{if(!current)return;const args={sessionId:current.sessionId,revision:current.revision,title:form.elements.title.value,pinned:form.elements.pinned.checked,historyTurns:Number(form.elements.historyTurns.value),renderMode:form.elements.renderMode.value,showDiagnostics:form.elements.showDiagnostics.checked};const session=await write('ai.session.update',args);show(session);await refresh();state('设置已保存');onChange(session);});};
 $('.archive').onclick=()=>run(async()=>{if(!current)return;const session=await write('ai.session.update',{sessionId:current.sessionId,revision:current.revision,archived:!current.archived});show(session);await refresh();state(session.archived?'会话已归档':'会话已恢复');onChange(session);});
 $('.open').onclick=()=>run(()=>onOpen?.(current.sessionId));$('.refresh').onclick=()=>run(refresh);$('.filter').onchange=()=>run(refresh);$('.search').oninput=paint;$('.sort').onchange=paint;
 function changed(){const next=JSON.stringify([client.generation,client.connected,client.view?.accountId,client.view?.role,client.view?.authorityEpoch]);if(next===identity||dead)return;identity=next;sequence++;selectionSequence++;current=null;items=[];uncertain=null;form.reset();form.hidden=true;$('.list').replaceChildren();$('.search').value='';$('.create input').value='';$('.owner').textContent=client.connected?client.view.accountId:'';locks();state(client.connected?'':'请先登录房间');if(client.connected)refresh().catch(e=>state(e.code||e.message));}
 recovery.onclick=()=>run(async()=>{const receipt=await client.aiReceipt(uncertain);if(!['committed','rejected'].includes(receipt.status)){state('结果仍未确认，请稍后查询原操作回执');return;}
  uncertain=null;if(receipt.status==='committed'){if(receipt.result?.sessionId){show(receipt.result);onChange(receipt.result);}await refresh();state('操作已确认');}else state('操作未提交：'+(receipt.code||receipt.status));
 });
 const unsubscribe=client.subscribe(changed);changed();
 return {refresh,select,suspend(){paused=true;sequence++;selectionSequence++;},async resume(){paused=false;await refresh();},destroy(){dead=true;sequence++;selectionSequence++;unsubscribe();element.remove();}};
}
