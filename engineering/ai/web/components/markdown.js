import {mountStyle} from './styles.js';
import {renderReferenceText,hydrateReferences} from './reference-editor.js';
import {bindReferenceDetails} from './reference-details.js';

// Deliberately DOM-only: model HTML is text, images never cause automatic requests.
function plain(parent,text){const span=document.createElement('span');renderReferenceText(span,text);parent.append(...span.childNodes);}
function inline(parent,text,depth=0){
 if(depth>12){plain(parent,text);return;}
 const pattern=/\[\[(?:config|entity|data|chat|event|ruling|knowledge):[^\]\n]+\]\]|\\[\\`*_[\]{}()#+.!|>-]|(`+)([^`\n]*?)\1|!\[([^\]\n]*)\]\([^\n)]*\)|\[([^\]\n]+)\]\(([^\s)]+)(?:\s+"[^"]*")?\)|\*\*([^\n]+?)\*\*|__([^\n]+?)__|~~([^\n]+?)~~|\*([^*\n]+)\*|_([^_\n]+)_/g;
 let end=0;
 for(const match of text.matchAll(pattern)){
  plain(parent,text.slice(end,match.index));const raw=match[0];let node;
  if(raw.startsWith('[['))plain(parent,raw);
  else if(raw.startsWith('\\'))plain(parent,raw.slice(1));
  else if(match[1]){if(/^\[\[(config|entity|data|chat|event|ruling|knowledge):[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+\]\]$/.test(match[2]))plain(parent,match[2]);else{node=document.createElement('code');node.textContent=match[2];parent.append(node);}}
  else if(raw.startsWith('!['))plain(parent,match[3]||'图片');
  else if(match[4]){
   let url;try{url=new URL(match[5],document.baseURI);}catch{}
   if(url&&['https:','http:','mailto:'].includes(url.protocol)){node=document.createElement('a');node.href=url.href;node.rel='noopener noreferrer';node.target='_blank';inline(node,match[4],depth+1);parent.append(node);}
   else plain(parent,match[4]);
  }else{node=document.createElement(match[6]||match[7]?'strong':match[8]?'del':'em');inline(node,match[6]||match[7]||match[8]||match[9]||match[10],depth+1);parent.append(node);}
  end=match.index+raw.length;
 }
 plain(parent,text.slice(end));
}
function cells(line){
 const values=[];let value='',code=false;
 for(let i=0;i<line.length;i++){const c=line[i];if(c==='\\'&&line[i+1]==='|'){value+='|';i++;continue;}if(c==='`')code=!code;if(c==='|'&&!code){values.push(value.trim());value='';}else value+=c;}
 values.push(value.trim());if(!values[0])values.shift();if(values.length&&!values.at(-1))values.pop();return values;
}
const separator=line=>cells(line).length>0&&cells(line).every(v=>/^:?-{3,}:?$/.test(v));
function blocks(parent,lines,depth=0){
 if(depth>12){const p=document.createElement('p');inline(p,lines.join('\n'));parent.append(p);return;}
 for(let i=0;i<lines.length;){
  const line=lines[i];if(!line.trim()){i++;continue;}
  const fence=/^\s{0,3}(`{3,}|~{3,})(.*)$/.exec(line);
  if(fence){
   const chunk=[];i++;const close=new RegExp('^\\s{0,3}'+fence[1][0]+'{'+fence[1].length+',}\\s*$');
   while(i<lines.length&&!close.test(lines[i]))chunk.push(lines[i++]);if(i<lines.length)i++;
   const wrap=document.createElement('div'),pre=document.createElement('pre'),code=document.createElement('code'),bar=document.createElement('div'),copy=document.createElement('button');wrap.className='md-code';bar.className='md-code-bar';bar.textContent=fence[2].trim().slice(0,40);copy.type='button';copy.textContent='复制代码';copy.onclick=async()=>{try{await navigator.clipboard.writeText(code.textContent);copy.textContent='已复制';}catch{copy.textContent='请选中代码复制';}};bar.append(copy);code.textContent=chunk.join('\n');pre.append(code);wrap.append(bar,pre);parent.append(wrap);continue;
  }
  const heading=/^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$/.exec(line);
  if(heading){const h=document.createElement('h'+heading[1].length);inline(h,heading[2]);parent.append(h);i++;continue;}
  if(/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line)){parent.append(document.createElement('hr'));i++;continue;}
  if(i+1<lines.length&&line.includes('|')&&separator(lines[i+1])){
   const headers=cells(line),align=cells(lines[i+1]),wrap=document.createElement('div'),table=document.createElement('table'),head=document.createElement('thead'),body=document.createElement('tbody');
   wrap.className='md-table';wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','数据表格');
   function tr(values,tag){const row=document.createElement('tr');headers.forEach((_,j)=>{const td=document.createElement(tag);if(tag==='th')td.scope='col';if(align[j]?.endsWith(':'))td.style.textAlign=align[j].startsWith(':')?'center':'right';inline(td,values[j]||'');row.append(td);});return row;}
   head.append(tr(headers,'th'));i+=2;while(i<lines.length&&lines[i].trim()&&lines[i].includes('|'))body.append(tr(cells(lines[i++]),'td'));table.append(head,body);wrap.append(table);parent.append(wrap);continue;
  }
  if(/^\s{0,3}>/.test(line)){const quote=document.createElement('blockquote'),part=[];while(i<lines.length&&/^\s{0,3}>/.test(lines[i]))part.push(lines[i++].replace(/^\s{0,3}> ?/,''));blocks(quote,part,depth+1);parent.append(quote);continue;}
  const list=/^(\s*)([-+*]|\d+[.)])\s+(.*)$/.exec(line);
  if(list){
   const ordered=/\d/.test(list[2]),base=list[1].length,node=document.createElement(ordered?'ol':'ul');if(ordered)node.start=parseInt(list[2]);
   while(i<lines.length){const item=/^(\s*)([-+*]|\d+[.)])\s+(.*)$/.exec(lines[i]);if(!item||item[1].length!==base||/\d/.test(item[2])!==ordered)break;
    const li=document.createElement('li'),part=[item[3]];i++;
    while(i<lines.length&&lines[i].trim()&&/^\s/.test(lines[i])&&(lines[i].match(/^\s*/)[0].length>base))part.push(lines[i++].slice(base+2));
    blocks(li,part,depth+1);node.append(li);
   }parent.append(node);continue;
  }
  const part=[line];i++;
  while(i<lines.length&&lines[i].trim()&&!/^\s{0,3}(?:#{1,6}\s|>|`{3,}|~{3,}|[-+*]\s|\d+[.)]\s)/.test(lines[i])&&!(i+1<lines.length&&separator(lines[i+1])))part.push(lines[i++]);
  const p=document.createElement('p');part.forEach((value,j)=>{if(j)p.append(document.createElement('br'));inline(p,value);});parent.append(p);
 }
}
/** Headings, emphasis, links, lists, quotes, fenced code and pipe tables; no HTML execution. */
export function renderMarkdown(target,text,{plainText=false}={}){
 target.replaceChildren();target.classList.add('ai-markdown');target.classList.toggle('md-plain',plainText);
 const value=String(text??'').slice(0,100000);
 if(plainText)renderReferenceText(target,value);else blocks(target,value.replace(/\r\n?/g,'\n').split('\n'));
}
export function markdownStyle(root){mountStyle(root,new URL('./markdown.css',import.meta.url));}
export function mountMarkdown(target,text,options={}){
 const element=document.createElement('div');target.append(element);const root=element.attachShadow({mode:'open'});markdownStyle(root);const body=document.createElement('div');root.append(body);let revision=0,dead=false;
 const details=bindReferenceDetails(body,tokens=>options.resolveReferences?.(tokens),{container:root,valid:()=>element.isConnected,audience:()=>options.audience||'player'});
 let previous;
 function update(value,next=options){if(dead)return;const unchanged=value===previous&&next.plainText===options.plainText&&next.resolveReferences===options.resolveReferences;options=next;if(unchanged){details.refresh();return;}previous=value;details.close();const stamp=++revision;renderMarkdown(body,value,next);hydrateReferences(body,next.resolveReferences,()=>!dead&&stamp===revision);}
 update(text);return {update,destroy(){dead=true;revision++;details.destroy();element.remove();}};
}
