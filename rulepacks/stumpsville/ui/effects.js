// Only committed, owner-authorized data enters this presenter. No game commands.
const fields=['hp','maxHp','str','dex','wil','strMax','dexMax','wilMax','armor','pips','xp','level','grit','incapacitated','litSlot','conditionPending',...Array.from({length:20},(_,i)=>'ticks'+(i+1))];
const relevant=c=>(fields.includes(c.key)||/^slot([1-9]|1\d|20)$/.test(c.key))&&c.before!==c.after;
export function effectSnapshot(state){
  if(!state.character)return null;
  const n=state.character.numbers,values=Object.fromEntries(fields.map(k=>[k,n[k]??0]));
  for(let slot=1;slot<=20;slot++){
    const id=n['item'+slot],item=state.items?.[id];
    values['slot'+slot]={id:id||0,name:item?.name||String(id),uses:item?.uses?(n['uses'+slot]??0):null};
  }
  return values;
}
export function effectChanges(before,after){
  const label=value=>!value.id?translate('inventory.empty'):value.uses===null?value.name:translate('effects.uses',{item:value.name,count:value.uses});
  return before&&after?Object.keys(after).flatMap(key=>{
    const a=before[key],b=after[key];
    if(key.startsWith('slot'))return a.id===b.id&&a.uses===b.uses?[]:[{key,before:label(a),after:label(b)}];
    return a===b?[]:[{key,before:a,after:b}];
  }):[];
}
let translate,renderChanges,renderResult=()=>'',acknowledge=async()=>{},busy,openLog,popup,timer,expiry,fade,scope='',seen=new Set(),knownClues=new Set(),snapshot=null,queue=[];
let notificationKey='',presented=new Set(),queuedNotices=new Set(),acking=new Set();
function acknowledgeNotice(id){const pending=acking;if(pending.has(id))return;pending.add(id);Promise.resolve().then(()=>acknowledge(id)).catch(()=>{}).finally(()=>pending.delete(id));}
function presentedNotice(id){
  presented.add(id);
  try{localStorage.setItem(notificationKey,JSON.stringify([...presented].slice(-500)));}catch{}
  acknowledgeNotice(id);
}
const clueKey=clue=>clue.id?String(clue.location??'')+':'+clue.id:null;
const sceneClues=state=>(state.locations||[]).flatMap(place=>(place.clues||[]).map(clue=>({...clue,location:clue.location??place.index})));
function newClues(clues){return (clues||[]).filter(clue=>{const key=clueKey(clue);if(!key||knownClues.has(key))return false;knownClues.add(key);return true;});}
function stopLifetime(){clearTimeout(expiry);clearTimeout(fade);if(popup)popup.classList.remove('fading');}
function dismiss(){stopLifetime();if(popup)popup.hidden=true;clearTimeout(timer);timer=setTimeout(showNext,80);}
function reset(){scope='';seen.clear();knownClues.clear();snapshot=null;queue=[];notificationKey='';presented=new Set();queuedNotices=new Set();acking=new Set();clearTimeout(timer);stopLifetime();if(popup)popup.hidden=true;}
function showNext(){
  clearTimeout(timer);
  if(popup&&!popup.hidden){popup.querySelector('.effects-count').textContent=queue.length?translate('effects.queued',{count:queue.length}):'';return;}
  if(!queue.length)return;
  if(busy()||document.querySelector('dialog[open]')){timer=setTimeout(showNext,150);return;}
  if(!popup){
    popup=document.createElement('section');popup.className='effects-popup';popup.hidden=true;
    popup.setAttribute('role','dialog');popup.setAttribute('aria-modal','false');popup.setAttribute('aria-labelledby','effects-title');
    popup.innerHTML='<header><strong id="effects-title"></strong><button type="button" class="quiet effects-close"></button></header><p class="effects-source"></p><div class="effects-result" aria-live="polite"></div><div class="effects-clues"></div><ul class="change-list"></ul><footer><span class="effects-count muted"></span><button type="button" class="effects-clues-link quiet"></button><button type="button" class="effects-log quiet"></button><button type="button" class="effects-ok primary"></button></footer>';
    popup.querySelector('.effects-close').onclick=dismiss;popup.querySelector('.effects-ok').onclick=dismiss;
    popup.querySelector('.effects-log').onclick=()=>{dismiss();openLog('records');};
    popup.querySelector('.effects-clues-link').onclick=()=>{dismiss();openLog('clues');};
    popup.addEventListener('keydown',e=>{if(e.key==='Escape'){e.stopPropagation();dismiss();}});
    document.body.append(popup);
  }
  const event=queue.shift();stopLifetime();popup.dataset.eventId=event.id||'';
  popup.querySelector('strong').textContent=translate(event.clues?.length?'effects.clues':event.changes.length?'effects.title':'effects.result');
  popup.querySelector('.effects-source').textContent=event.title||translate('effects.updated');
  popup.querySelector('.effects-result').innerHTML=event.id?renderResult(event):'';
  const clues=popup.querySelector('.effects-clues');clues.replaceChildren();
  for(const clue of event.clues||[]){
    const article=document.createElement('article'),title=document.createElement('strong'),body=document.createElement('p');
    title.textContent=clue.title;body.textContent=clue.text;article.append(title,body);clues.append(article);
  }
  popup.querySelector('ul').innerHTML=renderChanges(event.changes);
  popup.querySelector('ul').hidden=!event.changes.length;
  popup.querySelector('.effects-count').textContent=queue.length?translate('effects.queued',{count:queue.length}):'';
  popup.querySelector('.effects-close').textContent=translate('ui.m058');
  popup.querySelector('.effects-ok').textContent=translate('effects.confirm');
  const log=popup.querySelector('.effects-log');log.textContent=translate('effects.log');log.hidden=!event.id;
  const clueLink=popup.querySelector('.effects-clues-link');clueLink.textContent=translate('effects.viewClues');clueLink.hidden=!event.clues?.length;
  popup.hidden=false;
  if(event.notificationId)presentedNotice(event.notificationId);
  // Polling and newly queued notices must not extend this notice's lifetime.
  expiry=setTimeout(()=>{
    popup.classList.add('fading');
    const reduced=document.body.classList.contains('reduce-motion')||matchMedia('(prefers-reduced-motion: reduce)').matches;
    fade=setTimeout(dismiss,reduced?0:280);
  },3000);
}
export const effectsUI={
  configure(t,render,isBusy,log,result=()=>'',ack=async()=>{}){translate=t;renderChanges=render;busy=isBusy;openLog=log;renderResult=result;acknowledge=ack;},
  observe(state){
    if(!state||state.role!=='player'){reset();return;}
    const next=state.storageScope+':'+state.accountId+':'+(state.character?.instanceId||'');
    const events=(state.events||[]).filter(e=>e.account===state.accountId&&!['pending','processing'].includes(e.status));
    const current=effectSnapshot(state);
    if(scope!==next){
      reset();scope=next;seen=new Set(events.map(e=>e.id));newClues(sceneClues(state));newClues(events.flatMap(e=>e.result?.clues||[]));snapshot=current;
      notificationKey='sv.desktop.presentedNotifications.'+state.storageScope+'.'+state.accountId;
      try{presented=new Set(JSON.parse(localStorage.getItem(notificationKey)||'[]'));}catch{}
    }
    let newNotice=false;
    for(const notice of state.notifications||[]){
      const id=notice.notificationId;if(!id)continue;
      if(presented.has(id)){acknowledgeNotice(id);continue;}
      if(queuedNotices.has(id))continue;queuedNotices.add(id);newNotice=true;
      const event=events.find(e=>e.notificationId===id);
      queue.push({...(event||{}),id:'notification:'+id,notificationId:id,title:event?.title||'主持通知',
        result:{...(event?.result||{}),message:notice.text},changes:(event?.changes||[]).filter(relevant),clues:newClues(event?.result?.clues)});
    }
    const covered=new Map();
    for(const event of events){
      if(seen.has(event.id)||event.notificationId)continue;
      const changes=(event.changes||[]).filter(relevant);
      const clues=newClues(event.result?.clues);
      queue.push({...event,changes,clues});
      for(const c of changes)covered.set(c.key,c.after);
    }
    // Pending scene jobs can already have committed steps; defer their snapshot
    // diff until their final owner event arrives, avoiding an early duplicate.
    const pending=(state.autoSceneTasks||[]).some(task=>['running','finishing'].includes(task.status));
    if(!pending){
      const changes=effectChanges(snapshot,current).filter(c=>!covered.has(c.key)||covered.get(c.key)!==c.after);
      if(changes.length&&!newNotice)queue.push({title:translate('effects.updated'),changes});
      snapshot=current;
    }else if(snapshot){
      // Other completed events still advance their own keys during an open job.
      for(const [key] of covered)snapshot[key]=current[key];
    }
    // A KP disclosure can grant clues without creating a package action event.
    // Delay an in-progress recipe's snapshot clues to merge with its final result.
    if(!pending){const clues=newClues(sceneClues(state));if(clues.length)queue.push({title:translate('effects.clues'),changes:[],clues});}
    seen=new Set(events.map(e=>e.id));showNext();
  }
};
