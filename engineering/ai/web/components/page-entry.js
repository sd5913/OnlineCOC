import {AiClient,mountAIPage,mountAIConversation,mountAICollapsible,mountSessionManager} from './pack.js';
const $=id=>document.getElementById(id),client=new AiClient();let panel=null,dead=false;
const mounts={page:mountAIPage,conversation:mountAIConversation,collapsible:mountAICollapsible,sessions:mountSessionManager};
async function connected(){
 if(dead)return;panel?.destroy();
 const generation=client.generation;
 const capabilities=await client.transport.request('capabilities');
 if(dead||!client.connected||generation!==client.generation)return;
 if(!capabilities.ai?.available)throw new Error('当前房间未启用 AI 模块');
 $('login').hidden=true;$('room').hidden=false;$('account-label').textContent=client.view.accountId;
 panel=mounts[document.body.dataset.variant]($('panel'),client,{onOpen:id=>{location.href='conversation.html?session='+encodeURIComponent(id);}});
 const session=new URLSearchParams(location.search).get('session');
 if(session){if(!/^[a-f0-9]{32}$/.test(session))throw new Error('会话参数格式不正确');await panel.select(session);}
}
function fail(error){$('entry-status').textContent=error.code||error.message;}
$('login').onsubmit=async event=>{event.preventDefault();$('entry-status').textContent='';const password=$('password').value;$('password').value='';$('connect').disabled=true;
 try{await client.login($('account').value,password);await connected();}catch(error){fail(error);}finally{$('connect').disabled=false;}
};
$('logout').onclick=async()=>{panel?.destroy();panel=null;try{await client.logout();}catch(error){fail(error);}$('room').hidden=true;$('login').hidden=false;$('account-label').textContent='';};
client.subscribe(()=>{if(!client.connected){panel?.destroy();panel=null;$('room').hidden=true;$('login').hidden=false;$('account-label').textContent='';}});
window.addEventListener('pagehide',()=>{dead=true;panel?.destroy();client.destroy();},{once:true});
try{await client.resume();await connected();}catch(error){if(!String(error.code||'').startsWith('AUTH'))fail(error);}
