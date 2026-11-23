/** Semantic, atomic references; the wire format remains revision-bound tokens. */
const TOKEN=/\[\[(config|entity|data|chat|event|ruling|knowledge):([A-Za-z0-9_.-]{1,1500})@([A-Za-z0-9_.-]{1,200})\]\]/g;
const MIME='application/x-onlinecoc-ai-references';
const names={config:'配置',entity:'实体',data:'运行数据',chat:'聊天',event:'事件',ruling:'裁决',knowledge:'已知资料'};
const hydrationVersions=new WeakMap();
export const referenceToken=item=>item.token||`[[${item.kind}:${item.id}@${item.revision}]]`;

function chip(token,label,editable=false){
 const node=document.createElement('span');node.className='reference-chip';node.contentEditable='false';node.dataset.token=token;
 const text=document.createElement('span');text.className='reference-label';text.textContent=label||'数据引用';node.append(text);
 if(label){node.dataset.resolved='true';node.dataset.referenceLabel=label;}
 if(!editable){node.tabIndex=0;node.setAttribute('role','button');node.setAttribute('aria-haspopup','dialog');}
 const kind=token.slice(2,token.indexOf(':'));node.title=(names[kind]||'数据')+'引用';
 if(editable){const remove=document.createElement('button');remove.type='button';remove.className='reference-remove';remove.tabIndex=-1;remove.textContent='×';remove.setAttribute('aria-label','移除引用：'+text.textContent);node.append(remove);}
 return node;
}
function fragment(text,labels=new Map(),editable=false){
 const result=document.createDocumentFragment();let end=0;
 for(const match of text.matchAll(TOKEN)){result.append(document.createTextNode(text.slice(end,match.index)),chip(match[0],labels.get(match[0]),editable));end=match.index+match[0].length;}
 result.append(document.createTextNode(text.slice(end)));return result;
}
function read(node,semantic=false){
 if(node.nodeType===Node.TEXT_NODE)return node.data;
 if(node.dataset?.token)return semantic?node.querySelector('.reference-label').textContent:node.dataset.token;
 if(node.nodeName==='BR')return '\n';
 return [...node.childNodes].map(n=>read(n,semantic)).join('');
}
/** Labels are fetched from the current authorized source, never from message HTML. */
export async function hydrateReferences(target,resolve,valid=()=>true,{beforeUpdate,afterUpdate}={}){
 if(!resolve)return;
 const generation=(hydrationVersions.get(target)||0)+1;hydrationVersions.set(target,generation);
 const current=()=>valid()&&hydrationVersions.get(target)===generation;
 const nodes=[...target.querySelectorAll('.reference-chip')],
  tokens=[...new Set(nodes.map(n=>n.dataset.token))];
 function update(fn){const snapshot=beforeUpdate?.();fn();afterUpdate?.(snapshot);}
 async function batch(part){
  try{
   const result=await resolve(part);if(!current())return;
   if(!Array.isArray(result?.items)||part.some(token=>!result.items.some(item=>referenceToken(item)===token)))throw Object.assign(new Error('NOT_VISIBLE'),{code:'NOT_VISIBLE'});
   update(()=>{for(const item of result.items){const token=referenceToken(item);for(const node of nodes.filter(n=>n.dataset.token===token)){
    if(!target.contains(node))continue;
    const label=node.querySelector('.reference-label');if(label.textContent!==item.label)label.textContent=item.label;
    node.dataset.resolved='true';node.dataset.referenceLabel=item.label;node.classList.remove('unavailable');node.removeAttribute('aria-disabled');if(node.getAttribute('role')==='button')node.tabIndex=0;
    node.querySelector('button')?.setAttribute('aria-label','移除引用：'+item.label);
   }}});
  }catch(error){
   if(!current())return;
   if(part.length>1){for(const token of part)await batch([token]);return;}
   update(()=>{for(const node of nodes.filter(n=>n.dataset.token===part[0])){const label=node.querySelector('.reference-label'),text=node.dataset.referenceLabel||(error.code==='REFERENCE_STALE'?'已过期引用':'不可用引用');if(label.textContent!==text)label.textContent=text;node.classList.add('unavailable');node.setAttribute('aria-disabled','true');if(node.getAttribute('role')==='button')node.tabIndex=-1;}});
  }
 }
 for(let i=0;i<tokens.length&&current();i+=12)await batch(tokens.slice(i,i+12));
}
export function renderReferenceText(target,text){target.replaceChildren(fragment(text));}
/** Labels already delivered to this audience; never grant access to details. */
export function applyReferenceLabels(target,labels={}){for(const node of target.querySelectorAll('.reference-chip')){const label=labels[node.dataset.token];if(typeof label==='string'&&label){node.dataset.referenceLabel=label;const text=node.querySelector('.reference-label');if(text.textContent!==label)text.textContent=label;}}}

