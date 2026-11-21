const $=id=>document.getElementById(id);
const seed=[{id:1,title:'庭院向导设计',owner:'kp',level:'administrator',summary:'新增 NPC 的配置已提交，等待裁决',review:true,pinned:true},{id:2,title:'木栗的调查笔记',owner:'木栗',level:'player',summary:'入口隧道与主门的已知线索',review:false},{id:3,title:'下一场的规则准备',owner:'kp',level:'administrator',summary:'核对角色受伤与恢复规则',review:false},{id:4,title:'上次旅程回顾',owner:'木栗',level:'player',summary:'已整理，保留供下次查阅',archived:true}];
let sessions,selected=1,filter='active',undo,toastTimer;
function currentUser(){return $('role').value==='kp'?'kp':'木栗'}
function allowed(){return sessions.filter(s=>$('role').value==='kp'||s.owner===currentUser())}
function notify(text,restore){clearTimeout(toastTimer);$('toast').hidden=false;$('toast').querySelector('span').textContent=text;undo=restore;$('undo').hidden=!restore;toastTimer=setTimeout(()=>{$('toast').hidden=true;},restore?8000:4000);}
function actionButton(label,fn,cls=''){const b=document.createElement('button');b.textContent=label;b.className=cls;b.onclick=fn;return b;}
function select(s){selected=s.id;document.body.classList.add('detail-open');render();}
function render(){
 const kp=$('role').value==='kp';$('scope').textContent=kp?'全房间会话 · 可查看玩家提交':'只显示木栗的会话';$('mine-label').hidden=!kp;
 const rows=allowed().filter(s=>(!$('mine').checked||!kp||s.owner===currentUser())&&s.title.includes($('search').value)&&
  (filter==='archived'?s.archived:!s.archived&&(filter!=='review'||s.review))).sort((a,b)=>Number(!!b.pinned)-Number(!!a.pinned));
 $('count').textContent=rows.length+' 个会话';$('sessions').replaceChildren();
 for(const s of rows){const b=actionButton('',()=>select(s),'session'+(s.id===selected?' active':''));
  const title=document.createElement('span');title.className='title';title.textContent=(s.pinned?'★ ':'')+s.title;
  const summary=document.createElement('span');summary.className='summary';summary.textContent=s.summary;
  const meta=document.createElement('div');meta.className='meta';for(const text of [s.level==='administrator'?'管理员':'玩家',s.owner,s.archived?'已归档':s.review?'待裁决':'今天更新']){const item=document.createElement('span');item.className='badge'+(text==='待裁决'?' review':'');item.textContent=text;meta.append(item);}b.append(title,summary,meta);$('sessions').append(b);
 }
 if(!rows.length){const p=document.createElement('p');p.className='empty';p.textContent='这里还没有会话。试试切换状态，或新建一个。';$('sessions').append(p);}
 const s=allowed().find(s=>s.id===selected);const detail=$('details');detail.replaceChildren();if(!s){detail.textContent='选择会话查看详情';return;}
 detail.innerHTML='<div class="detail-top"><button class="back">← 返回列表</button><span class="eyebrow">会话详情</span></div><h2></h2><p class="owner"></p><div class="open-action"></div><div class="scope-card"><strong>本会话能读取什么</strong><p></p></div><div class="summary-card">最近进展<span></span></div><label class="detail-input">会话标题<input id="edit-title" maxlength="80"></label><label class="detail-input">携带最近历史<select id="history"><option value="0">不携带历史</option><option value="2">最近 2 轮</option><option value="4">最近 4 轮</option></select></label><div class="save-action"></div><div class="detail-footer"></div>';
 detail.querySelector('.back').onclick=()=>document.body.classList.remove('detail-open');detail.querySelector('h2').textContent=s.title;detail.querySelector('.owner').textContent=`创建者：${s.owner} · ${s.level==='administrator'?'管理员':'玩家'}级（固定）`;
 detail.querySelector('.scope-card p').textContent=s.level==='player'?'本人角色、进入过或向本人揭示的场景、个人线索、可参与的聊天与裁决。不能读取 KP 真相及其他玩家私密资料。':'KP 授权的房间资料与会话。修改提交为裁决批次；读取私聊仍受参与者权限限制。';
 detail.querySelector('.summary-card span').textContent=s.summary;detail.querySelector('.open-action').append(actionButton(s.owner===currentUser()?'继续对话':'查看玩家对话',()=>{$('conversation-title').textContent=s.title;$('conversation').showModal();},'primary'));
 $('edit-title').value=s.title;$('history').value=String(s.history??4);detail.querySelector('.save-action').append(actionButton('保存设置',()=>{if(!$('edit-title').value.trim())return;s.title=$('edit-title').value.trim();s.history=Number($('history').value);render();notify('设置已保存（原型）');}));
 detail.querySelector('.detail-footer').append(actionButton(s.pinned?'取消置顶':'置顶',()=>{s.pinned=!s.pinned;render();}),actionButton(s.archived?'恢复会话':'归档',()=>{s.archived=!s.archived;const value=s.archived;render();notify(value?'已归档，随时可以恢复':'已恢复到进行中',()=>{s.archived=!value;render();});}),actionButton('删除',()=>$('confirm').showModal(),'danger'));
}
$('filters').onclick=e=>{const f=e.target.dataset.filter;if(!f)return;filter=f;for(const b of $('filters').children)b.setAttribute('aria-pressed',String(b===e.target));render();};$('search').oninput=render;$('mine').onchange=render;
$('role').onchange=()=>{$('mine').checked=false;selected=null;document.body.classList.remove('detail-open');render();};
$('reset').onclick=()=>{sessions=structuredClone(seed);selected=1;filter='active';$('role').value='kp';$('search').value='';$('mine').checked=false;$('filters').querySelector('[data-filter=active]').click();$('toast').hidden=true;render();};
$('new').onclick=()=>{const form=$('create-form');form.reset();form.elements.level.value=$('role').value==='kp'?'administrator':'player';form.elements.level.disabled=$('role').value!=='kp';$('create').showModal();};
$('create-form').onsubmit=e=>{e.preventDefault();const f=e.currentTarget;const s={id:Date.now(),title:f.elements.title.value.trim(),owner:currentUser(),level:$('role').value==='kp'?f.elements.level.value:'player',summary:'还没有消息'};sessions.unshift(s);filter='active';$('filters').querySelector('[data-filter=active]').click();$('create').close();select(s);notify('会话已创建，身份已绑定（原型）');};
$('delete-confirm').onclick=()=>{sessions=sessions.filter(s=>s.id!==selected);selected=null;$('confirm').close();render();notify('会话已删除，审计记录仍保留（原型）');};
for(const b of document.querySelectorAll('[data-close]'))b.onclick=()=>b.closest('dialog').close();$('undo').onclick=()=>{undo?.();$('toast').hidden=true;};$('reset').click();
