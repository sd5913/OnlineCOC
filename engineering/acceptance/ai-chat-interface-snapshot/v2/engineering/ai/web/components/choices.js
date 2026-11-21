import {mountStyle} from './styles.js';
/** Display-only choices. The embedding application owns composition and submission. */
export function mountChoices(target,choices,{onSelect=null,disabled=false,hintText=null}={}){
 const element=document.createElement('div');element.className='response-choices';target.append(element);
 const root=element.attachShadow({mode:'open'});let dead=false;
 mountStyle(root,new URL('./choices.css',import.meta.url));
 function update(value,options={onSelect,disabled,hintText}){
  onSelect=options.onSelect??null;disabled=options.disabled??false;hintText=options.hintText??null;
  root.querySelector('fieldset')?.remove();
  if(!value||!Array.isArray(value.options))return;
  const box=document.createElement('fieldset'),legend=document.createElement('legend'),nav=document.createElement('nav'),hint=document.createElement('small');
  legend.textContent=value.prompt;nav.setAttribute('aria-label',value.prompt);
  hint.textContent=hintText||'选择后填入输入框；发送后继续，不会直接批准或执行。';
  for(const option of value.options.slice(0,6)){
   const b=document.createElement('button');b.type='button';b.textContent=option.label;b.disabled=!!disabled||!onSelect;
   b.onclick=()=>{if(!dead&&!disabled&&onSelect)onSelect({...option});};nav.append(b);
  }
  box.append(legend,nav,hint);root.append(box);
 }
 update(choices);return {update,destroy(){dead=true;element.remove();}};
}
