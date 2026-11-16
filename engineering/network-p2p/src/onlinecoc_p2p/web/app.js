import {WebRtcTransport} from "./transport.js";
import {mountPackage} from "./bridge.js";
import {displayCode,joinTarget,shareText} from "./join.js";
const $=id=>document.getElementById(id);
const fragment=new URLSearchParams(location.hash.slice(1));
const appToken=fragment.get("token")||sessionStorage.getItem("onlinecoc-local-token")||"";
if(fragment.has("token")){sessionStorage.setItem("onlinecoc-local-token",appToken);history.replaceState(null,"",location.pathname);}
let transport,manifest,unmount,subscription,view,parts,hostState,locked=false;
let initialized=false,hostEnabled=false,upstreamEdited=false,localHosts=[];
const messages={LOCAL_AUTH_REQUIRED:"请从本机启动入口重新打开页面。",UPSTREAM_UNAVAILABLE:"本机游戏宿主未就绪，请先启动游戏宿主。",ROOM_UNAVAILABLE:"房间不可加入，请检查房间码、邀请、密码或房主是否在线。",JOIN_REJECTED:"房主未批准本次加入。",ROOM_FULL:"房间人数已满。",AUTH_INVALID:"游戏账号或密码不正确。",AUTH_REQUIRED:"请先登录房间账号。",DIRECTORY_UNAVAILABLE:"暂时无法连接房间目录。",TURN_REQUIRED:"尚未配置可用的中继服务。",CONNECT_TIMEOUT:"连接超时，可开启仅中继后重试。",PUBLISHER_NOT_CONFIGURED:"此客户端未配置房主发布凭据，可正常加入房间。",CONTENT_CHANGED:"主机内容已经变化，请重新检查并下载。"};
function report(error){$("global-error").textContent=messages[error.code]||error.code||error.message||"操作失败";$("global-error").hidden=false;}
function clearError(){$("global-error").hidden=true;}
async function api(path,data,clientToken){
  const response=await fetch(path,{method:data===undefined?"GET":"POST",headers:{"Authorization":"Bearer "+appToken,...(data===undefined?{}:{"Content-Type":"application/json"}),...(clientToken?{"X-Client-Token":clientToken}:{})},body:data===undefined?undefined:JSON.stringify(data)});
  const value=await response.json();if(!response.ok)throw Object.assign(new Error(value.code),value);return value;
}
const control=(action,data={},credential)=>api("/control/"+action,data,credential);
function button(text,action,style="quiet"){const element=document.createElement("button");element.textContent=text;element.className=style;element.onclick=()=>Promise.resolve().then(action).catch(report);return element;}
function empty(target,text){const p=document.createElement("p");p.className="empty";p.textContent=text;target.replaceChildren(p);}
for(const tab of document.querySelectorAll("[data-tab]"))tab.onclick=()=>{for(const b of document.querySelectorAll("[data-tab]"))b.classList.toggle("active",b===tab);$("join-tab").hidden=tab.dataset.tab!=="join";$("host-tab").hidden=tab.dataset.tab!=="host";};
async function refresh(){
  const value=await control("rooms");$("rooms").replaceChildren();
  if(!value.items.length)empty($("rooms"),"还没有公开房间。房主发布后会出现在这里。");
  for(const room of value.items){
    const card=document.createElement("article");card.className="room-card";
    const title=document.createElement("h3");title.textContent=room.title;
    const note=document.createElement("p");note.textContent=room.summary||"房主尚未填写说明";
    const meta=document.createElement("small");meta.textContent=room.playerCount+" / "+room.maxPlayers+" 人 · "+(room.passwordRequired?"需要密码":"无房间密码")+" · "+(room.approvalRequired?"需审批":"直接申请");
    card.append(title,note,meta,button("选择房间",()=>{$("room-id").value=displayCode(room.roomCode)||room.roomId;$("invitation").value="";$("join-status").textContent="已选择："+room.title;}));
    $("rooms").append(card);
  }
  $("connection-state").textContent="目录已连接";$("connection-dot").style.background="#3a8c65";
}
$("refresh").onclick=()=>refresh().catch(report);
$("join-form").onsubmit=async event=>{
  event.preventDefault();clearError();leave();$("join-button").disabled=true;
  transport=new WebRtcTransport(control,appToken,status=>$("join-status").textContent=status);
  try{
    await transport.connect({...joinTarget($("room-id").value,$("invitation").value),password:$("room-password").value,relayOnly:$("relay-only").checked});
    $("room-password").value="";$("invitation").value="";$("login-form").hidden=false;$("leave").hidden=false;
    $("join-status").textContent="已连接房主。请登录你在该房间的账号。";
  }catch(error){report(error);$("join-status").textContent="未能加入，可修改设置后重试。";}
  finally{$("join-button").disabled=false;}
};
$("login-form").onsubmit=async event=>{
  event.preventDefault();clearError();
  try{
    await transport.request("login",{method:"POST",body:{loginName:$("login-name").value,password:$("login-password").value}});
    $("login-password").value="";manifest=await transport.manifest();
    const bytes=manifest.manifest.files.reduce((n,f)=>n+f.size,0);
    $("content-description").textContent=manifest.manifest.packageId+" · "+manifest.manifest.version+" · "+manifest.manifest.files.length+" 个文件 · "+(bytes/1048576).toFixed(2)+" MiB";
    $("content-confirm").hidden=false;
  }catch(error){report(error);}
};
$("prepare").onclick=async()=>{
  clearError();$("prepare").disabled=true;
  try{
    const data=await transport.sync(manifest,(done,total)=>{$("download-progress").value=total?done/total:1;});
    $("play-panel").hidden=false;$("package-title").textContent=data.manifest.packageId;
    unmount?.();unmount=await mountPackage($("package-frame"),data,transport,html=>api("/local/package-view",{html}));
    subscription?.close();subscription=transport.open(onState,()=>{clearRoomView();$("join-status").textContent="实时状态中断，请重新加入。";});
    $("join-status").textContent="已进入房间，本次下载 "+data.downloadedBytes+" 字节。";
    $("content-confirm").hidden=true;$("login-form").hidden=true;
    const network=await transport.stats();$("network-info").hidden=false;
    $("network-info").textContent=(network.localType==="relay"||network.remoteType==="relay"?"TURN 中继":"P2P 直连")+" · "+(network.rttMs===null?"延迟测量中":network.rttMs+" ms");
    $("play-panel").scrollIntoView({behavior:"smooth",block:"start"});
  }catch(error){report(error);}
  finally{$("prepare").disabled=false;}
};
function clearRoomView(){view=null;parts=null;unmount?.();unmount=null;$("snapshot").textContent="状态已清空";$("play-panel").hidden=true;}
function onState(message){
  if(message.type==="reset"){clearRoomView();transport?.close();$("join-status").textContent="主机已重置授权状态，请重新加入。";return;}
  if(message.type==="snapshot.begin"&&Number.isInteger(message.parts)&&message.parts>0&&message.parts<=128)parts={id:message.id,count:message.parts,values:Array(message.parts).fill(null)};
  if(message.type==="snapshot.part"&&parts?.id===message.id&&Number.isInteger(message.index)&&message.index>=0&&message.index<parts.count&&typeof message.data==="string")parts.values[message.index]=message.data;
  if(message.type==="snapshot.end"&&parts?.id===message.id){
    if(parts.values.filter(x=>typeof x==="string").length===parts.count){view=JSON.parse(parts.values.join(""));$("snapshot").textContent=JSON.stringify(view,null,2);}
    parts=null;
  }
}
$("send-chat").onclick=async()=>{
  clearError();try{
    if(!view)throw new Error("尚未收到主机状态");
    const command={protocolVersion:1,type:"command",requestId:crypto.randomUUID(),roomId:view.roomId,payload:{commandId:crypto.randomUUID(),runId:view.runId,authorityEpoch:view.authorityEpoch,catalogRevision:view.catalog.revision,rulesetRevision:view.catalog.rulesetRevision,expectedViews:{},op:"chat.message.send",args:{channelId:$("chat-channel").value,text:$("chat-text").value}}};
    const result=await transport.request("commands",{method:"POST",body:command});
    $("chat-status").textContent="已提交："+JSON.stringify(result);$("chat-text").value="";
  }catch(error){report(error);}
};
function leave(){
  unmount?.();unmount=null;subscription?.close();subscription=null;transport?.close();transport=null;view=null;manifest=null;
  for(const id of ["login-form","content-confirm","network-info","play-panel","leave"])$(id).hidden=true;
  $("join-status").textContent="尚未加入房间";
}
$("leave").onclick=leave;
$("host-form").onsubmit=async event=>{
  event.preventDefault();clearError();$("host-start").disabled=true;
  try{
    const result=await api("/local/host/start",{title:$("host-title").value,summary:$("host-summary").value,visibility:$("host-visibility").value,password:$("host-password").value,approvalRequired:$("host-approval").checked,maxPlayers:Number($("host-max").value),upstream:$("host-upstream").value,relayOnly:$("host-relay").checked});
    $("host-password").value="";$("host-notice").textContent="已发布。复制加入信息给玩家，即可粘贴快速加入。";
    $("host-invitation").hidden=!result.invitation;$("share-invitation").value=result.invitation||"";
    await status();await refresh();
  }catch(error){report(error);}
  finally{$("host-start").disabled=Boolean(hostState);}
};
$("host-stop").onclick=async()=>{try{await api("/local/host/stop",{});$("host-invitation").hidden=true;await status();await refresh();}catch(e){report(e);}};
$("host-lock").onclick=async()=>{try{locked=!locked;await api("/local/host/lock",{locked});await status();}catch(e){report(e);}};
async function status(){
  const state=await api("/local/status");$("directory-address").textContent=state.directory;hostState=state.host;
  hostEnabled=state.hostEnabled;
  if(!initialized){$("host-upstream").value=state.upstream;initialized=true;}
  $("host-form").hidden=!state.hostEnabled;
  $("local-hosts").disabled=$("host-upstream").disabled=$("host-start").disabled=Boolean(state.host);
  $("host-share").hidden=!state.host?.room?.roomId;
  $("host-invitation").hidden=!state.invitation;
  $("share-invitation").value=state.invitation||"";
  if(!state.hostEnabled)$("host-notice").textContent="此入口用于加入房间。发布房间需要配置发布者凭据。";
  $("host-running").textContent=state.host?.running?"已发布":state.host?"正在恢复连接":"未发布";
  $("host-lock").disabled=$("host-stop").disabled=!state.host;
  $("host-details").replaceChildren();
  if(state.host?.room?.roomId){
    const room=state.host.room;
    for(const [id,value] of [["share-code",displayCode(room.roomCode)||room.roomId],["share-join",shareText(room,state.invitation)]])if($(id).value!==value)$(id).value=value;
    for(const [label,value]of [[room.roomCode?"房间码":"房间 ID",displayCode(room.roomCode)||room.roomId],["房间名称",state.host.room.title],["状态",state.host.room.joinable?"允许新加入":"已锁定新加入"],["主机进程","由原启动器管理"]]){
      const dt=document.createElement("dt"),dd=document.createElement("dd");dt.textContent=label;dd.textContent=value;$("host-details").append(dt,dd);
    }
    locked=!state.host.room.joinable;$("host-lock").textContent=locked?"恢复新加入":"锁定新加入";
  }
  empty($("pending"),"暂无申请");empty($("players"),"暂无玩家");
  if(state.host?.pending.length){$("pending").replaceChildren();for(const item of state.host.pending){const row=document.createElement("div");row.className="person";const text=document.createElement("span");text.textContent="访客 "+item.clientKeyId.slice(0,12);row.append(text,button("批准",async()=>{await api("/local/host/decide",{intentId:item.intentId,approve:true});await status();}),button("拒绝",async()=>{await api("/local/host/decide",{intentId:item.intentId,approve:false});await status();},"quiet danger"));$("pending").append(row);}}
  if(state.host?.players.length){$("players").replaceChildren();for(const item of state.host.players){const row=document.createElement("div");row.className="person";const text=document.createElement("span");text.textContent=(item.accountId||"正在登录")+" · "+(item.ready?"已进入":"准备中");row.append(text,button("移出",async()=>{await api("/local/host/kick",{intentId:item.intentId,ban:false});await status();},"quiet danger"),button("封禁",async()=>{await api("/local/host/kick",{intentId:item.intentId,ban:true});await status();},"quiet danger"));$("players").append(row);}}
}
async function refreshLocal(){
  if(!hostEnabled)return;
  $("refresh-local").disabled=true;
  try{
    const result=await api("/local/hosts");localHosts=result.items;
    const select=$("local-hosts");select.replaceChildren(new Option("手动填写地址 / 请选择房间",""));
    for(const item of localHosts)select.append(new Option(item.label+" · "+item.url,item.url));
    let selected=localHosts.find(item=>item.url===$("host-upstream").value);
    if(!selected&&!upstreamEdited&&!hostState&&localHosts.length===1){
      selected=localHosts[0];$("host-upstream").value=selected.url;
    }
    select.value=selected?.url||"";
    $("local-host-note").textContent=selected?(selected.dataDirectory||selected.url):
      localHosts.length?"发现多个宿主，请选择要分享的房间。":"没有发现已运行的宿主。请先启动游戏，再刷新；也可在连接设置填写地址。";
  }finally{$("refresh-local").disabled=false;}
}
$("refresh-local").onclick=()=>refreshLocal().catch(report);
$("local-hosts").onchange=()=>{
  const item=localHosts.find(item=>item.url===$("local-hosts").value);
  if(item){$("host-upstream").value=item.url;upstreamEdited=true;$("local-host-note").textContent=item.dataDirectory||item.url;}
};
$("host-upstream").oninput=()=>{upstreamEdited=true;$("local-hosts").value="";};
async function copyShare(id){
  const input=$(id);
  try{await navigator.clipboard.writeText(input.value);$("share-note").textContent="已复制，请发给准备加入的玩家。";}
  catch{input.focus();input.select();$("share-note").textContent="已选中，请按 Ctrl+C 复制。";}
}
$("copy-code").onclick=()=>copyShare("share-code");
$("copy-join").onclick=()=>copyShare("share-join");
window.addEventListener("beforeunload",()=>transport?.close());
status().then(()=>Promise.all([refresh(),refreshLocal()])).catch(report);
setInterval(()=>status().catch(()=>{}),3000);