export function createReferenceEditor(element,{resolveReferences}={}){
 let dead=false,version=0,composing=false,labels=new Map(),history=[''],historyIndex=0,restoring=false;
 element.contentEditable='true';element.setAttribute('role','textbox');element.setAttribute('aria-multiline','true');element.classList.add('reference-editor');
 const selection=()=>element.getRootNode().getSelection?.()||window.getSelection();
 function range(){const s=selection();if(!s?.rangeCount)return null;const r=s.getRangeAt(0);return element.contains(r.commonAncestorContainer)?r:null;}
 function expand(r){
  const parent=n=>(n.nodeType===Node.ELEMENT_NODE?n:n.parentElement)?.closest('.reference-chip');
  const first=parent(r.startContainer),last=parent(r.endContainer);
  if(r.collapsed){if(first){r.setStartAfter(first);r.collapse(true);}}
  else{if(first)r.setStartBefore(first);if(last)r.setEndAfter(last);}
  return r;
 }
 function offset(node,count){const r=document.createRange();r.selectNodeContents(element);r.setEnd(node,count);return read(r.cloneContents()).length;}
 function cursor(){const r=range();if(!r)return {start:value().length,end:value().length};expand(r);return {start:offset(r.startContainer,r.startOffset),end:offset(r.endContainer,r.endOffset)};}
 function entries(){const result=[];let position=0;
  function walk(node){if(node.dataset?.token||node.nodeType===Node.TEXT_NODE||node.nodeName==='BR'){const size=read(node).length;result.push({node,start:position,end:position+size});position+=size;}else for(const n of node.childNodes)walk(n);}
  walk(element);return result;
 }
 function point(at,end=false){for(const item of entries()){if(at<=item.end){if(item.node.nodeType===Node.TEXT_NODE)return [item.node,Math.max(0,at-item.start)];const i=[...item.node.parentNode.childNodes].indexOf(item.node);return [item.node.parentNode,i+(at===item.end||(at>item.start&&end)?1:0)];}}return [element,element.childNodes.length];}
 function select(start,end=start){const r=document.createRange();r.setStart(...point(start));r.setEnd(...point(end,true));const s=selection();s.removeAllRanges();s.addRange(r);}
 function value(){return read(element);}
 function changed(){if(dead)return;version++;
  if(!composing){
   // Pasted/typed canonical markers also become indivisible references.
   const at=cursor(),text=value(),markers=entries().filter(item=>item.node.nodeType===Node.TEXT_NODE&&[...item.node.data.matchAll(TOKEN)].length);
   // Ordinary typing keeps the browser's text node, caret and composition.
   if(markers.length){const focused=element.getRootNode().activeElement===element;for(const item of markers)item.node.replaceWith(fragment(item.node.data,labels,true));element.normalize();if(focused)select(at.start,at.end);}
   if(!restoring&&history[historyIndex]!==text){history=history.slice(0,historyIndex+1);history.push(text);if(history.length>100)history.shift();historyIndex=history.length-1;}
   const stamp=version;hydrateReferences(element,resolveReferences,()=>!dead&&!composing&&stamp===version);
  }
 }
 function emit(){element.dispatchEvent(new Event('input',{bubbles:true}));}
 function replace(start,end,text,reference){
  if(reference)labels.set(referenceToken(reference),reference.label);
  const r=document.createRange();r.setStart(...point(start));r.setEnd(...point(end,true));expand(r);r.deleteContents();
  const content=fragment(text,labels,true);r.insertNode(content);element.focus();select(start+text.length);emit();
 }
 function setValue(text,references=[]){
  version++;composing=false;labels=new Map(references.map(item=>[referenceToken(item),item.label]));element.replaceChildren(fragment(text,labels,true));history=[text];historyIndex=0;
  if(element.getRootNode().activeElement===element)select(text.length);
  const stamp=version;hydrateReferences(element,resolveReferences,()=>!dead&&!composing&&stamp===version);
 }
 function undo(forward=false){const next=historyIndex+(forward?1:-1);if(next<0||next>=history.length)return;historyIndex=next;restoring=true;element.replaceChildren(fragment(history[next],labels,true));select(value().length);emit();restoring=false;}
 function keys(event){
  if(event.isComposing||composing)return;
  if((event.ctrlKey||event.metaKey)&&['z','y'].includes(event.key.toLowerCase())){event.preventDefault();undo(event.key.toLowerCase()==='y'||event.shiftKey);return;}
  // Browsers may suppress beforeinput for a partial selection inside a
  // contenteditable=false label. Treat that selection as the whole reference.
  if(event.key.length===1&&!event.ctrlKey&&!event.metaKey&&!event.altKey){
   const at=cursor();
   if(at.start!==at.end&&entries().some(x=>x.node.dataset?.token&&x.start<at.end&&x.end>at.start)){
    event.preventDefault();replace(at.start,at.end,event.key);return;
   }
  }
  if(!['Backspace','Delete'].includes(event.key))return;
  const at=cursor();
  if(at.start!==at.end){event.preventDefault();replace(at.start,at.end,'');return;}
  const item=entries().find(x=>x.node.dataset?.token&&(event.key==='Backspace'?x.end===at.start:x.start===at.start));
  if(item){event.preventDefault();replace(item.start,item.end,'');}
 }
 function before(event){
  if(event.isComposing||composing)return;
  const at=cursor();
  if(['insertParagraph','insertLineBreak'].includes(event.inputType)){event.preventDefault();replace(at.start,at.end,'\n');}
  if(['historyUndo','historyRedo'].includes(event.inputType)){event.preventDefault();undo(event.inputType==='historyRedo');}
  if(at.start!==at.end&&event.inputType==='insertText'){event.preventDefault();replace(at.start,at.end,event.data||'');}
  if(event.inputType.startsWith('delete')){
   const backward=event.inputType.endsWith('Backward');
   const item=entries().find(x=>x.node.dataset?.token&&(backward?x.end===at.start:x.start===at.start));
   if(at.start!==at.end||item){event.preventDefault();replace(item&&at.start===at.end?item.start:at.start,item&&at.start===at.end?item.end:at.end,'');}
  }
 }
 function clipboard(event){
  const r=range();if(!r||r.collapsed)return;expand(r);event.preventDefault();const content=r.cloneContents();
  event.clipboardData.setData('text/plain',read(content,true));event.clipboardData.setData(MIME,read(content));
  if(event.type==='cut'){const at=cursor();replace(at.start,at.end,'');}
 }
 function paste(event){event.preventDefault();const at=cursor();replace(at.start,at.end,event.clipboardData.getData(MIME)||event.clipboardData.getData('text/plain'));}
 function click(event){const button=event.target.closest('.reference-remove');if(button){const item=entries().find(x=>x.node===button.parentNode);if(item)replace(item.start,item.end,'');}}
 function compositionStart(){version++;composing=true;const r=range();if(r)expand(r);}
 function compositionEnd(){composing=false;emit();}
 const handlers={input:changed,keydown:keys,beforeinput:before,copy:clipboard,cut:clipboard,paste,click,compositionstart:compositionStart,compositionend:compositionEnd,drop:e=>e.preventDefault()};
 for(const [name,fn] of Object.entries(handlers))element.addEventListener(name,fn);
 return {element,get value(){return value();},get displayText(){return read(element,true);},get composing(){return composing;},cursor,replace,setValue,
  insertReference(item){const at=cursor();replace(at.start,at.end,referenceToken(item),item);},
  destroy(){dead=true;version++;labels.clear();history=[];for(const [name,fn] of Object.entries(handlers))element.removeEventListener(name,fn);element.replaceChildren();}
 };
}
