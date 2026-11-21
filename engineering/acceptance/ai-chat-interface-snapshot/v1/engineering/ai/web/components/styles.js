// Shared, immutable sheets survive Shadow DOM detach/reparent during host refresh.
const sheets=new Map(),states=new WeakMap();
export function mountStyle(root,url,inlineText){
 const key=String(url);let state=states.get(root);
 if(!state){state={pending:0,visibility:root.host.style.visibility};states.set(root,state);}
 state.pending++;root.host.style.visibility='hidden';
 async function load(){
  if(!sheets.has(key))sheets.set(key,(async()=>{const text=inlineText??await fetch(key).then(r=>{if(!r.ok)throw Error('STYLE_LOAD_FAILED');return r.text();});const sheet=new CSSStyleSheet();sheet.replaceSync(text);return sheet;})().catch(e=>{sheets.delete(key);throw e;}));
  try{const sheet=await sheets.get(key);if(!root.adoptedStyleSheets.includes(sheet))root.adoptedStyleSheets=[...root.adoptedStyleSheets,sheet];notice?.remove();state.pending--;if(!state.pending)root.host.style.visibility=state.visibility;}
  catch{if(!notice){notice=document.createElement('button');notice.type='button';notice.textContent='样式加载失败，点击重试';notice.style.visibility='visible';notice.onclick=()=>{notice.disabled=true;load().finally(()=>{notice.disabled=false;});};root.append(notice);}}
 }
 let notice;load();
}
