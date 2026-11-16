import {WebRtcTransport} from "./transport.js";
import {ResourceLoader} from "./resources.js";
import {mountGame} from "./sandbox.js";
import {rememberLogin} from "./remember.js";
const $=s=>document.querySelector(s);
export async function startGame(rid,user,api,showError){
  $("#connect").disabled=true;$("#game").hidden=false;let transport,loader,cleanup,timer,statsTimer,intentId,leaving=false;
  const info=await api("rooms/"+rid+"/presence",{});if(info.status!=="member")throw new Error("MEMBERSHIP_REQUIRED");
  const version=info.metadata.resourceVersion;
  const remembered=rememberLogin("game:"+user.accountId+":"+rid,$("#game-name"),$("#game-password"),$("#remember-game-login"),$("#forget-game-login"),message=>{$("#notice").textContent=message;});
  $("#game h1").textContent=info.metadata.title;$("#game-status").textContent="点击连接后建立 P2P；登录游戏账号后只加载启动资源。";
  const stop=async(clear=false)=>{
    if(leaving)return;leaving=true;document.body.classList.remove("web-playing");clearInterval(timer);clearInterval(statsTimer);cleanup?.();if(clear)loader?.clear();
    if(intentId)try{await api("game/leave",{intentId},undefined,true);}catch{}
    transport?.close();$("#game-login").hidden=true;$("#leave").hidden=true;$("#connect").disabled=false;$("#game-status").textContent="已离开游戏";intentId=null;leaving=false;
  };
  const failed=async error=>{showError(error);await stop(true);};
  const beat=()=>api("game/ping",{intentId}).catch(failed);
  $("#connect").onclick=async()=>{
    $("#connect").disabled=true;$("#error").hidden=true;
    try{
      const control=async(kind,data,credential)=>{
        if(kind==="turn"){
          const response=await fetch("/v1/turn-credentials",{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+credential},body:JSON.stringify(data)});
          const result=await response.json();if(!response.ok)throw Object.assign(new Error(result.code),result);return result;
        }
        const result=await api("game/"+(kind==="session"?"session":"join"),kind==="join"?{...data,resourceVersion:version}:data,credential);
        if(kind==="join"){intentId=result.intentId;timer=setInterval(beat,8000);$("#leave").hidden=false;}
        return result;
      };
      transport=new WebRtcTransport(control,null,status=>{$("#game-status").textContent=status;}, {signalPath:"/v1/signaling",auth:s=>({type:"auth",role:"client",token:s.clientToken})});
      const admitted=await transport.connect({roomId:rid,relayOnly:$("#relay").checked});
      if(admitted.resourceProtocol!==2||admitted.resourceVersion!==version)throw new Error("VERSION_CHANGED");
      $("#game-login").hidden=false;
      statsTimer=setInterval(async()=>{try{const s=await transport.stats();$("#network").textContent=(s.localType==="relay"||s.remoteType==="relay"?"TURN 中继":"P2P 直连")+" · "+s.state+" · 本次下载 "+((loader?.downloaded||0)/1024).toFixed(1)+" KiB";}catch{}},3000);
    }catch(error){await failed(error);}
  };
  $("#game-login").onsubmit=async event=>{
    event.preventDefault();const button=event.submitter;button.disabled=true;
    try{
      const name=$("#game-name").value,password=$("#game-password").value;
      await transport.request("login",{method:"POST",body:{loginName:name,password}});
      remembered.save(name,password);$("#game-password").value="";
      loader=new ResourceLoader(transport,user.accountId,version);$("#progress").hidden=false;
      const data=await loader.load("startup",(done,total)=>{$("#progress").max=total||1;$("#progress").value=done;});
      cleanup?.();cleanup=await mountGame($("#package-frame"),data,transport,loader,{onLeave:()=>stop(true)});$("#game-login").hidden=true;$("#progress").hidden=true;$("#error").hidden=true;$("#game-status").textContent="已进入游戏";document.body.classList.add("web-playing");
    }catch(error){showError(error);}finally{button.disabled=false;}
  };
  $("#leave").onclick=()=>stop(true);
  window.addEventListener("pagehide",()=>{if(intentId)api("game/leave",{intentId},undefined,true).catch(()=>{});transport?.close();});
  try{const channel=new BroadcastChannel("onlinecoc-web");channel.onmessage=e=>{if(e.data?.type==="logout")stop(true);};}catch{}
  $("#connect").disabled=false;
}
