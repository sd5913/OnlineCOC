import {mountStyle} from './styles.js';
import {guardedClient} from './guard.js';

/** Room settings only. Credentials stay in the separate local provider manager. */
export function mountAISettings(target,rawClient,{onChange=()=>{},onReceipt=()=>{}}={}){
 const shell=document.createElement('div');target.append(shell);const root=shell.attachShadow({mode:'open'});
 mountStyle(root,new URL('./settings.css',import.meta.url));
 root.innerHTML='<section><header><h2>AI 服务与权限</h2><button id="refresh">刷新</button></header><p id="status" role="status"></p><div id="settings" hidden><div class="settings-grid"><form id="service"><h3>服务接入</h3><label><input id="enabled" type="checkbox">允许调用 AI</label><label>服务配置<select id="profile"></select></label><fieldset><legend>允许外发的数据</legend><label><input id="public" type="checkbox">公开信息</label><label><input id="private" type="checkbox">有权读取的私密信息</label><label><input id="kp" type="checkbox">KP 信息</label></fieldset><details><summary>自动接收需求</summary><label><input id="auto" type="checkbox">接收指定频道</label><label>频道 ID（逗号分隔）<input id="channels"></label><label>需求前缀<input id="prefix"></label></details><button type="submit">保存服务设置</button></form><form id="access"><h3>读取、玩家与审批</h3><label><input id="admin-room" type="checkbox">管理员 AI 可查询全房间游戏资料</label><p>包括其他频道与历史记录；不含本机凭据，外发仍受左侧开关约束。</p><label><input id="data-queries" type="checkbox">允许 AI 调用资料查询工具</label><label><input id="runtime-changes" type="checkbox">允许提交运行时修改</label><label><input id="config-changes" type="checkbox">允许提交配置与规则修改</label><label><input id="knowledge-requests" type="checkbox">允许玩家主动向 KP 申请披露资料</label><label><input id="player-requests" type="checkbox">允许玩家提交创作／配置申请</label><label><input id="allow-player" type="checkbox">允许 PL 使用 AI 对话</label><p>玩家仅使用本人已知资料，KP 可查看会话。</p><label><input id="auto-batches" type="checkbox">自动批准普通管理员执行批次</label><label><input id="auto-config" type="checkbox">通过三检后自动批准普通配置</label><p>自动审批以保存设置的 KP 身份执行。高危修改始终需 KP 核对完整指令包并明确批准，无法开启自动通过。</p><button type="submit">保存权限设置</button></form></div></div></section>';
 const extraPermissions={allowAdminRoomRead:'admin-room',allowDataQueries:'data-queries',allowRuntimeChanges:'runtime-changes',allowConfigurationChanges:'config-changes',allowKnowledgeRequests:'knowledge-requests',allowPlayerRequests:'player-requests'};
 const $=id=>root.querySelector('#'+id);let dead=false,busy=false,revision=null,identity='',sequence=0;
 const client=guardedClient(rawClient,()=>dead),allowed=()=>client.connected&&client.view?.role==='kp';
 function disable(){for(const b of root.querySelectorAll('button'))b.disabled=busy||!allowed()||b.id!=='refresh'&&revision===null;}
 function clear(){sequence++;revision=null;$('settings').hidden=true;for(const input of root.querySelectorAll('input')){input.value='';input.checked=false;}$('profile').replaceChildren();disable();}
 async function refresh(){
  const token=++sequence;if(!allowed()){clear();$('status').textContent='仅 KP 可以管理 AI 服务与权限。';return;}
  $('status').textContent='正在读取设置…';
  try{const data=await client.aiSettings();if(dead||token!==sequence||!allowed())return;
   const s=data.settings;revision=data.access.revision;$('enabled').checked=s.enabled;
   $('profile').replaceChildren(new Option('未选择',''),...data.profiles.map(p=>new Option(p.profileId+' / '+p.model+(p.enabled?'':'（未启用）'),p.profileId)));
   $('profile').value=s.profileId||'';for(const key of ['public','private','kp'])$(key).checked=s.externalSources[key];
   $('auto').checked=s.auto.enabled;$('channels').value=s.auto.channelIds.join(',');$('prefix').value=s.auto.prefix;
   $('allow-player').checked=data.access.allowPlayerChat;$('auto-batches').checked=data.access.autoApproveBatches;$('auto-config').checked=data.access.autoApproveConfigurations;
   for(const [key,id] of Object.entries(extraPermissions))$(id).checked=data.access[key]!==false;
   $('settings').hidden=false;$('status').textContent='';disable();
  }catch(e){if(!dead&&token===sequence){clear();$('status').textContent=e.code||e.message;}}
 }
 async function save(op,args){if(dead||busy||!allowed()||revision===null)return;busy=true;disable();const scope=identity;$('status').textContent='正在保存…';
  try{const receipt=await client.aiCommand(op,args);if(receipt.status!=='committed')throw Object.assign(Error(receipt.code||receipt.status),{aiRequestId:receipt.requestId});
   if(dead||scope!==identity)return;await refresh();if(dead||scope!==identity)return;$('status').textContent='设置已保存';onChange(receipt.result);
  }catch(e){if(!dead&&scope===identity){$('status').textContent=(e.code||e.message)+(e.aiRequestId?' · 请求 '+e.aiRequestId:'');if(e.aiRequestId)onReceipt(e.aiRequestId);}}
  finally{busy=false;if(!dead)disable();}
 }
 $('service').onsubmit=e=>{e.preventDefault();save('ai.settings.update',{enabled:$('enabled').checked,profileId:$('profile').value||null,externalSources:Object.fromEntries(['public','private','kp'].map(k=>[k,$(k).checked])),auto:{enabled:$('auto').checked,channelIds:$('channels').value.split(',').map(s=>s.trim()).filter(Boolean),prefix:$('prefix').value}});};
 $('access').onsubmit=e=>{e.preventDefault();save('ai.access.update',{revision,...Object.fromEntries(Object.entries(extraPermissions).map(([key,id])=>[key,$(id).checked])),allowPlayerChat:$('allow-player').checked,autoApproveBatches:$('auto-batches').checked,autoApproveConfigurations:$('auto-config').checked});};
 $('refresh').onclick=()=>refresh();
 const update=()=>{const next=JSON.stringify([client.generation,client.connected,client.view?.accountId,client.view?.role,client.view?.authorityEpoch]);if(next!==identity){identity=next;clear();refresh();}};
 const unsub=client.subscribe(update);update();
 return {refresh,destroy(){dead=true;sequence++;unsub();clear();shell.remove();}};
}
