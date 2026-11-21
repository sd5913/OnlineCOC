export const rulingEscape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function rulingCard({time,timestamp,key='',type,source,summary,state='',actions='',attrs='',stale=false}){
  const e=rulingEscape;
  const seconds=typeof timestamp==='number'?timestamp:Date.parse(timestamp)/1000;
  const stamp=Number.isFinite(seconds)?seconds:0;
  return `<article class="queue-item ruling-card${stale?' ruling-stale':''}" data-queue-time="${stamp}" data-queue-key="${e(key||attrs)}" ${attrs}><header class="ruling-card-meta"><time ${stamp?'datetime="'+new Date(stamp*1000).toISOString()+'" title="'+e(new Date(stamp*1000).toLocaleString())+'"':''}>${e(time)}</time><span class="ruling-card-type">类型：${e(type)}</span><span class="queue-source" title="${e(source)}">${e(source)}</span></header><div class="ruling-card-summary">${summary}</div>${state?`<small class="ruling-card-state">${e(state)}</small>`:''}<div class="actions ruling-card-actions">${actions}</div></article>`;
}

// All sources share one DOM order, so keyboard and visual reading order agree.
export function mountRulingTimeline(target){
  const sources=new Map();
  function render(){
    const cards=[...sources.values()].flat().sort((a,b)=>Number(a.dataset.queueTime||0)-Number(b.dataset.queueTime||0)||String(a.dataset.queueKey||'').localeCompare(String(b.dataset.queueKey||'')));
    const keep=new Set(cards);
    for(const card of [...target.children])if(!keep.has(card))card.remove();
    cards.forEach((card,index)=>{if(target.children[index]!==card)target.insertBefore(card,target.children[index]||null);});
  }
  return {set(key,cards){sources.set(key,cards);render();},remove(key){sources.delete(key);render();}};
}
