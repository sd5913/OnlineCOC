// Presentation of committed host rolls only. This module never sends commands.
let translate, renderResult, popup, scope='', seen=new Set(), queue=[], timer, reveal, fade;
const enabledKey='sv.desktop.dice.enabled', motionKey='sv.desktop.reduceMotion';
function close(){
  clearTimeout(timer);clearTimeout(reveal);clearTimeout(fade);
  if(popup){popup.hidden=true;popup.classList.remove('fading');}
  timer=setTimeout(showNext,80);
}
function showNext(){
  if(!diceUI.enabled||!queue.length||popup&&!popup.hidden)return;
  if(!popup){
    popup=document.createElement('section');popup.className='dice-popup';popup.hidden=true;
    popup.setAttribute('role','dialog');popup.setAttribute('aria-modal','false');popup.setAttribute('aria-labelledby','dice-popup-title');
    popup.innerHTML='<header><strong id="dice-popup-title"></strong><button type="button" class="quiet dice-close"></button></header><p class="dice-phase" role="status"></p><div class="dice-spinner" aria-hidden="true"><svg viewBox="0 0 100 100"><path d="M50 4 91 27 91 73 50 96 9 73 9 27Z M50 4 25 30 9 27 M50 4 75 30 91 27 M25 30 9 73 50 96 75 30 25 30 50 96 M75 30 91 73"/><text x="50" y="55" text-anchor="middle">d20</text></svg></div><div class="dice-popup-results"></div>';
    popup.querySelector('button').onclick=close;
    popup.addEventListener('keydown',event=>{if(event.key==='Escape'){event.stopPropagation();close();}});
    document.body.append(popup);
  }
  const event=queue.shift();popup.querySelector('strong').textContent=event.title;
  const result=event.result||{};
  popup.querySelector('.dice-spinner text').textContent='d'+(result.checks?.length||Number.isFinite(result.target)||result.save>0?20:result.rolls?.[0]?.sides||20);
  popup.querySelector('button').textContent=translate('ui.m058');
  popup.querySelector('.dice-popup-results').innerHTML=renderResult(event);
  popup.querySelector('.dice-popup-results').hidden=true;
  popup.querySelector('.dice-phase').textContent=translate('dice.rolling');
  popup.dataset.phase='rolling';popup.hidden=false;
  const reduced=localStorage.getItem(motionKey)==='1'||matchMedia('(prefers-reduced-motion: reduce)').matches;
  reveal=setTimeout(()=>{
    popup.dataset.phase='result';popup.querySelector('.dice-popup-results').hidden=false;
    popup.querySelector('.dice-phase').textContent=translate('dice.settled');
    timer=setTimeout(()=>{popup.classList.add('fading');fade=setTimeout(close,reduced?0:280);},3000);
  },reduced?0:800);
}
export const diceUI={
  configure(t,render){translate=t;renderResult=render;},
  get presenting(){return queue.length>0||!!(popup&&!popup.hidden);},
  get enabled(){return localStorage.getItem(enabledKey)!=='0';},
  setEnabled(value){localStorage.setItem(enabledKey,value?'1':'0');if(!value){queue=[];close();}},
  setReduced(value){localStorage.setItem(motionKey,value?'1':'0');document.body.classList.toggle('reduce-motion',value);},
  get reduced(){return localStorage.getItem(motionKey)==='1';},
  observe(state){
    if(!state){scope='';seen.clear();queue=[];close();return;}
    const next=state.storageScope+':'+state.accountId;
    const events=(state.events||[]).filter(e=>e.account===state.accountId&&!['pending','processing'].includes(e.status));
    if(next!==scope){scope=next;seen=new Set(events.map(e=>e.id));queue=[];close();return;}
    for(const event of events){
      if(seen.has(event.id))continue;
      seen.add(event.id);
      const r=event.result||{};
      if(this.enabled&&((Number.isFinite(r.rolled)&&Number.isFinite(r.target))||r.save>0||r.checks?.some(c=>Number.isFinite(c.rolled))||r.rolls?.length))queue.push(event);
    }
    // Retain only IDs still in the bounded authoritative event history.
    seen=new Set(events.map(e=>e.id));
    showNext();
  }
};
