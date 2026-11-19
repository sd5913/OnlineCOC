import {mountStyle} from './styles.js';
import {mountChat} from './chat.js';
import {mountAI} from './room-panel.js';
import {mountSessionManager} from './session-manager.js';
import {mountUsage} from './usage.js';

function shell(target){
 const element=document.createElement('div');target.append(element);const root=element.attachShadow({mode:'open'});
 mountStyle(root,new URL('./views.css',import.meta.url));
 return {element,root};
}
function mountView(target,client,options={},full=false){
 const {element,root}=shell(target);const page=document.createElement('section');page.className='ai-view '+(full?'full':'conversation-only');root.append(page);
 page.innerHTML=`<header class="view-header"><strong class="view-title"></strong><span class="identity"></span><button class="review-open" hidden>KP 审核与设置</button></header><p class="view-status" role="status"></p><div class="view-workspace"><aside class="view-sidebar"><strong>本房间的会话</strong><div class="session-list"></div></aside><main><nav class="view-toolbar"><button class="new-chat">新建会话</button><select class="session-select" aria-label="选择会话"><option value="">选择会话</option></select><button class="archived">归档会话</button></nav><div class="view-chat"></div></main></div><dialog><button class="review-close">返回对话</button><div class="view-review"></div></dialog>`;
 const $=selector=>page.querySelector(selector);$('.view-title').textContent=options.title||'房间 AI 助手';
 const management=document.createElement('dialog');management.className='session-dialog';management.innerHTML='<button class="session-close">返回对话</button><div class="session-management"></div>';page.append(management);
 const manage=document.createElement('button');manage.className='manage-sessions';manage.textContent='会话管理';$('.view-toolbar').append(manage);
 const usageDialog=document.createElement('dialog');usageDialog.className='usage-dialog';usageDialog.innerHTML='<button class="usage-close">返回对话</button><div class="usage-container"></div>';page.append(usageDialog);
 const usageButton=document.createElement('button');usageButton.className='usage-open';usageButton.textContent='用量统计';$('.view-header').append(usageButton);
 let usagePanel=null;
 let dead=false,paused=false,chat=null,review=null,sessionManager=null,selectedSession=null,identity='',listKey='';
 async function run(fn){try{$('.view-status').textContent='';await fn();}catch(error){if(!dead)$('.view-status').textContent=error.code||error.message;}}
 function closeReview(){if($('dialog').open)$('dialog').close();review?.destroy();review=null;}
 function closeSessions(resume=true){if(management.open)management.close();sessionManager?.destroy();sessionManager=null;if(resume&&!paused&&!dead)chat?.resume().catch(()=>{});}
 async function manageSessions(){
  ready();if(paused)return;chat.suspend();
  if(!sessionManager)sessionManager=mountSessionManager($('.session-management'),client,{
   onOpen:async id=>{closeSessions(false);await ready().resume({sessionId:id});},
   onChange:session=>run(()=>ready().applySessionChange(session))
  });
  if(!management.open)management.showModal();
  if(selectedSession)await sessionManager.select(selectedSession);
 }
 function closeUsage(){if(usageDialog.open)usageDialog.close();usagePanel?.destroy();usagePanel=null;}
 async function showUsage(){ready();if(paused)return;usagePanel?.destroy();usagePanel=mountUsage($('.usage-container'),client,{sessionId:selectedSession});if(!usageDialog.open)usageDialog.showModal();}
 function disposePanels(){listKey='';closeReview();closeSessions(false);closeUsage();chat?.destroy();chat=null;selectedSession=null;$('.session-list').replaceChildren();$('.session-select').replaceChildren(new Option('选择会话',''));}
 async function openReview(id){
  if(dead||paused||!client.connected||client.view?.role!=='kp')throw new Error('PERMISSION_DENIED');
  if(options.review===false)return;
  if(options.onReview)return options.onReview(id);
  if(!review)review=mountAI(client,{target:$('.view-review'),onReceipt:options.onReceipt});
  if(!$('dialog').open)$('dialog').showModal();
  if(id)await review.review(id);else await review.showBatches();
 }
 function list(items){
  options.onSessions?.(items);
  const key=JSON.stringify(items.map(s=>[s.sessionId,s.title]));if(key===listKey)return;listKey=key;
  const selected=$('.session-select').value;
  $('.session-select').replaceChildren(new Option('选择会话',''),...items.map(s=>new Option(s.title,s.sessionId)));
  if(items.some(s=>s.sessionId===selected))$('.session-select').value=selected;
 }
 function ready(){if(dead||!client.connected||!chat)throw new Error('DISCONNECTED');return chat;}
 function update(){
  if(dead)return;
  const next=JSON.stringify([client.generation,client.connected,client.view?.accountId,client.view?.role,client.view?.authorityEpoch]);
  if(next!==identity){identity=next;disposePanels();}
  $('.identity').textContent=client.connected?(client.view.accountId+' · '+(client.view.role==='kp'?'KP':'PL')):'';
  $('.review-open').hidden=options.review===false||!client.connected||client.view?.role!=='kp';
  $('.view-workspace').hidden=!client.connected;
  if(!client.connected){$('.view-status').textContent='请先登录当前房间。';return;}
  if(!paused&&!chat){
   $('.view-status').textContent='';
   chat=mountChat($('.view-chat'),client,{listTarget:full?$('.session-list'):undefined,
    onChange:list,onReview:options.review===false?null:id=>run(()=>openReview(id)),
    onSelect:session=>{selectedSession=session?.sessionId||null;$('.session-select').value=selectedSession||'';options.onSession?.(session);}});
  }
 }
 $('.new-chat').onclick=()=>run(()=>ready().newChat());$('.archived').onclick=()=>run(async()=>{$('.archived').textContent=await ready().showArchived()?'返回进行中':'归档会话';});
 $('.session-select').onchange=()=>run(()=>$('.session-select').value?ready().select($('.session-select').value):undefined);
 $('.review-open').onclick=()=>run(()=>openReview());$('.review-close').onclick=closeReview;$('dialog').addEventListener('cancel',closeReview);
 usageButton.onclick=()=>run(showUsage);$('.usage-close').onclick=closeUsage;usageDialog.addEventListener('cancel',closeUsage);
 manage.onclick=()=>run(manageSessions);$('.session-close').onclick=closeSessions;management.addEventListener('cancel',closeSessions);
 const unsubscribe=client.subscribe(update);update();
 return {
  refresh:()=>chat?chat.refresh():Promise.resolve(),select:id=>ready().select(id),newChat:()=>ready().newChat(),
  setDraft:(text,references=[])=>ready().setDraft(text,references),insertReference:item=>ready().insertReference(item),
  review:openReview,manageSessions,showUsage,
  suspend(){paused=true;chat?.suspend();closeReview();closeSessions();closeUsage();},
  async resume({sessionId}={}){if(dead)return;const previous=chat;paused=false;update();if(previous===chat)await chat?.resume({sessionId});else if(sessionId)await chat?.select(sessionId);},
  destroy(){dead=true;unsubscribe();disposePanels();element.remove();}
 };
}
/** Full room page: session directory, conversation and optional KP review. */
export function mountAIPage(target,client,options={}){return mountView(target,client,options,true);}
/** Compact conversation page: session selector, composer and optional KP review. */
export function mountAIConversation(target,client,options={}){return mountView(target,client,options,false);}
/** Collapsing preserves drafts but pauses the component's own polling. Client belongs to host. */
export function mountAICollapsible(target,client,options={}){
 const {element,root}=shell(target),section=document.createElement('section');section.className='ai-collapsible';root.append(section);
 const button=document.createElement('button');button.className='collapse-toggle';button.textContent=options.title||'AI 助手';button.setAttribute('aria-expanded','false');
 const body=document.createElement('div');body.className='collapse-body';body.hidden=true;body.id='ai-fold-'+Math.random().toString(36).slice(2);button.setAttribute('aria-controls',body.id);section.append(button,body);
 let panel=null,opened=false,dead=false;
 function open(sessionId){if(dead)return Promise.resolve();opened=true;body.hidden=false;button.setAttribute('aria-expanded','true');
  let loaded;if(!panel){panel=mountAIConversation(body,client,options);loaded=sessionId?panel.select(sessionId):Promise.resolve();}else loaded=panel.resume({sessionId});options.onToggle?.(true);return loaded;
 }
 function close(){if(dead)return;opened=false;body.hidden=true;button.setAttribute('aria-expanded','false');panel?.suspend();options.onToggle?.(false);}
 button.onclick=()=>opened?close():open().catch(()=>{});if(options.open)open().catch(()=>{});
 return {open,close,toggle(){opened?close():open();},get isOpen(){return opened;},
  refresh:()=>opened?panel.refresh():Promise.resolve(),
  select(id){return open(id);},newChat(){open();return panel.newChat();},
  setDraft(text,references=[]){open();panel.setDraft(text,references);},insertReference(item){open();panel.insertReference(item);},
  review(id){open();return panel.review(id);},manageSessions(){open();return panel.manageSessions();},showUsage(){open();return panel.showUsage();},suspend:close,resume({sessionId}={}){return open(sessionId);},
  destroy(){dead=true;panel?.destroy();panel=null;element.remove();}
 };
}
