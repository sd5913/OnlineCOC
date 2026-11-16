import {chatUI} from './chat.js';
import {aiUI} from './ai.js';
import {embeddedAI} from './ai-embedded.js';
import {t, setLocale, locale, initLocale} from './i18n.js';
await initLocale(new URL('.',location.href));
const webMode=globalThis.stumpsvilleWeb;
const app = document.querySelector('#app');
const dialog = document.querySelector('#dialog');
// LAN pages use HTTP, where crypto.randomUUID/clipboard may be unavailable.
function newId(){
  const b=crypto.getRandomValues(new Uint8Array(16));b[6]=(b[6]&15)|64;b[8]=(b[8]&63)|128;
  const h=Array.from(b,x=>x.toString(16).padStart(2,'0')).join('');
  return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;
}
const pageId=newId();
const playerWindow=new URLSearchParams(location.search).get('view')==='player';
const statePath=()=> 'package/state?page='+pageId+(playerWindow?'&player=1':'')+'&locale='+encodeURIComponent(locale());
const base = new URL(webMode?'https://stumpsville.invalid/':'.', location.href);
let state = null;
let csrf = '';
let setup = null;
let dialogSubmit = null;
let selectedLocation = 1;
let currentChannel = 'general';
let history = [];
let nextBefore = null;
let creation = {step:0,preset:'mul',name:'木栗',swap:''};
let lastStage = '';
let dirtyForm = null;
let acceptedHash = location.hash;
let busy = false;
let lastFocus = null;
let connection = t('ui.m066');
let desktop = null, desktopAccount = '', consoleTab = 'control', selectedRequest = '', localAction = null, renderDeferred = false;
let executorBusy = false;
let roomVisitsOpen=false, mobileColumn='scene', logFilter='all';
const expandedLogs=new Map();
const fieldName=key=>t('field.'+String(key).toLowerCase(),{},key);
const displayValue=value=>typeof value==='boolean'?t(value?'state.yes':'state.no'):String(value??'—');
document.addEventListener('toggle',event=>{if(event.target.id==='room-visits')roomVisitsOpen=event.target.open;},true);
const playerNav = () => [['play/scene',t('ui.m005')]];
const gmNav = () => [['gm/room',t('nav.room')],['gm/rulings',t('nav.rulings')],['gm/map',t('nav.map')],['gm/console',t('ui.m001')],['gm/locations',t('ui.m002')],['gm/library',t('ui.m003')],['gm/session',t('ui.m004')]];
const icons = {weapon:'⚔',item:'◇',armor:'♧',condition:'✧',spell:'▤'};
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const number = value => Number(value);
const route = () => location.hash.replace(/^#\/?/,'') || 'lobby';
const button = (label, action, data = {}, style = '') => `<button type="button" class="${style}" data-action="${action}" data-args="${escape(JSON.stringify(data))}">${label}</button>`;
const link = (label, path) => `<a href="#/${path}">${label}</a>`;
const field = (label, name, value = '', type = 'text') => `<label>${label}<input name="${name}" type="${type}" value="${escape(value)}" ${type==='password'?'autocomplete="current-password"':''}></label>`;
const area = (label,name,value='') => `<label>${label}<textarea name="${name}">${escape(value)}</textarea></label>`;
const select = (label,name,options,value) => `<label>${label}<select name="${name}">${options.map(([key,text])=>`<option value="${escape(key)}" ${String(key)===String(value)?'selected':''}>${escape(text)}</option>`).join('')}</select></label>`;
const heading = (id,title,actions='') => `<div class="page-head"><div><div class="eyebrow">${id} · STUMPSVILLE</div><h1>${title}</h1></div><div class="actions">${actions}</div></div>`;
const panel = (title,body,kind='') => `<section class="panel ${kind}"><h2>${title}</h2>${body}</section>`;
const empty = text => `<div class="empty">${escape(text)}</div>`;
const actorOptions = () => (state.characters || [state.character].filter(Boolean)).map(x=>[x.instanceId,x.name]);
const pendingKey = () => 'stumpsville.pending.' + base.pathname + '.' + state.accountId;
const independentLogin = () => webMode?'':`<a class="account-link" href="/" target="_blank" rel="noopener">${t('account.new')}</a>`;
const rulingMode = () => select(t('ui.m077'),'ruling',[['auto',state.automation?.enabled?t('ui.m078'):t('ui.m080')],['manual',t('ui.m079')]],'auto');
function submitAction(kind,input,data){return data?.get('ruling')==='manual'?perform('request',{kind,input,manual:true,text:t('request.text',{kind:kind==='check'?t('ui.m051'):t('request.item')})}):perform(kind,input);}
function myRulings(){
  return panel('我的裁决申请',state.requests.filter(x=>x.account===state.accountId&&x.status!=='automatic').slice(-20).reverse().map(x=>`<article class="receipt"><strong>${escape(x.text||x.kind)}</strong><p>${{pending:'等待 KP 裁决',approved:'KP 已批准',rejected:'KP 已拒绝'}[x.status]||escape(x.status)} · ${escape(x.reason||'')}</p>${x.result?'<p>'+escape(resultText(x.result))+'</p>':''}</article>`).join('')||empty('没有待处理申请'));
}

async function api(path, body) {
  if(webMode){const data=await webMode.api(path==='package/action'?path+'?locale='+encodeURIComponent(locale()):path,body);if(data.status==='rejected'&&data.commandId)throw Object.assign(Error(data.code),{status:409});return data;}
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (csrf) headers['X-CSRF-Token'] = csrf;
  const response = await fetch(new URL(path==='package/action'?path+'?locale='+encodeURIComponent(locale()):path,base), {method:body===undefined?'GET':'POST',headers,body:body===undefined?undefined:JSON.stringify(body),credentials:'same-origin'});
  const data = await response.json();
  if (!response.ok || (data.status === 'rejected' && data.commandId)) {
    const messages={RULE_FAILED:t('error.rule_failed'),VERSION_CONFLICT:t('error.version_conflict'),NOT_VISIBLE:t('error.not_visible'),STALE_CATALOG:t('error.stale_catalog'),RATE_LIMITED:t('error.rate_limited'),ROOM_PAUSED:t('error.room_paused'),CSRF_REQUIRED:t('error.csrf_required')};
    const error = new Error(messages[data.code] || data.code || '请求失败');
    error.status = response.status;
    throw error;
  }
  return data;
}

function toast(message) {
  const element = document.querySelector('#toast');
  element.textContent = message;
  element.style.display = 'block';
  clearTimeout(toast.timer);
  toast.timer = setTimeout(()=>element.style.display='none',5000);
}

function resultText(result){
  if(!result||typeof result!=='object')return typeof result==='string'&&!/^[a-f0-9-]{24,}$/.test(result)?result:t('result.done');
  if(result.sceneAction)return [result.message,...(result.narrative||[])].filter(Boolean).join('\n');
  if(result.message)return result.message;
  if('channelId' in result)return t('result.chat');
  if('passed' in result)return t('result.check',{attribute:fieldName(result.attribute),rolled:result.rolled,target:result.target,outcome:t(result.passed?'ui.m085':'ui.m086')});
  if('damage' in result)return t('result.damage',{damage:result.damage,hp:result.hp})+(result.critical?' · '+t('state.critical'):'');
  if('round' in result)return t('scene.round',{count:result.round})+(result.encounterDue?' · '+t('result.encounterdue'):'');
  if('count' in result)return t('result.count',{count:result.count});
  if('entry' in result)return `${result.rolled} · ${result.entry}`;
  if('rolled' in result)return t('result.roll',{count:result.rolled});
  if('total' in result)return t('result.total',{count:result.total});
  if('ready' in result)return t(result.ready?'ui.m089':'ui.m090');
  if('operation' in result&&'slot' in result)return `${t('operation.'+result.operation,{},t('result.done'))} · ${t('field.slot',{count:result.slot})}${result.operation==='move'?' → '+result.target:result.operation==='use'?' · '+t('result.uses',{count:result.uses}):''}${result.overloaded?' · '+t('state.overloaded'):''}`;
  if('location' in result)return t('result.arrived',{place:state?.locations.find(p=>p.index===result.location)?.name||String(result.location)});
  if('uses' in result)return t('result.uses',{count:result.uses});
  return t('result.done');
}

async function refresh(render = true) {
  state = await api(statePath());
  connection = t('ui.m065');
  chatUI.update(state);
  if (render) renderPage();
}

async function perform(operation,args,existing) {
  if (busy) throw new Error(t('action.busy'));
  if(!existing && localStorage.getItem(pendingKey())) throw new Error(t('action.recoverfirst'));
  let webRules;
  busy = true;
  try{if(webMode){webRules=(await api('api/v1/view')).catalog.rulesetRevision;if(existing?._webRules&&existing._webRules!==webRules)throw Error('规则版本已变化，请联系KP核对待恢复行动。');}}
  catch(error){busy=false;throw error;}
  const body = existing ? {id:existing.id,operation:existing.operation,args:existing.args} : {id:newId(),operation,args};
  const key = pendingKey();
  localStorage.setItem(key,JSON.stringify(webMode?{...body,_webRules:webRules}:body));
  localAction = {status:'submitting',text:t('action.submitting')};
  updateActivity();
  try {
    if(webMode)await webMode.flush();
    const result = await api('package/action',body);
    localStorage.removeItem(key);
    dirtyForm = null;
    closeDialog();
    localAction = null;
    await refresh();
    toast(result.status==='processing'?t('action.queued'):resultText(result));
    return result;
  } catch(error) {
    localAction = {status:'error',text:error.message + (error.status>=400&&error.status<500?t('action.failed'):t('action.uncertain'))};
    updateActivity();
    toast(error.message);
    if (error.status === 400 || error.status === 403 || error.status === 409) localStorage.removeItem(key);
    throw error;
  } finally {
    busy = false;
  }
}

function openDialog(title,body,onSubmit,label=t('ui.m062'),id='S14') {
  lastFocus = document.activeElement;
  dialogSubmit = onSubmit;
  dialog.innerHTML = `<div class="dialog-head"><h2 id="dialog-title"><span class="eyebrow">${id}</span> ${title}</h2>${button(t('ui.m058'),'close',{},'quiet')}</div><form id="dialog-form"><div class="dialog-body">${body}<div class="dialog-actions">${button(t('ui.m061'),'close')}${onSubmit?`<button class="primary" type="submit">${label}</button>`:''}</div></div></form>`;
  if (!dialog.open) dialog.showModal();
}

function closeDialog() {
  if(dialog.querySelector('#player-ai-embedded'))embeddedAI.close();
  dialog.close();
  dialogSubmit = null;
  if (lastFocus?.isConnected) lastFocus.focus();
}

function statCards(character){
  const n=character.numbers;
  return `<div class="statgrid">${['str','dex','wil'].map(key=>`<div class="stat">${button(escape(fieldName(key)),'check',{attribute:key},'quiet')}<strong>${n[key]} / ${n[key+'Max']}</strong></div>`).join('')}</div><div class="row"><strong>${t('field.hp')} ${n.hp} / ${n.maxHp}</strong><span>${t('field.armor')} ${n.armor}</span><span>${t('field.pips')} ${n.pips}</span></div>`;
}

function roomActors(index) {
  return (state.characters||[]).map(actor=>({...actor,kind:'pc'}))
    .filter(actor=>actor.numbers.location===index);
}

function roomRoster(index, includeNpcs=false) {
  const actors=includeNpcs?[...roomActors(index),...(state.npcs||[]).filter(a=>a.numbers.location===index).map(a=>({...a,kind:'npc'}))]:roomActors(index);
  return `<div class="room-roster" data-room="${index}"><h3>${t('map.occupants',{count:actors.length})}</h3>${actors.length?`<ul>${actors.map(actor=>`<li><strong>${escape(actor.name)}</strong><span>${t('map.'+actor.kind)}${actor.kind==='pc'?' · '+escape(actor.owner):''}</span>${button(t('ui.m109'),'actor-edit',{id:actor.instanceId},'small')}</li>`).join('')}</ul>`:`<p class="muted">${t('map.empty')}</p>`}</div>`;
}

function playerContacts(){
  const contacts=state.mapContacts||[];
  return `<section class="player-map-contacts"><strong>${t('map.discovered')}</strong><ul>${contacts.map(a=>`<li>${escape(a.name)} <small>${t('map.'+a.kind)}${a.self?' · '+t('map.self'):''}</small></li>`).join('')||`<li>${t('map.empty')}</li>`}</ul></section>`;
}

function discoveryControls(index){
  const actors=[...(state.characters||[]).filter(a=>a.numbers.location===index).map(a=>({id:a.instanceId,name:a.name})),...(state.mapNpcCatalog||[]).filter(a=>a.location===index)];
  return `<section class="discovery-controls"><h3>${t('map.revealTitle')}</h3><p>${t('map.revealHint')}</p>${actors.map(a=>`<div class="row"><span>${escape(a.name)}</span>${button(t('map.reveal'),'actor-reveal',{id:a.id},'small')}</div>`).join('')}</section>`;
}

function roomPage(){
  return heading('P15',t('nav.room'),button(t('room.share'),'web-room',{},'primary'))+roomNetworkPanel();
}
function mapPage(){
  return heading('P16',t('nav.map'))+panel(t('ui.m105'),mapView(Object.values(state.allLocations),selectedLocation,true));
}
function messageQueue(){
  const channels=Object.values(state.channels).filter(c=>c.unreadCount>0);
  return channels.map(c=>`<button type="button" class="message-queue-item" data-action="chat-channel" data-args="${escape(JSON.stringify({channel:c.channelId}))}"><strong>${escape(c.name)}</strong><span class="tag">${c.unreadCount}</span></button>`).join('')||empty(t('ruling.noMessages'));
}
function rulingsPage(){
  return `<div class="rulings-grid"><div class="ruling-queues"><section class="panel message-queue"><h2>${t('ruling.messages')}</h2><div id="message-queue-list" class="ruling-scroll">${messageQueue()}</div></section><section class="panel ruling-work"><h2>${t('ruling.queue')}</h2><div class="ruling-scroll">${rulingQueue()}<div class="ruling-detail">${rulingDetail()}</div><details><summary>${t('ruling.history')}</summary>${activityFeed()}</details></div></section></div><section class="panel ruling-ai" aria-label="${t('ai.title')}"><div id="kp-ai-embedded"></div></section><aside id="chat-column" class="ruling-chat" aria-label="${t('chat.title')}"></aside></div>`;
}

function mapView(locations,current,rosters=false) {
  const positions={1:[90,280],2:[90,180],3:[270,180],4:[120,65],5:[290,65],6:[460,65],7:[460,180],8:[640,180],9:[640,280],10:[460,280]};
  const points=locations.map(l=>positions[l.index]);
  const minX=Math.min(...points.map(p=>p[0]))-85,minY=Math.min(...points.map(p=>p[1]))-65;
  const mapBox=`${minX} ${minY} ${Math.max(250,Math.max(...points.map(p=>p[0]))-minX+85)} ${Math.max(170,Math.max(...points.map(p=>p[1]))-minY+65)}`;
  const edges=locations.flatMap(x=>x.exits.filter(y=>y>x.index&&locations.some(l=>l.index===y)).map(y=>{
    const [x1,y1]=positions[x.index],[x2,y2]=positions[y];
    const door=state.doors?.[[x.index,y].sort((a,b)=>a-b).join('-')]||x.doors?.[String(y)]||'open';
    if(x.index===3&&y===8)return `<path d="M${x1} ${y1} C${x1} 255 ${x2} 255 ${x2} ${y2}" class="${door==='open'?'':'closed'}"/>`;
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="${door==='open'?'':'closed'}"/>`;
  })).join('');
  const action=rosters===true?'map-room':'location';
  const nodes=locations.map(x=>{const [left,top]=positions[x.index],show=rosters===true||rosters==='player'&&x.index===current,actors=rosters===true?roomActors(x.index):show?(state.mapContacts||[]):[],names=actors.map(a=>a.name).join('、'),count=t('map.occupants',{count:actors.length});return `<g role="button" tabindex="0" aria-label="${escape(x.name+(show?' · '+count+' · '+names:''))}" data-action="${action}" data-args="${escape(JSON.stringify({index:x.index}))}" class="${x.index===current?'current':''}" transform="translate(${left},${top})"><title>${escape(x.name+(show?' · '+count+' · '+names:''))}</title><rect x="-64" y="-24" width="128" height="${show?84:48}" rx="9"/><text text-anchor="middle"><tspan x="0" y="-6" class="map-index">${String(x.index).padStart(2,'0')}</tspan><tspan x="0" y="13" ${x.name.length>13?'textLength="112" lengthAdjust="spacingAndGlyphs"':''}>${escape(x.name)}</tspan>${show?`<tspan x="0" y="32" class="map-count">${count}</tspan><tspan x="0" y="49" class="map-names">${escape(names.length>11?names.slice(0,10)+'…':names||t('map.empty'))}</tspan>`:''}</text>${x.index===current?'<circle cx="57" cy="-20" r="6"/>':''}</g>`;}).join('');
  const selected=locations.find(x=>x.index===current)||locations[0];
  return `<div class="node-map ${rosters===true?'kp-map':''}"><svg viewBox="${locations.length?mapBox:'10 20 710 310'}" aria-label="${t('scene.maplabel')}">${edges}${nodes}</svg></div><div class="map compact-map">${locations.map(x=>button(`${String(x.index).padStart(2,'0')} ${escape(x.name)}${rosters===true?' · '+t('map.occupants',{count:roomActors(x.index).length}):rosters==='player'&&x.index===current?' · '+t('map.occupants',{count:state.mapContacts?.length||0}):''}`,action,{index:x.index},x.index===current?'current':'')).join('')}</div><p class="map-links">${t(rosters===true?'map.legend':'scene.legend')}</p>${rosters===true&&selected?`<section class="map-room-detail"><header><strong>${escape(selected.name)}</strong>${button(t('map.manage'),'location',{index:selected.index},'small')}</header>${roomRoster(selected.index)}</section>`:''}`;
}

function renderEntry() {
  if(webMode){app.innerHTML=empty('连接已断开，请在网页上方退出并重新连接房主。');return;}
  aiUI.update(null);embeddedAI.close();
  chatUI.mount(null);document.body.classList.remove('scene-workspace','rulings-workspace','player-ui','topbar-collapsed');
  app.innerHTML = `<section class="entry"><div class="entry-card"><div class="eyebrow">${t('entry.tagline')}</div><h1>${t('app.name')}</h1><div class="subtitle">STUMPSVILLE</div><p>${t('entry.intro')}</p><div class="notice">${setup?.canSetup?t('entry.setup'):t('entry.login')}</div><form id="entry-form">${setup?.canSetup?'':field(t('ui.m157'),'loginName','kp')}${field(setup?.canSetup?t('entry.password'):t('ui.m158'),'password','','password')}${setup?.canSetup?`<p class="muted">${t('entry.accounts')}</p>`:''}<button class="primary" type="submit">${setup?.canSetup?t('entry.prepare'):t('ui.m156')}</button><div id="entry-error" role="alert"></div></form><p>${independentLogin()}</p><p class="muted">${t('entry.sessions')}</p><p class="muted">Mausritter · OnlineCOC 配置包</p></div></section>`;
}

function renderPage() {
  if (!state) return renderEntry();
  const logScroll=document.querySelector('#action-feedback')?.scrollTop||0;
  const sceneScroll=document.querySelector('.scene-column')?.scrollTop||0;
  restoreDesktop();
  let path = route();
  const legacyPanels = {'play/character':'inventory','play/journal':'clues','play/records':'records'};
  if(legacyPanels[path]){
    if(state.role==='kp'){path='gm/rulings';}
    else {if(legacyPanels[path]!=='records'){desktop[legacyPanels[path]]={open:true,collapsed:false};desktop.front=legacyPanels[path];}else mobileColumn='log';saveDesktop();path='play/scene';}
    historyReplace('#/'+path);acceptedHash=location.hash;
  }
  if(['gm/overview','gm/encounters'].includes(path)){path=path==='gm/encounters'?'gm/rulings':'gm/console';historyReplace('#/'+path);acceptedHash=location.hash;}
  if(/^gm\/locations\/\d+$/.test(path)){selectedLocation=Number(path.split('/')[2]);path='gm/locations';}
  const gm = state.role === 'kp';
  aiUI.update(state,gm,locale());
  if(gm&&(!path.startsWith('gm/'))){path='gm/console';historyReplace('#/'+path);}
  const navigation = gm ? gmNav() : [...playerNav(),['lobby',t('ui.m033')],['recap',t('ui.m034')]];
  const workspace=!gm&&path==='play/scene';
  document.body.classList.toggle('scene-workspace',workspace);
  document.body.classList.toggle('rulings-workspace',gm&&path==='gm/rulings');
  document.body.classList.toggle('player-ui',!gm);
  const pending = localStorage.getItem(pendingKey());
  const folded=localStorage.getItem('sv.desktop.topbar.'+base.pathname+'.'+state.accountId)==='1';
  document.body.classList.toggle('topbar-collapsed',folded);
  app.innerHTML = `<header class="topbar"><div class="brand"><span class="brand-symbol">♧</span><span>${t('app.name')}<small>STUMPSVILLE</small></span></div>${!gm?`<nav class="top-nav" aria-label="${t('nav.main')}">${navigation.map(([url,label])=>`<a href="#/${url}" class="${path===url?'active':''}">${label}</a>`).join('')}</nav>`:''}<div class="toptools"><span class="identity">${gm?t('ui.m015'):t('ui.m016')} · ${escape(state.accountId)}</span><span class="tag" id="connection">${connection}</span>${state.canManage?`<a class="account-link" target="_blank" rel="noopener" href="${base.pathname}${gm?'?view=player#/play/scene':'#/gm/console'}">${gm?t('ui.m017'):t('ui.m018')}</a>`:''}${gm?'':button(t('ai.title'),'ai-assistant',{},'quiet')}${button(t('ui.m011'),'rules',{},'quiet')}${button(t('ui.m012'),'preferences',{},'quiet')}${button(t('ui.m013'),'logout',{},'quiet')}${select(t('ui.m014'),'locale',[['zh-CN','简体中文'],['en','English']],locale())}</div><button class="topbar-toggle quiet" data-action="topbar-toggle" aria-expanded="${!folded}" aria-label="${t(folded?'nav.expandTop':'nav.collapseTop')}" title="${t(folded?'nav.expandTop':'nav.collapseTop')}">${folded?t('nav.expandTop')+' ▾':'▴'}</button></header>${pending?`<div class="pendingbar">${t('status.pendingcommand')} ${button(t('action.recover'),'recover',{},'small')}</div>`:''}<div class="shell ${gm?'':'player-shell'}">${gm?`<nav class="sidebar" aria-label="${t('nav.main')}">${navigation.map(([url,label])=>`<a href="#/${url}" class="${path.startsWith(url)?'active':''}">${label}</a>`).join('')}</nav>`:''}<main id="main"></main></div>`;
  const main = document.querySelector('#main');
  if (!state.initialized) {
    chatUI.mount(null);main.innerHTML = heading('准备',t('ui.m073')) + panel(t('ui.m074'),gm?button(t('ui.m075'),'initialize',{},'primary'):empty(t('ui.m076')));
    return;
  }
  if (path.startsWith('gm/') && !gm) {
    main.innerHTML = heading('S16',t('ui.m068')) + empty(t('ui.m069'));
    return;
  }
  const routes = {
    'lobby':lobbyPage,'character/new':creationPage,'ready':readyPage,
    'play/scene':workspacePage,'gm/console':consolePage,'gm/locations':locationsPage,
    'gm/room':roomPage,'gm/rulings':rulingsPage,'gm/map':mapPage,
    'gm/library':libraryPage,'gm/session':sessionPage,'recap':recapPage
  };
  main.innerHTML = (routes[path] || (()=>heading('S16',t('ui.m070'))+link(t('ui.m071'),'lobby')))();
  chatUI.update(state);
  chatUI.mount(workspace||path==='gm/rulings'?document.querySelector('#chat-column'):null);
  embeddedAI.mount(path==='gm/rulings'?document.querySelector('#kp-ai-embedded'):null,{base,manager:gm,account:state.accountId,onReview:()=>aiUI.open({base,manager:gm,language:locale()})});
  updateActivity();
  if(workspace){document.querySelector('#action-feedback').scrollTop=logScroll;document.querySelector('.scene-column').scrollTop=sceneScroll;}
}

function lobbyPage() {
  const character = state.character;
  return heading('P02',t('ui.m033'),state.role==='kp'?button(t('ui.m035'),'navigate',{path:'gm/console'},'primary'):'')+
    `<div class="grid2">${panel(t('ui.m038'),character?`<img class="portrait" src="art/mouse.png" alt="小鼠冒险者"><h2>${escape(character.name)}</h2>${statCards(character)}${button(t('ui.m040'),'navigate',{path:'ready'},'primary')}`:empty(t('ui.m037')))}${panel(t('ui.m039'),`<p>${t('lobby.intro')}</p>${state.draft?`<div class="notice">${t('lobby.draft')} · ${escape(state.draft.name)} · ${t('state.'+state.draft.status)}<br>${escape(state.draft.reason||'')}</div>`:''}${!character?button(t('ui.m036'),'navigate',{path:'character/new'},'primary'):''}<p class="muted">${t('lobby.ready')}</p>`)}</div>`;
}

function creationPage() {
  const preset=creation.preset==='random'?state.generatedCharacter:state.presets.find(x=>x.id===creation.preset);
  const steps=[t('create.identity'),t('dialog.attribute'),t('create.equipment'),t('ui.m062')];
  let body='';
  if(creation.step===0) body=`<div class="grid2">${state.presets.map(p=>`<article class="preset"><img src="art/mouse.png" alt=""><h3>${escape(p.name)}</h3><p>${escape(p.description)}</p>${button(t('create.preset'),'choose-preset',{preset:p.id,name:p.name},'primary')}</article>`).join('')}</div><p>${t('create.explanation')}</p>${button(t('create.random'),'create-roll',{},'primary')}`;
  if(creation.step===1) body=`<form id="creation-form">${field(t('create.name'),'name',creation.name)}<p>${fieldName('str')} ${preset?.str} · ${fieldName('dex')} ${preset?.dex} · ${fieldName('wil')} ${preset?.wil} · ${fieldName('hp')} ${preset?.hp} · ${preset?.pips}p</p>${creation.preset==='random'?select(t('create.swap'),'swap',[['',t('create.noswap')],['str-dex',fieldName('str')+' ↔ '+fieldName('dex')],['str-wil',fieldName('str')+' ↔ '+fieldName('wil')],['dex-wil',fieldName('dex')+' ↔ '+fieldName('wil')]],creation.swap):''}<button class="primary">${t('create.nextequipment')}</button></form>`;
  if(creation.step===2) body=`<p>${t('create.starting')}</p><div class="notice">${t('create.background')}</div>${button(t('create.nextconfirm'),'create-next',{},'primary')}`;
  if(creation.step===3) body=`<h3>${escape(creation.name)}</h3><p>${t('create.source')} · ${creation.preset==='random'?t('create.randomsource'):t('create.presetsource')}; ${t('create.swapped')} · ${escape(creation.swap?creation.swap.split('-').map(fieldName).join(' ↔ '):t('create.none'))}</p><p>${t('create.help')}</p>${button(t('create.submit'),'create-submit',{},'primary')}`;
  return heading('P03',t('ui.m032'))+panel(steps.map((x,i)=>`${i+1}. ${x}`).join(' → '),body+`<div class="divider"></div>${creation.step?button(t('create.back'),'create-back'):''}`);
}

function readyPage() {
  const c=state.character;
  if (!c) return heading('P04',t('ui.m041'))+empty(t('ready.wait'));
  const started=state.session?.numbers.phase===1;
  return heading('P04',t('ui.m041'))+panel(escape(c.name),`${statCards(c)}<p>${t('ready.check')}</p><div class="actions">${button(c.numbers.ready?t('ui.m043'):t('ui.m042'),'ready',{ready:!c.numbers.ready},'primary')}${button(t('ui.m044'),'navigate',{path:'play/character'})}${started&&c.numbers.ready?button(t('ui.m045'),'navigate',{path:'play/scene'},'primary'):''}</div><p class="muted">${started?t('ready.started'):t('ready.notstarted')}</p>`);
}

function scenePage(){
  const c=state.character;
  if(!c)return `<div class="scene-empty">${empty(t('scene.nocharacter'))}${link(t('ui.m033'),'lobby')}</div>`;
  if(!c.numbers.ready||state.session?.numbers.phase!==1)return `<div class="scene-empty">${empty(t('ui.m041'))}${link(t('ui.m040'),'ready')}</div>`;
  const place=state.locations.find(x=>x.index===c.numbers.location);
  if(!place)return empty(t('scene.unpublished'));
  return `<header class="scene-heading"><div><small>${t('scene.current')}</small><h1>${String(place.index).padStart(2,'0')} ${escape(place.name)}</h1></div><span class="tag">${t('scene.round',{count:state.session?.numbers.round||0})}</span></header><p class="scene-description">${escape(place.description)}</p><div class="scene-map-area">${mapView(state.locations,place.index,'player')}${playerContacts()}</div><div class="available-actions"><header><h2>${t('scene.actions')}</h2><span class="tag">${state.automation.enabled?t('ui.m078'):t('ui.m091')}</span></header><div class="preset-actions">${sceneButtons(place)}</div><div class="travel-actions">${place.exits.map(index=>button(t('scene.go',{place:escape(state.locations.find(x=>x.index===index)?.name||String(index))}),'travel',{destination:index},'small')).join('')}</div><div class="generic-actions">${button(t('ui.m051'),'check',{},'primary')}${button(t('ui.m049'),'request',{kind:'free'})}${button(t('ui.m050'),'review')}</div></div>${sceneStatusPanel()}`;
}

function inventoryCards(c) {
  const n=c.numbers;
  const covered={};
  for(let slot=1;slot<=10;slot++){
    const def=state.items[String(n['item'+slot])];
    if(!def) continue;
    let cells=[slot];
      if(def.slots===2) cells=[slot,slot+1];
    if(def.slots===4) cells=[slot,slot+1,slot+3,slot+4];
    cells.slice(1).forEach(index=>covered[index]=slot);
  }
  let coins=Math.ceil(Math.max(0,n.pips-250)/250);
  for(let slot=10;slot>=1;slot--){if(coins&&!covered[slot]&&!n['item'+slot]){covered[slot]=-1;coins--;}}
  const card=slot=>{
    const index=n['item'+slot],def=state.items[String(index)];
    if(covered[slot]) return `<div class="slot occupied"><span class="number">${slot}</span><span>${covered[slot]===-1?t('inventory.coins'):t('inventory.occupied')}</span></div>`;
    if(!def) return `<div class="slot"><span class="number">${slot}</span><span class="muted">${t('inventory.empty')}</span></div>`;
    return `<button class="slot occupied" data-action="item" data-args="${escape(JSON.stringify({slot}))}"><span class="number">${slot}</span><span class="item-icon">${icons[def.kind]||'◇'}</span><strong>${escape(def.name)}</strong><span class="uses">${def.uses?'■'.repeat(n['uses'+slot])+'□'.repeat(Math.max(0,def.uses-n['uses'+slot])):''}</span></button>`;
  };
  return `<div class="inventory"><section class="slotgroup"><h3>${t('inventory.hands')}</h3><div class="slots vertical">${[1,2].map(card).join('')}</div></section><section class="slotgroup"><h3>${t('inventory.body')}</h3><div class="slots vertical">${[3,4].map(card).join('')}</div></section><section class="slotgroup"><h3>${t('inventory.pack')}</h3><div class="slots">${[5,6,7,8,9,10].map(card).join('')}</div></section></div><h3 style="margin-top:24px">${t('inventory.overflow')}</h3><div class="overflow">${Array.from({length:10},(_,i)=>i+11).filter(i=>n['item'+i]).map(card).join('')||`<p class="muted">${t('inventory.nooverflow')}</p>`}</div>`;
}

function charactersTable() {
  return `<table><thead><tr><th>角色</th><th>资源</th><th>状态</th><th>管理</th></tr></thead><tbody>${state.characters.map(c=>`<tr><td><strong>${escape(c.name)}</strong><br><small>${escape(c.owner)}</small></td><td>${fieldName('hp')} ${c.numbers.hp}/${c.numbers.maxHp}<br>${fieldName('str')} ${c.numbers.str} · ${fieldName('dex')} ${c.numbers.dex} · ${fieldName('wil')} ${c.numbers.wil}</td><td>${c.numbers.ready?t('ui.m089'):t('ui.m090')}<br>地点 ${c.numbers.location}</td><td>${button(t('ui.m109'),'actor-edit',{id:c.instanceId},'small')}${button(t('ui.m110'),'grant',{actor:c.instanceId},'small')}${button(t('ui.m111'),'rest',{actor:c.instanceId},'small')}</td></tr>`).join('')}</tbody></table>`;
}

function locationsPage() {
  const place=state.allLocations[String(selectedLocation)]||Object.values(state.allLocations)[0];
  const doors=place.exits.map(x=>{const edge=[place.index,x].sort((a,b)=>a-b).join('-');return button(`通往 ${x} · ${{open:'开启',closed:t('ui.m058'),locked:'锁住'}[state.doors[edge]]}`,'door',{edge});}).join('');
  const stock=place.stock.map(x=>`<div class="row"><span>${escape(state.items[String(x.item)]?.name)} × ${x.count}</span>${x.count?button('领取','take-stock',{index:place.index,item:x.item},'small'):''}</div>`).join('');
  return heading('P10',t('ui.m128'),button(t('ui.m127'),'preview',{index:place.index}))+`<div class="layout-aside"><div>${panel(`${place.index} ${escape(place.name)}`,`<form id="location-form"><input type="hidden" name="index" value="${place.index}"><input type="hidden" name="revision" value="${place.revision||0}"><div class="grid2"><div>${area('公开描述','description',place.description)}</div><div>${area('KP 主持真相','truth',place.truth)}</div></div><div class="actions"><button class="primary">保存草稿</button>${button(t('ui.m126'),'publish',{index:place.index})}</div></form><h3>通路与门</h3><div class="actions">${doors}</div><h3>库存</h3>${stock||'<p class="muted">无固定物品</p>'}${place.index===4?button('首次生成铜锅盘','generate',{kind:'pots'}):''}${place.index===7?button('首次生成鼠帮人数','generate',{kind:'rats'}):''}${roomRoster(place.index,true)}${discoveryControls(place.index)}`,'private')}</div><aside>${panel('地点索引',`<div class="stack">${Object.values(state.allLocations).map(x=>button(`${String(x.index).padStart(2,'0')} ${escape(x.name)}`,'select-location',{index:x.index},x.index===place.index?'primary':'')).join('')}</div>`)}</aside></div>`;
}

function libraryPage() {
  return heading('P12',t('ui.m129'),button(t('ui.m131'),'export'))+panel(t('ui.m130'),`<p>${escape(state.sourceStatus)}</p><div class="actions">${button(t('ui.m132'),'stage',{},'primary')}${button(t('ui.m133'),'install')}${button(t('ui.m134'),'rules')}${button(t('ui.m135'),'tables')}</div>`)+panel(t('ui.m136'),state.ruleRevisions.map(r=>`<div class="receipt"><code>${escape(r)}</code> ${r===state.catalog.rulesetRevision?'<span class="tag">当前</span>':''}<div class="actions">${button(t('ui.m137'),'rules-preview',{revision:r})}${button(t('ui.m138'),'rules-activate',{revision:r})}</div></div>`).join(''))+panel(t('ui.m139'),`<div class="grid3">${Object.entries(state.items).map(([index,item])=>`<article class="receipt"><h3>${icons[item.kind]||'◇'} ${escape(item.name)}</h3><p>${escape(item.description)}</p><small>${item.slots} 槽 · ${item.uses} 格用量</small></article>`).join('')}</div>`)+panel(t('ui.m140'),state.encounters.map((x,i)=>`<p>${i+1} · ${escape(x)}</p>`).join(''));
}

function sessionPage() {
  return heading('P13',t('ui.m141'))+panel(t('ui.m142'),`<p>房间状态 · ${t('state.'+state.roomStatus)}</p>${button(t('ui.m143'),'backup',{},'primary')}<p class="muted">账号密码通过本机账号工具维护。回合、角色审核、自动裁决与暂停控制统一在主持控制台。</p>${link(t('ui.m144'),'gm/console')}`)+panel(t('ui.m034'),`<form id="recap-form">${area('拟公开回顾','recapDraft',state.recapDraft)}${area('KP 私密备注','recapPrivate',state.recapPrivate)}<label><input type="checkbox" name="publish">同时发布公开回顾</label><button class="primary">保存回顾</button></form>`);
}

function recapPage() {
  return heading('P14',t('ui.m034'))+panel(t('ui.m145'),`<p style="white-space:pre-wrap">${escape(state.recap||t('recap.empty'))}</p>${mapView(state.locations,state.character?.numbers.location)}<div class="actions">${state.roomStatus==='active'&&state.session.numbers.phase===1?button(t('ui.m096'),'navigate',{path:state.role==='kp'?'gm/console':'play/scene'},'primary'):`<span class="tag">${t('recap.wait')}</span>`}${button(t('ui.m071'),'navigate',{path:'lobby'})}</div>`);
}

async function rawCommand(op,args) {
  return {result:await perform('chat',{operation:op,input:args})};
}

const paneNames = () => ({status:t('ui.m006'),inventory:t('ui.m007'),clues:t('ui.m008')});
function desktopKey(){return 'sv.desktop.'+base.pathname+'.'+state.accountId;}
function restoreDesktop(){
  const key=desktopKey();
  if(desktopAccount===key)return;
  desktopAccount=key;
  try{desktop=JSON.parse(localStorage.getItem(key)||'{}');}catch{desktop={};}
  for(const name of Object.keys(paneNames()))desktop[name]??={open:false,collapsed:false};
  desktop.front??='status';desktop.seen??=[];
  localAction=null;
}
function saveDesktop(){localStorage.setItem(desktopKey(),JSON.stringify(desktop));}
function unreadEvents(){return (state.events||[]).filter(e=>!desktop.seen.includes(e.account+':'+e.id)).length;}
function unreadMessages(){return Object.values(state.channels||{}).reduce((n,c)=>n+(c.unreadCount||0),0);}
function markEventsRead(){desktop.seen=(state.events||[]).map(e=>e.account+':'+e.id);saveDesktop();}
function sceneButtons(place){
  if(!state.sceneAutomation?.ready)return `<p class="notice">${t('scene.rulesmissing')}</p>`;
  return (!state.sceneAutomation.executorOnline?`<p class="notice">${t('scene.executoroffline')}</p>`:'')+(state.autoSceneTasks?.length?`<p class="notice">${t('scene.queued')}</p>`:'')+(state.sceneActions||[]).map(a=>button(escape(a.label),'scene-action',{id:a.id})).join('');
}
function sceneStatusPanel(){
  const data=state.sceneStatus||{};if(!data.facts?.length&&!data.supplies?.length)return '';
  return panel(t('ui.m054'),`<div class="scene-facts">${(data.facts||[]).map(f=>`<p><strong>${escape(f.label)}</strong> · ${escape(f.value)}</p>`).join('')}${(data.supplies||[]).map(x=>`<p>${escape(x.name)} · ${t('result.remaining',{count:x.count})}</p>`).join('')}</div>`);
}
function diceBlock(r){return `<div class="dice-result ${r.passed?'passed':'failed'}"><strong>${r.rolled}</strong><span>${escape(fieldName(r.attribute))} ≤ ${r.target}<br>${t(r.passed?'ui.m085':'ui.m086')} · ${t('mode.'+(r.mode||'normal'))}</span></div><small>${t('result.dice',{first:r.first,second:r.second?' / '+r.second:'',rolled:r.rolled})}</small>`;}
function sceneValue(key,value){
  if(['trapState','gateTrap'].includes(key))return t(['state.untreated','state.disarmed','state.triggered'][value]);
  if(['gateOpen','hallDoor','ironOpen','caveOpen'].includes(key))return t(value?'state.open':'state.closed');
  if(key==='villagersFreed')return t(value?'state.freed':'state.trapped');
  if(key==='ernieAwake')return t(value?'state.awake':'state.asleep');
  if(['spidersAlert','ratsAlert','snakeAlert'].includes(key))return t(value?'state.alert':'state.calm');
  const quantities=['ratsCount','cheese1','moneyRemaining','idolRemaining','potsRemaining','fluteRemaining','paddleRemaining','clothRemaining','cheese10'];
  return typeof value==='number'&&!quantities.includes(key)?t(value?'state.yes':'state.no'):displayValue(value);
}
function sceneResult(result){
  if(!result?.sceneAction)return '';
  return `<div class="scene-result"><p class="muted">${escape(result.process)}</p>${(result.checks||[]).map(r=>`<div class="scene-check"><strong>${escape(r.label)}</strong>${diceBlock(r)}</div>`).join('')}${result.rolls?.length?`<ul class="scene-rolls">${result.rolls.map(r=>`<li>${escape(r.label)} · d${r.sides} → <b>${r.value}</b></li>`).join('')}</ul>`:''}<ol class="scene-narrative">${(result.narrative||[]).map(line=>`<li>${escape(line)}</li>`).join('')}</ol>${result.stateChanges?.length?`<h4>${t('log.scenechanges')}</h4><ul class="change-list">${result.stateChanges.map(c=>`<li><span>${escape(c.label.replace(/（0待处理[^）]*）/,''))}</span><span><del>${escape(sceneValue(c.key,c.before))}</del> <b>→ ${escape(sceneValue(c.key,c.after))}</b></span></li>`).join('')}</ul>`:''}${result.clues?.length?`<p class="notice">${t('log.clues')} ${result.clues.map(c=>escape(c.title)).join(' / ')}</p>`:''}</div>`;
}
function eventCard(e,compact=false){
  const waiting=['pending','processing'].includes(e.status),denied=e.status==='rejected';
  const label=t(e.status==='processing'?'ui.m095':waiting?'ui.m091':denied?'ui.m093':e.result?.outcome==='blocked'?'state.blocked':e.status==='approved'?'state.approved':'ui.m092');
  const r=e.result&&typeof e.result==='object'?e.result:{};
  const changes=(e.changes||[]).map(c=>`<li><span>${escape(c.key.startsWith('slot')?t('field.slot',{count:Number(c.key.slice(4))}):fieldName(c.key))}</span><span><del>${escape(['ready','incapacitated'].includes(c.key)?t(c.before?'state.yes':'state.no'):displayValue(c.before))}</del> <b>→ ${escape(['ready','incapacitated'].includes(c.key)?t(c.after?'state.yes':'state.no'):displayValue(c.after))}</b></span></li>`).join('');
  return `<article class="event-card ${waiting?'waiting':denied?'denied':''}" data-event-id="${escape(e.id)}"><div class="event-head"><strong>${escape(e.title)}</strong><span class="tag">${label}</span></div><small class="muted">${new Date(e.time*1000).toLocaleString(locale())} · ${t(e.mode==='kp'?'log.keeper':'ui.m078')}${state.role==='kp'?' · '+escape(e.account):''}</small>${compact?'':`<p class="action-steps">${t('log.submitted')} → ${t(e.mode==='kp'?'log.keeper':'log.rules')} → ${label}</p>`}${e.text&&!compact?'<p>'+escape(e.text)+'</p>':''}${sceneResult(r)||('passed' in r?diceBlock(r):`<p>${escape(waiting?t('log.waiting'):denied?t('log.rejected'):resultText(r))}</p>`)}${e.reason?`<p class="ruling-reason">${t(waiting?'log.reason':'log.ruling')}：${escape(e.reason)}</p>`:''}${changes?`<ul class="change-list">${changes}</ul>`:!waiting?`<p class="muted">${t('log.nochanges')}</p>`:''}${!compact&&state.character&&e.receiptId?button(t('ui.m119'),'review',{receiptId:e.receiptId,text:t('log.review',{title:e.title})},'small quiet'):''}</article>`;
}
function activityFeed(){
  const events=(state.events||[]).slice().reverse();
  return `<div class="activity-feed">${events.map(e=>eventCard(e)).join('')||empty('还没有行动记录。提交行动后，过程和变化会保存在这里。')}</div>`;
}
function logEntry(e,index){
  const key=e.account+':'+e.id;
  const waiting=['pending','processing'].includes(e.status);
  const label=waiting?t(e.status==='processing'?'ui.m095':'ui.m091'):e.status==='rejected'?t('ui.m093'):t('ui.m092');
  const open=expandedLogs.has(key)?expandedLogs.get(key):index===0;
  return `<details class="log-entry ${waiting?'waiting':''}" data-log="${escape(key)}" ${open?'open':''}><summary><time>${new Date(e.time*1000).toLocaleTimeString(locale(),{hour:'2-digit',minute:'2-digit'})}</time><strong>${escape(e.title)}</strong><span class="tag">${label}</span></summary><div class="log-details">${eventCard(e,true)}<div class="log-actions">${e.receiptId?button(t('ui.m119'),'review',{receiptId:e.receiptId,text:t('log.review',{title:e.title})},'quiet small'):''}${e.receiptId&&['check','inventory','ready'].includes(state.receipts.find(r=>r.id===e.receiptId)?.operation)?button(t('log.share'),'share',{id:e.receiptId},'quiet small'):''}</div></div></details>`;
}
function updateActivity(){
  const target=document.querySelector('#action-feedback');if(!target||!state)return;
  const events=(state.events||[]).slice().reverse().filter(e=>logFilter==='all'||(logFilter==='pending'?['pending','processing'].includes(e.status):e.result?.checks?.length||e.result?.rolled!==undefined));
  const fingerprint=JSON.stringify([events,localAction,logFilter,locale()]);
  if(target.dataset.content===fingerprint)return;
  target.dataset.content=fingerprint;
  const top=target.scrollTop;
  target.innerHTML=`${localAction?`<p class="notice ${localAction.status==='error'?'error':''}">${escape(localAction.text)}</p>`:''}${events.map(logEntry).join('')||empty(t('log.empty'))}`;
  target.scrollTop=top;
}
document.addEventListener('click',event=>{const summary=event.target.closest('details[data-log]>summary');if(summary){const entry=summary.parentElement;expandedLogs.set(entry.dataset.log,!entry.open);}},true);
function paneContent(name){
  const c=state.character;
  if(name==='status')return c?`<div class="character-mini"><img src="art/mouse.png" alt=""><div><h3>${escape(c.name)}</h3><p>${t('field.level')} ${c.numbers.level} · ${t('field.xp')} ${c.numbers.xp} · ${t('field.grit')} ${c.numbers.grit}</p><span class="tag">${c.numbers.incapacitated?t('state.incapacitated'):t('state.able')}</span></div></div>${statCards(c)}<p>${t('field.light')}：${c.numbers.litSlot?t('light.slot',{count:c.numbers.litSlot}):t('light.off')}</p>`:empty(t('ui.m072'));
  if(name==='inventory')return c?inventoryCards(c):empty(t('ui.m072'));
  if(name==='clues'){
    const clues=state.locations.flatMap(p=>p.clues.map(c=>({...c,place:p.name})));
    return field(t('ui.m116'),'clue-search')+(clues.map(c=>`<article class="receipt clue"><h3>${escape(c.title)}</h3><small>${escape(c.place)}</small><p>${escape(c.text)}</p></article>`).join('')||empty(t('clues.empty')))+`<form id="note-form">${area(t('ui.m117'),'text',state.note)}<button class="primary">${t('clues.save')}</button></form>`;
  }
  return '';
}
function floatingPanel(name){
  const p=desktop[name];if(!p.open)return '';
  return `<section class="floating-panel pane-${name} ${p.collapsed?'collapsed':''} ${desktop.front===name?'front':''}" aria-label="${t('panel.label',{name:paneNames()[name]})}"><header class="floating-head">${button(paneNames()[name],'pane-front',{name},'pane-title quiet')}<div>${button(p.collapsed?t('ui.m059'):t('ui.m060'),'pane-collapse',{name},'small quiet')}${button(t('ui.m058'),'pane-close',{name},'small quiet')}</div></header><div class="floating-body" ${p.collapsed?'hidden':''}>${p.collapsed?'':paneContent(name)}</div></section>`;
}
function workspacePage(){
  return `<div class="workspace-toolbar"><div class="character-tools">${Object.entries(paneNames()).map(([name,label])=>button(label,'pane-toggle',{name},desktop[name].open?'primary small':'small')).join('')}</div><nav class="workspace-tabs" aria-label="${t('nav.workspace')}">${[['scene',t('ui.m005')],['log',t('ui.m009')],['chat',t('chat.title')]].map(([column,label])=>button(label,'workspace-column',{column},mobileColumn===column?'primary small':'small')).join('')}</nav><span class="workspace-identity">${escape(state.character?.name||'')} ${state.character?`${t('field.hp')} ${state.character.numbers.hp}/${state.character.numbers.maxHp}`:''}</span></div><div id="scene-desktop" data-column="${mobileColumn}"><section class="scene-column workspace-column" aria-label="${t('scene.mapactions')}">${scenePage()}</section><section class="log-column workspace-column" aria-label="${t('ui.m009')}"><header class="column-head"><h2>${t('ui.m009')}</h2>${select(t('log.filter'),'log-filter',[['all',t('log.all')],['pending',t('log.pending')],['checks',t('ui.m051')]],logFilter)}</header><section id="action-feedback" aria-live="polite"></section></section><section id="chat-column" class="workspace-column" aria-label="${t('chat.title')}"></section></div><div class="desktop-panels">${Object.keys(paneNames()).map(floatingPanel).join('')}</div>`;
}
function requestDescription(r){
  const a=r.args.input||r.args;
  const kind={scene:'场景预设',travel:'移动',check:'检定',inventory:t('request.item'),transfer:'转交',review:'复核',free:t('ui.m049'),interact:'场景互动'}[r.kind]||r.kind;
  const detail=r.kind==='scene'?((state.sceneDefinitions||[]).find(x=>x.id===a.action)?.choices.find(c=>c.id===a.choice)?.label||a.choice):r.kind==='check'?`${fieldName(a.attribute)} · ${{normal:t('ui.m082'),advantage:t('ui.m083'),disadvantage:t('ui.m084')}[a.mode]||''}`:r.kind==='inventory'?`${{move:'移动',use:'使用',light:t('ui.m121'),extinguish:t('ui.m122')}[a.operation]||a.operation} · 槽位 ${a.slot}${a.operation==='move'?' → '+a.value:''}`:r.kind==='travel'?'前往 '+(state.allLocations?.[String(a.destination)]?.name||a.destination):r.kind==='transfer'?`槽位 ${a.slot} → ${state.team.find(t=>t.account===a.targetAccount)?.name||a.targetAccount} 的槽位 ${a.destination}`:'';
  return `${kind}${detail?' · '+detail:''}`;
}
function rulingQueue(){
  return state.requests.filter(r=>r.status==='pending').map(r=>`<article class="queue-item ${selectedRequest===r.id?'selected':''}"><small>${escape(r.account)} · ${new Date(r.time*1000).toLocaleTimeString()}</small><strong>${escape(requestDescription(r))}</strong><p>${escape(r.text||'等待主持处理')}</p>${button(t('ui.m097'),'console-request',{id:r.id},'primary small')}</article>`).join('')||empty(t('ui.m108'));
}
function rulingDetail(){
  const r=state.requests.find(r=>r.id===selectedRequest)||state.requests.find(r=>r.status==='pending');
  if(!r)return empty('玩家提交行动申请后，可在这里查看上下文并裁决。');
  selectedRequest=r.id;
  const actor=state.characters.find(c=>c.instanceId===r.actor);
  return `<h3>${escape(requestDescription(r))}</h3><p>${escape(r.account)} · ${escape(actor?.name||'角色')} · ${escape(state.allLocations[String(r.location)]?.name||'')}</p><blockquote>${escape(r.text||'')}</blockquote><p>转交原因：${escape(r.reason||'玩家申请')}</p>${actor?`<p>当前资源：${fieldName('hp')} ${actor.numbers.hp}/${actor.numbers.maxHp} · ${fieldName('str')} ${actor.numbers.str} / ${fieldName('dex')} ${actor.numbers.dex} / ${fieldName('wil')} ${actor.numbers.wil}</p>`:''}${r.status==='pending'?`<form id="ruling-form"><input type="hidden" name="requestId" value="${escape(r.id)}">${select(t('ui.m101'),'approve',[['yes',t('ui.m099')],['no',t('ui.m100')]],'yes')}${area(t('ui.m102'),'reason')}<p class="muted">${['check','inventory','travel','transfer','scene'].includes(r.kind)?'批准后执行规则，结算结果与资源变化会送达相关玩家。':'此类申请记录主持回复，数值影响请使用控制台工具另行结算。'}</p><button class="primary" type="submit">保存裁决并通知玩家</button></form>`:`<span class="tag">${r.status==='approved'?'已批准':t('ui.m093')}</span><p>${escape(r.reason||'未附说明')}</p>`}`;
}
function roomNetworkPanel(){
  const n=state.network;
  if(!n)return '';
  const rows=n.players.map(p=>`<tr><td>${escape(p.name)}<br><small>${escape(p.accountId)} · ${p.role==='kp'?'KP':p.role==='player'?'PL':'旁观'}</small></td><td>${escape(p.character||'尚未建角')}</td><td><span class="tag">${{online:t('ui.m153'),stale:t('ui.m155'),offline:t('ui.m154')}[p.status]}</span></td><td>${p.pages}</td><td>${p.ips.map(escape).join('、')||'—'}</td><td>${p.lastSeen?new Date(p.lastSeen*1000).toLocaleTimeString():'本次启动尚未连接'}</td></tr>`).join('');
  const visits=n.visits.slice(-8).reverse().map(v=>`<li>${new Date(v.time*1000).toLocaleTimeString()} · ${escape(v.ip)}${v.local?'（本机）':''} · ${escape(v.kind)} · HTTP ${v.status}</li>`).join('');
  return `<section class="panel room-network" id="room-network"><h2>房间信息与连线玩家</h2><p><strong>树桩镇 ${escape(n.version)}</strong> · 房间 ${escape(state.roomId)} · ${{active:'运行中',paused:'已暂停',archived:'已归档'}[state.roomStatus]} · ${n.players.filter(p=>p.role==='player'&&p.status==='online').length} 位玩家在线</p><label>玩家连接地址<input id="room-url" readonly value="${escape(n.url)}"></label><div class="actions">${button(t('ui.m055'),'copy-room-address',{},'small')}<span>监听 ${escape(n.bind)}:${n.port} · 本次启动 ${new Date(n.startedAt*1000).toLocaleString()}</span></div>${n.bind==='127.0.0.1'?'<p class="notice">当前仅本机可访问。局域网游玩请用 start-lan.cmd 启动并选择 Wi-Fi 网卡。</p>':''}<p class="muted">朋友只需浏览器打开完整地址并登录自己的账号。在线按最近30秒的页面心跳判断，关闭页面后会延迟变为失联／离线；多个页面合并到同一账号。</p><table aria-label="连线玩家"><thead><tr><th>账号／身份</th><th>角色</th><th>连接状态</th><th>在线页面</th><th>来源 IP</th><th>最后心跳</th></tr></thead><tbody>${rows}</tbody></table><details id="room-visits" ${roomVisitsOpen?'open':''}><summary>最近访问与连接排查</summary><p>看不到朋友的访问记录时，请在局域网启动窗口点击“检查连接 / 启动问题”，核对地址、端口、防火墙和 Wi-Fi 设备隔离。本机可以打开页面，不代表其他设备一定可达。</p><ul>${visits||'<li>本次启动尚无页面／登录访问记录。</li>'}</ul><small>仅记录最近60次页面、登录及异常请求；此记录不是在线人数，不保存密码或令牌。</small></details></section>`;
}
function consolePage(){
  const pending=state.requests.filter(r=>r.status==='pending').length;
  const drafts=Object.values(state.drafts).filter(d=>d.status==='submitted');
  const controls=`<div class="console-controls"><div><small>探索时钟</small><strong>第 ${state.session?.numbers.round||0} 回合</strong></div><div class="actions">${button(t('ui.m025'),'start',{},'primary')}${button(t('ui.m026'),'round')}${button(state.roomStatus==='paused'?t('ui.m028'):t('ui.m027'),'room',{status:state.roomStatus==='paused'?'active':'paused'})}${button(state.automation.enabled?t('ui.m029'):t('ui.m030'),'automation-console')}</div></div>`;
  let content='';
  content=`<div class="console-columns"><div>${panel(t('ui.m103'),charactersTable())}${panel(t('ui.m104'),`<div class="actions">${button('掷遭遇检查','generate',{kind:'encounter'})}${button('抽取遭遇内容','generate',{kind:'encounter-table'})}${button('反应骰','generate',{kind:'reaction'})}${button('战利品骰','generate',{kind:'loot'})}${button('角色伤害','damage')}${button('创建生物','npc-create')}</div>${(state.npcs||[]).map(n=>`<div class="row"><span>${escape(n.name)} · ${fieldName('hp')} ${n.numbers.hp}/${n.numbers.maxHp}</span><div>${button(t('ui.m112'),'damage',{actor:n.instanceId},'small')}${button(t('ui.m113'),'morale',{actor:n.instanceId},'small')}${button(t('ui.m109'),'actor-edit',{id:n.instanceId},'small')}</div></div>`).join('')}`)}</div><aside>${panel('建角审核 · '+drafts.length,drafts.map(d=>`<article class="receipt"><strong>${escape(d.name)} · ${escape(d.account)}</strong><p>${fieldName('str')} ${d.str} / ${fieldName('dex')} ${d.dex} / ${fieldName('wil')} ${d.wil} · ${fieldName('hp')} ${d.hp}</p>${button(t('ui.m114'),'approve',{account:d.account},'primary small')}${button(t('ui.m115'),'reject',{account:d.account},'small')}</article>`).join('')||empty(t('ui.m107')))}</aside></div>`;
  return heading('P09',t('ui.m019'))+`<section class="kp-console">${controls}<div class="console-content">${content}</div></section>`;
}

function updateRoomNetwork(){
  const panel=document.querySelector('#room-network');
  if(!panel||panel.contains(document.activeElement))return;
  const template=document.createElement('template');template.innerHTML=roomNetworkPanel();
  if(template.content.firstElementChild)panel.replaceWith(template.content.firstElementChild);
}

function changePane(name,change){
  if(dirtyForm){toast('请先保存正在编辑的内容，再切换面板。');return;}
  Object.assign(desktop[name],change);desktop.front=name;saveDesktop();renderPage();
}

const actions = {
  'topbar-toggle':()=>{const folded=document.body.classList.toggle('topbar-collapsed');localStorage.setItem('sv.desktop.topbar.'+base.pathname+'.'+state.accountId,folded?'1':'0');const b=document.querySelector('.topbar-toggle');b.setAttribute('aria-expanded',String(!folded));b.setAttribute('aria-label',t(folded?'nav.expandTop':'nav.collapseTop'));b.title=t(folded?'nav.expandTop':'nav.collapseTop');b.textContent=folded?t('nav.expandTop')+' ▾':'▴';},
  'chat-channel':({channel})=>chatUI.select(channel),
  'actor-reveal':({id})=>openDialog(t('map.revealTitle'),select(t('map.revealState'),'visible',[['yes',t('map.show')],['no',t('map.hide')]],'yes')+state.characters.map(a=>`<label><input type="checkbox" name="account" value="${escape(a.owner)}" ${state.actorDiscoveries?.[a.owner]?.[id]?'checked':''}>${escape(a.name)} · ${escape(a.owner)}</label>`).join(''),data=>perform('actor.reveal',{id,visible:data.get('visible')==='yes',accounts:data.getAll('account')})),
  'workspace-column':({column})=>{mobileColumn=column;document.querySelector('#scene-desktop').dataset.column=column;document.querySelectorAll('.workspace-tabs button').forEach(b=>b.classList.toggle('primary',JSON.parse(b.dataset.args).column===column));},
  'web-room':async()=>{
    const w=await api('package/web/status');
    const failure=`<p><strong>${escape(w.error||'请使用 start-web.cmd 启动网页分享。')}</strong></p>${w.hint?`<p>${escape(w.hint)}</p><p>本机游戏与存档仍可正常使用。</p>`:''}${w.errorCode?`<p class="muted">${escape(w.stage)} · ${escape(w.errorCode)}</p>`:''}${w.logPath?`<p class="muted" style="overflow-wrap:anywhere">日志：${escape(w.logPath)}</p>`:''}`;
    const platform=w.url?new URL(w.url).origin:'';
    const setup=w.creationString&&w.claimExpiresAt*1000>Date.now()?`<label>${t('web.setup')}<textarea id="web-setup" readonly>${escape(w.creationString)}</textarea></label>${button(t('web.copySetup'),'copy-web-setup')}<p class="muted">${t('web.setupHint')}</p>`:w.claim?`<p class="notice">${t('web.expired')}</p>`:`<p>${t('web.claimed')}</p>`;
    openDialog('网页分享',w.running?`<div class="actions"><a href="${escape(platform+'/create')}" target="_blank" rel="noopener">${t('web.create')}</a><a href="${escape(platform+'/manage')}" target="_blank" rel="noopener">${t('web.manage')}</a><a href="${escape(platform+'/join')}" target="_blank" rel="noopener">${t('web.join')}</a></div>${field('房间代号（分享给玩家）','room-code',w.roomCode)}${setup}<p>玩家使用平台账号及游戏账号两次登录。保持本机KP管理台在线。</p>`:failure,w.running?async()=>{await api('package/web/stop',{});closeDialog();toast('网页分享已停止，游戏宿主继续运行。');}:null,'停止网页分享');
  },
  'copy-web-setup':async()=>{const input=document.querySelector('#web-setup');try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(input.value);return toast(t('web.copied'));}}catch{}input.focus();input.select();toast(document.execCommand('copy')?t('web.copied'):t('web.selectCopy'));},
  'ai-assistant':()=>{if(state.role==='kp'){location.hash='/gm/rulings';return;}openDialog(t('ai.title'),'<div id="player-ai-embedded"></div>',null,'','AI');embeddedAI.mount(document.querySelector('#player-ai-embedded'),{base,account:state.accountId});},
  'open-chat':()=>chatUI.open(),
  'copy-room-address':async()=>{
    const input=document.querySelector('#room-url');
    try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(input.value);return toast('玩家地址已复制');}}catch{}
    input.focus();input.select();
    toast(document.execCommand('copy')?'玩家地址已复制':'请复制已选中的玩家地址');
  },
  'scene-action':({id})=>{
    const a=state.sceneActions.find(x=>x.id===id);
    openDialog(a.label,`<p>${escape(a.hint)}</p>${select(t('scene.choose'),'scene-choice',a.choices.map(c=>[c.id,c.label]),a.choices[0].id)}<div id="scene-process" class="notice">${escape(a.choices[0].process)}</div>${select(t('ui.m077'),'ruling',[['auto',t('scene.auto')],['manual',t('ui.m079')]],'auto')}`,data=>perform('scene.action',{action:id,choice:data.get('scene-choice'),manual:data.get('ruling')==='manual'}),t('scene.execute'),'S18');
    dialog.dataset.sceneAction=id;
  },
  'pane-toggle':({name})=>changePane(name,{open:desktop.front!==name||desktop[name].collapsed?true:!desktop[name].open,collapsed:false}),
  'pane-close':({name})=>changePane(name,{open:false}),
  'pane-collapse':({name})=>changePane(name,{collapsed:!desktop[name].collapsed}),
  'pane-front':({name})=>{desktop.front=name;saveDesktop();document.querySelectorAll('.floating-panel').forEach(p=>p.classList.toggle('front',p.classList.contains('pane-'+name)));},
  'panes-hide':()=>{if(dirtyForm)return toast('请先保存正在编辑的内容。');for(const name of Object.keys(paneNames()))desktop[name].open=false;saveDesktop();renderPage();},
  'events-read':()=>{markEventsRead();renderPage();},
  'console-tab':({tab})=>{if(dirtyForm)return toast('请先保存当前表单。');location.hash=tab==='control'?'/gm/console':'/gm/rulings';renderPage();},
  'console-request':({id})=>{if(dirtyForm)return toast('请先完成当前裁决。');selectedRequest=id;location.hash='/gm/rulings';renderPage();},
  'automation-console':()=>actions.automation({enabled:!state.automation.enabled}),
  close:closeDialog,
  navigate:({path})=>{location.hash='/'+path;},
  initialize:()=>perform('initialize',{}),
  recover:()=>{const body=JSON.parse(localStorage.getItem(pendingKey())); return perform(body.operation,body.args,body);},
  logout:async()=>{await api('api/v1/logout',{});state=null;chatUI.update(null);csrf='';history=[];closeDialog();location.hash='/entry';renderEntry();},
  draft:args=>openDialog('为小鼠取个名字',field('名字','name',args.name),data=>perform('draft',{preset:args.preset,name:data.get('name')}),t('create.submit'),'P03'),
  'choose-preset':args=>{creation={...args,step:1,swap:''};renderPage();},
  'create-roll':async()=>{await perform('draft.roll',{});creation={step:1,preset:'random',name:'',swap:''};renderPage();},
  'create-next':()=>{creation.step++;renderPage();},
  'create-back':()=>{creation.step--;renderPage();},
  'create-submit':async()=>{await perform('draft',{preset:creation.preset,name:creation.name,swap:creation.swap});location.hash='/ready';},
  ready:args=>perform('ready',args),
  check:args=>openDialog(t('ui.m051'),select(t('dialog.attribute'),'attribute',[['str',fieldName('str')],['dex',fieldName('dex')],['wil',fieldName('wil')]],args.attribute||'dex')+select(t('dialog.mode'),'mode',[['normal',t('ui.m082')],['advantage',t('ui.m083')],['disadvantage',t('ui.m084')]],'normal')+rulingMode(),data=>submitAction('check',{attribute:data.get('attribute'),mode:data.get('mode')},data),t('ui.m081'),'S02'),
  request:args=>openDialog(t('dialog.request'),area(t('dialog.intent'),'text',args.text||''),data=>perform('request',{kind:args.kind||'free',text:data.get('text')}),t('dialog.submitrequest'),'S10'),
  travel:args=>openDialog(t('dialog.travel'),`<p>${t('dialog.travelhelp')}</p>`+rulingMode(),data=>perform('request',{kind:'travel',destination:args.destination,manual:data.get('ruling')==='manual',text:t('travel.text',{count:args.destination})}),t('dialog.move'),'S07'),
  automation:args=>openDialog('自动裁决设置',`<p>${args.enabled?'开启后，规则明确的行动由系统直接结算。':'关闭后，检定、物品操作与移动将进入主持队列。'}已有申请仍等待主持处理。</p>`,()=>perform('automation.configure',args),'保存设置','S14'),
  review:args=>openDialog(t('ui.m050'),area(t('dialog.reviewtext'),'text',args.text||'')+`<p class="muted">${args.receiptId?t('dialog.reviewlinked'):t('dialog.reviewhelp')}</p>`,data=>perform('request',{kind:'review',text:data.get('text'),...(args.receiptId?{receiptId:args.receiptId}:{})}),t('dialog.submitreview'),'S10'),
  'map-room':args=>{selectedLocation=args.index;renderPage();},
  location:args=>{if(state.role==='kp'){selectedLocation=args.index;location.hash='/gm/locations/'+args.index;renderPage();}else{const p=state.locations.find(x=>x.index===args.index);openDialog(p.name,'<p>'+escape(p.description)+'</p>',null,'','S07');}},
  'select-location':args=>{selectedLocation=args.index;location.hash='/gm/locations/'+args.index;renderPage();},
  start:()=>perform('world',{operation:'start',round:state.session.numbers.round}),
  round:()=>openDialog('推进一个探索回合',`<p>当前为第 ${state.session.numbers.round} 回合。确认后同步更新所有角色的燃烧计时。</p>`,()=>perform('world',{operation:'round',round:state.session.numbers.round}),'推进一次','S12'),
  generate:args=>perform('generate',args),
  approve:args=>perform('approve',args),
  reject:args=>openDialog('退回角色草稿',area('修改建议','reason'),data=>perform('approve',{...args,reject:true,reason:data.get('reason')}),'退回','S10'),
  resolve:args=>{const request=state.requests.find(x=>x.id===args.id);openDialog('主持裁定','<p>'+escape(request.text||request.kind)+'</p><p>'+escape(request.reason||'')+'</p>'+(request.kind==='review'?'<p>复核只记录裁定说明，必要的数值修正请另用主持管理工具执行。</p>':'')+select('决定','approve',[['yes',t('ui.m099')],['no',t('ui.m100')]],'yes')+area('裁定依据','reason'),data=>perform('resolve',{requestId:args.id,approve:data.get('approve')==='yes',reason:data.get('reason')}),'保存裁定','S10');},
  publish:args=>{const p=state.allLocations[String(args.index)];const old=state.published[String(args.index)];openDialog(t('ui.m126'),`<span class="tag">受众 · 房间成员</span><h3>${escape(p.name)}</h3><div class="grid2"><div><h3>当前公开</h3><p>${escape(old?.description||'尚未发布')}</p></div><div><h3>拟发布</h3><p>${escape(p.description)}</p></div></div>${p.clues.map(x=>`<label><input type="checkbox" name="clue" value="${escape(x.id)}" ${old?.clues.some(c=>c.id===x.id)?'checked':''}> ${escape(x.title)}<br>${escape(x.text)}</label>`).join('')}<p class="muted">仅发布已保存的描述和勾选线索，主持真相保持私密。</p>`,data=>perform('location.publish',{...args,clues:data.getAll('clue')}),'公开此地点','S08');},
  preview:async args=>{const account=state.members.find(x=>x.role==='player')?.accountId;if(!account)return toast('房间内还没有玩家');const data=await api('package/state?preview='+encodeURIComponent(account));openDialog('玩家公开预览',`<div class="notice">只读 · ${escape(account)} · 包侧公开投影</div>${mapView(data.locations,1)}<p>${escape(data.locations.find(x=>x.index===args.index)?.description||'该地点尚未公开')}</p>`,null,'','S09');},
  damage:args=>openDialog('伤害与豁免',select('目标','actor',[...actorOptions(),...(state.npcs||[]).map(x=>[x.instanceId,x.name])],args.actor)+field('伤害骰最终值（减甲前）','amount',1,'number')+select('溢出扣减属性','attribute',[['str',fieldName('str')],['dex',fieldName('dex')]],'str'),data=>perform('damage',{actor:data.get('actor'),amount:number(data.get('amount')),attribute:data.get('attribute')}),'确认结算','S11'),
  grant:args=>openDialog(t('ui.m110'),select('物品','item',Object.entries(state.items).map(([id,x])=>[id,x.name]),1)+field('起始槽位（1–10，超载11–20）','slot',5,'number'),data=>{const item=number(data.get('item'));return perform('grant',{actor:args.actor,item,slot:number(data.get('slot')),uses:state.items[String(item)].uses});},'授予','S01'),
  rest:args=>openDialog('主持确认休息',select('休息类型','kind',[['short','短休 · 一探索轮'],['long','长休 · 吃饭与睡眠'],['full','完整休整 · 安全地一周']],'short')+select('长休时若 HP 已满，恢复哪项属性','attribute',[['str',fieldName('str')],['dex',fieldName('dex')],['wil',fieldName('wil')]],'str')+'<p class="muted">确认食物、水、照料及安全条件；恢复不自动推进时间，请另行推进探索轮。</p>',data=>perform('rest',{actor:args.actor,kind:data.get('kind'),attribute:data.get('attribute')}),'执行恢复','S03'),
  'actor-edit':args=>{const c=[...(state.characters||[]),...(state.npcs||[])].find(x=>x.instanceId===args.id);openDialog('主持数值调整',select('字段','key',[['hp',fieldName('hp')],['str',fieldName('str')],['dex',fieldName('dex')],['wil',fieldName('wil')],['armor','护甲'],['pips','钱币'],['xp',fieldName('xp')],['level','等级'],['grit',fieldName('grit')]],'hp')+field('新的数值','value',c.numbers.hp,'number'),data=>perform('actor.update',{id:args.id,numbers:{[data.get('key')]:number(data.get('value'))}}),t('ui.m063'),'S14');},
  room:args=>openDialog('确认房间状态','<p>将房间设为 '+escape(args.status==='paused'?'暂停':'运行')+'。</p>',()=>perform('room',args),t('ui.m062'),'S14'),
  backup:()=>openDialog(t('ui.m143'),'<p>保存宿主房间备份与包侧手记、草稿和请求记录。</p>',()=>perform('backup',{}),'创建备份','S14'),
  rules:()=>openDialog(t('rules.title'),state.rules.map(x=>`<h3>${escape(x.title)}</h3><p>${escape(x.text)}</p><a href="${escape(x.source)}" target="_blank" rel="noreferrer">${t('rules.source')}</a>`).join('<hr>'),null,'','S13'),
  preferences:()=>openDialog(t('ui.m146'),select(t('ui.m147'),'font',[['16',t('ui.m148')],['18',t('ui.m149')],['20',t('ui.m150')]],localStorage.getItem('sv.font')||'16')+`<label><input type="checkbox" name="reduce">${t('preferences.reduce')}</label><p>${t('preferences.help')}</p><p>${independentLogin()}</p>`,data=>{localStorage.setItem('sv.font',data.get('font'));document.documentElement.style.fontSize=data.get('font')+'px';document.body.classList.toggle('reduce-motion',data.has('reduce'));closeDialog();},t('ui.m063'),'S17'),
  export:async()=>{const data=await api('package/bundle');const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='stumpsville-bundle.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);},
  item:({slot})=>{const n=state.character.numbers;const def=state.items[String(n['item'+slot])];openDialog(def.name,`<p>${escape(def.description)}</p><p>${t('inventory.details',{slots:def.slots,uses:n['uses'+slot],max:def.uses})}</p><div class="actions">${def.uses&&def.kind!=='spell'?button(t('ui.m120'),'use',{slot}):''}${def.kind==='spell'?button(t('spell.request'),'request',{kind:'free',text:t('spell.text',{name:def.name})}):''}${def.light?button(n.litSlot===slot?t('ui.m122'):t('ui.m121'),'light',{slot,operation:n.litSlot===slot?'extinguish':'light'}):''}${button(t('ui.m123'),'move-item',{slot})}${button(t('ui.m124'),'transfer',{slot})}</div>`,null,'','S01');},
  use:({slot})=>openDialog(t('inventory.use'),`<p>${t('inventory.usehelp')}</p>`+rulingMode(),data=>submitAction('inventory',{operation:'use',slot,value:0},data),t('inventory.confirmuse'),'S03'),
  light:({slot,operation})=>perform('inventory',{operation,slot,value:0}),
  'move-item':({slot})=>openDialog(t('inventory.move'),field(t('inventory.destination'),'value',5,'number')+rulingMode(),data=>submitAction('inventory',{operation:'move',slot,value:number(data.get('value'))},data),'移动','S04'),
  transfer:({slot})=>openDialog(t('inventory.transfer'),select(t('inventory.receiver'),'targetAccount',state.team.filter(x=>x.account!==state.accountId).map(x=>[x.account,x.name]))+field(t('inventory.receiverslot'),'destination',5,'number'),data=>perform('request',{kind:'transfer',slot,targetAccount:data.get('targetAccount'),destination:number(data.get('destination')),text:t('transfer.text',{count:slot})}),t('inventory.submit'),'S05'),
  share:({id})=>{const receipt=state.receipts.find(x=>x.id===id);openDialog(t('share.title'),`<p>${escape(resultText(receipt.result))}</p>`+select(t('share.channel'),'channelId',Object.values(state.channels).filter(x=>x.canPost).map(x=>[x.channelId,x.name]),currentChannel)+`<p class="muted">${t('share.help')}</p>`,data=>perform('share.receipt',{receiptId:id,channelId:data.get('channelId')}),t('share.submit'),'S06');},
  'channel-create':()=>openDialog(t('ui.m024'),field('频道名称','name')+select('范围','kind',[['room','公共'],['group','分组']],'room')+state.members.filter(x=>x.accountId!==state.accountId).map(x=>`<label><input type="checkbox" name="member" value="${escape(x.accountId)}"> ${escape(x.nickname)}</label>`).join(''),data=>rawCommand('chat.channel.create',{name:data.get('name'),kind:data.get('kind'),...(data.get('kind')==='group'?{participants:[state.accountId,...data.getAll('member')]}:{})}),'创建','S06'),
  'door':args=>openDialog('通路状态',select('门或通路','status',[['open','开启'],['closed',t('ui.m058')],['locked','锁住']],state.doors[args.edge]),data=>perform('door',{edge:args.edge,status:data.get('status')}),t('ui.m063'),'S14'),
  'take-stock':args=>openDialog('从地点领取',select('接收角色','actor',state.characters.filter(x=>x.numbers.location===args.index).map(x=>[x.instanceId,x.name]))+field('放入槽位','slot',7,'number'),data=>perform('stock.take',{...args,actor:data.get('actor'),slot:number(data.get('slot'))}),'确认领取','S01'),
  morale:args=>perform('morale',args),
  'npc-create':()=>openDialog('新建主持生物',field('名称','name')+['str','dex','wil','hp','armor','location'].map((x,i)=>field(fieldName(x),x,[9,9,9,3,0,1][i],'number')).join('')+'<p class="muted">默认是SRD通用小鼠，专属角色请按原版输入。</p>',data=>perform('npc.create',{name:data.get('name'),numbers:Object.fromEntries(['str','dex','wil','hp','armor','location'].map(x=>[x,number(data.get(x))]))}),'创建','S10'),
  'tables':()=>openDialog('主持随机表',area('d6 遭遇内容（每行一项，共6行）','encounters',state.encounters.join('\n'))+area('d20 战利品（每行一项，共20行）','loot',state.loot.join('\n')),data=>perform('tables.save',{encounters:data.get('encounters').split('\n'),loot:data.get('loot').split('\n')}),t('ui.m063'),'S14'),
  'stage':()=>openDialog('导入与检查','<label>选择导出的配置包 JSON<input type="file" id="bundle-file" accept=".json"></label><p>检查不会激活规则；通过后可在隔离快照预览。</p>',async()=>{const f=document.querySelector('#bundle-file').files[0];if(!f)throw new Error('请选择 JSON 文件');if(f.size>131072)throw new Error('配置文件超过本机接口限制');const data=JSON.parse(await f.text());const result=await perform('rules.stage',{bundle:data});lastStage=result.revision;renderPage();},'检查暂存','S14'),
  'rules-preview':({revision})=>openDialog(t('ui.m137'),select(t('ui.m011'),'rule',[['sv.layout','物品栏布局'],['sv.check',t('ui.m051')]],'sv.layout')+select('角色','actor',actorOptions()),async data=>{const rule=data.get('rule');const input={actor:data.get('actor'),...(rule==='sv.check'?{attribute:'dex',mode:'normal'}:{})};const result=await perform('rules.preview',{revision,rule,input});openDialog('预览结果','<pre>'+escape(JSON.stringify(result,null,2))+'</pre>',null,'','S14');},'运行预览','S14'),
  'rules-activate':args=>openDialog('激活 / 回退修订','<p>将使用修订 '+escape(args.revision)+'。已有角色数值不会自动迁移。</p>',()=>perform('rules.activate',args),'确认激活','S14'),

};

document.addEventListener('click',async event=>{
  const target=event.target.closest('[data-action]');
  if(!target)return;
  const action=actions[target.dataset.action];
  if(!action)return;
  target.disabled=true;
  try { await action(JSON.parse(target.dataset.args||'{}')); }
  catch(error){toast(error.message);}
  finally { if(target.isConnected)target.disabled=false; }
});
document.addEventListener('change',async event=>{
  if(event.target.name==='locale'){if(dirtyForm){event.target.value=locale();toast(t('status.savefirst'));return;}await setLocale(event.target.value);connection=t('ui.m065');await refresh();chatUI.redraw();}
  if(event.target.name==='log-filter'){logFilter=event.target.value;updateActivity();}
  if(event.target.name==='scene-choice'){
    const a=state.sceneActions.find(x=>x.id===dialog.dataset.sceneAction);
    document.querySelector('#scene-process').textContent=a.choices.find(c=>c.id===event.target.value).process;
  }
});
document.addEventListener('input',event=>{
  const form=event.target.closest('form');
  if(form&&['note-form','location-form','recap-form','creation-form','ruling-form'].includes(form.id))dirtyForm=form.id;
  if(event.target.name==='clue-search'){const q=event.target.value.toLocaleLowerCase();document.querySelectorAll('.clue').forEach(x=>x.hidden=!x.textContent.toLocaleLowerCase().includes(q));}
});
document.addEventListener('keydown',event=>{if(event.target.matches('g[role=button]')&&['Enter',' '].includes(event.key)){event.preventDefault();event.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));}});
document.addEventListener('submit',async event=>{
  if(event.target.closest('#chat-layer'))return;
  event.preventDefault();
  const form=event.target,data=new FormData(form);
  const submit=form.querySelector('[type=submit],button:not([type])');
  if(submit)submit.disabled=true;
  try{
    if(form.id==='entry-form'){
      if(setup.canSetup){await api('setup',{password:data.get('password')});setup=await api('setup/status');renderEntry();toast('准备完成，请登录');}
      else{const me=await api('api/v1/login',Object.fromEntries(data));csrf=me.csrf;await refresh(false);location.hash='/lobby';renderPage();}
    }else if(form.id==='dialog-form'&&dialogSubmit){await dialogSubmit(data);}
    else if(form.id==='creation-form'){creation.name=data.get('name');creation.swap=data.get('swap')||'';creation.step=2;renderPage();}
    else if(form.id==='note-form'){await perform('note',{text:data.get('text')});}
    else if(form.id==='ruling-form'){await perform('resolve',{requestId:data.get('requestId'),approve:data.get('approve')==='yes',reason:data.get('reason')});}
    else if(form.id==='location-form'){await perform('location.save',{index:number(data.get('index')),revision:number(data.get('revision')),description:data.get('description'),truth:data.get('truth')});}
    else if(form.id==='recap-form'){await perform('recap',{recapDraft:data.get('recapDraft'),recapPrivate:data.get('recapPrivate'),publish:data.has('publish')});}

  }catch(error){const target=document.querySelector('#entry-error');if(target)target.textContent=error.message;toast(error.message);}
  finally{if(submit?.isConnected)submit.disabled=false;}
});
window.addEventListener('hashchange',()=>{
  if(dirtyForm){
    const target=location.hash;
    historyReplace(acceptedHash);
    openDialog('尚有未保存的修改','<p>取消可返回继续编辑；放弃后前往目标页面。</p>',()=>{dirtyForm=null;closeDialog();location.hash=target;},'放弃修改并离开','S14');
    return;
  }
  acceptedHash=location.hash;closeDialog();renderPage();window.scrollTo(0,0);
});
function historyReplace(hash){if(webMode){if(location.hash!==hash)location.hash=hash;return;}window.history.replaceState(null,'',location.pathname+location.search+hash);}
window.addEventListener('beforeunload',event=>{if(dirtyForm){event.preventDefault();event.returnValue='';}});
dialog.addEventListener('cancel',()=>{dialogSubmit=null;});
document.documentElement.style.fontSize=(localStorage.getItem('sv.font')||'16')+'px';
async function boot(){
  try{
    setup=await api('setup/status');
    if(setup.ready){try{const me=await api('api/v1/me');csrf=me.csrf;await refresh(false);}catch{state=null;}}
    renderPage();
  }catch(error){app.innerHTML=empty('连接失败 · '+error.message);}
}
async function runAutoScenes(){
  if(!state||state.role!=='kp'||!state.initialized||executorBusy||busy)return;
  executorBusy=true;
  try{
    const ready=await api('package/scene-executor',{});
    for(const job of ready.jobs){
      await api('package/action',{id:job.commandId,operation:'scene.autorun',args:{jobId:job.id}});
      renderDeferred=true;
    }
  }catch(error){
    const label=document.querySelector('#connection');
    if(label)label.textContent='自动执行暂缓 · '+error.message;
  }finally{executorBusy=false;}
}
chatUI.configure({api,send:rawCommand,toast,t});
if(!webMode&&base.pathname==='/'){
  const bytes=crypto.getRandomValues(new Uint8Array(12));
  const slot='tab-'+Array.from(bytes,x=>x.toString(16).padStart(2,'0')).join('');
  location.replace('/sessions/'+slot+'/'+location.hash);
}else await boot();
setInterval(async()=>{
  if(!state||busy)return;
  try{
    const next=await api(statePath());
    const visual=value=>{const {network,channels,...rest}=value;return JSON.stringify(rest);};
    const changed=visual(next)!==visual(state);
    state=next;chatUI.update(state);connection=t('ui.m065');
    const editing=['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)&&!document.activeElement?.readOnly;
    if(changed)renderDeferred=true;
    if(renderDeferred&&!editing&&!dialog.open&&!dirtyForm){renderDeferred=false;renderPage();}
    else if(changed){updateActivity();}
    updateRoomNetwork();
    const queue=document.querySelector('#message-queue-list');if(queue)queue.innerHTML=messageQueue();
    const chatBadge=document.querySelector('.chat-badge');if(chatBadge)chatBadge.textContent=unreadMessages()||'';
    await chatUI.poll();
    await runAutoScenes();
    const label=document.querySelector('#connection');if(label)label.textContent=t('ui.m065');
  }catch(error){
    chatUI.update(null);aiUI.update(null);embeddedAI.close();
    connection=t('ui.m067');
    const label=document.querySelector('#connection');if(label)label.textContent=connection;
    if(error.status===401){state=null;chatUI.update(null);csrf='';history=[];closeDialog();renderEntry();}
  }
},2500);

