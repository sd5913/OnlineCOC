// A small package-owned view over the module's public headless client.
// No model replies enter the action engine, and no publishing UI is mounted.
let identity = '', current = null, epoch = 0;
import {t} from './i18n.js';
const wordKeys = ["title", "close", "refresh", "disabled", "scope", "sessions", "new", "name", "send", "text", "archive", "archived", "queue", "dispatch", "cancel", "settings", "enabled", "public", "kp", "private", "save", "saved", "submitted", "more", "empty", "loading", "offline", "unconfigured", "p2p", "running", "stopped", "p2perror", "pending", "receipt", "consult", "received", "queued", "generating", "validating", "review_ready", "blocked", "needs_input", "failed", "cancelled", "interrupted", "stale", "approved", "published", "profile"];

const esc = value => String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const aiUI = {
  update(state, manager, language) {
    const next=state?JSON.stringify([state.accountId,manager,language]):'';
    if(next!==identity){this.close();identity=next;}
  },
  close(){epoch++;const previous=current;current=null;previous?.destroy();},
  async open({base,manager,language,onQueue=()=>{}}) {
    this.close();const generation=epoch, w=Object.fromEntries(wordKeys.map(key=>[key,t('ai.'+key)]));
    const dialog=document.createElement('dialog');dialog.className='ai-dialog';dialog.setAttribute('aria-label',w.title);
    dialog.innerHTML=`<header><h2>${w.title}</h2><button data-close>${w.close}</button></header><p>${w.scope}</p><p data-status role="status">${w.loading}</p><div data-body></div>`;
    document.body.append(dialog);dialog.showModal();const status=dialog.querySelector('[data-status]'),body=dialog.querySelector('[data-body]');
    let client=null,timer=null,session=null,loading=false,nextBefore=null,uncertain=null;
    const live=()=>generation===epoch&&dialog.isConnected;
    current={destroy(){clearInterval(timer);client?.destroy();dialog.remove();}};
    dialog.querySelector('[data-close]').onclick=()=>this.close();dialog.addEventListener('cancel',e=>{e.preventDefault();this.close();});
    const check=r=>{if(r.status!=='committed')throw new Error(r.code||r.status);return r.result;};
    const run=async fn=>{if(loading||!live())return;loading=true;try{await fn();}catch(e){if(live()){uncertain=e.aiRequestId||null;status.textContent=(e.code==='AI_CONSULTATION_ONLY'?w.consult:e.code||e.message)+(uncertain?' · '+w.pending+' · '+uncertain:'');body.querySelector('[data-receipt]')?.removeAttribute('hidden');}}finally{loading=false;}};
    const command=async(op,args)=>{if(uncertain)throw new Error(w.pending);return check(await client.aiCommand(op,args));};
    const button=(text,fn)=>{const b=document.createElement('button');b.textContent=text;b.type='button';b.onclick=()=>run(fn);return b;};
    try {
      const web=globalThis.stumpsvilleWeb;
      const transport=web?{request(path,{method='GET',body}={}){
        if(path==='me')return Promise.resolve({csrf:null});
        if(path==='view')return web.api('api/v1/view');
        return web.api('package/ai',{path,method,...(body===undefined?{}:{body})});
      }}:null;
      const caps=transport?await transport.request('capabilities'):await fetch(new URL('api/v1/capabilities',base),{credentials:'same-origin'}).then(r=>r.json());
      if(!live())return;
      if(!caps.ai?.available){status.textContent=w.disabled;return;}
      const {AiClient,HttpTransport,mountMarkdown}=web?web.aiModules:await import(new URL('ai-ui/pack.js',base).href);
      if(!live())return;
      client=new AiClient(transport||new HttpTransport(new URL('api/v1/',base).href));await client.resume();
      if(!live()){client.destroy();return;}
      const account=client.view.accountId,authority=client.view.authorityEpoch;
      client.subscribe(()=>{if(live()&&(!client.connected||client.view?.accountId!==account||client.view?.authorityEpoch!==authority)){this.close();}});
      body.innerHTML=`<div class="ai-columns" ${manager?'hidden':''}><section><h3>${w.sessions}</h3><form data-create><input name="title" maxlength="120" required placeholder="${w.name}" aria-label="${w.name}"><button>${w.new}</button></form><label><input type="checkbox" data-archived>${w.archived}</label><div data-list></div></section><section><div data-detail hidden><h3 data-title></h3><div data-history></div><form data-send><textarea name="text" maxlength="8000" required aria-label="${w.text}" placeholder="${w.text}"></textarea><button>${w.send}</button></form><button data-archive>${w.archive}</button></div></section></div>${manager?`<details><summary>${w.settings}</summary><form data-settings></form></details><p>${t('queue.allInRulings')}</p><button data-queue>${t('queue.open')}</button><p data-network>${w.p2p}</p>`:''}<button data-refresh>${w.refresh}</button><button data-receipt hidden>${w.receipt}</button>`;
      const $=s=>body.querySelector(s);
      if(manager)$('[data-queue]').onclick=onQueue;
      const rows=(target,items)=>{target.replaceChildren();for(const item of items){const row=document.createElement('article');row.className='ai-task';const p=document.createElement('p');p.textContent=(item.text||'')+' · '+(w[item.status]||item.status);row.append(p);
        if(item.response){const answer=document.createElement('div');answer.className='ai-answer';row.append(answer);mountMarkdown(answer,item.response,{plainText:target.matches('[data-history]')&&session?.renderMode==='plain',resolveReferences:tokens=>client.aiResolve(tokens)});}
        if(item.error){const err=document.createElement('p');err.textContent=item.error;row.append(err);}
        if(manager)row.append(button(t('queue.open'),onQueue));
        if(!manager&&['received','queued','generating','validating','review_ready','needs_input'].includes(item.status))row.append(button(w.cancel,async()=>{await command('ai.request.cancel',{requestId:item.requestId});await refresh();}));
        target.append(row);
      }if(!items.length)target.textContent=w.empty;};
      async function select(id){const data=await client.aiSession(id);if(!live())return;session=data.session;$('[data-detail]').hidden=false;$('[data-title]').textContent=session.title;$('[data-send]').hidden=session.archived;$('[data-archive]').hidden=session.archived;rows($('[data-history]'),data.items);}
      async function sessions(){const data=await client.aiSessions($('[data-archived]').checked);if(!live())return;$('[data-list]').replaceChildren(...data.items.map(s=>button(s.title+' · '+s.requestCount,()=>select(s.sessionId))));if(!data.items.length)$('[data-list]').textContent=w.empty;}

      async function refresh(){if(manager)return;await sessions();if(session)await select(session.sessionId);}
      $('[data-create]').onsubmit=e=>{e.preventDefault();run(async()=>{const form=e.target;const result=await command('ai.session.create',{title:form.elements.title.value.trim()});if(!live())return;form.reset();$('[data-archived]').checked=false;await sessions();await select(result.sessionId);});};
      $('[data-send]').onsubmit=e=>{e.preventDefault();run(async()=>{await command('ai.session.submit',{sessionId:session.sessionId,text:e.target.elements.text.value});if(!live())return;e.target.reset();status.textContent=w.submitted;await refresh();});};
      $('[data-archive]').onclick=()=>run(async()=>{await command('ai.session.update',{sessionId:session.sessionId,revision:session.revision,archived:true});session=null;$('[data-detail]').hidden=true;await sessions();});
      $('[data-archived]').onchange=()=>run(async()=>{session=null;$('[data-detail]').hidden=true;await sessions();});
      $('[data-refresh]').onclick=()=>manager?this.open({base,manager,language,onQueue}):run(refresh);
      $('[data-receipt]').onclick=()=>run(async()=>{if(!uncertain)return;const result=await client.aiReceipt(uncertain);if(!live())return;status.textContent=JSON.stringify(result);if(result.status==='committed'||result.status==='rejected'){uncertain=null;$('[data-receipt]').hidden=true;await refresh();}});
      if(manager){
        const data=await client.aiSettings();if(!live())return;const s=data.settings,form=$('[data-settings]');
        if(!s.enabled||!Object.values(s.externalSources).some(Boolean))form.parentElement.open=true;
        const readiness=(enabled,policy,profile)=>t(!profile?.enabled?'ai.setupProvider':!enabled?'ai.enableHint':!Object.values(policy).some(Boolean)?'ai.noRoomData':'ai.ready');
        form.innerHTML=`<p data-ai-readiness>${readiness(s.enabled,s.externalSources,data.profiles.find(p=>p.profileId===s.profileId))}</p><p class="muted">${t('ai.scopeHelp')}</p><label><input name="enabled" type="checkbox" ${s.enabled?'checked':''}>${w.enabled}</label><select name="profile" aria-label="${w.profile}">${data.profiles.map(p=>`<option value="${esc(p.profileId)}" ${p.profileId===s.profileId?'selected':''}>${esc(p.profileId+' / '+p.model)}${p.enabled?'':' ('+w.unconfigured+')'}</option>`).join('')}</select>${['public','kp','private'].map(k=>`<label><input type="checkbox" name="${k}" ${s.externalSources[k]?'checked':''}>${w[k]}</label>`).join('')}<button>${w.save}</button>`;
        let accessRevision=data.access.revision;
        const accessForm=document.createElement('form');accessForm.dataset.accessSettings='';
        accessForm.innerHTML=`<h3>${t('ai.accessTitle')}</h3><label><input type="checkbox" name="allowPlayerChat">${t('ai.allowPlayers')}</label><label><input type="checkbox" name="autoApproveBatches">${t('ai.autoApprove')}</label><label><input type="checkbox" name="autoApproveConfigurations">通过三检后自动批准并加载配置</label><button>${t('ai.saveAccess')}</button>`;
        form.after(accessForm);accessForm.elements.allowPlayerChat.checked=data.access.allowPlayerChat;accessForm.elements.autoApproveBatches.checked=data.access.autoApproveBatches;accessForm.elements.autoApproveConfigurations.checked=data.access.autoApproveConfigurations;
        accessForm.onsubmit=e=>{e.preventDefault();run(async()=>{const value=await command('ai.access.update',{revision:accessRevision,allowPlayerChat:accessForm.elements.allowPlayerChat.checked,autoApproveBatches:accessForm.elements.autoApproveBatches.checked,autoApproveConfigurations:accessForm.elements.autoApproveConfigurations.checked});accessRevision=value.revision;status.textContent=w.saved;});};
        form.onsubmit=e=>{e.preventDefault();run(async()=>{await command('ai.settings.update',{enabled:form.elements.enabled.checked,profileId:form.elements.profile.value||null,externalSources:Object.fromEntries(['public','kp','private'].map(k=>[k,form.elements[k].checked])),auto:{enabled:false,channelIds:['general'],prefix:'!ai '}});if(live()){status.textContent=w.saved;const profile=data.profiles.find(p=>p.profileId===form.elements.profile.value);form.querySelector('[data-ai-readiness]').textContent=readiness(form.elements.enabled.checked,Object.fromEntries(['public','kp','private'].map(k=>[k,form.elements[k].checked])),profile);}});};
        // Network diagnostics must not hold up the room's session and review UI.
        client.transport.request('../../package/integrations').then(network=>{
          if(!live()||!form.isConnected)return;
          if(network.ai?.queryMode!=='demand'||!network.ai?.guideCurrent){
            const warning=document.createElement('p');warning.className='ai-guide-warning';warning.setAttribute('role','status');warning.textContent=t('ai.reloadGuide');
            form.prepend(warning);form.parentElement.open=true;
          }
          $('[data-network]').textContent=network.web?.requested?t('ai.web'):network.p2p.requested?w.p2p+' '+(network.p2p.error?w.p2perror:network.p2p.running?w.running:w.stopped):'';
        }).catch(error=>{if(live()&&$('[data-network]'))$('[data-network]').textContent=error.code||w.offline;});
      }
      await refresh();if(!live())return;if(status.textContent===w.loading)status.textContent='';if(!manager)timer=setInterval(()=>run(refresh),4000);
    }catch(e){if(live())status.textContent=e.code||e.message;}
  }
};
