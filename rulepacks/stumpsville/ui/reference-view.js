import {t} from './i18n.js';

const esc=value=>String(value??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels={str:'力量',dex:'敏捷',wil:'意志',hp:'生命',armor:'护甲',pips:'钱币'};

// The same display functions serve ordinary sheets/items and authorized references.
// They consume only the supplied record: no current-state lookup or network access.
export function characterStatsHTML(character,{label=key=>labels[key]||key,check=null}={}){
  const n=character.numbers||{};
  return '<div class="statgrid">'+['str','dex','wil'].filter(key=>key in n).map(key=>'<div class="stat">'+(check?check(key):'<span>'+esc(label(key))+'</span>')+'<strong>'+esc(n[key])+' / '+esc(n[key+'Max'])+'</strong></div>').join('')+'</div><div class="row">'+['hp','armor','pips'].filter(key=>key in n).map(key=>'<span><strong>'+esc(label(key))+'</strong> '+esc(n[key])+(key==='hp'?' / '+esc(n.maxHp):'')+'</span>').join('')+'</div>';
}

export function itemDetailsHTML(item,{uses=item.uses,maxUses=item.maxUses??item.uses}={}){
  return (item.description?'<p>'+esc(item.description)+'</p>':'')+'<p>'+esc(t('inventory.details',{slots:item.slots??'—',uses:uses??'—',max:maxUses??'—'}))+'</p>'+(['damage','armor'].filter(key=>key in item).map(key=>'<span class="tag">'+(key==='damage'?'伤害':'护甲')+' '+esc(item[key])+'</span>').join(' '));
}

export function renderPackageReference(item){
  const value=item?.value?.data??item?.value;
  if(!value||typeof value!=='object'||Array.isArray(value))return null;
  let content='';
  if(typeof value.configurationId==='string'&&value.configurationId.startsWith('sv.')&&value.numbers&&typeof value.numbers==='object'&&!Array.isArray(value.numbers)&&['str','dex','wil','hp'].some(key=>key in value.numbers)){
    content='<h3>'+esc(value.name||item.label)+'</h3>'+characterStatsHTML(value);
    const inventory=value.metadata?.inventory;
    if(Array.isArray(inventory)&&inventory.length)content+='<h4>携带物品</h4><div class="reference-items">'+inventory.slice(0,20).map(i=>'<article class="reference-item"><strong>槽位 '+esc(i.slot)+' · '+esc(i.name)+'</strong>'+itemDetailsHTML(i)+'</article>').join('')+'</div>';
    else if(Object.keys(value.numbers).some(k=>/^item\d+$/.test(k)&&value.numbers[k]))content+='<h4>携带槽位</h4><div class="reference-items">'+Object.entries(value.numbers).filter(([k,v])=>/^item\d+$/.test(k)&&v).map(([k,v])=>'<article class="reference-item">槽位 '+esc(k.slice(4))+' · 物品编号 '+esc(v)+'</article>').join('')+'</div>';
    if('location' in value.numbers)content+='<p>地点编号 '+esc(value.numbers.location)+'</p>';
  }else if(value.name&&Array.isArray(value.exits)&&typeof value.description==='string'){
    content='<h3>'+esc(value.index==null?'':String(value.index).padStart(2,'0')+' ')+esc(value.name)+'</h3><p>'+esc(value.description)+'</p>';
    if(value.exits.length)content+='<h4>已记录通路</h4><div class="row">'+value.exits.map(index=>'<span class="tag">地点 '+esc(index)+'</span>').join('')+'</div>';
    content+=(Array.isArray(value.clues)?value.clues:[]).slice(0,30).filter(Boolean).map(c=>'<article class="reference-item"><strong>'+esc(c.title)+'</strong><p>'+esc(c.text)+'</p></article>').join('');
    if(Array.isArray(value.actions)&&value.actions.length)content+='<h4>已知做法</h4>'+value.actions.slice(0,30).filter(Boolean).map(a=>'<details><summary>'+esc(a.label)+'</summary><p>'+esc(a.hint||'')+'</p>'+(Array.isArray(a.choices)?a.choices:[]).filter(Boolean).map(c=>'<p><strong>'+esc(c.label)+'</strong> '+esc(c.process||'')+'</p>').join('')+'</details>').join('');
  }else if(value.name&&['item','weapon','armor','spell','container'].includes(value.kind)&&'slots' in value){
    content='<h3>'+esc(value.name)+'</h3>'+itemDetailsHTML(value);
  }else if(value.name&&value.entityId&&'location' in value){
    content='<h3>'+esc(value.name)+'</h3><p>地点编号 '+esc(value.location)+'</p>';
  }else return null;
  const element=document.createElement('section');element.className='stumpsville-reference';
  const root=element.attachShadow({mode:'open'}),style=document.createElement('style'),body=document.createElement('div');
  style.textContent=':host{display:block;color:inherit;font:inherit}h3{font-size:1.25em;margin:0 0 12px}h4{margin:18px 0 8px}p{line-height:1.65;overflow-wrap:anywhere}.statgrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.stat{padding:12px;border:1px solid #b8b2a0;border-radius:7px;display:flex;flex-direction:column;gap:8px;text-align:center}.stat strong{font-size:1.25em}.row{display:flex;flex-wrap:wrap;gap:14px;margin:12px 0}.tag{display:inline-block;padding:4px 8px;border:1px solid #b8b2a0;border-radius:4px}.reference-items{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px}.reference-item{padding:10px;margin:8px 0;border:1px solid #b8b2a0;border-radius:7px}.reference-item p{margin:8px 0}details{padding:8px 0}summary{cursor:pointer}';
  body.innerHTML=content;root.append(style,body);return element;
}
