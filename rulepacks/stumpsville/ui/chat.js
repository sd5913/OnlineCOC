import {t} from './i18n.js';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let services, state, identity='', root, shown=false, selected='general', minimized=false, serial=0, pinned=false, channelGroup='room';
const windows=new Map(), drafts=new Map(), pages=new Map();
const label=c=>c.kind==='direct'?(c.participants||[]).filter(id=>id!==state.accountId).map(id=>{const member=state.team?.find(p=>p.account===id);return member?member.name+' · '+id:id;}).join(' / ')||c.name:c.channelId==='general'?t('chat.global'):c.kind==='party'?t('chat.party'):c.kind==='scene'?t('chat.scene')+' · '+c.name.replace('场景 ',''):c.name;
const btn=(text,action,channel='')=>`<button type="button" data-chat="${action}" data-channel="${esc(channel)}">${esc(text)}</button>`;
function box(channel, popout=false){
  const c=state.channels[channel]; if(!c)return '';
  return `<section class="conversation" data-conversation="${esc(channel)}"><header><strong>${esc(label(c))}</strong><small>${esc(c.kind==='direct'?t('chat.private'):t('chat.membersonly'))}</small>${!popout&&c.kind==='direct'?btn(t('chat.popout'),'popout',channel):''}</header><div class="chat-history" ${popout?'':'id="chat-history"'} aria-live="polite"></div><div class="chat-tools">${btn(t('chat.older'),'older',channel)}${btn(t('chat.read'),'read',channel)}</div><form ${popout?'':'id="chat-form"'} data-chat-form="${esc(channel)}"><textarea aria-label="${esc(t('chat.message'))}" name="text" maxlength="4000" placeholder="${esc(t('chat.placeholder'))}" ${c.canPost?'':'disabled'}>${esc(drafts.get(channel)||'')}</textarea><footer><small>Ctrl + Enter</small><button type="submit" ${c.canPost?'':'disabled'}>${esc(t('chat.send'))}</button></footer></form></section>`;
}
function render(){
  if(!root||!state)return;
  if(!state.channels[selected])selected=Object.values(state.channels).find(c=>!pinned||c.kind===channelGroup)?.channelId||'';
  const groups=[['room',t('chat.global')],['scene',t('chat.scene')],['party',t('chat.party')],['group',t('chat.groups')],['direct',t('chat.private')]];
  const conversationList=groups.map(([kind,name])=>`<section class="channel-group" data-kind="${kind}" ${pinned&&kind!==channelGroup?'hidden':''}><h4>${esc(name)}</h4>${Object.values(state.channels).filter(c=>c.kind===kind).map(c=>`<button type="button" class="${c.channelId===selected?'selected':''}" data-chat="select" data-channel="${esc(c.channelId)}"><span class="chat-avatar">${kind==='direct'?'●':'♧'}</span><span>${esc(label(c))}</span><b>${c.unreadCount||''}</b></button>`).join('')}</section>`).join('');
  root.classList.toggle('chat-pinned',pinned);
  root.innerHTML=`${shown?`<section class="messenger ${minimized?'minimized':''}" aria-label="${esc(t('chat.title'))}"><header class="messenger-title"><strong>${esc(t('chat.title'))}</strong><span>${btn(t('chat.direct'),'direct')}${pinned?'':btn(minimized?t('chat.expand'):t('chat.minimize'),'minimize')+btn(t('chat.close'),'close')}</span></header>${pinned?`<nav class="chat-scope-tabs">${groups.filter(([kind])=>kind!=='group'||Object.values(state.channels).some(c=>c.kind==='group')).map(([kind,name])=>`<button type="button" class="${channelGroup===kind?'selected':''}" data-chat="group" data-channel="${kind}">${esc(name)}<b data-unread-group="${kind}">${Object.values(state.channels).filter(c=>c.kind===kind).reduce((n,c)=>n+(c.unreadCount||0),0)||''}</b></button>`).join('')}</nav>`:''}<div class="messenger-body" ${minimized?'hidden':''}><aside class="conversation-list" ${pinned&&Object.values(state.channels).filter(c=>c.kind===channelGroup).length<=1?'hidden':''}>${conversationList}</aside>${box(selected)||`<p class="empty">${esc(t('chat.nochannels'))}</p>`}</div></section>`:''}${[...windows].map(([channel,w],i)=>`<section class="dm-window ${w.minimized?'minimized':''}" style="--window-index:${i%4};z-index:${w.z}" aria-label="${esc(t('chat.private'))}: ${esc(label(state.channels[channel]))}"><header class="messenger-title" data-drag="${esc(channel)}"><strong>${esc(label(state.channels[channel]))}</strong><span>${btn(w.minimized?t('chat.expand'):t('chat.minimize'),'dm-minimize',channel)}${btn(t('chat.close'),'dm-close',channel)}</span></header><div ${w.minimized?'hidden':''}>${box(channel,true)}</div></section>`).join('')}`;
  for(const channel of pages.keys())paint(channel);
  for(const [channel,w] of windows){const node=[...root.querySelectorAll('.dm-window')].find(n=>n.querySelector('[data-drag]').dataset.drag===channel);if(w.x!==undefined){node.style.left=w.x+'px';node.style.top=w.y+'px';node.style.right='auto';node.style.bottom='auto';}}
  poll().catch(error=>services.toast(error.message));
}
function paint(channel){
  const p=pages.get(channel);if(!p)return;
  for(const node of root.querySelectorAll('[data-conversation]')){
    if(node.dataset.conversation!==channel)continue;
    const target=node.querySelector('.chat-history');
    const bottom=target.scrollHeight-target.scrollTop-target.clientHeight<35;
    const old=target.scrollTop;
    target.innerHTML=p.items.map(m=>`<article class="chat-bubble ${m.senderAccountId===state.accountId?'own':''}"><small>${esc(m.speakerName||m.senderAccountId)} · ${new Date(m.createdAt*1000).toLocaleTimeString()}</small><p>${esc(m.deleted?t('chat.retracted'):m.text||JSON.stringify(m.card?.result||''))}</p>${m.senderAccountId===state.accountId&&!m.deleted?`<span>${btn(t('chat.edit'),'edit:'+m.messageId,channel)}${btn(t('chat.retract'),'retract:'+m.messageId,channel)}</span>`:''}</article>`).join('')||`<p class="empty">${esc(t('chat.empty'))}</p>`;
    target.dataset.atBottom=String(bottom);target.scrollTop=bottom?target.scrollHeight:old;
  }
}
async function history(channel,older=false){
  if(!state?.channels[channel])return;
  const who=identity, generation=serial, prior=pages.get(channel), revision=state.channels[channel].revision;
  const result=await services.api('package/chat/history',{channelId:channel,limit:50,...(older&&prior?.nextBefore?{before:prior.nextBefore}:{})});
  if(who!==identity||generation!==serial||!state?.channels[channel]||state.channels[channel].revision!==revision)return;
  pages.set(channel,{...result,revision,items:older&&prior?.revision===revision?[...result.items,...prior.items]:result.items});paint(channel);
}
async function poll(){
  if(!state)return;
  const visible=new Set([...windows].filter(([,w])=>!w.minimized).map(([id])=>id));
  if(shown&&!minimized)visible.add(selected);
  for(const c of visible)if(state.channels[c]&&pages.get(c)?.revision!==state.channels[c].revision)await history(c);
}
async function send(operation,input){const r=await services.send(operation,input);if(!r)throw Error(t('chat.busy'));return r.result;}
async function click(event){
  const b=event.target.closest('[data-chat]');if(!b)return;
  event.stopPropagation();const action=b.dataset.chat, channel=b.dataset.channel;
  try{
    if(action==='close'&&!pinned)shown=false;
    else if(action==='group'){channelGroup=channel;selected=Object.values(state.channels).find(c=>c.kind===channelGroup)?.channelId||'';}
    else if(action==='minimize'&&!pinned)minimized=!minimized;
    else if(action==='select'){selected=channel;channelGroup=state.channels[channel].kind;}
    else if(action==='popout'){windows.set(channel,{z:++serial+110});}
    else if(action==='dm-close')windows.delete(channel);
    else if(action==='dm-minimize')windows.get(channel).minimized=!windows.get(channel).minimized;
    else if(action==='older'){if(pages.get(channel)?.nextBefore)await history(channel,true);return;}
    else if(action==='read'){await send('chat.read',{channelId:channel,sequence:state.channels[channel].lastSequence});return;}
    else if(action.startsWith('edit:')||action.startsWith('retract:')){
      const message=pages.get(channel)?.items.find(m=>m.messageId===action.split(':')[1]);if(!message)return;
      if(action.startsWith('edit:')){
        const node=[...root.querySelectorAll('[data-conversation]')].find(n=>n.dataset.conversation===channel);
        const form=node.querySelector('form');form.dataset.edit=message.messageId;form.dataset.revision=message.revision;
        form.querySelector('textarea').value=message.text;form.querySelector('textarea').focus();return;
      }
      await send('chat.message.retract',{channelId:channel,messageId:message.messageId,revision:message.revision});await history(channel);return;
    }else if(action==='direct'){
      const members=await services.api('api/v1/chat/members');
      const chooser=document.createElement('dialog');chooser.className='chat-contacts';
      chooser.innerHTML=`<h2>${esc(t('chat.contacts'))}</h2>${members.items.filter(m=>m.accountId!==state.accountId).map(m=>`<button data-contact="${esc(m.accountId)}">${esc(m.nickname||m.accountId)} · ${esc(m.accountId)}</button>`).join('')}${btn(t('chat.close'),'dismiss')}`;
      root.append(chooser);chooser.showModal();
      chooser.onclick=async e=>{const account=e.target.closest('[data-contact]')?.dataset.contact;if(!account){if(e.target.closest('[data-chat]'))chooser.remove();return;}try{const r=await send('chat.direct.open',{accountId:account});selected=r.channelId;channelGroup='direct';windows.set(selected,{z:++serial+110});chooser.remove();render();}catch(error){services.toast(error.message);}};return;
    }
    render();
  }catch(error){services.toast(error.message);}
}
function configure(options){
  services=options;root=document.createElement('div');root.id='chat-layer';document.body.append(root);
  root.addEventListener('scroll',e=>{if(e.target.matches('.chat-history'))e.target.dataset.atBottom=String(e.target.scrollHeight-e.target.scrollTop-e.target.clientHeight<35);},true);
  root.addEventListener('click',click);
  root.addEventListener('input',e=>{const form=e.target.closest('[data-chat-form]');if(form)drafts.set(form.dataset.chatForm,e.target.value);});
  root.addEventListener('keydown',e=>{if(e.ctrlKey&&e.key==='Enter'&&e.target.matches('textarea')){e.preventDefault();e.target.closest('form').requestSubmit();}});
  root.addEventListener('submit',async e=>{
    const form=e.target.closest('[data-chat-form]');if(!form)return;e.preventDefault();e.stopPropagation();
    const channel=form.dataset.chatForm, input=form.querySelector('textarea'), text=input.value, button=form.querySelector('[type=submit]');button.disabled=true;
    try{await send(form.dataset.edit?'chat.message.edit':'chat.message.send',{channelId:channel,text,...(form.dataset.edit?{messageId:form.dataset.edit,revision:Number(form.dataset.revision)}:{})});drafts.delete(channel);delete form.dataset.edit;input.value='';await history(channel);}
    catch(error){services.toast(error.message);}finally{button.disabled=false;}
  });
  root.addEventListener('pointerdown',e=>{
    const header=e.target.closest('[data-drag]');if(!header||e.target.closest('button'))return;
    const node=header.closest('.dm-window'),w=windows.get(header.dataset.drag),r=node.getBoundingClientRect(),dx=e.clientX-r.left,dy=e.clientY-r.top;
    header.setPointerCapture(e.pointerId);node.style.zIndex=++serial+110;w.z=serial+110;
    header.onpointermove=event=>{w.x=Math.max(0,Math.min(innerWidth-r.width,event.clientX-dx));w.y=Math.max(0,Math.min(innerHeight-45,event.clientY-dy));Object.assign(node.style,{left:w.x+'px',top:w.y+'px',right:'auto',bottom:'auto'});};
    header.onpointerup=()=>{header.onpointermove=null;};
  });
}
function update(next){
  const who=next?location.pathname+':'+next.accountId:'';
  if(who!==identity){identity=who;serial++;windows.clear();drafts.clear();pages.clear();shown=pinned;minimized=false;channelGroup='room';if(root)root.innerHTML='';}
  const previous=state;state=next;if(!state)return;
  let changed=false;
  for(const channel of new Set([...pages.keys(),...drafts.keys(),...windows.keys()]))if(!state.channels[channel]){pages.delete(channel);drafts.delete(channel);windows.delete(channel);changed=true;}
  if(previous&&Object.keys(previous.channels).join()!==Object.keys(state.channels).join())changed=true;
  if(changed||(pinned&&!root.querySelector('.messenger')))render();
  if(root)for(const node of root.querySelectorAll('[data-unread-group]'))node.textContent=Object.values(state.channels).filter(c=>c.kind===node.dataset.unreadGroup).reduce((n,c)=>n+(c.unreadCount||0),0)||'';
  if(root)for(const node of root.querySelectorAll('[data-chat="select"]'))node.querySelector('b').textContent=state.channels[node.dataset.channel]?.unreadCount||'';
}
function mount(host){
  if(!root)return;const next=Boolean(host),changed=next!==pinned;pinned=next;
  (host||document.body).append(root);
  if(pinned){shown=true;minimized=false;}else if(changed)shown=false;
  if(changed||!root.querySelector('.messenger')&&shown)render();
  requestAnimationFrame(()=>{for(const node of root.querySelectorAll('.chat-history[data-at-bottom=true]'))node.scrollTop=node.scrollHeight;});
}
export const chatUI={configure,update,poll,mount,redraw:render,select(channel){if(!state?.channels[channel])return;selected=channel;channelGroup=state.channels[channel].kind;shown=true;minimized=false;render();},open(){shown=true;minimized=false;render();}};
