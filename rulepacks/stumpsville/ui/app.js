import {rulingCard,mountRulingTimeline} from './ruling-card.js';
import {explainAIError} from './ai-recovery.js';
import {batchDetailsHTML} from './batch-details.js';
import {characterStatsHTML,itemDetailsHTML,renderPackageReference} from './reference-view.js';
import {chatUI} from './chat.js';
import {diceUI} from './dice.js';
import {effectsUI} from './effects.js';
import {mapPositions,mapRoutes,mapRoutePath} from './map.js';
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
let executorBusy = false, aiQueuePending=0, rulingPane='queue', queueTab='rulings';
let statePollRunning=false,lastStatePoll=0,stateGeneration=0;
let chatPollRunning=null,chatPollAgain=false,lastChatPoll=0,chatGeneration=0;
let chatCursor=null,channelSnapshot=0;
const chatSending=new Set();
const replyOpen=new Set();
let libraryCache=null,libraryLoading=false,libraryError='',libraryTab='configurations',libraryQuery='',libraryType='';
const libraryKey=()=>JSON.stringify([state?.accountId,state?.storageScope,state?.catalog?.revision,state?.catalog?.rulesetRevision]);
let roomVisitsOpen=false, mobileColumn='scene', logFilter='all', notebookDrag=null;
const expandedLogs=new Map();
const fieldName=key=>t('field.'+String(key).toLowerCase(),{},key);
const displayValue=value=>typeof value==='boolean'?t(value?'state.yes':'state.no'):String(value??'—');
document.addEventListener('toggle',event=>{if(event.target.id==='room-visits')roomVisitsOpen=event.target.open;if(event.target.dataset.rulingReply){if(event.target.open)replyOpen.add(event.target.dataset.rulingReply);else replyOpen.delete(event.target.dataset.rulingReply);}},true);
const playerNav = () => [['play/scene',t('ui.m005')]];
const gmNav = () => [['gm/room',t('nav.room')],['gm/rulings',t('nav.rulings')],['gm/map',t('nav.map')],['gm/console',t('ui.m001')],['gm/locations',t('ui.m002')],['gm/library',t('ui.m003')],['gm/session',t('ui.m004')],['gm/ai-settings','AI 设置']];
const icons = {weapon:'⚔',item:'◇',armor:'♧',condition:'✧',spell:'▤'};
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const number = value => Number(value);
const route = () => location.hash.replace(/^#\/?/,'') || 'lobby';
const button = (label, action, data = {}, style = '') => `<button type="button" class="${style}" data-action="${action}" data-args="${escape(JSON.stringify(data))}">${label}</button>`;
const link = (label, path) => `<a href="#/${path}">${label}</a>`;
const field = (label, name, value = '', type = 'text') => `<label>${label}<input name="${name}" type="${type}" value="${escape(value)}" ${type==='password'?'autocomplete="current-password"':''}></label>`;
const area = (label,name,value='') => `<label>${label}<textarea name="${name}">${escape(value)}</textarea></label>`;
const select = (label,name,options,value) => `<label>${label}<select name="${name}">${options.map(([key,text])=>`<option value="${escape(key)}" ${String(key)===String(value)?'selected':''}>${escape(text)}</option>`).join('')}</select></label>`;
const heading = (id,title,actions='') => `<div class="page-head"><div><h1>${title}</h1></div><div class="actions">${actions}</div></div>`;
const panel = (title,body,kind='') => `<section class="panel ${kind}"><h2>${title}</h2>${body}</section>`;
const empty = text => `<div class="empty">${escape(text)}</div>`;
const actorOptions = () => (state.characters || [state.character].filter(Boolean)).map(x=>[x.instanceId,x.name]);
const pendingKey = () => 'stumpsville.pending.' + base.pathname + '.' + state.accountId + '.' + state.storageScope;
const chatIdentity = () => JSON.stringify([state?.accountId,state?.storageScope]);
const chatPendingKey = () => state?'stumpsville.pending.chat.'+base.pathname+'.'+state.accountId+'.'+state.storageScope:null;
const chatPending = () => {const key=chatPendingKey();return key&&localStorage.getItem(key);};
const independentLogin = () => webMode?'':`<a class="account-link" href="/" target="_blank" rel="noopener">${t('account.new')}</a>`;
const rulingMode = () => select(t('ui.m077'),'ruling',[['auto',state.automation?.enabled?t('ui.m078'):t('ui.m080')],['manual',t('ui.m079')]],'auto');
function submitAction(kind,input,data){return data?.get('ruling')==='manual'?perform('request',{kind,input,manual:true,text:t('request.text',{kind:kind==='check'?t('ui.m051'):t('request.item')})}):perform(kind,input);}
function myRulings(){
  return panel('我的裁决申请',state.requests.filter(x=>x.account===state.accountId&&x.status!=='automatic').slice(-20).reverse().map(x=>`<article class="receipt"><strong>${escape(x.text||x.kind)}</strong><p>${{pending:'等待 KP 裁决',approved:'KP 已批准',rejected:'KP 已拒绝'}[x.status]||escape(x.status)} · ${escape(x.reason||'')}</p>${x.result?'<p>'+escape(resultText(x.result))+'</p>':''}</article>`).join('')||empty('没有待处理申请'));
}

function actionError(data){return Object.assign(new Error(data.failure.reason+' '+data.failure.nextStep),{status:409,failure:data.failure});}
function failurePanel(f){return `<div class="notice error action-failure"><strong>${t('failure.reason')}</strong><p>${escape(f.reason)}</p><strong>${t('failure.next')}</strong><p>${escape(f.nextStep)}</p>${f.actionId?`<small>${t('failure.id')} ${escape(f.actionId)}</small>`:''}</div>`;}
async function api(path, body, extraHeaders = {}) {
  if(webMode){const data=await webMode.api(path==='package/action'?path+'?locale='+encodeURIComponent(locale()):path,body);if(data.failure)throw actionError(data);if(data.status==='rejected'&&data.commandId)throw Object.assign(Error(data.code),{status:409});return data;}
  const headers = {...extraHeaders};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (csrf) headers['X-CSRF-Token'] = csrf;
  const response = await fetch(new URL(path==='package/action'?path+'?locale='+encodeURIComponent(locale()):path,base), {method:body===undefined?'GET':'POST',headers,body:body===undefined?undefined:JSON.stringify(body),credentials:'same-origin'});
  let data;try{data=await response.json();}catch{throw Object.assign(Error('主机响应格式异常（HTTP '+response.status+'）'),{code:'HOST_RESPONSE_INVALID',status:response.ok?502:response.status,operation:path});}
  if(data.failure)throw actionError(data);
  if (!response.ok || (data.status === 'rejected' && data.commandId)) {
    const messages={RULE_FAILED:t('error.rule_failed'),VERSION_CONFLICT:t('error.version_conflict'),NOT_VISIBLE:t('error.not_visible'),STALE_CATALOG:t('error.stale_catalog'),RATE_LIMITED:t('error.rate_limited'),ROOM_PAUSED:t('error.room_paused'),CSRF_REQUIRED:t('error.csrf_required')};
    const error = new Error(data.message || messages[data.code] || data.code || '请求失败');
    Object.assign(error,data,{status:response.status});
    throw error;
  }
  return data;
}

function toast(message) {
  const element = document.querySelector('#toast');
  element.textContent = message;
  element.classList.remove('fading');
  element.style.display = 'block';
  clearTimeout(toast.timer);clearTimeout(toast.fade);
  toast.timer = setTimeout(()=>{
    element.classList.add('fading');
    toast.fade=setTimeout(()=>element.style.display='none',diceUI.reduced||matchMedia('(prefers-reduced-motion: reduce)').matches?0:280);
  },3000);
}

function resultText(result){
  if(!result||typeof result!=='object')return typeof result==='string'&&!/^[a-f0-9-]{24,}$/.test(result)?result:t('result.done');
  if(result.dropped)return `已丢弃到地点 ${result.dropped.location}，剩余用量 ${result.dropped.uses}。`;
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

let projectionCache = null;
async function nextProjection(){
  if(webMode)return {value:await api(statePath()), changed:null, cache:null};
  const prior=state ? projectionCache : null;
  const packet=await api(statePath(),undefined,{'X-Projection-Versions':prior?.versions.join(',') || 'initial'});
  if(!Array.isArray(packet.versions))return {value:packet,changed:null,cache:null};
  const domains=packet.versions.map((_,i)=>packet.domains[i] ?? prior?.domains[i]);
  if(domains.some(domain=>!domain))throw Error('状态分区不完整，请刷新');
  return {value:Object.assign({},...domains),changed:!prior || packet.versions.slice(0,3).some((v,i)=>v!==prior.versions[i]),
          cache:{versions:packet.versions,domains}};
}

async function refresh(render = true) {
  const generation=++stateGeneration,chats=chatGeneration;
  const packet=await nextProjection(),next=packet.value;
  if(generation!==stateGeneration)return;
  projectionCache=packet.cache;
  channelSnapshot++;
  if(chats!==chatGeneration&&next.accountId===state?.accountId&&next.storageScope===state?.storageScope)next.channels=state.channels;
  state = next;
  connection = t('ui.m065');
  chatUI.update(state);diceUI.observe(state);effectsUI.observe(state);
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
  const ruling=['resolve','approve','reject','host-flow','ai.review','location.reveal'].includes(operation)&&state.role==='kp';
  const rulingIdentity=noticeIdentity(),locator={actionId:body.id,operation,requestId:args.requestId,sourceId:args.id||args.account||args.input?.waitId||args.input?.flowId};
  if(ruling){closeDialog();recordRulingNotice({title:'裁决行动',status:'processing',reason:'正在提交',locator,identity:rulingIdentity});}
  localStorage.setItem(key,JSON.stringify(webMode?{...body,_webRules:webRules}:body));
  localAction = {status:'submitting',text:t('action.submitting')};
  updateActivity();toast(t('action.submitting'));
  try {
    if(webMode)await webMode.flush();
    const result = await api('package/action',body);
    localStorage.removeItem(key);
    if(result.status==='processing')actionWake?.postMessage({scope:state.storageScope});
    dirtyForm = null;
    if(!ruling)closeDialog();
    localAction = null;
    let refreshFailure;try{await refresh();}catch(error){refreshFailure=error;}
    const notified=state.role==='player'&&state.events?.some(e=>e.id===state.accountId+':'+body.id&&!['pending','processing'].includes(e.status));
    if(!notified)toast(result.status==='processing'?t('action.queued'):resultText(result));
    if(ruling)recordRulingNotice({title:'裁决行动',status:operation==='reject'||operation==='resolve'&&!args.approve?'rejected':result.status==='processing'?'processing':'completed',reason:args.reason||((operation==='reject'||operation==='resolve'&&!args.approve)?'KP 拒绝本次申请（未填写备注）':resultText(result)),locator,identity:rulingIdentity});
    if(refreshFailure){const reason='行动已完成，但刷新资料失败：'+refreshFailure.message;toast(reason);if(ruling)recordRulingNotice({title:'裁决行动',status:'completed',reason,locator:{...locator,traceId:refreshFailure.traceId},identity:rulingIdentity});}
    return result;
  } catch(error) {
    if(ruling)recordRulingNotice({title:'裁决行动',status:error.status>=400&&error.status<500?'failed':'unknown',reason:error.failure?.reason||error.message,locator,identity:rulingIdentity});
    localAction = {status:'error',failure:error.failure,text:error.failure?'':error.message + (error.status>=400&&error.status<500?t('action.failed'):t('action.uncertain'))};
    updateActivity();
    toast(error.message);
    if ([400,403,409].includes(error.status)) localStorage.removeItem(key);
    if(error.failure){await refresh(false).catch(()=>{});if(state?.events?.some(e=>e.result?.failure?.actionId===body.id))localAction=null;updateActivity();updateKeeperQueue();const target=dialog.querySelector('[data-action-error]');if(target)target.innerHTML=failurePanel(error.failure);}
    throw error;
  } finally {
    busy = false;
  }
}

function openDialog(title,body,onSubmit,label=t('ui.m062'),id='S14') {
  lastFocus = document.activeElement;
  dialogSubmit = onSubmit;
  dialog.innerHTML = `<div class="dialog-head"><h2 id="dialog-title">${title}</h2>${button(t('ui.m058'),'close',{},'quiet')}</div><form id="dialog-form"><div class="dialog-body">${body}<div data-action-error role="alert"></div><div class="dialog-actions">${button(t('ui.m061'),'close')}${onSubmit?`<button class="primary" type="submit">${label}</button>`:''}</div></div></form>`;
  if (!dialog.open) dialog.showModal();
}

dialog.addEventListener('close',()=>{if(!dialog.open){if(dialog.querySelector('.embedded-ai-root'))embeddedAI.close();if(dirtyForm==='ruling-form')dirtyForm=null;dialog.replaceChildren();}});
function closeDialog() {
  if(dialog.open&&dialog.querySelector('#player-ai-embedded'))embeddedAI.close();
  if(dirtyForm==='ruling-form')dirtyForm=null;
  dialog.close();
  dialog.replaceChildren();
  dialogSubmit = null;
  if (lastFocus?.isConnected) lastFocus.focus();
}

async function chooseAIKnowledge(item,decide){
  const [view,capabilities,members]=await Promise.all([api('api/v1/view'),api('api/v1/knowledge/capabilities'),api('api/v1/chat/members')]);
  const policy=capabilities.policies.find(p=>p.policyId==='stumpsville-personal-v1');
  const member=members.items.find(m=>m.accountId===item.initiator);
  if(!policy||!member)throw Error('资料策略或申请玩家已变化，请刷新');
  const candidates=Object.values(view.entities).filter(e=>e.lifecycle==='active'&&(e.configurationId==='sv.location'||e.configurationId==='sv.character'||e.configurationId==='sv.npc'||e.configurationId.startsWith('sv.ext.npc.')));
  let selected=null,generation=0;
  openDialog('批准资料申请',`<p>${escape(item.initiator)} · ${escape(item.summary||'')}</p>${select('选择披露资料','disclose-resource',[['','请选择'],...candidates.map(e=>[e.instanceId,e.name+' · '+(e.configurationId==='sv.location'?'地点描述与已发布线索':'身份与位置')])],'')}<div data-knowledge-preview></div>`,async()=>{
    if(!selected)throw Error('请先选择并查看披露内容');
    closeDialog();
    const result=await decide([{op:'knowledge.observe',args:{policyId:policy.policyId,expectedPolicyRevision:policy.revision,subjectMemberId:member.memberId,resource:selected.resource,facetIds:selected.facetIds,expectedSourceRevision:selected.preview.sourceRevision,reason:'KP 批准玩家 AI 资料申请'}}]);
    if(result.status!=='completed')throw Error('资料披露尚未全部完成，请在原申请中核对回执');
    closeDialog();toast('已向申请玩家披露所选资料');
    await refresh(false);
  },'批准并披露');
  dialog.querySelector('[name=disclose-resource]').onchange=async event=>{
    const ticket=++generation;selected=null;
    const target=dialog.querySelector('[data-knowledge-preview]');target.textContent='';
    const entity=candidates.find(e=>e.instanceId===event.target.value);if(!entity)return;
    const resource={namespace:'stumpsville',kind:'entity',id:entity.instanceId},facetIds=[entity.configurationId==='sv.location'?'scene':'identity'];
    target.textContent='读取披露预览…';
    try{
      const preview=await api('api/v1/knowledge/preview',{policyId:policy.policyId,resource,facetIds});
      if(ticket!==generation||!target.isConnected)return;
      selected={resource,facetIds,preview};
      const shown=(preview.preview||preview.facets||{})[facetIds[0]]||{};
      const placeName=index=>Object.values(view.entities).find(e=>e.configurationId==='sv.location'&&e.numbers.index===index)?.name||String(index);
      target.innerHTML='<section><h3>将披露给该玩家的内容</h3><strong>'+escape(shown.name||entity.name)+'</strong>'+(shown.description?'<p>'+escape(shown.description)+'</p>':'')+(shown.location?'<p>位置：'+escape('地点 '+shown.location)+'</p>':'')+(shown.exits?.length?'<p>通路：'+shown.exits.map(i=>escape('地点 '+i)).join('、')+'</p>':'')+(shown.clues||[]).map(c=>'<p><strong>'+escape(c.title)+'</strong> '+escape(c.text)+'</p>').join('')+(shown.actions?.length?'<p>可见行动：'+shown.actions.map(a=>escape(a.label)).join('、')+'</p>':'')+'</section>';
    }catch(error){if(ticket===generation&&target.isConnected)target.textContent=error.message;}
  };
}

function statCards(character){
  return characterStatsHTML(character,{label:fieldName,check:key=>button(escape(fieldName(key)),'check',{attribute:key},'quiet')});
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

function stormOverview(story) {
  if (!story) return '';
  const names = {home:'守住家园', allied:'共同渡险', evacuated:'溪岸撤离', withdrawn:'记录损失并撤退'};
  const status = story.ending ? '已结局 · ' + names[story.ending.route]
    : story.rescued ? '两名村民已获救' : story.started ? '搜救中' : '等待接取委托';
  const tasks = Object.entries(story.tasks).map(([name, done]) =>
    `<li>${escape(name)} · ${done ? '已完成' : '待完成'}</li>`).join('');
  const choices = story.started ? [...story.routes, 'withdrawn'] : [];
  const finish = story.ending ? `<p>队员去向 · ${escape(story.ending.roster)}</p>`
    : choices.map(route => button('确认结局 · ' + names[route], 'storm-finish', {route})).join('');
  return `<p>暴雨前的树桩镇 · ${escape(status)}</p><ul>${tasks}</ul>${story.debt ? '<p>居民仍欠渡工一笔行粮。</p>' : ''}${finish}`;
}

function roomOverview(){
  const characters=state.characters||[],phase=state.session?.numbers.phase||0,active=phase===1&&state.roomStatus==='active';
  const stats=[['状态',state.roomStatus==='paused'?'暂停':phase===1?'进行中':phase===2?'已结束':'待开场'],['回合',state.session?.numbers.round||0],['在线玩家',state.network?.players.filter(p=>p.role==='player'&&p.status==='online').length??'—'],['已准备角色',characters.filter(c=>c.numbers.ready).length+' / '+characters.length],['游戏待办',keeperLocalPending()],['已发布地点',Object.keys(state.published||{}).length]];
  return `<section class="panel" id="room-overview"><h2>房间总览</h2>${stormOverview(state.storm)}<div class="room-stats">${stats.map(([label,value])=>`<div><span>${label}</span><strong>${value}</strong></div>`).join('')}</div><div class="actions"><button type="button" class="primary" data-action="start" ${active||phase===2?'disabled':''}>${active?'已开场':state.roomStatus==='paused'?'恢复开场':'一键开场'}</button>${state.initialized?`${button(t('ui.m026'),'round')}${button(state.roomStatus==='paused'?t('ui.m028'):t('ui.m027'),'room',{status:state.roomStatus==='paused'?'active':'paused'})}${button(state.automation.enabled?t('ui.m029'):t('ui.m030'),'automation-console')}${button(t('ui.m143'),'backup')}`:''}${button('处理裁决','navigate',{path:'gm/rulings'})}</div><p class="room-readiness">规则 ${state.initialized?'已安装':'待初始化'} · 个人资料 ${state.knowledge?.status==='ready'?'已就绪':'待启用'} · 自动裁决 ${state.automation.enabled?'开启':'关闭'}</p></section>`;
}
function roomPage(){
  const grants=state.knowledgeGrants?.items||[];
  const knowledge=state.initialized?`<details class="panel"><summary>个人资料授权管理</summary>${state.knowledge?.status!=='ready'?button('启用个人知识服务','knowledge-enable'):''}${button('处理旧地点记录','knowledge-import')}<div class="stack">${grants.map(g=>`<div class="row"><span>${escape(g.label)} · ${escape(g.subject.accountId)} · ${g.mode==='live_scope'?'持续告知':'观察记录'}</span>${button('撤回','knowledge-revoke',{grantId:g.grantId,revision:g.revision},'small')}</div>`).join('')||'<p>暂无授权记录。</p>'}</div>${state.knowledgeGrants?.nextCursor?'<p>当前显示前50项。</p>':''}</details>`:'';
  return heading('P15',t('nav.room'),webMode?'':button(t('room.share'),'web-room',{},'primary'))+'<div class="room-dashboard">'+roomOverview()+roomNetworkPanel()+'</div>'+knowledge;
}
function mapPage(){
  return heading('P16',t('nav.map'))+panel(t('ui.m105'),mapView(Object.values(state.allLocations),selectedLocation,true));
}
function noticeIdentity(){return JSON.stringify([state?.storageScope,state?.accountId]);}
function noticeKey(){return 'sv.desktop.rulingNotices.'+state.storageScope+'.'+state.accountId;}
function rulingNotices(){try{return JSON.parse(localStorage.getItem(noticeKey())||'[]').map(n=>({...n,reason:explainAIError(n.reason)}));}catch{return [];}}
function recordRulingNotice(value){
  if(!state||state.role!=='kp'||value.identity&&value.identity!==noticeIdentity())return;
  const reasons={INPUT_INVALID:'提交参数无效，请刷新原裁决后重试',RULING_STALE:'裁决依据已更新，请重新打开原裁决',PERMISSION_DENIED:'当前账号无权执行该裁决',HIGH_RISK_REVIEW_REQUIRED:'高危确认已失效，请重新核对原方案',STORAGE_UNAVAILABLE:'房间存储暂不可用，请保留定位并联系房主排查',SOURCE_STALE:'来源已变化，请重新生成方案',SESSION_ACCESS_CHANGED:'会话权限已变化，请重新登录核对'};
  const entry={id:newId(),time:Date.now(),...value,reason:reasons[value.reason]?reasons[value.reason]+'（'+value.reason+'）':explainAIError(value.reason)};const records=rulingNotices();records.unshift(entry);localStorage.setItem(noticeKey(),JSON.stringify(records.slice(0,100)));
  const label={pending:'等待确认',processing:'处理中',completed:'已完成',published:'已发布',accepted:'已接收',rejected:'已拒绝',cancelled:'已取消',failed:'失败',blocked:'已阻止',partial:'部分完成',rolled_back:'整批已撤销',unknown:'结果待核对'}[entry.status]||entry.status;
  toast(entry.title+' · '+label+'\n'+entry.reason);
  const target=document.querySelector('#message-queue-list');if(target)target.innerHTML=messageQueue();
}
function messageQueue(){
  const channels=Object.values(state.channels).filter(c=>c.unreadCount>0);
  return channels.map(c=>`<button type="button" class="message-queue-item" data-action="chat-channel" data-args="${escape(JSON.stringify({channel:c.channelId}))}"><strong>${escape(c.name)}</strong><span class="tag">${c.unreadCount}</span></button>`).join('')+rulingNotices().map(n=>rulingCard({time:new Date(n.time).toLocaleTimeString(locale(),{hour:'2-digit',minute:'2-digit'}),type:'执行结果',source:'KP',summary:escape(n.title+' · '+n.reason),state:({pending:'等待确认',failed:'失败',rejected:'已拒绝',processing:'处理中',unknown:'结果待核对',blocked:'已阻止',completed:'已完成',rolled_back:'整批已撤销'}[n.status]||n.status),actions:button('详情与定位','ruling-notice',{id:n.id})})).join('')||empty(t('ruling.noMessages'));
}
function keeperLocalPending(){return (state?.requests||[]).filter(r=>r.status==='pending').length+Object.values(state?.drafts||{}).filter(d=>d.status==='submitted').length+(state?.keeperWaits||[]).length+(state?.keeperFlows||[]).length;}
function updateQueueCount(value=aiQueuePending){aiQueuePending=value;const count=document.querySelector('#keeper-pending-count');if(count)count.textContent=keeperLocalPending()+aiQueuePending;}
function updateKeeperQueue(){
  if(state?.role!=='kp'||!document.querySelector('.ruling-work'))return;
  for(const [selector,render] of [['#keeper-character-approvals',characterApprovalQueue],['#keeper-host-flows',hostFlowQueue],['#keeper-game-requests',rulingQueue],['#keeper-archived-rulings',archivedRulings]]){
    const node=document.querySelector(selector);if(!node)continue;
    const markup=render();if(node._queueMarkup!==markup){const template=document.createElement('template');template.innerHTML=markup;node._queueCards=[...template.content.children];node.replaceChildren();node._queueMarkup=markup;}
  }
  const target=document.querySelector('#keeper-ruling-timeline');
  if(target){target._timeline??=mountRulingTimeline(target);const selectors=queueTab==='archived'?['#keeper-archived-rulings']:['#keeper-character-approvals','#keeper-host-flows','#keeper-game-requests'];target._timeline.set('manual',selectors.flatMap(q=>document.querySelector(q)?._queueCards||[]));}
  updateQueueCount();
}
function queueTime(value){
  if(!value)return '—';const date=new Date(typeof value==='number'?value*1000:value);
  return Number.isNaN(date.getTime())?'—':date.toLocaleTimeString(locale(),{hour:'2-digit',minute:'2-digit'});
}
function compactQueue(time,source,summary,action,args,actions='',attrs=''){
  const type=attrs.includes('data-draft')?'角色申请':attrs.includes('data-wait')?'流程裁决':attrs.includes('data-flow')?'流程异常':'玩家行动';
  return rulingCard({time:queueTime(time),timestamp:time,type,source,summary:`<button type="button" class="queue-summary quiet" data-action="${action}" data-args="${escape(JSON.stringify(args))}">${escape(summary)}</button>`,actions,attrs});
}
function rulingAIButton(kind,id,account){return button('转 AI 处理','ruling-ai',{kind,id,...(account?{account}:{})},'small');}
function rulingDebugTools(kind,id,account){
  const args={kind,id,...(account?{account}:{})};
  return `<details class="ruling-debug"><summary>调试</summary><label><input type="checkbox" data-review-content> 包含裁决内容</label><div class="actions">${button('复制引用','ruling-reference',args,'small')}${button('导出调试','ruling-export',args,'small')}</div></details>`;
}
async function readRulingSource(args){
  const identity=JSON.stringify([state.storageScope,state.accountId,state.role]),opened=dialog.firstElementChild;
  const source=await api('package/ai-source',args);
  if(state.role!=='kp'||identity!==JSON.stringify([state.storageScope,state.accountId,state.role]))throw Error('身份已变化，请刷新');
  if(!dialog.open||dialog.firstElementChild!==opened)throw Error('裁决窗口已变化，请重新操作');
  return source;
}
async function copyRulingReference(args){
  const source=await readRulingSource(args);
  const value=JSON.stringify({storageScope:state.storageScope,kind:source.kind,sourceId:source.sourceId,category:source.category,id:source.id,revision:source.revision,title:source.title,requestedBy:source.requestedBy,locator:source.context.sourceLocator});
  try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(value);return toast('裁决引用已复制');}}catch{}
  const input=document.createElement('textarea');input.value=value;dialog.append(input);input.readOnly=true;input.setAttribute('aria-label','可复制的裁决引用');input.focus();input.select();let copied=false;try{copied=!!document.execCommand?.('copy');}catch{}if(copied)input.remove();toast(copied?'裁决引用已复制':'请选择并复制引用');
}
async function exportRulingDebug(args){
  const includeContent=!!dialog.querySelector('[data-review-content]')?.checked,source=await readRulingSource(args);
  const content=includeContent?source:Object.fromEntries(Object.entries(source).filter(([key])=>!['summary','context'].includes(key)));
  const data={schemaVersion:1,storageScope:state.storageScope,exportedAt:new Date().toISOString(),contentIncluded:includeContent,locator:source.context.sourceLocator,source:content};
  const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download='stumpsville-ruling-debug.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function openRulingSource(source){
  if(source.kind!=='package'||source.sourceId!=='stumpsville')return toast('该来源不属于当前配置包');
  const args=source.context?.sourceLocator||{kind:source.category,id:source.id,account:source.requestedBy};
  if(args.kind==='request'&&state.requests.some(r=>r.id===args.id&&r.status==='pending'))actions['console-request']({id:args.id});else queueDetail(args);
}
function characterApprovalQueue(){
  return Object.values(state.drafts||{}).filter(d=>d.status==='submitted').map(d=>compactQueue(d.time,d.account,t('queue.characterApproval')+' · '+d.name,'queue-detail',{kind:'draft',id:d.account},button(t('ui.m114'),'approve',{account:d.account},'primary small')+button(t('ui.m115'),'reject',{account:d.account},'small')+rulingAIButton('draft',d.account),`data-draft="${escape(d.account)}"`)).join('');
}
function hostFlowQueue(){
  return (state.keeperWaits||[]).map(w=>compactQueue(w.createdAt||w.created,w.account||'宿主',w.options?.question||w.options?.prompt||t('queue.flowWait'),'queue-detail',{kind:'wait',id:w.id},button(t('ui.m099'),'host-flow',{operation:'flow.respond',input:{waitId:w.id,revision:w.revision,answer:true}},'primary small')+button(t('ui.m100'),'host-flow',{operation:'flow.respond',input:{waitId:w.id,revision:w.revision,answer:false}},'small')+rulingAIButton('wait',w.id),`data-wait="${escape(w.id)}"`)).join('')+(state.keeperFlows||[]).map(f=>compactQueue(f.updatedAt||f.createdAt,f.rule,f.error||t('queue.flowAttention'),'queue-detail',{kind:'flow',id:f.id},button(t('queue.retryFlow'),'host-flow',{operation:'flow.retry',input:{flowId:f.id}},'small')+button(t('queue.cancelFlow'),'host-flow',{operation:'flow.cancel',input:{flowId:f.id}},'small')+rulingAIButton('flow',f.id),`data-flow="${escape(f.id)}"`)).join('');
}
function queueDetail({kind,id,account}){
  const item=kind==='request'?state.requests.find(x=>x.id===id):kind==='draft'?state.drafts[id]:kind==='wait'?state.keeperWaits.find(x=>x.id===id):kind==='event'?(state.events||[]).find(x=>x.id===id&&(!account||x.account===account)):state.keeperFlows.find(x=>x.id===id);
  if(!item)return toast('原裁决已不在当前列表中，请刷新或查看处理记录');
  const title=kind==='request'?'玩家行动申请':kind==='event'?'裁决与行动记录':kind==='draft'?t('queue.characterApproval'):kind==='wait'?t('queue.flowWait'):t('queue.flowAttention');
  const body=kind==='draft'?`<h3>${escape(item.name)}</h3><p>${escape(item.account)} · ${fieldName('str')} ${item.str} / ${fieldName('dex')} ${item.dex} / ${fieldName('wil')} ${item.wil} · ${fieldName('hp')} ${item.hp}</p>`:`<p>${escape(item.options?.question||item.options?.prompt||item.text||item.error||item.status||'')}</p>`;
  openDialog(title,body+`<pre class="data-detail">${escape(JSON.stringify(item,null,2))}</pre><div class="actions">${rulingAIButton(kind,id,account)}</div>`+rulingDebugTools(kind,id,account),null);
}
function rulingsPage(){
  return `<nav class="ruling-switch" aria-label="裁决工作区">${[['queue','裁决队列'],['ai','AI 对话'],['chat','聊天']].map(([pane,label])=>button(label,'ruling-pane',{pane},pane===rulingPane?'primary small':'small')).join('')}</nav><div class="rulings-grid" data-pane="${rulingPane}"><section class="panel ruling-work ruling-queues"><header class="queue-heading"><div role="tablist" aria-label="消息与裁决"><button type="button" role="tab" aria-selected="${queueTab==='messages'}" data-action="queue-tab" data-args='{"tab":"messages"}'>消息队列</button><button type="button" role="tab" aria-selected="${queueTab==='rulings'}" data-action="queue-tab" data-args='{"tab":"rulings"}'>裁决队列 <span id="keeper-pending-count">${keeperLocalPending()+aiQueuePending}</span></button><button type="button" role="tab" aria-selected="${queueTab==='archived'}" data-action="queue-tab" data-args='{"tab":"archived"}'>已归档</button></div><div class="queue-header-actions">${button('记录','ruling-history',{},'small')}${button('刷新','queue-refresh',{},'small')}${button('设置','navigate',{path:'gm/ai-settings'},'small')}</div></header><div id="keeper-queue-status" class="queue-status-host" aria-label="裁决处理状态"></div><div id="message-queue-list" class="ruling-scroll" role="tabpanel" ${queueTab!=='messages'?'hidden':''}>${messageQueue()}</div><div id="ruling-queue-list" class="ruling-scroll" role="tabpanel" ${queueTab==='messages'?'hidden':''}><div data-pending-rulings ${queueTab==='archived'?'hidden':''}><div id="keeper-character-approvals">${characterApprovalQueue()}</div><div id="keeper-host-flows">${hostFlowQueue()}</div><div id="keeper-game-requests">${rulingQueue()}</div></div><div id="keeper-archived-rulings" ${queueTab!=='archived'?'hidden':''}>${archivedRulings()}</div><div id="kp-ai-rulings"></div><div id="keeper-ruling-timeline"></div></div></section><section class="panel ruling-ai" aria-label="${t('ai.title')}"><div id="kp-ai-embedded"></div></section><aside id="chat-column" class="ruling-chat" aria-label="${t('chat.title')}"></aside></div>`;
}

function mapView(locations,current,rosters=false) {
  const positions=mapPositions;
  const points=locations.map(l=>positions[l.index]);
  const minX=Math.min(...points.map(p=>p[0]))-85,minY=Math.min(...points.map(p=>p[1]))-65;
  const mapBox=`${minX} ${minY} ${Math.max(250,Math.max(...points.map(p=>p[0]))-minX+85)} ${Math.max(170,Math.max(...points.map(p=>p[1]))-minY+65)}`;
  const edges=mapRoutes(locations,rosters===true?state.doors:null).map(edge=>`<path data-route="${edge.key}" data-status="${edge.status}" d="${mapRoutePath(edge)}" class="${edge.status==='open'?'open':edge.status==='unknown'?'unknown':'closed'}"><title>${edge.key} · ${t('map.route.'+edge.status)}</title></path>`).join('');
  const action=rosters===true?'map-room':'location';
  const nodes=locations.map(x=>{const [left,top]=positions[x.index],show=rosters===true||rosters==='player'&&x.index===current,actors=rosters===true?roomActors(x.index):show?(state.mapContacts||[]):[],names=actors.map(a=>a.name).join('、'),count=t('map.occupants',{count:actors.length});return `<g role="button" tabindex="0" aria-label="${escape(x.name+(show?' · '+count+' · '+names:''))}" data-action="${action}" data-args="${escape(JSON.stringify({index:x.index}))}" class="${x.index===current?'current':''}" transform="translate(${left},${top})"><title>${escape(x.name+(show?' · '+count+' · '+names:''))}</title><rect x="-64" y="-24" width="128" height="${show?84:48}" rx="9"/><text text-anchor="middle"><tspan x="0" y="-6" class="map-index">${String(x.index).padStart(2,'0')}</tspan><tspan x="0" y="13" ${x.name.length>13?'textLength="112" lengthAdjust="spacingAndGlyphs"':''}>${escape(x.name)}</tspan>${show?`<tspan x="0" y="32" class="map-count">${count}</tspan><tspan x="0" y="49" class="map-names">${escape(names.length>11?names.slice(0,10)+'…':names||t('map.empty'))}</tspan>`:''}</text>${x.index===current?'<circle cx="57" cy="-20" r="6"/>':''}</g>`;}).join('');
  const selected=locations.find(x=>x.index===current)||locations[0];
  return `<div class="node-map ${rosters===true?'kp-map':''}"><svg viewBox="${locations.length?mapBox:'10 20 710 310'}" aria-label="${t('scene.maplabel')}">${edges}${nodes}</svg></div><div class="map compact-map">${locations.map(x=>button(`${String(x.index).padStart(2,'0')} ${escape(x.name)}${rosters===true?' · '+t('map.occupants',{count:roomActors(x.index).length}):rosters==='player'&&x.index===current?' · '+t('map.occupants',{count:state.mapContacts?.length||0}):''}`,action,{index:x.index},x.index===current?'current':'')).join('')}</div><p class="map-links">${t(rosters===true?'map.legend':'scene.legend')}</p>${rosters===true&&selected?`<section class="map-room-detail"><header><strong>${escape(selected.name)}</strong>${button(t('map.manage'),'location',{index:selected.index},'small')}</header>${roomRoster(selected.index)}</section>`:''}`;
}

function renderEntry() {
  diceUI.observe(null);effectsUI.observe(null);
  if(webMode){app.innerHTML=empty('连接已断开，请在网页上方退出并重新连接房主。');return;}
  aiUI.update(null);embeddedAI.close();
  chatUI.mount(null);document.body.classList.remove('scene-workspace','rulings-workspace','player-ui','topbar-collapsed');
  app.innerHTML = `<section class="entry"><div class="entry-card"><div class="eyebrow">${t('entry.tagline')}</div><h1>${t('app.name')}</h1><div class="subtitle">STUMPSVILLE</div><p>${t('entry.intro')}</p><div class="notice">${setup?.canSetup?t('entry.setup'):t('entry.login')}</div><form id="entry-form">${setup?.canSetup?'':field(t('ui.m157'),'loginName','kp')}${field(setup?.canSetup?t('entry.password'):t('ui.m158'),'password','','password')}${setup?.canSetup?`<p class="muted">${t('entry.accounts')}</p>`:''}<button class="primary" type="submit">${setup?.canSetup?t('entry.prepare'):t('ui.m156')}</button><div id="entry-error" role="alert"></div></form><p>${independentLogin()}</p></div></section>`;
}

// Replace surrounding game panels without disconnecting the conversation's editor.
// Even re-inserting the same contenteditable node cancels the browser's native composition.
function renderAround(container, markup, selector) {
  const original = selector && container.querySelector(selector);
  if (!original) {
    container.innerHTML = markup;
    return;
  }
  const template = document.createElement('template');
  template.innerHTML = markup;
  const branches = [];
  let kept = original, fresh = template.content.querySelector(selector);
  while (fresh && kept !== container && fresh !== template.content && kept.tagName === fresh.tagName && kept.id === fresh.id) {
    branches.push([kept, fresh]);
    kept = kept.parentNode;
    fresh = fresh.parentNode;
  }
  if (kept !== container || fresh !== template.content) {
    container.replaceChildren(template.content);
    return;
  }
  for (const [live, replacement] of branches) {
    for (const attr of [...live.attributes]) {
      if (!replacement.hasAttribute(attr.name)) live.removeAttribute(attr.name);
    }
    for (const attr of replacement.attributes) {
      if (live.getAttribute(attr.name) !== attr.value) live.setAttribute(attr.name, attr.value);
    }
    while (live.previousSibling) live.previousSibling.remove();
    while (live.nextSibling) live.nextSibling.remove();
    while (replacement.previousSibling) live.before(replacement.parentNode.firstChild);
    while (replacement.nextSibling) live.parentNode.append(replacement.nextSibling);
  }
}

function renderPage() {
  if (!state) return renderEntry();
  const logScroll=document.querySelector('#action-feedback')?.scrollTop||0;
  const sceneScroll=document.querySelector('.scene-column')?.scrollTop||0;
  const characterScroll=document.querySelector('.character-column')?.scrollTop||0;
  restoreDesktop();
  let path = route();
  const legacyPanels = {'play/character':'inventory','play/journal':'clues','play/records':'records'};
  if(legacyPanels[path]){
    if(state.role==='kp'){path='gm/rulings';}
    else {const name=legacyPanels[path];if(name==='inventory')mobileColumn='character';else{for(const key of Object.keys(paneNames()))desktop[key].open=key===name;desktop[name].collapsed=false;desktop.front=name;}saveDesktop();path='play/scene';}
    historyReplace('#/'+path);acceptedHash=location.hash;
  }
  if(['gm/overview','gm/encounters'].includes(path)){path=path==='gm/encounters'?'gm/rulings':'gm/console';historyReplace('#/'+path);acceptedHash=location.hash;}
  if(/^gm\/locations\/\d+$/.test(path)){selectedLocation=Number(path.split('/')[2]);path='gm/locations';}
  const gm = state.role === 'kp';
  aiUI.update(state,gm,locale());
  if(gm&&(!path.startsWith('gm/'))){path='gm/room';historyReplace('#/'+path);}
  const navigation = gm ? gmNav() : [...playerNav(),['lobby',t('ui.m033')],['recap',t('ui.m034')]];
  const workspace=!gm&&path==='play/scene';
  document.body.classList.toggle('scene-workspace',workspace);
  document.body.classList.toggle('rulings-workspace',gm&&path==='gm/rulings');
  document.body.classList.toggle('player-ui',!gm);
  document.body.classList.toggle('library-workspace',gm&&path==='gm/library');
  document.body.classList.toggle('ai-settings-workspace',gm&&path==='gm/ai-settings');
  const pending = localStorage.getItem(pendingKey());
  const folded=localStorage.getItem('sv.desktop.topbar.'+base.pathname+'.'+state.accountId)==='1';
  document.body.classList.toggle('topbar-collapsed',folded);
  const aiSlot = workspace ? '#player-ai-embedded' : gm && path === 'gm/rulings' && !webMode ? '#kp-ai-embedded' : null;
  renderAround(app, `<header class="topbar"><div class="brand"><span class="brand-symbol">♧</span><span>${t('app.name')}<small>STUMPSVILLE</small></span></div>${!gm?`<nav class="top-nav" aria-label="${t('nav.main')}">${navigation.map(([url,label])=>`<a href="#/${url}" class="${path===url?'active':''}">${label}</a>`).join('')}</nav>`:''}<div class="toptools"><span class="identity">${gm?t('ui.m015'):t('ui.m016')} · ${escape(state.accountId)}</span><span class="tag" id="connection">${connection}</span>${state.canManage&&!webMode?`<a class="account-link" target="_blank" rel="noopener" href="${base.pathname}${gm?'?view=player#/play/scene':'#/gm/room'}">${gm?t('ui.m017'):t('ui.m018')}</a>`:''}${gm||workspace?'':button(t('ai.title'),'ai-assistant',{},'quiet')}${button(t('ui.m011'),'rules',{},'quiet')}${button(t('ui.m012'),'preferences',{},'quiet')}${button(t('ui.m013'),'logout',{},'quiet')}${select(t('ui.m014'),'locale',[['zh-CN','简体中文'],['en','English']],locale())}</div><button class="topbar-toggle quiet" data-action="topbar-toggle" aria-expanded="${!folded}" aria-label="${t(folded?'nav.expandTop':'nav.collapseTop')}" title="${t(folded?'nav.expandTop':'nav.collapseTop')}">${folded?t('nav.expandTop')+' ▾':'▴'}</button></header>${pending?`<div class="pendingbar">${t('status.pendingcommand')} ${button(t('action.recover'),'recover',{},'small')}</div>`:''}<div class="shell ${gm?'':'player-shell'}">${gm?`<nav class="sidebar" aria-label="${t('nav.main')}">${navigation.map(([url,label])=>`<a href="#/${url}" class="${path.startsWith(url)?'active':''}">${label}</a>`).join('')}</nav>`:''}<main id="main"></main></div>`, aiSlot && app.querySelector(aiSlot) ? '#main' : null);
  const main = document.querySelector('#main');
  if (!state.initialized) {
    chatUI.mount(null);main.innerHTML = gm?roomPage():empty(t('ui.m076'));
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
    'gm/library':libraryPage,'gm/ai-settings':()=>heading('P18','AI 设置')+'<section id="kp-ai-settings" aria-label="AI 设置"></section>','gm/session':sessionPage,'recap':recapPage
  };
  if(webMode&&gm&&['gm/library','gm/ai-settings'].includes(path)){main.innerHTML=empty('规则资料管理和 AI 设置请在房主本机打开；远程 KP 可使用房间、地图、地点、控制台和游戏裁决。');embeddedAI.close();return;}
  renderAround(main, (routes[path] || (()=>heading('S16',t('ui.m070'))+link(t('ui.m071'),'lobby')))(), aiSlot);
  if(gm&&state.publicationSync&&state.publicationSync.status!=='completed')main.insertAdjacentHTML('afterbegin','<div class="notice error" role="status">规则发布已提交；包侧'+(state.publicationSync.status==='conflict'?'同步冲突':'等待同步')+'：'+escape(state.publicationSync.message)+'</div>');
  chatUI.update(state);
  chatUI.mount(workspace||path==='gm/rulings'?document.querySelector('#chat-column'):null);
  updateKeeperQueue();
  const renderedIdentity=noticeIdentity();
  if(webMode&&gm&&path==='gm/rulings')document.querySelector('#kp-ai-embedded').textContent='远程 KP 可处理游戏裁决。AI 管理与审核请在房主本机打开。';
  const assistantTarget = aiSlot ? main.querySelector(aiSlot) :
    gm && path==='gm/ai-settings' ? main.querySelector('#kp-ai-settings') :
    !gm && dialog.open ? dialog.querySelector('#player-ai-embedded') : null;
  embeddedAI.mount(assistantTarget,{base,manager:gm,account:state.accountId,scope:state.storageScope,settings:path==='gm/ai-settings',rulingsTarget:document.querySelector('#kp-ai-rulings'),statusTarget:document.querySelector('#keeper-queue-status'),timeline:document.querySelector('#keeper-ruling-timeline')?._timeline,archived:queueTab==='archived',readBundle:()=>api('package/bundle?form=active'),renderReference:renderPackageReference,onQueueCount:updateQueueCount,onNotice:value=>recordRulingNotice({...value,identity:renderedIdentity}),onSettings:()=>{location.hash='/gm/ai-settings';},onReveal:account=>actions['knowledge-ruling']({account}),onKnowledgeRequest:chooseAIKnowledge,onOpenSource:openRulingSource,onReview:()=>{location.hash='/gm/rulings';}});
  updateActivity();
  if(workspace){const log=document.querySelector('#action-feedback');if(log)log.scrollTop=logScroll;document.querySelector('.scene-column').scrollTop=sceneScroll;document.querySelector('.character-column').scrollTop=characterScroll;positionNotebook();}
}

function lobbyPage() {
  const character = state.character;
  return heading('P02',t('ui.m033'),state.role==='kp'?button(t('ui.m035'),'navigate',{path:'gm/console'},'primary'):'')+
    `<div class="grid2">${panel(t('ui.m038'),character?`<img class="portrait" src="art/mouse.png" alt="小鼠冒险者"><h2>${escape(character.name)}</h2>${statCards(character)}${button(t('ui.m040'),'navigate',{path:'ready'},'primary')}`:empty(t('ui.m037')))}${panel(t('ui.m039'),`<p>${t('lobby.intro')}</p>${state.draft?`<div class="notice">${t('lobby.draft')} · ${escape(state.draft.name)} · ${t('state.'+state.draft.status)}<br>${escape(state.draft.reason||'')}</div>`:''}${!character?button(t('ui.m036'),'navigate',{path:'character/new'},'primary'):''}`)}</div>`;
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
  if(state.knowledge?.status!=='ready')return empty('个人资料暂不可用，请联系 KP 确认知识服务或重新揭示。');
  const c=state.character;
  if(!c)return `<div class="scene-empty">${empty(t('scene.nocharacter'))}${link(t('ui.m033'),'lobby')}</div>`;
  if(!c.numbers.ready||state.session?.numbers.phase!==1)return `<div class="scene-empty">${empty(t('ui.m041'))}${link(t('ui.m040'),'ready')}</div>`;
  const place=state.locations.find(x=>x.index===c.numbers.location);
  if(!place)return empty(t('scene.unpublished'));
  const observation=place.observedAt?`观察记录 · ${new Date(place.observedAt*1000).toLocaleString()}（非实时场景）`:t('scene.current');
  return `<header class="scene-heading"><div><small>${escape(observation)}</small><h1>${String(place.index).padStart(2,'0')} ${escape(place.name)}</h1></div><span class="tag">${t('scene.round',{count:state.session?.numbers.round||0})}</span></header><p class="scene-description">${escape(place.description)}</p><div class="scene-map-area">${mapView(state.locations,place.index,'player')}${playerContacts()}</div><div class="available-actions"><header><h2>${t('scene.actions')}</h2><span class="tag scene-settlement" role="status">${settlementStatus()}</span></header><div class="preset-actions">${sceneButtons(place)}</div><div class="travel-actions">${place.exits.map(index=>button(t('scene.go',{place:escape(state.locations.find(x=>x.index===index)?.name||String(index))}),'travel',{destination:index},'small')).join('')}</div><div class="generic-actions">${button(t('ui.m051'),'check',{},'primary')}${button(t('ui.m049'),'request',{kind:'free'})}${button(t('ui.m050'),'review')}</div></div>${sceneStatusPanel()}${groundItems(place.index)}`;
}

function groundItems(location,keeper=false){
  const rows=(state.groundItems||[]).filter(x=>x.location===location);
  const supplies=keeper?[]:(state.pickupOptions||[]);
  if(!rows.length&&!supplies.length)return '';
  const drops=rows.map(x=>`<div class="row"><span>${escape(state.items[String(x.item)]?.name||'物品')} · 剩余用量 ${x.uses}</span>${x.claim?'拿取处理中':button('拿取',keeper?'take-ground':'pickup-drop',{id:x.id,index:location},'small')}</div>`);
  const stock=supplies.map(x=>`<div class="row"><span>${escape(x.name)} · 剩余 ${x.count}</span>${button('拿取','pickup-stock',{actionId:x.action,choice:x.choice},'small')}</div>`);
  return `<section class="ground-items"><h3>可拿取物品</h3>${drops.join('')}${stock.join('')}</section>`;
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

function keeperSceneMenu(index){
  const facts=state.sceneKnowledge||[],label=id=>facts.find(f=>f.id===id)?.title||'包定义的个人发现';
  const actions=(state.scenePlayerDefinitions||[]).filter(a=>a.location===index);
  return `<section class="keeper-scene-menu"><h3>行动说明 · KP</h3><p class="muted">主持机制仅在本管理页展示。玩家只收到自己的观察和已解锁选项；这些规则说明不是玩家预览。</p>${actions.map(a=>`<details><summary>${escape(a.label)}</summary><p>${escape(a.hint)}</p>${a.choices.map(c=>`<div class="receipt"><strong>${escape(c.label)}</strong><p>${escape(c.process)}</p><small>玩家显示：${escape(c.player?.label||'未提供')} · ${[...(a.player?.requiresAny||[]),...(c.player?.requiresAny||[])].map(label).map(escape).join(' / ')||'基础探索选项'}</small></div>`).join('')}</details>`).join('')||'<p>没有可用行动定义。</p>'}</section>`;
}
function locationsPage() {
  const place=state.allLocations[String(selectedLocation)]||Object.values(state.allLocations)[0];
  const doors=place.exits.map(x=>{const edge=[place.index,x].sort((a,b)=>a-b).join('-');return button(`通往 ${x} · ${{open:'开启',closed:t('ui.m058'),locked:'锁住'}[state.doors[edge]]}`,'door',{edge});}).join('');
  const stock=place.stock.map(x=>`<div class="row"><span>${escape(state.items[String(x.item)]?.name)} × ${x.count}</span>${x.count?button('领取','take-stock',{index:place.index,item:x.item},'small'):''}</div>`).join('');
  return heading('P10',t('ui.m128'),button(t('ui.m127'),'preview',{index:place.index}))+`<div class="layout-aside"><div>${panel(`${place.index} ${escape(place.name)}`,`<form id="location-form"><input type="hidden" name="index" value="${place.index}"><input type="hidden" name="revision" value="${place.revision||0}"><div class="grid2"><div>${area('公开描述','description',place.description)}</div><div>${area('KP 主持真相','truth',place.truth)}</div></div><div class="actions"><button class="primary">保存草稿</button>${button(t('ui.m126'),'publish',{index:place.index})}${state.published[String(place.index)]?button('向玩家揭示','location-reveal',{index:place.index}):''}</div></form><h3>通路与门</h3><div class="actions">${doors}</div>${groundItems(place.index,true)}<h3>库存</h3>${stock||'<p class="muted">无固定物品</p>'}${place.index===4?button('首次生成铜锅盘','generate',{kind:'pots'}):''}${place.index===7?button('首次生成鼠帮人数','generate',{kind:'rats'}):''}${roomRoster(place.index,true)}${discoveryControls(place.index)}${keeperSceneMenu(place.index)}`,'private')}</div><aside>${panel('地点索引',`<div class="stack">${Object.values(state.allLocations).map(x=>button(`${String(x.index).padStart(2,'0')} ${escape(x.name)}`,'select-location',{index:x.index},x.index===place.index?'primary':'')).join('')}</div>`)}</aside></div>`;
}

function libraryGroups(){
  if(!libraryCache||libraryCache.key!==libraryKey())return [];
  const {admin,bundle,contracts,view}=libraryCache;
  const groups=[{id:'configurations',label:'配置定义',value:admin.configurations},{id:'rules',label:'规则与流程',value:bundle.sources}];
  const labels={items:'物品',locations:'地点定义',presets:'角色预设',npcs:'NPC 模板',encounters:'遭遇表',loot:'战利品',actions:'场景行动',knowledge:'场景知识',rules:'规则参数',playerKnowledge:'个人知识定义'};
  for(const [file,data] of Object.entries(bundle.data||{})){
    if(data&&typeof data==='object'&&!Array.isArray(data)){
      const notes={};
      for(const [key,value] of Object.entries(data)){if(value&&typeof value==='object')groups.push({id:'data:'+file+':'+key,label:labels[key]||file+' / '+key,value,source:file+' / '+key});else notes[key]=value;}
      if(Object.keys(notes).length)groups.push({id:'data:'+file+':about',label:({'game.json':'游戏说明','scene-actions.json':'场景说明'}[file]||file+' 说明'),value:notes});
    }else groups.push({id:'data:'+file,label:file,value:data});
  }
  groups.push({id:'room-scenes',label:'房间场景',value:{locations:state.allLocations,doors:state.doors,published:state.published,sceneKnowledge:state.sceneKnowledge}},
    {id:'contracts',label:'类型与接口',value:contracts},{id:'entities',label:'活动实例',value:view.entities},
    {id:'relations',label:'关系与进度',value:{relations:view.relations,progress:view.progress,waits:view.waits}},
    {id:'members-assets',label:'成员与素材',value:{members:admin.members,assets:admin.assets}},
    {id:'package',label:'包信息',value:bundle.manifest});
  return groups;
}
function libraryRows(value){
  if(Array.isArray(value))return value.map((value,index)=>[String(index+1),value]);
  if(value&&typeof value==='object')return Object.entries(value);
  return [['值',value]];
}
function libraryContent(){
  const groups=libraryGroups();if(!groups.length)return libraryError?`<p role="alert">${escape(libraryError)}</p>${button('重试','library-refresh')}`:empty('加载资料…');
  const group=groups.find(g=>g.id===libraryTab)||groups[0];libraryTab=group.id;
  const types=group.id==='configurations'?[...new Set(Object.values(group.value).map(c=>c.typeRef))]:[];
  const rows=libraryRows(group.value).filter(([,v])=>group.id!=='configurations'||!libraryType||v.typeRef===libraryType).map(([id,value])=>{const obj=value&&typeof value==='object'?value:{};const name=obj.name||obj.label||obj.configurationId||obj.id||id;const summary=typeof value==='string'?value:typeof value!=='object'?String(value):obj.description||obj.hint||obj.process||obj.typeRef||Object.keys(obj).join(' · ');return {id,name,summary,value};}).filter(r=>!libraryQuery||JSON.stringify(r).toLocaleLowerCase().includes(libraryQuery.toLocaleLowerCase()));
  const tabs=`<nav class="library-tabs" role="tablist" aria-label="资料类型">${groups.map(g=>`<button type="button" role="tab" aria-selected="${g.id===group.id}" data-action="library-tab" data-args="${escape(JSON.stringify({id:g.id}))}">${escape(g.label)}</button>`).join('')}</nav>`;
  const tools=group.id==='rules'?`<div class="actions">${button(t('ui.m132'),'stage',{},'primary small')}${button(t('ui.m134'),'rules',{},'small')}${button(t('ui.m135'),'tables',{},'small')}${select('规则版本','library-revision',state.ruleRevisions.map(r=>[r,r]),state.catalog.rulesetRevision)}${button(t('ui.m137'),'library-revision',{},'small')}${button(t('ui.m138'),'library-activate',{},'small')}</div>`:'';
  return tabs+`<section class="panel library-content" role="tabpanel" aria-label="${escape(group.label)}"><div class="library-toolbar"><strong>${escape(group.label)} · ${rows.length}</strong>${types.length?select('配置类型','library-type',[['','全部'],...types.map(type=>[type,type])],libraryType):''}<input type="search" name="library-search" aria-label="搜索资料" placeholder="搜索资料" value="${escape(libraryQuery)}"></div>${tools}<div class="library-table"><table><thead><tr><th>名称</th><th>概要</th><th>操作</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${escape(r.name)}</td><td class="library-summary"><span>${escape(r.summary)}</span></td><td>${button('查看','library-detail',{group:group.id,id:r.id},'small')}</td></tr>`).join('')||'<tr><td colspan="3">没有匹配资料</td></tr>'}</tbody></table></div></section>`;
}
function libraryPage(){
  if(!libraryCache||libraryCache.key!==libraryKey())queueMicrotask(loadLibrary);
  return heading('P12',t('ui.m129'),button('刷新资料','library-refresh',{},'small')+button(t('ui.m131'),'export',{},'small'))+'<div id="library-browser">'+libraryContent()+'</div>';
}
async function loadLibrary(force=false){
  if(state?.role!=='kp'||libraryLoading||!force&&libraryCache?.key===libraryKey())return;
  const key=libraryKey();libraryLoading=true;libraryError='';
  try{
    const [admin,bundle,contracts,view]=await Promise.all([api('api/v1/admin'),api('package/bundle'),api('api/v1/contracts'),api('api/v1/view')]);
    if(state?.role==='kp'&&key===libraryKey())libraryCache={key,admin,bundle,contracts,view};
  }catch(e){libraryError=e.message;toast(e.message);}finally{libraryLoading=false;const target=document.querySelector('#library-browser');if(target&&state?.role==='kp'){target.innerHTML=libraryContent();if(key!==libraryKey())queueMicrotask(loadLibrary);}}
}

function sessionPage() {
  return heading('P13',t('ui.m141'))+panel(t('ui.m034'),`<form id="recap-form">${area('拟公开回顾','recapDraft',state.recapDraft)}${area('KP 私密备注','recapPrivate',state.recapPrivate)}<label><input type="checkbox" name="publish">同时发布公开回顾</label><button class="primary">保存回顾</button></form>`);
}

function recapPage() {
  return heading('P14',t('ui.m034'))+panel(t('ui.m145'),`<p style="white-space:pre-wrap">${escape(state.recap||t('recap.empty'))}</p>${mapView(state.locations,state.character?.numbers.location)}<div class="actions">${state.roomStatus==='active'&&state.session.numbers.phase===1?button(t('ui.m096'),'navigate',{path:state.role==='kp'?'gm/console':'play/scene'},'primary'):`<span class="tag">${t('recap.wait')}</span>`}${button(t('ui.m071'),'navigate',{path:'lobby'})}</div>`);
}

async function rawCommand(op,args,existing) {
  const who=chatIdentity(),key=chatPendingKey();
  if(!key)throw Error('请先登录');
  if(chatSending.has(key))throw Error('消息正在发送，请稍候');
  if(!existing&&chatPending())throw Error('上条消息结果未确认，请先核对原消息');
  chatSending.add(key);
  const body=existing?{id:existing.id,operation:existing.operation,args:existing.args}:{id:newId(),operation:'chat',args:{operation:op,input:args}};
  try{
    if(body.operation!=='chat')throw Error('聊天恢复记录无效');
    localStorage.setItem(key,JSON.stringify(body));chatUI.pendingChanged();
    if(webMode)await webMode.flush();
    const result=await api('package/action',body);localStorage.removeItem(key);
    if(who===chatIdentity()){
      actionWake?.postMessage({scope:state.storageScope,chat:true});
      if(['chat.direct.open','chat.channel.create','chat.channel.update'].includes(body.args.operation)){await pollChat();if(result.channelId&&!state?.channels[result.channelId])await pollChat();}
      else pollChat();
    }
    return {result};
  }catch(error){
    if([400,401,403,404,409,422,429].includes(error.status))localStorage.removeItem(key);
    throw error;
  }finally{chatSending.delete(key);if(who===chatIdentity())chatUI.pendingChanged();}
}
async function recoverChat(){
  const saved=chatPending();if(!saved)return;
  const body=JSON.parse(saved),who=chatIdentity();
  await rawCommand(null,null,body);
  if(who===chatIdentity()){chatUI.confirmed(body.args);toast('原消息结果已核对');}
}
function pollChat(){
  if(!state||state.preview)return Promise.resolve();
  if(chatPollRunning){chatPollAgain=true;return chatPollRunning;}
  const who=chatIdentity(),snapshot=channelSnapshot;
  chatPollRunning=(async()=>{
    try{
      const wait=!webMode&&!document.hidden&&leaderPoll(performance.now());
      const previous=chatCursor?.who===who ? chatCursor.version : null;
      const next=await api('package/chat/state'+(playerWindow?'?player=1':''),undefined,
        wait?{'X-Chat-Version':previous||'initial'}:{});
      if(who!==chatIdentity()||next.accountId!==state?.accountId)return;
      if(snapshot!==channelSnapshot&&next.channels){chatCursor=null;chatPollAgain=true;return;}
      chatCursor=next.version?{who,version:next.version}:null;
      if(!next.channels)return;
      if(actionWake&&leaderPoll(performance.now())&&JSON.stringify(next.channels)!==JSON.stringify(state.channels))
        actionWake.postMessage({group:pollScope(),projectionChanged:true});
      chatGeneration++;state={...state,channels:next.channels};chatUI.update(state);await chatUI.poll();
    }catch(error){
      if(who===chatIdentity()&&[401,403].includes(error.status)){
        // Remove previously authorized channel content immediately on revocation.
        chatCursor=null;chatGeneration++;state={...state,channels:{}};chatUI.update(state);
      }
    }finally{
      chatPollRunning=null;lastChatPoll=performance.now();
      if(chatPollAgain){chatPollAgain=false;queueMicrotask(pollChat);}
    }
  })();return chatPollRunning;
}

const paneNames = () => ({clues:t('ui.m008'),records:t('ui.m009')});
function desktopKey(){return 'sv.desktop.'+base.pathname+'.'+state.accountId;}
function restoreDesktop(){
  const key=desktopKey();
  if(desktopAccount===key)return;
  desktopAccount=key;
  try{desktop=JSON.parse(localStorage.getItem(key)||'{}');}catch{desktop={};}
  for(const name of Object.keys(paneNames()))desktop[name]??={open:false,collapsed:false};
  desktop.front??='clues';desktop.seen??=[];desktop.communication??='chat';desktop.notebook??={};
  localAction=null;
}
function saveDesktop(){localStorage.setItem(desktopKey(),JSON.stringify(desktop));}
function unreadEvents(){return (state.events||[]).filter(e=>!desktop.seen.includes(e.account+':'+e.id)).length;}
function unreadMessages(){return Object.values(state.channels||{}).reduce((n,c)=>n+(c.unreadCount||0),0);}
function markEventsRead(){desktop.seen=(state.events||[]).map(e=>e.account+':'+e.id);saveDesktop();}
function settlementStatus(){
  if(!state.automation.enabled)return t('ui.m091');
  if(!state.sceneAutomation?.ready)return '自动结算 · 未就绪';
  if(!state.sceneAutomation.executorOnline)return '自动结算 · 离线待结算';
  const pending=(state.autoSceneTasks||[]).filter(x=>!['completed','cancelled','failed'].includes(x.status)).length;
  return t('ui.m078')+(pending?' · '+pending+' 项待结算':'');
}
function sceneButtons(place){
  if(!state.sceneAutomation?.ready)return `<p class="notice">${t('scene.rulesmissing')}</p>`;
  return (state.sceneActions||[]).map(a=>button(escape(a.label),'scene-action',{id:a.id})).join('');
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
function notificationResult(event){
  const result=event.result||{};
  if(result.failure)return failurePanel(result.failure);
  const lines=event.status==='rejected'?[t('log.rejected')]:result.narrative?.length?result.narrative:[resultText(result)];
  return lines.map(line=>`<p>${escape(line)}</p>`).join('')+
    (event.reason?`<p class="muted">${escape(event.reason)}</p>`:'')+
    (result.stateChanges||[]).map(c=>`<p>${escape(c.label)}：${escape(sceneValue(c.key,c.before))} → ${escape(sceneValue(c.key,c.after))}</p>`).join('');
}
function changeList(changes){return changes.map(c=>`<li><span>${escape(c.key.startsWith('slot')?t('field.slot',{count:Number(c.key.slice(4))}):c.key.startsWith('ticks')?t('effects.ticks',{count:Number(c.key.slice(5))}):fieldName(c.key))}</span><span><del>${escape(['ready','incapacitated'].includes(c.key)?t(c.before?'state.yes':'state.no'):displayValue(c.before))}</del> <b>→ ${escape(['ready','incapacitated'].includes(c.key)?t(c.after?'state.yes':'state.no'):displayValue(c.after))}</b></span></li>`).join('');}
function eventCard(e,compact=false){
  const waiting=['pending','processing'].includes(e.status),denied=e.status==='rejected';
  const label=t(e.status==='processing'?'ui.m095':waiting?'ui.m091':denied?'ui.m093':e.status==='blocked'||e.result?.outcome==='blocked'?'state.blocked':e.status==='approved'?'state.approved':'ui.m092');
  const r=e.result&&typeof e.result==='object'?e.result:{};
  const changes=changeList(e.changes||[]);
  return `<article class="event-card ${waiting?'waiting':denied?'denied':''}" data-event-id="${escape(e.id)}"><div class="event-head"><strong>${escape(e.title)}</strong><span class="tag">${label}</span></div><small class="muted">${new Date(e.time*1000).toLocaleString(locale())} · ${t(e.mode==='kp'?'log.keeper':'ui.m078')}${state.role==='kp'?' · '+escape(e.account):''}</small>${compact?'':`<p class="action-steps">${t('log.submitted')} → ${t(e.mode==='kp'?'log.keeper':'log.rules')} → ${label}</p>`}${e.text&&!compact?'<p>'+escape(e.text)+'</p>':''}${r.failure?failurePanel(r.failure):sceneResult(r)||('passed' in r?diceBlock(r):`<p>${escape(waiting?t('log.waiting'):denied?t('log.rejected'):resultText(r))}</p>`)}${e.reason?`<p class="ruling-reason">${t(waiting?'log.reason':'log.ruling')}：${escape(e.reason)}</p>`:''}${changes?`<ul class="change-list">${changes}</ul>`:!waiting&&!r.failure?`<p class="muted">${t('log.nochanges')}</p>`:''}${!compact&&state.character&&e.receiptId?button(t('ui.m119'),'review',{receiptId:e.receiptId,text:t('log.review',{title:e.title})},'small quiet'):''}${state.role==='kp'?`<div class="actions">${rulingAIButton('event',e.id,e.account)}${button('详情与调试','queue-detail',{kind:'event',id:e.id,account:e.account},'small')}</div>`:''}</article>`;
}
function activityFeed(){
  const events=(state.events||[]).slice().reverse();
  return `<div class="activity-feed">${events.map(e=>eventCard(e)).join('')||empty('还没有行动记录。提交行动后，过程和变化会保存在这里。')}</div>`;
}
function logEntry(e,index){
  const key=e.account+':'+e.id;
  const waiting=['pending','processing'].includes(e.status);
  const label=waiting?t(e.status==='processing'?'ui.m095':'ui.m091'):e.status==='blocked'||e.result?.outcome==='blocked'?t('state.blocked'):e.status==='rejected'?t('ui.m093'):t('ui.m092');
  const open=expandedLogs.has(key)?expandedLogs.get(key):index===0;
  return `<details class="log-entry ${waiting?'waiting':''}" data-log="${escape(key)}" ${open?'open':''}><summary><time>${new Date(e.time*1000).toLocaleTimeString(locale(),{hour:'2-digit',minute:'2-digit'})}</time><strong>${escape(e.title)}</strong><span class="tag">${label}</span></summary><div class="log-details">${eventCard(e,true)}<div class="log-actions">${e.receiptId?button(t('ui.m119'),'review',{receiptId:e.receiptId,text:t('log.review',{title:e.title})},'quiet small'):''}${e.receiptId&&['check','inventory','ready'].includes(state.receipts.find(r=>r.id===e.receiptId)?.operation)?button(t('log.share'),'share',{id:e.receiptId},'quiet small'):''}</div></div></details>`;
}
function updateActivity(){
  const badge=document.querySelector('[data-log-badge]');if(badge&&state)badge.textContent=unreadEvents()||'';
  const target=document.querySelector('#action-feedback');if(!target||!state)return;
  const events=(state.events||[]).slice().reverse().filter(e=>logFilter==='all'||(logFilter==='pending'?['pending','processing'].includes(e.status):e.result?.checks?.length||e.result?.rolled!==undefined));
  const fingerprint=JSON.stringify([events,localAction,logFilter,locale()]);
  if(target.dataset.content===fingerprint)return;
  target.dataset.content=fingerprint;
  const top=target.scrollTop;
  target.innerHTML=`${localAction?.failure?failurePanel(localAction.failure):localAction?`<p class="notice ${localAction.status==='error'?'error':''}">${escape(localAction.text)}</p>`:''}${events.map(logEntry).join('')||empty(t('log.empty'))}`;
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
function notebookPanel(){
  const name=desktop.front==='records'?'records':'clues';
  const expanded=desktop[name].open&&!desktop[name].collapsed;
  return `<aside class="player-notebook ${expanded?'expanded':''}" aria-label="${t('workspace.notebook')}"><header class="notebook-head" data-notebook-drag><button type="button" class="notebook-grip quiet" aria-label="${t('workspace.drag')}" title="${t('workspace.drag')}">⠿</button>${Object.entries(paneNames()).map(([key,label])=>`<button type="button" data-action="notebook-toggle" data-args="${escape(JSON.stringify({name:key}))}" aria-expanded="${expanded&&key===name}" aria-controls="notebook-body" class="${expanded&&key===name?'primary':''}">${label}${key==='records'?` <b data-log-badge>${unreadEvents()||''}</b>`:''}</button>`).join('')}</header><div id="notebook-body" class="notebook-body pane-${name}" ${expanded?'':'hidden'}>${expanded?(name==='records'?`<header class="column-head"><h2>${t('ui.m009')}</h2>${select(t('log.filter'),'log-filter',[['all',t('log.all')],['pending',t('log.pending')],['checks',t('ui.m051')]],logFilter)}${button(t('chat.read'),'events-read',{},'small')}</header><section id="action-feedback" aria-live="polite"></section>`:paneContent('clues')):''}</div></aside>`;
}
function workspacePage(){
  const ai=desktop.communication==='ai';
  return `<div class="workspace-toolbar"><nav class="workspace-tabs" aria-label="${t('nav.workspace')}">${[['character',t('workspace.character')],['scene',t('scene.mapactions')],['communication',t('workspace.communication')]].map(([column,label])=>button(label,'workspace-column',{column},mobileColumn===column?'primary small':'small')).join('')}</nav></div><div id="scene-desktop" data-column="${mobileColumn}"><section class="character-column workspace-column" aria-label="${t('workspace.character')}"><section class="resident-status"><h2>${t('ui.m006')}</h2>${paneContent('status')}</section><section class="resident-inventory"><h2>${t('ui.m007')}</h2>${paneContent('inventory')}</section></section><section class="scene-column workspace-column" aria-label="${t('scene.mapactions')}">${scenePage()}</section><section class="communication-column workspace-column" aria-label="${t('workspace.communication')}"><div class="communication-tabs" role="tablist" aria-label="${t('workspace.communication')}">${[['chat',t('chat.title')],['ai',t('ai.title')]].map(([tab,label])=>`<button role="tab" id="comm-tab-${tab}" aria-selected="${(tab==='ai')===ai}" aria-controls="comm-${tab}" tabindex="${(tab==='ai')===ai?0:-1}" data-action="communication-tab" data-args="${escape(JSON.stringify({tab}))}">${label}</button>`).join('')}</div><div id="comm-chat" class="communication-body" role="tabpanel" aria-labelledby="comm-tab-chat" ${ai?'hidden':''}><section id="chat-column" aria-label="${t('chat.title')}"></section></div><div id="comm-ai" class="communication-body" role="tabpanel" aria-labelledby="comm-tab-ai" ${ai?'':'hidden'}><div id="player-ai-embedded"></div></div></section></div>${notebookPanel()}`;
}
function communicationTab(tab){
  desktop.communication=tab;saveDesktop();
  document.querySelectorAll('.communication-tabs [role=tab]').forEach(node=>{const active=node.id==='comm-tab-'+tab;node.setAttribute('aria-selected',String(active));node.tabIndex=active?0:-1;});
  for(const name of ['chat','ai']){const body=document.querySelector('#comm-'+name);if(body)body.hidden=name!==tab;}
}
function positionNotebook(){
  const node=document.querySelector('.player-notebook');if(!node||!desktop)return;
  const rect=node.getBoundingClientRect(),pos=desktop.notebook;
  const x=Number.isFinite(pos.x)?pos.x:20,y=Number.isFinite(pos.y)?pos.y:document.querySelector('#main').getBoundingClientRect().top+4;
  node.style.left=Math.max(8,Math.min(x,innerWidth-rect.width-8))+'px';
  node.style.top=Math.max(8,Math.min(y,innerHeight-rect.height-8))+'px';
}
let suppressNotebookClick=false;
document.addEventListener('pointerdown',event=>{
  const head=event.target.closest('[data-notebook-drag]');if(!head||event.button!==0)return;
  const node=head.closest('.player-notebook'),rect=node.getBoundingClientRect();
  notebookDrag={id:event.pointerId,node,head,startX:event.clientX,startY:event.clientY,x:rect.x,y:rect.y,moved:false};
});
document.addEventListener('pointermove',event=>{
  const drag=notebookDrag;if(!drag||event.pointerId!==drag.id)return;
  const dx=event.clientX-drag.startX,dy=event.clientY-drag.startY;
  if(!drag.moved&&Math.hypot(dx,dy)<5)return;
  drag.moved=true;drag.head.setPointerCapture(drag.id);event.preventDefault();
  desktop.notebook={x:drag.x+dx,y:drag.y+dy};positionNotebook();
});
function finishNotebookDrag(event){
  const drag=notebookDrag;if(!drag||event.pointerId!==drag.id)return;
  if(drag.moved){const r=drag.node.getBoundingClientRect();desktop.notebook={x:r.x,y:r.y};saveDesktop();suppressNotebookClick=true;setTimeout(()=>suppressNotebookClick=false,0);}
  notebookDrag=null;
}
document.addEventListener('pointerup',finishNotebookDrag);
document.addEventListener('pointercancel',finishNotebookDrag);
document.addEventListener('click',event=>{if(suppressNotebookClick&&event.target.closest('.player-notebook')){event.preventDefault();event.stopImmediatePropagation();}},true);
document.addEventListener('keydown',event=>{
  if(event.target.matches('.notebook-grip')&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)){
    event.preventDefault();const r=event.target.closest('.player-notebook').getBoundingClientRect(),step=event.shiftKey?40:10;
    desktop.notebook={x:r.x+(event.key==='ArrowLeft'?-step:event.key==='ArrowRight'?step:0),y:r.y+(event.key==='ArrowUp'?-step:event.key==='ArrowDown'?step:0)};positionNotebook();saveDesktop();
  }else if(event.target.matches('.communication-tabs [role=tab]')&&['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){
    event.preventDefault();const tab=event.key==='Home'?'chat':event.key==='End'?'ai':desktop.communication==='ai'?'chat':'ai';communicationTab(tab);document.querySelector('#comm-tab-'+tab).focus();
  }
});
window.addEventListener('resize',positionNotebook);

function requestDescription(r){
  const a=r.args.input||r.args;
  const kind={scene:'场景预设',travel:'移动',check:'检定',inventory:t('request.item'),transfer:'转交',review:'复核',free:t('ui.m049'),interact:'场景互动'}[r.kind]||r.kind;
  const detail=r.kind==='scene'?((state.sceneDefinitions||[]).find(x=>x.id===a.action)?.choices.find(c=>c.id===a.choice)?.label||a.choice):r.kind==='check'?`${fieldName(a.attribute)} · ${{normal:t('ui.m082'),advantage:t('ui.m083'),disadvantage:t('ui.m084')}[a.mode]||''}`:r.kind==='inventory'?`${{move:'移动',use:'使用',drop:'丢弃',light:t('ui.m121'),extinguish:t('ui.m122')}[a.operation]||a.operation} · 槽位 ${a.slot}${a.operation==='move'?' → '+a.value:''}`:r.kind==='travel'?'前往 '+(state.allLocations?.[String(a.destination)]?.name||a.destination):r.kind==='transfer'?`槽位 ${a.slot} → ${state.team.find(t=>t.account===a.targetAccount)?.name||a.targetAccount} 的槽位 ${a.destination}`:'';
  return `${kind}${detail?' · '+detail:''}`;
}
function rulingQueue(){
  return state.requests.filter(r=>r.status==='pending').map(r=>compactQueue(r.time,r.account,requestDescription(r)+(r.failure?' · '+r.failure.reason:r.text?' · '+r.text:''),'console-request',{id:r.id},(['check','inventory','travel','transfer','scene'].includes(r.kind)?button('执行','ruling-execute',{id:r.id},'primary small'):'')+button('处理','console-request',{id:r.id},'small')+(!['check','inventory','travel','transfer','scene'].includes(r.kind)?button('拒绝','ruling-decline',{id:r.id},'small'):'')+rulingAIButton('request',r.id),`data-request-id="${escape(r.id)}"`)).join('');
}
function archivedRulings(){
  const requests=state.requests.filter(r=>r.status!=='pending').map(r=>({time:r.time,type:'玩家行动',source:r.account,summary:requestDescription(r)+(r.text?' · '+r.text:''),status:r.status,args:{kind:'request',id:r.id},attrs:'data-archived-request="'+escape(r.id)+'"'}));
  const drafts=Object.values(state.drafts||{}).filter(d=>['approved','rejected'].includes(d.status)).map(d=>({time:d.time,type:'角色申请',source:d.account,summary:d.name,status:d.status,args:{kind:'draft',id:d.account},attrs:'data-archived-draft="'+escape(d.account)+'"'}));
  return [...requests,...drafts].sort((a,b)=>(b.time||0)-(a.time||0)).map(r=>rulingCard({time:queueTime(r.time),timestamp:r.time,type:r.type,source:r.source,summary:escape(r.summary),state:({approved:'已接受',rejected:'已拒绝',automatic:'已自动执行',cancelled:'已取消'}[r.status]||r.status),attrs:r.attrs,actions:button('查看详情','queue-detail',r.args)+rulingAIButton(r.args.kind,r.args.id,r.source)})).join('');
}
function rulingResolutionFields(kind){
  if(kind==='check')return select('属性','resolution-attribute',[['str',fieldName('str')],['dex',fieldName('dex')],['wil',fieldName('wil')]],'dex')+select('模式','resolution-mode',[['normal','普通'],['advantage','优势'],['disadvantage','劣势']],'normal');
  if(kind==='damage')return field('伤害（减甲前）','resolution-amount',1,'number')+select('溢出属性','resolution-attribute',[['str',fieldName('str')],['dex',fieldName('dex')]],'str');
  if(kind==='rest')return select('休息','resolution-kind',[['short','短休'],['long','长休'],['full','完整休整']],'short')+select('恢复属性','resolution-attribute',[['str',fieldName('str')],['dex',fieldName('dex')],['wil',fieldName('wil')]],'str');
  if(kind==='grant')return select('物品','resolution-item',Object.entries(state.items).map(([id,x])=>[id,x.name]))+field('起始槽位','resolution-slot',5,'number');
  return '';
}
function rulingResolution(data){
  const operation=data.get('resolution');if(!operation)return undefined;
  const get=name=>data.get('resolution-'+name);
  const input=operation==='check'?{attribute:get('attribute'),mode:get('mode')}:operation==='damage'?{amount:number(get('amount')),attribute:get('attribute')}:operation==='rest'?{kind:get('kind'),attribute:get('attribute')}:{item:number(get('item')),slot:number(get('slot')),uses:state.items[get('item')].uses};
  return {operation,input};
}
function rulingDetail(){
  const r=state.requests.find(r=>r.id===selectedRequest&&r.status==='pending');
  if(!r)return '';selectedRequest=r.id;
  const actor=state.characters.find(c=>c.instanceId===r.actor),mechanical=['check','inventory','travel','transfer','scene'].includes(r.kind);
  return `<h3>${escape(requestDescription(r))}</h3><p>${escape(actor?.name||r.account)} · ${escape(state.allLocations[String(r.location)]?.name||'')}</p><p class="full-request">${escape(r.text||'')}</p>${r.failure?failurePanel(r.failure):''}<input type="hidden" name="requestId" value="${escape(r.id)}">${select('决定','approve',[['yes','批准'],['no','拒绝']],'yes')}${!mechanical?select('执行动作','resolution',[['','仅回复'],['check','属性检定'],['damage','伤害结算'],['rest','休息恢复'],['grant','授予物品']],'')+'<div data-resolution-fields></div>':''}<details data-ruling-reply="${escape(r.id)}" ${replyOpen.has(r.id)?'open':''}><summary>回复（可选）</summary>${area('回复内容','reason')}</details><button class="primary" type="submit" data-ruling-submit>${mechanical?'批准并执行':'批准并回复'}</button>${rulingAIButton('request',r.id)}${rulingDebugTools('request',r.id)}`;
}
function roomNetworkPanel(){
  const n=state.network;if(!n)return '';
  const status=p=>({online:t('ui.m153'),stale:t('ui.m155'),offline:t('ui.m154')}[p.status]);
  const rows=n.players.map(p=>`<tr><td>${escape(p.name)}</td><td>${escape(p.character||'尚未建角')}</td><td><span class="tag">${status(p)}</span></td></tr>`).join('');
  const diagnostics=n.players.map(p=>`<tr><td>${escape(p.accountId)}</td><td>${p.pages}</td><td>${p.ips.map(escape).join('、')||'—'}</td><td>${p.lastSeen?new Date(p.lastSeen*1000).toLocaleTimeString():'—'}</td></tr>`).join('');
  const visits=n.visits.slice(-8).reverse().map(v=>`<li>${new Date(v.time*1000).toLocaleTimeString()} · ${escape(v.ip)} · ${escape(v.kind)} · HTTP ${v.status}</li>`).join('');
  return `<section class="panel room-network" id="room-network"><h2>连接与成员</h2>${webMode?'<p class="notice">请让其他成员通过平台房间代号加入。</p>':`<label>玩家连接地址<input id="room-url" readonly value="${escape(n.url)}"></label>${button(t('ui.m055'),'copy-room-address',{},'small')}${n.bind==='127.0.0.1'?'<p class="notice">仅本机可访问</p>':''}`}<table aria-label="连线玩家"><thead><tr><th>玩家</th><th>角色</th><th>状态</th></tr></thead><tbody>${rows}</tbody></table><details id="room-visits" ${roomVisitsOpen?'open':''}><summary>连接排查</summary><p>房间 ${escape(state.roomId)} · 版本 ${escape(n.version)} · 监听 ${escape(n.bind)}:${n.port} · 在线心跳窗口30秒</p><table><thead><tr><th>账号</th><th>页面</th><th>来源IP</th><th>最后心跳</th></tr></thead><tbody>${diagnostics}</tbody></table><ul>${visits||'<li>暂无访问记录</li>'}</ul></details></section>`;
}
function consolePage(){
  const pending=state.requests.filter(r=>r.status==='pending').length;
  const drafts=Object.values(state.drafts).filter(d=>d.status==='submitted');
  const controls=`<div class="console-controls">${link('房间总览与开场','gm/room')}</div>`;
  let content='';
  content=`<div class="console-columns"><div>${panel(t('ui.m103'),charactersTable())}${panel(t('ui.m104'),`<div class="actions">${button('掷遭遇检查','generate',{kind:'encounter'})}${button('抽取遭遇内容','generate',{kind:'encounter-table'})}${button('反应骰','generate',{kind:'reaction'})}${button('战利品骰','generate',{kind:'loot'})}${button('角色伤害','damage')}${button('创建生物','npc-create')}</div>${(state.npcs||[]).map(n=>`<div class="row"><span>${escape(n.name)} · ${fieldName('hp')} ${n.numbers.hp}/${n.numbers.maxHp}</span><div>${button(t('ui.m112'),'damage',{actor:n.instanceId},'small')}${button(t('ui.m113'),'morale',{actor:n.instanceId},'small')}${button(t('ui.m109'),'actor-edit',{id:n.instanceId},'small')}</div></div>`).join('')}`)}</div><aside>${panel(t('queue.characterApproval'),`<p>${drafts.length} 项待审核</p>${button(t('queue.open'),'navigate',{path:'gm/rulings'},'primary')}`)}</aside></div>`;
  return heading('P09',t('ui.m019'))+`<section class="kp-console">${controls}<div class="console-content">${content}</div></section>`;
}

function updateRoomNetwork(){
  const overview=document.querySelector('#room-overview');
  if(overview&&!overview.contains(document.activeElement)){
    const template=document.createElement('template');template.innerHTML=roomOverview();overview.replaceWith(template.content.firstElementChild);
  }
  const panel=document.querySelector('#room-network');
  if(!panel||panel.contains(document.activeElement))return;
  const template=document.createElement('template');template.innerHTML=roomNetworkPanel();
  if(template.content.firstElementChild)panel.replaceWith(template.content.firstElementChild);
}


const actions = {
  'knowledge-ruling':({account})=>{
    const character=state.characters.find(c=>c.owner===account);
    if(!state.characters.length)return toast('当前没有可接收揭示的已审核角色');
    const places=Object.values(state.published),index=places.find(p=>p.index===character?.numbers.location)?.index||places[0]?.index;
    if(!index)return toast('请先发布可揭示的地点');
    const choices=index=>(state.sceneKnowledge||[]).filter(c=>c.location===Number(index)).map(c=>`<label><input type="checkbox" name="knowledge" value="${escape(c.id)}">${escape(c.title)}</label>`).join('');
    openDialog('执行信息揭示',`${select('接收玩家','knowledge-ruling-account',[['','请选择玩家'],...state.characters.map(c=>[c.owner,c.name+' · '+c.owner])],character?.owner||'')}${select('地点','knowledge-ruling-location',places.map(p=>[p.index,p.name]),index)}<p>将向所选玩家揭示该地点当前的公开描述。</p><details><summary>附加线索</summary><div data-disclosure-choices>${choices(index)}</div></details>`,data=>{const recipient=data.get('knowledge-ruling-account');if(!state.characters.some(c=>c.owner===recipient))throw Error('请选择接收玩家');return perform('location.reveal',{index:number(data.get('knowledge-ruling-location')),accounts:[recipient],knowledge:data.getAll('knowledge')});},'执行揭示');
    dialog.querySelector('[name=knowledge-ruling-location]').onchange=e=>{dialog.querySelector('[data-disclosure-choices]').innerHTML=choices(e.target.value);};
  },
  'topbar-toggle':()=>{requestAnimationFrame(positionNotebook);const folded=document.body.classList.toggle('topbar-collapsed');localStorage.setItem('sv.desktop.topbar.'+base.pathname+'.'+state.accountId,folded?'1':'0');const b=document.querySelector('.topbar-toggle');b.setAttribute('aria-expanded',String(!folded));b.setAttribute('aria-label',t(folded?'nav.expandTop':'nav.collapseTop'));b.title=t(folded?'nav.expandTop':'nav.collapseTop');b.textContent=folded?t('nav.expandTop')+' ▾':'▴';},
  'communication-tab':({tab})=>communicationTab(tab),
  'notebook-toggle':({name})=>{if(dirtyForm)return toast(t('status.savefirst'));const was=desktop.front===name&&desktop[name].open&&!desktop[name].collapsed;for(const key of Object.keys(paneNames()))desktop[key].open=false;desktop[name]={open:!was,collapsed:false};desktop.front=name;saveDesktop();renderPage();},
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
  'ai-assistant':()=>{if(state.role==='kp'){location.hash='/gm/rulings';return;}if(route()==='play/scene'){communicationTab('ai');actions['workspace-column']({column:'communication'});return;}openDialog(t('ai.title'),'<div id="player-ai-embedded"></div>',null,'','AI');embeddedAI.mount(dialog.querySelector('#player-ai-embedded'),{base,account:state.accountId,scope:state.storageScope,renderReference:renderPackageReference});},
  'open-chat':()=>chatUI.open(),
  'copy-room-address':async()=>{
    const input=document.querySelector('#room-url');
    try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(input.value);return toast('玩家地址已复制');}}catch{}
    input.focus();input.select();
    toast(document.execCommand('copy')?'玩家地址已复制':'请复制已选中的玩家地址');
  },
  'scene-action':({id})=>{
    const a=state.sceneActions.find(x=>x.id===id);
    openDialog(a.label,`<p>${escape(a.hint)}</p>${select(t('scene.choose'),'scene-choice',a.choices.map(c=>[c.id,c.label]),a.choices[0].id)}<div id="scene-process" class="notice">${escape(a.choices[0].process)}</div>${select(t('ui.m077'),'ruling',[['auto',t('scene.auto')],['manual',t('ui.m079')]],'auto')}`,data=>{
      const choice=a.choices.find(c=>c.id===data.get('scene-choice'));
      return perform('scene.action',{action:id,choice:choice.id,eventVersion:choice.eventVersion,manual:data.get('ruling')==='manual'});
    },t('scene.execute'),'S18');
    dialog.dataset.sceneAction=id;
  },
  'events-read':()=>{markEventsRead();renderPage();},
  'console-tab':({tab})=>{if(dirtyForm)return toast('请先保存当前表单。');location.hash=tab==='control'?'/gm/console':'/gm/rulings';renderPage();},
  'ruling-ai':async args=>{if(dirtyForm&&dirtyForm!=='ruling-form')throw Error(t('status.savefirst'));const result=await perform('ai.review',args);rulingPane='ai';location.hash='/gm/rulings';renderPage();embeddedAI.openSession(result.sessionId);},
  'queue-tab':({tab})=>{if(!['messages','rulings','archived'].includes(tab))return;queueTab=tab;document.querySelector('#message-queue-list').hidden=tab!=='messages';document.querySelector('#ruling-queue-list').hidden=tab==='messages';document.querySelector('[data-pending-rulings]').hidden=tab==='archived';document.querySelector('#keeper-archived-rulings').hidden=tab!=='archived';embeddedAI.setArchived(tab==='archived');updateKeeperQueue();document.querySelectorAll('[data-action=queue-tab]').forEach(b=>b.setAttribute('aria-selected',String(JSON.parse(b.dataset.args).tab===tab)));},
  'queue-refresh':async()=>{await refresh(false);updateKeeperQueue();await embeddedAI.refreshQueue();},
  'ruling-history':()=>{const content=activityFeed();if(!embeddedAI.queueHistory(content))openDialog('裁决与行动记录',content,null);},
  'ruling-notice':({id})=>{const n=rulingNotices().find(x=>x.id===id);if(!n)return;openDialog('执行结果与定位',`<p>${escape(n.title)}</p><p class="notice ${['failed','rejected','blocked','unknown','partial','rolled_back'].includes(n.status)?'error':''}">${escape(n.reason)}</p>${batchDetailsHTML(n.batch||{})}<pre class="data-detail">${escape(JSON.stringify({room:state.storageScope,account:state.accountId,time:new Date(n.time).toISOString(),status:n.status,...n.locator},null,2))}</pre><p>按以上原裁决／请求定位核对记录；结果未知时请查询原回执。</p>${button('复制定位','notice-copy',{id})}${n.locator?.rulingId?button('打开原裁决','notice-source',{id}):''}`,null);},
  'notice-copy':async({id})=>{const n=rulingNotices().find(x=>x.id===id);if(!n)return;const text=JSON.stringify({room:state.storageScope,account:state.accountId,...n.locator});try{await navigator.clipboard.writeText(text);toast('定位已复制');}catch{const input=document.createElement('textarea');input.readOnly=true;input.value=text;input.setAttribute('aria-label','可复制的结果定位');dialog.append(input);input.select();}},
  'notice-source':async({id})=>{const n=rulingNotices().find(x=>x.id===id);closeDialog();await embeddedAI.openRulingSource(n.locator);},
  'ruling-reference':copyRulingReference,
  'ruling-export':exportRulingDebug,
  'ruling-execute':({id})=>dirtyForm?toast(t('status.savefirst')):perform('resolve',{requestId:id,approve:true,reason:''}),
  'ruling-pane':({pane})=>{rulingPane=pane;const grid=document.querySelector('.rulings-grid');if(grid)grid.dataset.pane=pane;document.querySelectorAll('.ruling-switch button').forEach(b=>b.classList.toggle('primary',JSON.parse(b.dataset.args).pane===pane));},
  'library-tab':({id})=>{libraryTab=id;libraryQuery='';document.querySelector('#library-browser').innerHTML=libraryContent();},
  'library-refresh':()=>loadLibrary(true),
  'library-detail':({group,id})=>{const value=libraryRows(libraryGroups().find(g=>g.id===group)?.value).find(r=>r[0]===id)?.[1];const shown=renderPackageReference({kind:'data',value:{data:value}});openDialog('资料详情',shown?'<div data-reference-view></div>':`<pre class="data-detail">${escape(typeof value==='string'?value:JSON.stringify(value,null,2))}</pre>`,null);if(shown)dialog.querySelector('[data-reference-view]').append(shown);},
  'library-activate':()=>actions['rules-activate']({revision:document.querySelector('[name=library-revision]').value}),
  'library-revision':()=>actions['rules-preview']({revision:document.querySelector('[name=library-revision]').value}),
  'queue-detail':queueDetail,
  'console-request':({id})=>{if(dirtyForm)return toast('请先完成当前裁决。');selectedRequest=id;replyOpen.delete(id);const body=rulingDetail();if(!body)return toast('该申请已处理。');openDialog('裁决详情',body,null);dialog.querySelector('form').id='ruling-form';},
  'ruling-decline':args=>{if(dirtyForm)return toast('请先完成当前裁决。');actions['console-request'](args);const select=dialog.querySelector('[name=approve]');if(select){select.value='no';select.dispatchEvent(new Event('change',{bubbles:true}));}},
  'automation-console':()=>actions.automation({enabled:!state.automation.enabled}),
  close:closeDialog,
  navigate:({path})=>{location.hash='/'+path;},
  initialize:()=>perform('initialize',{}),
  recover:()=>{const body=JSON.parse(localStorage.getItem(pendingKey())); return perform(body.operation,body.args,body);},
  logout:async()=>{await api('api/v1/logout',{});embeddedAI.close();libraryCache=null;projectionCache=null;chatCursor=null;state=null;chatUI.update(null);csrf='';history=[];closeDialog();location.hash='/entry';renderEntry();},
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
  'storm-finish':({route})=>openDialog('确认暴雨结局',area('清点队员并记录每人的去向','roster'),
    data=>perform('storm.finish',{route,roster:data.get('roster')}),'记录结局'),
  start:()=>perform('session.start',{}),
  round:()=>openDialog('推进一个探索回合',`<p>当前为第 ${state.session.numbers.round} 回合。确认后同步更新所有角色的燃烧计时。</p>`,()=>perform('world',{operation:'round',round:state.session.numbers.round}),'推进一次','S12'),
  generate:args=>perform('generate',args),
  'host-flow':args=>perform('host-flow',args),
  approve:args=>perform('approve',args),
  reject:args=>openDialog('退回角色草稿',area('修改建议','reason'),data=>perform('approve',{...args,reject:true,reason:data.get('reason')}),'退回','S10'),
  resolve:args=>{const request=state.requests.find(x=>x.id===args.id);openDialog('主持裁定','<p>'+escape(request.text||request.kind)+'</p><p>'+escape(request.reason||'')+'</p>'+(request.kind==='review'?'<p>复核只记录裁定说明，必要的数值修正请另用主持管理工具执行。</p>':'')+select('决定','approve',[['yes',t('ui.m099')],['no',t('ui.m100')]],'yes')+area('裁定依据','reason'),data=>perform('resolve',{requestId:args.id,approve:data.get('approve')==='yes',reason:data.get('reason')}),'保存裁定','S10');},
  publish:args=>{const p=state.allLocations[String(args.index)];const old=state.published[String(args.index)];openDialog(t('ui.m126'),`<span class="tag">受众 · 已进入或已被揭示的玩家</span><h3>${escape(p.name)}</h3><div class="grid2"><div><h3>当前公开</h3><p>${escape(old?.description||'尚未发布')}</p></div><div><h3>拟发布</h3><p>${escape(p.description)}</p></div></div>${p.clues.map(x=>`<label><input type="checkbox" name="clue" value="${escape(x.id)}" ${old?.clues.some(c=>c.id===x.id)?'checked':''}> ${escape(x.title)}<br>${escape(x.text)}</label>`).join('')}<p class="muted">发布已保存的描述和勾选线索；未进入的玩家仍只见导航占位。可再使用“向玩家揭示”，主持真相保持私密。</p>`,data=>perform('location.publish',{...args,clues:data.getAll('clue')}),'公开此地点','S08');},
  'location-reveal':args=>openDialog('向指定玩家揭示地点',`<p>保存当前已发布内容的固定观察。之后修改地点不会更新这次观察；不会公开主持真相。</p><h3>接收玩家</h3>${state.characters.map(c=>`<label><input type="checkbox" name="account" value="${escape(c.owner)}"> ${escape(c.name)} · ${escape(c.owner)}</label>`).join('')}<h3>额外揭示的已知内容</h3><p class="muted">默认不勾选。勾选会向选中玩家明确披露下方事实，并解锁相关行动；不执行行动，也不改变库存或机关。</p>${(state.sceneKnowledge||[]).filter(c=>c.location===args.index).map(c=>`<label><input type="checkbox" name="knowledge" value="${escape(c.id)}"> ${escape(c.title)}<p>${escape(c.text)}</p></label>`).join('')}`,data=>perform('location.reveal',{index:args.index,accounts:data.getAll('account'),knowledge:data.getAll('knowledge')}),'揭示地点'),
  'knowledge-enable':()=>openDialog('启用个人知识服务',`<p>确认当前安全投影。若投影版本已升级，旧地点及人物观察将保持不可读，需要到地点或人物页明确重新揭示。不会自动重建过去的观察。</p><p>本人角色与公共回合仍按明确的持续告知规则提供。</p>`,()=>perform('knowledge.enable',{}),'确认启用'),
  'knowledge-revoke':args=>openDialog('撤回知识授权','<p>撤回后会复验引用及 AI 历史。若同内容仍有其他有效授权，仍可读取。</p>',()=>perform('knowledge.revoke',args),'撤回授权'),
  'knowledge-import':()=>openDialog('旧地点记录：现在揭示',`<p>旧记录没有当时内容。只对勾选项创建现在的观察；未发布地点需先由 KP 编辑和发布。</p>${Object.entries(state.legacyKnowledge||{}).flatMap(([account,indices])=>indices.map(index=>`<label><input type="checkbox" name="legacy" value="${escape(JSON.stringify({account,index:Number(index)}))}" ${state.published[index]?'':'disabled'}> ${escape(account)} · ${escape(state.allLocations[index]?.name||index)}</label>`)).join('')||'<p>没有待处理的旧地点记录。</p>'}`,data=>perform('knowledge.import-current',{items:data.getAll('legacy').map(JSON.parse)}),'现在揭示所选内容'),
  preview:async args=>{const account=state.members.find(x=>x.role==='player')?.accountId;if(!account)return toast('房间内还没有玩家');const data=await api('package/state?preview='+encodeURIComponent(account));openDialog('玩家公开预览',`<div class="notice">只读 · ${escape(account)} · 包侧公开投影</div>${mapView(data.locations,1)}<p>${escape(data.locations.find(x=>x.index===args.index)?.description||'该地点尚未公开')}</p>`,null,'','S09');},
  damage:args=>openDialog('伤害与豁免',select('目标','actor',[...actorOptions(),...(state.npcs||[]).map(x=>[x.instanceId,x.name])],args.actor)+field('伤害骰最终值（减甲前）','amount',1,'number')+select('溢出扣减属性','attribute',[['str',fieldName('str')],['dex',fieldName('dex')]],'str'),data=>perform('damage',{actor:data.get('actor'),amount:number(data.get('amount')),attribute:data.get('attribute')}),'确认结算','S11'),
  grant:args=>openDialog(t('ui.m110'),select('物品','item',Object.entries(state.items).map(([id,x])=>[id,x.name]),1)+field('起始槽位（1–10，超载11–20）','slot',5,'number'),data=>{const item=number(data.get('item'));return perform('grant',{actor:args.actor,item,slot:number(data.get('slot')),uses:state.items[String(item)].uses});},'授予','S01'),
  rest:args=>openDialog('主持确认休息',select('休息类型','kind',[['short','短休 · 一探索轮'],['long','长休 · 吃饭与睡眠'],['full','完整休整 · 安全地一周']],'short')+select('长休时若 HP 已满，恢复哪项属性','attribute',[['str',fieldName('str')],['dex',fieldName('dex')],['wil',fieldName('wil')]],'str')+'<p class="muted">确认食物、水、照料及安全条件；恢复不自动推进时间，请另行推进探索轮。</p>',data=>perform('rest',{actor:args.actor,kind:data.get('kind'),attribute:data.get('attribute')}),'执行恢复','S03'),
  'actor-edit':args=>{const c=[...(state.characters||[]),...(state.npcs||[])].find(x=>x.instanceId===args.id);openDialog('主持数值调整',select('字段','key',[['hp',fieldName('hp')],['str',fieldName('str')],['dex',fieldName('dex')],['wil',fieldName('wil')],['armor','护甲'],['pips','钱币'],['xp',fieldName('xp')],['level','等级'],['grit',fieldName('grit')]],'hp')+field('新的数值','value',c.numbers.hp,'number'),data=>perform('actor.update',{id:args.id,numbers:{[data.get('key')]:number(data.get('value'))}}),t('ui.m063'),'S14');},
  room:args=>openDialog('确认房间状态','<p>将房间设为 '+escape(args.status==='paused'?'暂停':'运行')+'。</p>',()=>perform('room',args),t('ui.m062'),'S14'),
  backup:()=>openDialog(t('ui.m143'),'<p>保存宿主房间备份与包侧手记、草稿和请求记录。</p>',()=>perform('backup',{}),'创建备份','S14'),
  rules:()=>openDialog(t('rules.title'),state.rules.map(x=>`<h3>${escape(x.title)}</h3><p>${escape(x.text)}</p><a href="${escape(x.source)}" target="_blank" rel="noreferrer">${t('rules.source')}</a>`).join('<hr>'),null,'','S13'),
  preferences:()=>openDialog(t('ui.m146'),select(t('ui.m147'),'font',[['16',t('ui.m148')],['18',t('ui.m149')],['20',t('ui.m150')]],localStorage.getItem('sv.font')||'16')+`<label><input type="checkbox" name="reduce" ${diceUI.reduced?'checked':''}>${t('preferences.reduce')}</label><label><input type="checkbox" name="dice" ${diceUI.enabled?'checked':''}>${t('dice.preference')}</label><p>${independentLogin()}</p>`,data=>{localStorage.setItem('sv.font',data.get('font'));document.documentElement.style.fontSize=data.get('font')+'px';diceUI.setReduced(data.has('reduce'));diceUI.setEnabled(data.has('dice'));closeDialog();},t('ui.m063'),'S17'),
  export:async()=>{const data=await api('package/bundle');const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='stumpsville-bundle.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);},
  item:({slot})=>{const n=state.character.numbers;const def=state.items[String(n['item'+slot])];openDialog(def.name,`${itemDetailsHTML(def,{uses:n['uses'+slot],maxUses:def.uses})}<div class="actions">${def.uses&&def.kind!=='spell'?button(t('ui.m120'),'use',{slot}):''}${def.kind==='spell'?button(t('spell.request'),'request',{kind:'free',text:t('spell.text',{name:def.name})}):''}${def.light?button(n.litSlot===slot?t('ui.m122'):t('ui.m121'),'light',{slot,operation:n.litSlot===slot?'extinguish':'light'}):''}${button(t('ui.m123'),'move-item',{slot})}${button(t('ui.m124'),'transfer',{slot})}${def.kind!=='condition'?button('丢弃','drop-item',{slot,item:n['item'+slot]}):''}</div>`,null,'','S01');},
  use:({slot})=>openDialog(t('inventory.use'),`<p>${t('inventory.usehelp')}</p>`+rulingMode(),data=>submitAction('inventory',{operation:'use',slot,value:0},data),t('inventory.confirmuse'),'S03'),
  light:({slot,operation})=>perform('inventory',{operation,slot,value:0}),
  'drop-item':({slot,item})=>openDialog('丢弃物品','<p>物品会落在执行时所在场景，保留剩余用量。点燃的光源会熄灭。</p>'+rulingMode(),data=>submitAction('inventory',{operation:'drop',slot,value:item},data),'确认丢弃'),
  'pickup-stock':args=>perform('pickup',{action:args.actionId,choice:args.choice}),
  'pickup-drop':args=>openDialog('拿取物品',field('放入槽位','slot',7,'number'),data=>perform('pickup',{id:args.id,slot:number(data.get('slot'))}),'确认拿取'),
  'take-ground':args=>openDialog('拿取物品',select('接收角色','actor',state.characters.filter(x=>x.numbers.location===args.index).map(x=>[x.instanceId,x.name]))+field('放入槽位','slot',7,'number'),data=>perform('ground.take',{id:args.id,actor:data.get('actor'),slot:number(data.get('slot'))}),'确认领取'),
  'move-item':({slot})=>openDialog(t('inventory.move'),field(t('inventory.destination'),'value',5,'number')+rulingMode(),data=>submitAction('inventory',{operation:'move',slot,value:number(data.get('value'))},data),'移动','S04'),
  transfer:({slot})=>openDialog(t('inventory.transfer'),select(t('inventory.receiver'),'targetAccount',state.team.filter(x=>x.account!==state.accountId).map(x=>[x.account,x.name]))+field(t('inventory.receiverslot'),'destination',5,'number'),data=>perform('request',{kind:'transfer',slot,targetAccount:data.get('targetAccount'),destination:number(data.get('destination')),text:t('transfer.text',{count:slot})}),t('inventory.submit'),'S05'),
  share:({id})=>{const receipt=state.receipts.find(x=>x.id===id);openDialog(t('share.title'),`<p>${escape(resultText(receipt.result))}</p>`+select(t('share.channel'),'channelId',Object.values(state.channels).filter(x=>x.canPost).map(x=>[x.channelId,x.name]),currentChannel)+``,data=>perform('share.receipt',{receiptId:id,channelId:data.get('channelId')}),t('share.submit'),'S06');},
  'channel-create':()=>openDialog(t('ui.m024'),field('频道名称','name')+select('范围','kind',[['room','公共'],['group','分组']],'room')+state.members.filter(x=>x.accountId!==state.accountId).map(x=>`<label><input type="checkbox" name="member" value="${escape(x.accountId)}"> ${escape(x.nickname)}</label>`).join(''),async data=>{const form=dialog.querySelector('form'),who=chatIdentity();await rawCommand('chat.channel.create',{name:data.get('name'),kind:data.get('kind'),...(data.get('kind')==='group'?{participants:[state.accountId,...data.getAll('member')]}:{})});if(form?.isConnected&&who===chatIdentity()){closeDialog();renderPage();toast(t('result.chat'));}},'创建','S06'),
  'door':args=>openDialog('通路状态',select('门或通路','status',[['open','开启'],['closed',t('ui.m058')],['locked','锁住']],state.doors[args.edge]),data=>perform('door',{edge:args.edge,status:data.get('status')}),t('ui.m063'),'S14'),
  'take-stock':args=>openDialog('从地点领取',select('接收角色','actor',state.characters.filter(x=>x.numbers.location===args.index).map(x=>[x.instanceId,x.name]))+field('放入槽位','slot',7,'number'),data=>perform('stock.take',{...args,actor:data.get('actor'),slot:number(data.get('slot'))}),'确认领取','S01'),
  morale:args=>perform('morale',args),
  'npc-create':()=>openDialog('新建主持生物',field('名称','name')+['str','dex','wil','hp','armor','location'].map((x,i)=>field(fieldName(x),x,[9,9,9,3,0,1][i],'number')).join('')+'<p class="muted">默认是SRD通用小鼠，专属角色请按原版输入。</p>',data=>perform('npc.create',{name:data.get('name'),numbers:Object.fromEntries(['str','dex','wil','hp','armor','location'].map(x=>[x,number(data.get(x))]))}),'创建','S10'),
  'tables':()=>openDialog('主持随机表',area('d6 遭遇内容（每行一项，共6行）','encounters',state.encounters.join('\n'))+area('d20 战利品（每行一项，共20行）','loot',state.loot.join('\n')),data=>perform('tables.save',{encounters:data.get('encounters').split('\n'),loot:data.get('loot').split('\n')}),t('ui.m063'),'S14'),
  'stage':()=>{
    const baseRevision=state.catalog.rulesetRevision;
    openDialog('导入与检查','<label>选择规则包 JSON、已声明的数据 JSON 或 Lua 规则<input type="file" id="bundle-file" accept=".json,.lua"></label><p>单文件按文件名合入当前活动修订，检查通过后可预览并激活。</p>',async()=>{
      const f=document.querySelector('#bundle-file').files[0];
      if(!f)throw new Error('请选择配置或规则文件');
      if(f.size>512*1024)throw new Error('配置文件超过本机接口限制');
      const lua=f.name.endsWith('.lua'),raw=await f.text(),value=lua?raw:JSON.parse(raw);
      const args=!lua&&value?.sources&&value?.data?{bundle:value}:{baseRevision,file:(lua?'rules/':'config/')+f.name,value};
      const result=await perform('rules.stage',args);lastStage=result.revision;renderPage();
    },'检查暂存','S14');
  },
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
  if(event.target.name==='library-type'){libraryType=event.target.value;document.querySelector('#library-browser').innerHTML=libraryContent();}
  if(event.target.name==='resolution'){document.querySelector('[data-resolution-fields]').innerHTML=rulingResolutionFields(event.target.value);}
  if(['resolution','approve'].includes(event.target.name)){const form=event.target.form;form.querySelector('[data-ruling-submit]').textContent=form.elements.approve.value==='no'?'拒绝并回复':!form.elements.resolution||form.elements.resolution.value?'批准并执行':'批准并回复';}
  if(event.target.name==='log-filter'){logFilter=event.target.value;updateActivity();}
  if(event.target.name==='scene-choice'){
    const a=state.sceneActions.find(x=>x.id===dialog.dataset.sceneAction);
    document.querySelector('#scene-process').textContent=a.choices.find(c=>c.id===event.target.value).process;
  }
});
document.addEventListener('input',event=>{
  if(event.target.name==='library-search'){libraryQuery=event.target.value;document.querySelector('#library-browser').innerHTML=libraryContent();const search=document.querySelector('[name=library-search]');search.focus();return;}
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
    else if(form.id==='ruling-form'){await perform('resolve',{requestId:data.get('requestId'),approve:data.get('approve')==='yes',reason:data.get('reason'),...(data.get('approve')==='yes'&&data.get('resolution')?{resolution:rulingResolution(data)}:{})});}
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
      actionWake?.postMessage({scope:state.storageScope,completed:true});
    }
    if(ready.jobs.length)pollState();
  }catch(error){
    const label=document.querySelector('#connection');
    if(label)label.textContent='自动执行暂缓 · '+error.message;
  }finally{executorBusy=false;}
}
diceUI.configure(t,event=>{
  const r=event.result||{};
  const check=r.save>0?{attribute:r.attribute,rolled:r.save,first:r.save,target:r.remaining,passed:!r.critical,mode:'normal'}:Number.isFinite(r.rolled)&&Number.isFinite(r.target)?{...r,first:r.first??r.rolled}:null;
  return (check?diceBlock(check):'')+(r.checks||[]).map(check=>`<div class="scene-check"><strong>${escape(check.label)}</strong>${diceBlock(check)}</div>`).join('')+(r.rolls||[]).map(roll=>`<p>${escape(roll.label)} · d${roll.sides} → <strong>${roll.value}</strong></p>`).join('');
});
diceUI.setReduced(diceUI.reduced);
effectsUI.configure(t,changeList,()=>diceUI.presenting,(pane='records')=>{
  for(const key of Object.keys(paneNames()))desktop[key].open=false;
  desktop[pane]={open:true,collapsed:false};desktop.front=pane;saveDesktop();
  if(route()!=='play/scene')location.hash='#/play/scene';else renderPage();
},notificationResult,async notificationId=>{
  if(!state||state.role!=='player')return;
  await api('package/action',{id:'notice-ack-'+notificationId,operation:'notification.ack',args:{notificationId}});
});
let actionWake=null;
const pollingPeers=new Map();
let nextBeacon=0;
const pollScope=()=>state && JSON.stringify([base.pathname,state.storageScope,state.accountId,state.role,locale()]);
function leaderPoll(now){
  if(!state||!actionWake||document.hidden)return true;
  const scope=pollScope();
  if(now>=nextBeacon){
    actionWake.postMessage({pollPeer:pageId,group:scope});
    nextBeacon=now+1000;
  }
  let leader=pageId;
  for(const [id,peer] of pollingPeers){
    if(now-peer.seen>3000)pollingPeers.delete(id);
    else if(peer.scope===scope&&id<leader)leader=id;
  }
  return leader===pageId;
}
if(!webMode&&typeof BroadcastChannel!=='undefined'){
  try{
    actionWake=new BroadcastChannel('stumpsville-action-wake');
    actionWake.onmessage=({data})=>{
      if(data?.pollPeer){
        if(data.group===pollScope()&&pollingPeers.size<256)
          pollingPeers.set(data.pollPeer,{scope:data.group,seen:performance.now()});
      }else if(data?.group && data.group===pollScope() && data.projectionChanged)pollState();
      else if(data?.scope===state?.storageScope){
        if(data.chat)pollChat();else if(data.completed)pollState();else runAutoScenes();
      }
    };
  }catch{}
}
chatUI.configure({api,send:rawCommand,pending:chatPending,recover:recoverChat,toast,t});
if(!webMode&&base.pathname==='/'){
  const bytes=crypto.getRandomValues(new Uint8Array(12));
  const slot='tab-'+Array.from(bytes,x=>x.toString(16).padStart(2,'0')).join('');
  location.replace('/sessions/'+slot+'/'+location.hash);
}else await boot();
async function pollState(){
  if(!state||busy||statePollRunning)return;
  statePollRunning=true;
  try{
    const generation=stateGeneration,chats=chatGeneration;
    const packet=await nextProjection(),next=packet.value;
    if(busy||!state||generation!==stateGeneration)return;
    const priorVersions=projectionCache?.versions;
    if(!priorVersions||priorVersions[3]!==packet.cache?.versions[3])channelSnapshot++;
    projectionCache=packet.cache;
    if(priorVersions&&packet.cache&&leaderPoll(performance.now())&&packet.cache.versions.slice(0,4).some((v,i)=>v!==priorVersions[i]))
      actionWake?.postMessage({group:pollScope(),projectionChanged:true});
    const visual=value=>{const {network,channels,...rest}=value;return JSON.stringify(rest);};
    const changed=packet.changed ?? (visual(next)!==visual(state));
    if(chats!==chatGeneration&&next.accountId===state.accountId&&next.storageScope===state.storageScope)next.channels=state.channels;
    state=next;chatUI.update(state);diceUI.observe(state);effectsUI.observe(state);connection=t('ui.m065');
    const editing=['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)&&!document.activeElement?.readOnly;
    const activityOnly=priorVersions&&packet.cache&&[0,1].every(i=>priorVersions[i]===packet.cache.versions[i])
      &&['gm/rulings','play/scene'].includes(route());
    if(changed&&!activityOnly)renderDeferred=true;
    if(renderDeferred&&!editing&&!dialog.open&&!dirtyForm&&!notebookDrag){renderDeferred=false;renderPage();}
    else if(changed){updateActivity();}
    if(!priorVersions||!packet.cache||priorVersions[4]!==packet.cache.versions[4])updateRoomNetwork();
    if(changed)updateKeeperQueue();
    const queue=document.querySelector('#message-queue-list');
    if(queue){const markup=messageQueue();if(queue._markup!==markup){queue.innerHTML=markup;queue._markup=markup;}}
    const chatBadge=document.querySelector('.chat-badge');if(chatBadge)chatBadge.textContent=unreadMessages()||'';
    await chatUI.poll();
    if(chats===chatGeneration&&!chatCursor)lastChatPoll=performance.now();

    const label=document.querySelector('#connection');if(label)label.textContent=t('ui.m065');
  }catch(error){
    connection=t('ui.m067');
    const label=document.querySelector('#connection');if(label)label.textContent=connection;
    // A failed refresh does not revoke a conversation or erase an in-flight
    // response. Actual authorization failures still clear the previous view.
    if(error.status===401||error.status===403){embeddedAI.close();aiUI.update(null);libraryCache=null;projectionCache=null;chatCursor=null;state=null;chatUI.update(null);csrf='';history=[];closeDialog();renderEntry();}
  }
  finally{statePollRunning=false;lastStatePoll=performance.now();}
}
// Keep executor work independent of full projections and chat history requests.
document.addEventListener('visibilitychange',()=>{if(!document.hidden){pollState();pollChat();runAutoScenes();}});
setInterval(runAutoScenes,500);
setInterval(()=>{
  const settling=state?.autoSceneTasks?.some(task=>['queued','running','finishing'].includes(task.status));
  const leader=leaderPoll(performance.now());
  if(performance.now()-lastStatePoll>=(settling?400:document.hidden?10000:leader?2500:5000))pollState();
  else if(performance.now()-lastChatPoll>=(document.hidden?5000:leader?(chatCursor?200:1000):2500)&&!chatPollRunning)pollChat();
},200);
