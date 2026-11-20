export const rulingEscape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function rulingCard({time,type,source,summary,state='',actions='',attrs=''}){
  const e=rulingEscape;
  return `<article class="queue-item ruling-card" ${attrs}><header class="ruling-card-meta"><time>${e(time)}</time><span class="ruling-card-type">类型：${e(type)}</span><span class="queue-source" title="${e(source)}">${e(source)}</span></header><div class="ruling-card-summary">${summary}</div>${state?`<small class="ruling-card-state">${e(state)}</small>`:''}<div class="actions ruling-card-actions">${actions}</div></article>`;
}
