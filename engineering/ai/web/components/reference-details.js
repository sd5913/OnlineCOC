import {mountStyle} from './styles.js';
/** Authorized, revision-bound reference inspector. No value cache or mutation commands. */
const names={config:'配置模板',entity:'实体',data:'运行数据',chat:'聊天',event:'事件',ruling:'裁决',knowledge:'已知资料'};
const fields={name:'名称',text:'内容',description:'说明',numbers:'数值',rules:'规则',metadata:'补充信息',components:'组件',tags:'标签',
 hp:'生命',str:'力量',dex:'敏捷',wil:'意志',armor:'护甲',location:'位置',index:'编号',owner:'归属',visibility:'可见性',lifecycle:'状态',
 configurationId:'使用模板',instanceId:'实体标识',typeRef:'类型',revision:'修订',messages:'相关聊天',actions:'行动',rulings:'裁决',executions:'执行结果',coverage:'资料覆盖',reason:'原因'};
function node(tag,text){const value=document.createElement(tag);if(text!==undefined)value.textContent=text;return value;}
const technical=new Set(['id','entityId','instanceId','configurationId','typeRef','revision','digest','scopeId','navigation','rules','components','sourceGuard','ref','provenance','owner','visibility','lifecycle','index']);
Object.assign(fields,{id:'标识',entityId:'实体标识',label:'名称',features:'环境特征',clues:'已知线索',actions:'已记录行动',choices:'行动选项',hint:'提示',process:'处理说明',exits:'出口编号',doors:'观察时的门状态',round:'回合',phase:'阶段',autoResolve:'自动裁决',maxHp:'生命上限',pips:'钱币',testimony:'证词',note:'备注',status:'状态',uses:'剩余用量',slot:'携带槽位',itemIndex:'物品编号',kind:'类别',slots:'占用槽位',damage:'伤害',light:'照明',useDie:'用量骰',maxUses:'用量上限',ticks:'刻度',inventory:'携带物品',title:'标题',value:'数值',count:'数量',known:'已获知'});
/** Format authorized data only; this is not an authorization filter. */
export function describeData(value,{audience='player'}={}){
 let count=0;
 function describe(value,depth=0){
  if(++count>250||depth>12)return node('span','部分内容未展开，请缩小资料范围。');
  if(value===null||typeof value!=='object')return node('span',value===null?'未记录':typeof value==='boolean'?(value?'是':'否'):String(value));
  const entries=Object.entries(value).filter(([key])=>audience==='administrator'||!technical.has(key));
  if(!entries.length)return node('span','无可展示条目');
  if(Array.isArray(value)){const list=node('ol');for(const [,item] of entries.slice(0,100)){const li=node('li');li.append(describe(item,depth+1));list.append(li);}if(entries.length>100)list.append(node('li','部分条目未展开。'));return list;}
  const list=node('dl');for(const [key,item] of entries.slice(0,100)){
   const label=fields[key]||(audience==='administrator'?key:/[\u4e00-\u9fff]/.test(key)?key:/^\d+$/.test(key)?'编号 '+key:'其他已知资料');
   list.append(node('dt',label));const content=node('dd');content.append(describe(item,depth+1));list.append(content);
  }
  if(entries.length>100)list.append(node('dd','部分字段未展开。'));return list;
 }
 const section=node('section');section.className='authorized-data';section.append(describe(value));return section;
}
export function bindReferenceDetails(target,resolveReferences,{container=target.parentNode,valid=()=>true,audience=()=> 'player'}={}){
 const element=node('div');element.className='reference-details';container.append(element);const root=element.attachShadow({mode:'open'});
 mountStyle(root,new URL('./reference-details.css',import.meta.url));
 const dialog=node('dialog');dialog.setAttribute('aria-labelledby','reference-title');const header=node('header'),title=node('h2','引用详情');title.id='reference-title';
 const dismiss=node('button','关闭');dismiss.type='button';dismiss.setAttribute('aria-label','关闭引用详情');header.append(title,dismiss);
 const status=node('p');status.setAttribute('role','status');const body=node('div');body.className='reference-value';dialog.append(header,status,body);root.append(dialog);
 let dead=false,version=0,token=null,anchor=null,fingerprint=null;
 function close(){version++;token=null;fingerprint=null;body.replaceChildren();status.textContent='';title.textContent='引用详情';if(dialog.open)dialog.close();if(anchor?.isConnected)anchor.focus();anchor=null;}
 async function refresh(){
  if(dead||!token)return;if(!valid()||anchor&&!target.contains(anchor)){close();return;}
  const stamp=++version,current=token;
  try{
   const result=await resolveReferences([current]);if(dead||stamp!==version)return;if(!valid()){close();return;}
   const item=result.items.find(i=>`[[${i.kind}:${i.id}@${i.revision}]]`===current);if(!item)throw new Error('NOT_VISIBLE');
   const level=typeof audience==='function'?audience():audience;const admin=level==='administrator';const next=JSON.stringify([item,admin]);if(next===fingerprint)return;fingerprint=next;title.textContent=item.label;
   status.textContent=item.kind==='knowledge'?(item.value?.mode==='live_scope'?'持续告知资料':'观察记录 · '+(item.value?.observedAt?new Date(item.value.observedAt*1000).toLocaleString():'已记录'))+' · 仅本人已知':(names[item.kind]||'数据')+(admin?' · 修订 '+item.revision+' · '+({public:'公开',kp:'KP 可见',private:'私有'}[item.visibility]||'已授权'):' · 已授权资料');
   body.replaceChildren(describeData(item.value?.data??item.value??null,{audience:admin?'administrator':'player'}));
   if(admin){const raw=node('details'),summary=node('summary','技术详情（原始数据）'),pre=node('pre',JSON.stringify(item.value??null,null,2));raw.append(summary,pre);body.append(raw);}
  }catch(error){if(dead||stamp!==version)return;if(!valid()){close();return;}fingerprint=null;body.replaceChildren();title.textContent='引用详情';status.textContent=error.code==='REFERENCE_STALE'||error.message==='REFERENCE_STALE'?'引用已过期，请重新引用当前版本。':'当前无法读取此引用，可能已失去权限或数据已不可用。';}
 }
 function open(value,source=null){
  if(dead||!valid()||typeof resolveReferences!=='function')return;
  token=value;anchor=source;fingerprint=null;body.replaceChildren();title.textContent='引用详情';status.textContent='正在读取…';
  if(!dialog.open)dialog.showModal();dismiss.focus();return refresh();
 }
 function activate(event){const chip=event.target.closest?.('.reference-chip');if(!chip||!target.contains(chip)||chip.closest('.reference-editor'))return;
  if(event.type==='keydown'&&!['Enter',' '].includes(event.key))return;event.preventDefault();open(chip.dataset.token,chip);}
 target.addEventListener('click',activate);target.addEventListener('keydown',activate);dismiss.onclick=close;
 dialog.addEventListener('cancel',event=>{event.preventDefault();close();});dialog.onclick=event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)close();}};
 return {open,close,refresh,destroy(){close();dead=true;target.removeEventListener('click',activate);target.removeEventListener('keydown',activate);element.remove();}};
}
