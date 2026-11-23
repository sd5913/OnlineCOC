import {rememberLogin} from "./remember.js";
const $=s=>document.querySelector(s);
let user, poll, nextPublicOffset = null;
const [pageKind, pageRoom] = location.pathname.split("/").filter(Boolean);
const joinPage = !pageKind || pageKind === "join";
const messages={LOGIN_REQUIRED:"请先登录",AUTH_INVALID:"账号、密码或恢复码不正确",NAME_INVALID:"账号须为 3–32 位字母、数字、下划线或连字符",PASSWORD_LENGTH:"密码至少 6 位",ACCOUNT_EXISTS:"账号已存在",ROOM_UNAVAILABLE:"房间不可加入，请核对代号、凭据及房主是否在线",MEMBERSHIP_REQUIRED:"成员资格无效或已被移除",ROOM_CLOSED:"房间已永久解散",GAME_ALREADY_OPEN:"此账号已在该房间打开游戏。请先离开原游戏页；异常关闭后最多等待 35 秒",ROOM_FULL:"游戏席位已满",CLAIM_INVALID:"房主认领码无效或已过期",RESOURCE_FORBIDDEN:"无权读取该资源",RATE_LIMITED:"请求过于频繁，请稍后重试"};
Object.assign(messages,{SETUP_INVALID:"开房串格式无效，请从配置包重新复制",SETUP_VERSION_UNSUPPORTED:"此开房串版本暂不支持",SETUP_PLATFORM_MISMATCH:"此开房串属于其他平台，请打开房主配置的平台地址",ROOM_PASSWORD_INVALID:"房间密码须为 1–128 个字符",OWNER_REQUIRED:"只有房主可以管理这个房间",CLAIM_INVALID:"开房串已使用、过期或房主离线，请在本机重新生成"});
const remembered=rememberLogin("platform",$("#name"),$("#password"),$("#remember-login"),$("#forget-login"),message=>{$("#notice").textContent+="\n"+message;});
export function showError(error){$("#error").hidden=false;$("#error").textContent=messages[error.code]||error.message||String(error);}
export async function api(path,data,credential,keepalive=false){
  const response=await fetch("/v1/web/"+path,{method:data===undefined?"GET":"POST",credentials:"same-origin",keepalive,headers:{"Content-Type":"application/json",...(user?{"X-CSRF-Token":user.csrf}:{}),...(credential?{Authorization:"Bearer "+credential}:{})},...(data===undefined?{}:{body:JSON.stringify(data)})});
  const result=await response.json();if(!response.ok)throw Object.assign(new Error(result.code),result);return result;
}
function run(fn){return async e=>{e?.preventDefault();$("#error").hidden=true;try{await fn(e);}catch(error){showError(error);}};}
function text(parent,tag,value){const element=document.createElement(tag);element.textContent=value;parent.append(element);return element;}
function action(parent,label,handler){const b=text(parent,"button",label);b.onclick=run(handler);return b;}
async function identity(){
  $("#identity").replaceChildren();text($("#identity"),"span",user.name);
  action($("#identity"),"退出账号",async()=>{await api("auth/logout",{});try{new BroadcastChannel("onlinecoc-web").postMessage({type:"logout"});for(const db of await indexedDB.databases())if(db.name?.startsWith("onlinecoc-web:"+user.accountId+":"))indexedDB.deleteDatabase(db.name);}catch{}location.assign("/");});
}
async function lobby(){
  $("#lobby").hidden=false;const result=await api("rooms");$("#recent").replaceChildren();
  for(const room of result.items){const link=text($("#recent"),"a",room.title+" · "+(room.closed?"已解散":room.online?"在线":"房主离线"+(room.expiresAt?" · 保留至 "+new Date(room.expiresAt*1000).toLocaleString():"")));if(!room.closed)link.href="/room/"+encodeURIComponent(room.roomId);}
  if(!result.items.length)text($("#recent"),"p","成功加入后，房间会保存在这里。");
}
async function room(rid){
  $("#room").hidden=false;
  async function refresh(){
    const data=await api("rooms/"+rid+"/presence",{});
    if(data.status==="pending"){$("#room-title").textContent="等待房主批准";$("#enter-game").disabled=true;return;}
    const m=data.metadata;$("#room-title").textContent=m.title;$("#room-status").textContent=(data.online?"房主在线":"房主暂时离线，以下为上次发布信息")+" · 更新于 "+new Date(data.updated*1000).toLocaleString();
    $("#package-info").textContent=m.package.name+" · "+m.package.version;$("#package-source").textContent="来源："+m.package.source;$("#package-description").textContent=m.description;$("#rules").textContent=m.rules;
    $("#download-info").textContent="启动资源 "+(m.startupBytes/1024).toFixed(1)+" KiB；全部资源上限 "+(m.totalBytes/1024).toFixed(1)+" KiB。游戏席位 "+data.seats+" / "+data.maxPlayers;
    $("#people").replaceChildren();for(const p of data.people)text($("#people"),"li",p.name+" · "+(p.role==="host"?"房主":"玩家")+" · "+(p.state==="game"?"游戏中":"房间中"));
    $("#enter-game").disabled=!data.online||data.seats>=data.maxPlayers;
    $("#enter-game").onclick=()=>window.open("/game/"+encodeURIComponent(rid),"onlinecoc-game-"+rid,"noopener");
    $("#manage-room-link").hidden=!data.owner;
    $("#manage-room-link").href="/manage/"+encodeURIComponent(rid);
  }
  await refresh();poll=setInterval(()=>refresh().catch(error=>{clearInterval(poll);$("#room").hidden=true;showError(error);}),10000);
}
async function publicRooms(append=false){
  $("#public-list").hidden=false;
  const result=await api("public-rooms?offset="+(append?nextPublicOffset||0:0));
  const box=$("#public-rooms");if(!append)box.replaceChildren();
  for(const room of result.items){
    const card=document.createElement("article");box.append(card);text(card,"h3",room.title);
    text(card,"p",room.package.name+" · "+room.package.version);
    text(card,"p",(room.passwordRequired?"需要密码":"无密码")+(room.approvalRequired?" · 需要审批":"")+(room.invitationRequired?" · 需要邀请":"")+" · 游戏席位 "+room.seats+" / "+room.maxPlayers);
    action(card,"选择此房间",async()=>{
      $("#room-code").value=room.roomCode;$("#room-password").value="";$("#invitation").value="";
      if(!user){$("#notice").textContent="已选择房间，请先登录后加入。";$("#auth").scrollIntoView();return;}
      $("#join-form").scrollIntoView();(room.passwordRequired?$("#room-password"):$("#room-code")).focus();
    });
  }
  if(!box.children.length)text(box,"p","暂无公开且在线的房间，也可以登录后凭代号加入。");
  nextPublicOffset=result.nextOffset;$("#more-public").hidden=nextPublicOffset===null;
}
async function management(rid){
  $("#management").hidden=false;
  const mine=await api("rooms");const box=$("#owned-rooms");box.replaceChildren();
  const owned=mine.items.filter(r=>r.owner);
  for(const r of owned){const link=text(box,"a",r.title+" · "+(r.closed?"已解散":r.online?"在线":"离线"+(r.expiresAt?" · 保留至 "+new Date(r.expiresAt*1000).toLocaleString():"")));if(!r.closed)link.href="/manage/"+encodeURIComponent(r.roomId);}
  if(!owned.length)text(box,"p","还没有创建房间，请从创建页粘贴配置包提供的开房串。");
  if(!rid)return;
  let settingsLoaded=false;
  async function refresh(){
    const data=await api("rooms/"+rid+"/presence",{});
    if(!data.owner)throw Object.assign(new Error("OWNER_REQUIRED"),{code:"OWNER_REQUIRED"});
    $("#owner").hidden=false;$("#manage-title").textContent=data.metadata.title;
    $("#share").textContent="房间代号："+data.roomCode.slice(0,4)+"-"+data.roomCode.slice(4)+(data.online?" · 在线":" · 房主离线");
    $("#managed-room-link").href="/room/"+encodeURIComponent(rid);
    if(!settingsLoaded){$("#manage-public").checked=data.public;$("#password-mode").value="keep";$("#manage-password").value="";$("#manage-password-label").hidden=true;$("#manage-password").required=false;settingsLoaded=true;}
    $("#password-status").textContent=data.passwordRequired?"当前已设置房间密码":"当前无房间密码";
    const manage=async(action,accountId,extra={})=>{await api("rooms/"+rid+"/manage",{action,accountId,...extra});await refresh();};
    for(const [selector,items]of [["#applications",data.pending],["#members",data.members],["#bans",data.banned]]){
      const target=$(selector);target.replaceChildren();
      for(const item of items){const row=document.createElement("div");row.className="member";target.append(row);text(row,"span",item.name+" ");
        if(selector==="#applications"){action(row,"批准",()=>manage("approve",item.accountId));action(row,"拒绝",()=>manage("reject",item.accountId));}
        if(selector==="#members"&&item.accountId!==user.accountId){action(row,"移除",()=>manage("remove",item.accountId));action(row,"拉黑",()=>manage("ban",item.accountId));action(row,"资源授权",async()=>{const value=prompt("允许的受限资源组 ID（逗号分隔）；清空撤销，变更后玩家须重新连接。",(item.groups||[]).join(","));if(value!==null)await manage("grant",item.accountId,{groups:value.split(",").map(x=>x.trim()).filter(Boolean)});});}
        if(selector==="#bans")action(row,"解除黑名单",()=>manage("unban",item.accountId));
      }
    }
    $("#settings-form").onsubmit=run(async()=>{
      await api("rooms/"+rid+"/manage",{action:"settings",public:$("#manage-public").checked,passwordMode:$("#password-mode").value,password:$("#manage-password").value});
      settingsLoaded=false;await refresh();$("#notice").textContent="房间设置已保存；密码变更影响首次加入，已有成员仍可快捷重入。";
    });
    $("#close-room").onclick=run(async()=>{if(confirm("解散并移除房间后，代号、成员和快捷入口立即失效。本机存档保留。继续？")){await api("rooms/"+rid+"/manage",{action:"close"});location.assign("/manage");}});
  }
  await refresh();poll=setInterval(()=>refresh().catch(error=>{clearInterval(poll);$("#owner").hidden=true;showError(error);}),10000);
}
async function ready(){
  await identity();$("#auth").hidden=true;
  if(pageKind==="game"){const {startGame}=await import("./game.js");await startGame(pageRoom,user,api,showError);}
  else if(pageKind==="room")await room(pageRoom);
  else if(pageKind==="create")$("#create").hidden=false;
  else if(pageKind==="manage")await management(pageRoom);
  else await lobby();
}
$("#auth-form").onsubmit=run(async e=>{
  const name=$("#name").value,password=$("#password").value;
  if([...password].length<6)throw Object.assign(new Error("PASSWORD_LENGTH"),{code:"PASSWORD_LENGTH"});
  user=await api("auth/"+e.submitter.value,{name,password,recovery:$("#recovery").value});
  if(user.recovery)$("#notice").textContent="请现在保存账号恢复码（仅显示一次）：\n"+user.recovery+"\n遗失密码且没有恢复码时无法自助找回。";
  remembered.save(name,password);$("#password").value="";$("#recovery").value="";await ready();
});
$("#recover-toggle").onclick=()=>{$("#recovery-label").hidden=false;$("#recover-submit").hidden=false;};
$("#join-form").onsubmit=run(async()=>{const result=await api("join",{roomCode:$("#room-code").value,password:$("#room-password").value,invitation:$("#invitation").value});location.assign("/room/"+encodeURIComponent(result.roomId));});
$("#claim-form").onsubmit=run(async()=>{const result=await api("claim",{roomCode:$("#claim-room").value,claim:$("#claim-token").value});location.assign("/manage/"+encodeURIComponent(result.roomId));});
$("#create-locked").onchange=()=>{$("#create-password-label").hidden=!$("#create-locked").checked;$("#create-password").required=$("#create-locked").checked;if(!$("#create-locked").checked)$("#create-password").value="";};
$("#password-mode").onchange=()=>{$("#manage-password-label").hidden=$("#password-mode").value!=="set";$("#manage-password").required=$("#password-mode").value==="set";};
$("#setup-string").oninput=()=>{$("#setup-preview").textContent="";};
$("#preview-setup").onclick=run(async()=>{const data=await api("rooms/preview",{setupString:$("#setup-string").value});$("#setup-preview").textContent=data.metadata.title+"\n"+data.metadata.package.name+" · "+data.metadata.package.version+(data.approvalRequired?"\n首次加入需房主审批":"")+(data.invitationRequired?"\n首次加入还需本机设置的邀请凭据":"");});
$("#create-form").onsubmit=run(async()=>{
  $("#create-submit").disabled=true;
  try{const result=await api("rooms/create",{setupString:$("#setup-string").value,public:$("#create-public").checked,password:$("#create-locked").checked?$("#create-password").value:""});$("#setup-string").value="";$("#create-password").value="";location.assign("/manage/"+encodeURIComponent(result.roomId));}
  finally{$("#create-submit").disabled=false;}
});
$("#refresh-public").onclick=run(()=>publicRooms());$("#more-public").onclick=run(()=>publicRooms(true));
for(const link of document.querySelectorAll("nav a"))if(link.pathname==="/"+(joinPage?"join":pageKind))link.setAttribute("aria-current","page");
if(joinPage)await publicRooms().catch(showError);
try{user=await api("me");await ready();}catch(error){if(error.code==="LOGIN_REQUIRED")$("#auth").hidden=false;else showError(error);}
