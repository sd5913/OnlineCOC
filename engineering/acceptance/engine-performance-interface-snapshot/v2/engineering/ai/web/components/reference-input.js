import {guardedClient} from './guard.js';
import {referenceToken} from './reference-editor.js';
import {referenceCommands} from './reference-commands.js';
/** Command-name completion followed by authorized data completion. */
export function bindReferenceInput(input,container,rawClient,{editor}={}){
 let dead=false,epoch=0,timer,items=[],index=0,match=null;
 const client=guardedClient(rawClient,()=>dead),list=document.createElement('div');list.className='reference-options';list.setAttribute('role','listbox');list.hidden=true;container.append(list);
 const id='refs-'+Math.random().toString(36).slice(2);list.id=id;input.setAttribute('aria-controls',id);input.setAttribute('aria-autocomplete','list');
 const adapter=editor||{get value(){return input.value;},cursor:()=>({start:input.selectionStart,end:input.selectionEnd}),replace(start,end,text){input.setRangeText(text,start,end,'end');input.dispatchEvent(new Event('input',{bubbles:true}));}};
 function close(){epoch++;items=[];list.hidden=true;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');}
 function reset(){clearTimeout(timer);match=null;close();}
 function choose(i){if(!match||!items[i])return;const item=items[i],from=match.index,to=match.end;reset();
  if(item.command){adapter.replace(from,to,'/'+item.kind+' ');search();}
  else{adapter.replace(from,to,referenceToken(item),item);input.focus();}
 }
 function paint(){list.replaceChildren();items.forEach((item,i)=>{const b=document.createElement('button');b.type='button';b.id=id+'-'+i;b.setAttribute('role','option');b.setAttribute('aria-selected',String(i===index));b.textContent=item.command?'/'+item.kind+' · '+item.label+' — '+item.hint:item.label+' · '+({public:'公开',private:'私密',kp:'KP'}[item.visibility]||item.visibility);b.onmousedown=e=>e.preventDefault();b.onclick=()=>choose(i);list.append(b);});list.hidden=!items.length;input.setAttribute('aria-expanded',String(!!items.length));if(items.length)input.setAttribute('aria-activedescendant',id+'-'+index);}
 async function search(){if(dead||editor?.composing)return;const at=adapter.cursor();if(at.start!==at.end){reset();return;}
  const prefix=adapter.value.slice(0,at.start),found=/\/([a-z]*)(?:[ \t]+([^\n]*))?$/i.exec(prefix);if(!found){reset();return;}
  match={index:found.index,end:at.start};const word=found[1].toLowerCase();const available=referenceCommands(client.view?.role);
  if(found[2]===undefined){items=available.filter(c=>c.kind.startsWith(word)).map(c=>({...c,command:true}));index=0;paint();return;}
  if(!available.some(c=>c.kind===word)){reset();return;}
  const seq=++epoch;try{const data=await client.aiReferences(word,found[2]||'');if(dead||seq!==epoch)return;items=data.items;index=0;paint();}catch{if(seq===epoch)reset();}
 }
 function changed(event){reset();if(event?.isComposing||editor?.composing)return;const prefix=adapter.value.slice(0,adapter.cursor().start);if(/\/[a-z]*$/i.test(prefix))search();else timer=setTimeout(search,180);}
 function keys(e){if(e.isComposing||editor?.composing||list.hidden)return;if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();index=(index+(e.key==='ArrowDown'?1:-1)+items.length)%items.length;paint();}else if(['Enter','Tab'].includes(e.key)&&!e.ctrlKey&&!e.metaKey){e.preventDefault();choose(index);}else if(e.key==='Escape'){e.preventDefault();reset();}}
 function moved(e){if(e.type==='mouseup'||['ArrowLeft','ArrowRight','Home','End'].includes(e.key))changed();}
 const listeners={input:changed,keydown:keys,keyup:moved,mouseup:moved};for(const [name,fn] of Object.entries(listeners))input.addEventListener(name,fn);
 return {reset,destroy(){dead=true;reset();for(const [name,fn] of Object.entries(listeners))input.removeEventListener(name,fn);list.remove();}};
}
