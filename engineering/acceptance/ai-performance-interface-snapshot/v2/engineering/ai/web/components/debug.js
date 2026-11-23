/** Local debug controls: explicit content opt-in, no persisted export or hidden context. */
export function appendDebugTools(target,client,locator,{valid=()=>true}={}){
 const details=document.createElement('details');details.className='ai-debug-tools';const caption=document.createElement('summary');caption.textContent='引用与调试';details.append(caption);
 const status=document.createElement('small');status.setAttribute('role','status');
 const label=document.createElement('label'),include=document.createElement('input');include.type='checkbox';label.append(include,document.createTextNode('包含当前可见正文（可能含私密资料）'));
 const copy=document.createElement('button');copy.type='button';copy.textContent='复制定位';copy.onclick=async()=>{if(!valid())return;const text=JSON.stringify({roomId:client.view?.roomId,...(typeof locator==='function'?locator():locator)});try{if(!navigator.clipboard?.writeText)throw Error('CLIPBOARD_UNAVAILABLE');await navigator.clipboard.writeText(text);if(valid())status.textContent='定位已复制';}catch{if(!valid())return;let field=details.querySelector('textarea');if(!field){field=document.createElement('textarea');field.readOnly=true;field.rows=3;field.cols=24;field.setAttribute('aria-label','可复制的调试定位');details.append(field);}field.value=text;field.focus();field.select();let copied=false;try{copied=!!document.execCommand?.('copy');}catch{}status.textContent=copied?'定位已复制':'已选中定位，请按 Ctrl+C 或使用系统复制。';}};
 const download=document.createElement('button');download.type='button';download.textContent='导出调试 JSON';download.onclick=async()=>{if(!valid())return;download.disabled=true;try{const value=await client.aiDebug({...((typeof locator==='function')?locator():locator),includeContent:include.checked});if(!valid())return;const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='ai-debug.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),0);status.textContent='已导出';}catch(e){if(valid())status.textContent=e.code||e.message;}finally{if(valid())download.disabled=false;}};
 details.append(copy,label,download,status);target.append(details);return details;
}
export function appendReviewSource(target,source,{onOpenSource=null,onOpenSession=null}={}){
 const card=document.createElement('details');card.className='ai-review-source';const title=document.createElement('summary');title.textContent='来源 · '+source.title+(source.requestedBy?' · '+source.requestedBy:'');card.append(title);
 const note=document.createElement('p');note.textContent='引用材料 · 请核对当前状态；转交不代表批准执行。';const summary=document.createElement('p');summary.textContent=source.summary;card.append(note,summary);
 const open=(label,fn)=>{const b=document.createElement('button');b.type='button';b.textContent=label;b.onclick=async()=>{try{await fn();}catch(e){note.textContent=e.code||e.message;}};card.append(b);};
 if(onOpenSource)open('查看原裁决',()=>onOpenSource(source));
 if(source.sessionId&&onOpenSession)open('查看原对话',()=>onOpenSession(source.sessionId));
 if(source.context&&Object.keys(source.context).length){const more=document.createElement('details'),caption=document.createElement('summary'),pre=document.createElement('pre');caption.textContent='提交时的来源快照';pre.textContent=JSON.stringify(source.context,null,2);more.append(caption,pre);card.append(more);}
 target.append(card);return card;
}
