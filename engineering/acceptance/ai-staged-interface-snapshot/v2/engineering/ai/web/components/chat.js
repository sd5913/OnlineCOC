import {requestId as newSubmissionKey} from './client.js';
import {appendDebugTools,appendReviewSource} from './debug.js';
import {mountStyle} from './styles.js';
import {renderMarkdown,markdownStyle} from './markdown.js';
import {guardedClient} from './guard.js';
import {mountChoices} from './choices.js';
import {bindReferenceDetails,referenceView} from './reference-details.js';
import {bindReferenceInput} from './reference-input.js';
import {createReferenceEditor,renderReferenceText,hydrateReferences,applyReferenceLabels} from './reference-editor.js';

const providerErrorHints={
 KNOWLEDGE_UNAVAILABLE:'本房间尚未提供可用的个人知识服务，请 KP 检查配置包接入',
 KNOWLEDGE_EGRESS_DISABLED:'配置包禁止个人已知资料外发给 AI，请 KP 检查知识策略',
 EXTERNAL_SCOPE_DISABLED:'房间尚未允许向 AI 外发本人已知资料，请 KP 检查服务设置',
 DATA_QUERIES_DISABLED:'KP 已关闭 AI 资料查询，仍可通过创作申请提交需求',
 PLAYER_AI_DISABLED:'KP 已关闭玩家 AI 对话',
 PLAYER_REQUESTS_DISABLED:'KP 已关闭玩家创作申请',
 KNOWLEDGE_REQUESTS_DISABLED:'KP 已关闭资料披露申请',
 SOURCE_STALE:'资料依据已变化，请重新读取相关资料后准备方案',
 HISTORY_PROVENANCE_INCOMPLETE:'旧记录未保存足够的来源标识，无法确认历史资料仍可查看；请重新描述需求并查询当前资料',
 HISTORY_REQUERY_REQUIRED:'已保留此前方案意图；需重新读取目标资料后生成待审核修改',
 NOTIFICATION_SOURCE_ACTION_INVALID:'通知必须绑定同一批次中先前的受支持宿主修改动作',
 BATCH_PREFLIGHT_BLOCKED:'指令预检未通过，自动技术修复已停止；打开执行批次查看逐项原因',
 BATCH_UNSUPPORTED:'当前指令组合不支持整批事务，未执行；请查看批次范围说明',
 MODEL_TOOL_REPAIR_LIMIT:'工具参数自动修复已达上限；失败原因已保留在诊断中',
 BATCH_REGENERATE_REQUIRED:'旧候选不具备整批事务保证，请根据原需求生成新候选',
 STALE_AUTHORITY:'房间已重启，旧执行依据不可继续使用；请重新准备方案',
 BASELINE_STALE:'房间状态已变化，请重新读取后准备方案',
 VALIDATOR_STALE:'包契约或检查器已更新，请重新校验方案',
 NOT_VISIBLE:'所选资料当前不可核验，请重新选择本人已知引用',
 SESSION_ACCESS_CHANGED:'会话授权已变化，请重新发送需求',
 PROVIDER_REQUEST_INVALID:'AI 服务商拒绝了请求参数，请联系 KP 检查接入设置',
 PROVIDER_CONTEXT_OVERFLOW:'输入超出 AI 模型窗口，本次生成未完成；请缩小需求后重试',
 PROVIDER_BALANCE_INSUFFICIENT:'AI 服务商余额不足，请联系 KP 处理',
 PROVIDER_NOT_FOUND:'AI 服务接口或模型不存在，请联系 KP 检查配置',
 PROVIDER_REQUEST_TOO_LARGE:'发送给 AI 服务商的请求过大，请缩小资料范围',
 PROVIDER_HTTP_ERROR:'AI 服务商返回异常状态，请联系 KP 查看诊断',
 CONSULTATION_REVIEW_REQUIRED:'请打开裁决详情，核对并明确接受本次来源评估后执行',
 COMPRESSION_INVALID:'上下文摘要格式修复失败，原文已保留；请缩小当前需求后重试',
 COMPRESSION_PROVENANCE_INVALID:'摘要引用或来源身份未通过核验，未执行修改；原文已保留，请重试',
 COMPRESSION_RESULT_LIMIT:'摘要仍然过大，原文已保留；请缩小当前需求后重试',
 COMPRESSION_NOT_REDUCED:'摘要未减少输入大小，原文已保留；请缩小当前需求后重试',
 COMPRESSION_LIMIT:'本次压缩轮数已到上限，请按原方案拆成明确的下一步继续',
 CONTEXT_WINDOW_INVALID:'模型窗口与最大输出预算不匹配，请在本机服务配置中调整',
 CONTEXT_LIMIT_EXCEEDED:'累计资料已达到本地请求容量，请缩小查询范围；KP 可展开诊断查看实际大小',
 UNSUPPORTED_CAPABILITY:'AI 服务返回了当前接入不支持的能力，请联系 KP 检查模型设置'
};
function errorText(code){return providerErrorHints[code]?providerErrorHints[code]+'（'+code+'）':code;}

function appendProgress(target,item){
 const events=item.events||[];
 if(events.length){
  const box=document.createElement('details');box.className='task-progress';box.open=['queued','generating','validating','executing'].includes(item.status);
  const title=document.createElement('summary');title.textContent='处理过程 · '+events.length+' 步';box.append(title);
  const list=document.createElement('ol');
  for(const event of events){const row=document.createElement('li');row.dataset.stage=event.stage;row.dataset.status=event.status;row.dataset.seq=event.seq;
   const time=document.createElement('time');time.dateTime=new Date(event.at*1000).toISOString();time.textContent=new Date(event.at*1000).toLocaleTimeString();row.append(time);
   const state={running:'进行中',completed:'完成',failed:'失败'}[event.status]||event.status;
   row.append(' · '+state+' · '+event.summary+(event.tool?' · '+event.tool:'')+(event.operation?' · '+event.operation:'')+(event.durationMs!==undefined?' · '+(event.durationMs/1000).toFixed(2)+' 秒':'')+(event.receiptStatus?' · 回执 '+event.receiptStatus:'')+(event.code?' · '+event.code:''));list.append(row);
  }box.append(list);target.append(box);
 }
 const check=item.dependencyCheck;
 if(check?.status==='changed'){
  const warning=document.createElement('aside');warning.className='dependency-warning';
  const heading=document.createElement('p');heading.textContent='生成期间资料发生变化。回答和候选已保留，请 KP 判断是否需要重新生成；实际执行仍需通过当前校验。';warning.append(heading);
  const list=document.createElement('ul');for(const change of check.changes||[]){const line=document.createElement('li');line.textContent=change.kind+' · '+change.id+'：'+change.summary+'（'+change.code+'）';list.append(line);}warning.append(list);target.append(warning);
 }
}

function appendDiagnostics(target,item){
 const info=item.diagnostics;
 if(item.error){const error=document.createElement('p');error.className='task-error';error.textContent=(['completed','published','partial','unknown'].includes(item.status)?'原操作状态保留，请核对回执，勿重复执行。旧依据：':'错误：')+errorText(item.error);target.append(error);}
 if(!info)return;
 const reasons={MODEL_JSON_INVALID:'回答不是完整 JSON',MODEL_OBJECT_REQUIRED:'回答应为对象',MODEL_KIND_INVALID:'回答类型无效',MODEL_TEXT_INVALID:'正文为空或超长',MODEL_FIELDS_INVALID:'回答缺少字段或包含额外字段',MODEL_CHOICES_INVALID:'选择项格式无效',REFERENCE_UNVERIFIED:'引用未获得授权证据',REFERENCE_INVALID:'引用格式无效',INPUT_INVALID:'修改参数不符合接口契约'};
 for(const failure of info.outputFailures||[]){const line=document.createElement('p');line.className='task-error';line.textContent='格式修复 '+failure.attempt+'：'+(reasons[failure.code]||failure.code)+'（'+failure.path+'）';target.append(line);}
 const calls=(info.toolCalls||[]).filter(c=>['room_search_data','room_read_data','room_read_chat','room_read_case','room_search_knowledge','room_read_knowledge'].includes(c.name));
 const box=document.createElement('details');box.className='task-diagnostics';
 const title=document.createElement('summary'),completed=calls.filter(c=>c.status==='completed').length;
 title.textContent=completed?'资料查询：已完成 '+completed+' 次':'本次未完成资料查询';box.append(title);
 const stageNames={task_start:'开始任务',profile_check:'检查服务配置',provider_create:'创建模型连接',context_capture:'准备上下文',
  context_recheck:'复验资料权限',budget_reserve:'预留用量',provider_complete:'调用模型',budget_settle:'结算用量',
  response_recheck:'响应后复验',tool_arguments:'解析工具参数',tool_execute:'执行查询',tool_evidence_save:'保存查询依据',
  tool_result_encode:'整理工具结果',output_validate:'校验模型回答',result_save:'保存回答',proposal_create:'创建提案',
  proposal_validate:'检查提案',provider_close:'关闭模型连接',diagnostic_persist:'保存诊断',completed:'已完成'};
 for(const call of info.toolCalls||[]){const line=document.createElement('p');line.textContent=call.name+' · '+({started:'已尝试',completed:'已完成',rejected:'参数或来源被拒绝',failed:'失败'}[call.status]||call.status)+(call.code?' · '+call.code:'');box.append(line);}
 for(const error of info.errors||[]){const line=document.createElement('p');line.textContent=(stageNames[error.stage]||error.stage)+' · '+error.exceptionType+' · '+error.code+(Number.isInteger(error.httpStatus)?' · HTTP '+error.httpStatus:'');box.append(line);
  for(const frame of error.frames||[]){const code=document.createElement('code');code.style.display='block';code.textContent=frame.module+'.'+frame.function+':'+frame.line;box.append(code);}}
 if(info.contextBudget){const b=info.contextBudget,line=document.createElement('p');line.textContent='累计请求 '+Math.ceil(b.bytes/1024)+' / '+Math.round(b.limitBytes/1024)+' KiB；工具资料 '+Math.ceil(b.toolMessageBytes/1024)+' KiB';box.append(line);}
 target.append(box);
}

export function mountChat(target,rawClient,{listTarget,debugTarget=null,renderReference=null,onReview=null,onOpenSource=null,onChange=()=>{},onSelect=()=>{}}={}){
 const shell=document.createElement('div');target.append(shell);const root=shell.attachShadow({mode:'open'});
 mountStyle(root,new URL('./chat.css',import.meta.url));
 markdownStyle(root);const panel=document.createElement('section');panel.className='conversation';root.append(panel);
 panel.innerHTML=`<header><input id="rename" aria-label="会话名称" value="新会话" maxlength="120"><button id="save" title="保存名称">改名</button><span id="session-access"></span><button id="archive">归档</button></header><p id="knowledge-notice"></p><div class="history-wrap"><div id="history" class="messages" role="log" aria-label="对话记录"><div class="welcome"><span>✳</span><h2>今天想为这个房间做些什么？</h2><p>讨论规则、引用数据，或提出一个可供审核的配置方案。</p></div></div><button id="latest" hidden aria-label="回到最新消息">↓ 回到最新</button></div><div class="compose"><button id="reply-target" hidden title="点击取消关联"></button><div id="reference-preview" hidden></div><div id="completion"></div><div id="text" data-placeholder="描述需求，输入 / 选择指令或引用房间数据" aria-label="输入需求"></div><div class="compose-tools"><button id="insert-reference" title="插入数据引用" aria-label="插入数据引用">＋ 引用</button><button id="preview">查看引用</button><button id="player-request" hidden title="只提交需求，由 KP 接收并准备待审方案">提交创作申请</button><label class="send-mode"><select id="send-mode" aria-label="发送快捷键"><option value="enter">Enter 发送</option><option value="ctrl">Ctrl + Enter 发送</option></select></label><span id="length" hidden></span><button id="stop" class="stop" hidden title="停止生成" aria-label="停止生成">■</button><button id="send" class="send" title="发送消息" aria-label="发送消息" disabled>↑</button></div><p id="status" role="status">AI 的建议需经 KP 审核后才能加载到游戏。</p></div>`;
 const $=id=>panel.querySelector('#'+id);let dead=false,paused=false,busy=false,current=null,seq=0,records=[],timer=null,active=false,archivedView=false,listSeq=0,canChat=false,lastData=null,accessPolicy={},replyToRequestId=null,pendingSubmission=null,pendingPlayerSubmission=null;
 function setReply(id){replyToRequestId=id;const button=$('reply-target');button.hidden=!id;button.textContent=id?'继续此前请求 · 点击取消关联':'';}
 $('reply-target').onclick=()=>setReply(null);
 const debugDialog=document.createElement('dialog');debugDialog.className='chat-debug-dialog';debugDialog.setAttribute('aria-label','引用与调试');
 debugDialog.innerHTML='<header><strong>引用与调试</strong><button type="button" class="debug-close" aria-label="关闭引用与调试">关闭</button></header><label>调试范围 <select aria-label="调试范围"></select></label><div class="debug-content"></div>';
 panel.append(debugDialog);const debugButton=document.createElement('button');debugButton.type='button';debugButton.className='debug-open';debugButton.textContent='引用与调试';debugButton.disabled=true;(debugTarget||panel.querySelector('header')).append(debugButton);let debugVersion=0;
 function closeDebug(){debugVersion++;if(debugDialog.open)debugDialog.close();debugDialog.querySelector('.debug-content').replaceChildren();}
 function showDebug(requestId=null){
  if(dead||paused||!current)return;closeDebug();const sid=current.sessionId,version=debugVersion,select=debugDialog.querySelector('select');
  select.replaceChildren(new Option('整个会话',''),...(lastData?.items||[]).map((item,i)=>new Option('第 '+(i+1)+' 条 · '+(titles[item.status]||item.status),item.requestId)));
  if(requestId&&[...select.options].some(o=>o.value===requestId))select.value=requestId;
  const fill=()=>{const body=debugDialog.querySelector('.debug-content');body.replaceChildren();const controls=appendDebugTools(body,client,{sessionId:sid,...(select.value?{requestId:select.value}:{})},{valid:()=>!dead&&debugDialog.open&&current?.sessionId===sid&&version===debugVersion&&controls.isConnected});controls.open=true;controls.querySelector('summary').hidden=true;};
  select.onchange=fill;debugDialog.showModal();fill();
 }
 debugButton.onclick=()=>showDebug();debugDialog.querySelector('.debug-close').onclick=closeDebug;debugDialog.addEventListener('cancel',event=>{event.preventDefault();closeDebug();});
 const drafts=new Map();const messageRows=new Map();let choiceDraft=null,choiceBase='',listKey='',scrollVersion=0;const client=guardedClient(rawClient,()=>dead);const editor=createReferenceEditor($('text'),{resolveReferences:tokens=>client.aiResolve(tokens)});const refs=bindReferenceInput($('text'),$('completion'),client,{editor});
 function composer(){
  panel.querySelector('header').hidden=!current;debugButton.disabled=!current||!canChat;
  const readonly=!canChat||!!current?.archived||!!current&&current.owner!==client.view?.accountId;
  $('text').contentEditable=String(!readonly);$('text').setAttribute('aria-disabled',String(readonly));
  $('send').disabled=readonly||busy||active||!editor.value.trim()||editor.value.length>8000;
  $('stop').hidden=!active||readonly;$('stop').disabled=busy;$('send').hidden=active&&!readonly;
  $('preview').disabled=readonly||busy||!editor.value.includes('[[');$('insert-reference').disabled=readonly||busy;
  const personal=current?.accessLevel==='player'||!current&&client.view?.role!=='kp';
  $('player-request').hidden=!personal;$('player-request').disabled=readonly||busy||accessPolicy.allowPlayerRequests===false||!editor.value.trim()||editor.value.length>8000;
  $('player-request').title=accessPolicy.allowPlayerRequests===false?'KP 已关闭玩家创作申请':'提交原需求，由 KP 接收并准备方案；修改仍需另行审核';
  $('length').hidden=editor.value.length<6400;$('length').textContent=editor.value.length+' / 8000';
  $('save').disabled=busy||!current;$('archive').disabled=busy||!current;
 }
 function welcome(){
  const box=document.createElement('div');box.className='welcome';box.innerHTML='<span class="welcome-mark">✳</span><h2>从一个想法开始</h2><p>引用资料、梳理线索，或准备下一步方案。</p><div class="starter-grid"></div>';
  const personal=current?.accessLevel==='player'||client.view?.role!=='kp';
  const suggestions=personal?[['整理已知线索','只使用本人已经获知的资料','整理当前已经核验的本人已知线索。'],['查找一份资料','输入 /knowledge 选择引用','/knowledge '],['向 KP 请求说明','提交问题，由 KP 决定揭示范围','请 KP 说明本次问题中允许我获知的信息。']]:[['梳理房间资料','整理资料与待处理事项','请简要梳理当前房间的资料和待处理事项。'],['设计新内容','准备可供审核的方案','我想设计一个新 NPC，请先给出简洁方案。'],['引用配置','从已授权目录中选择','/config ']];
  for(const [label,hint,text] of suggestions){const b=document.createElement('button');b.className='starter';b.append(document.createTextNode(label));const small=document.createElement('small');small.textContent=hint;b.append(small);b.onclick=()=>{editor.setValue(text);$('text').focus();$('text').dispatchEvent(new Event('input',{bubbles:true}));composer();};box.querySelector('.starter-grid').append(b);}
  $('history').replaceChildren(box);
 }
 function latest(){const h=$('history');$('latest').hidden=h.scrollHeight-h.clientHeight-h.scrollTop<96;}
 $('history').addEventListener('scroll',()=>{scrollVersion++;latest();},{passive:true});
 $('latest').onclick=()=>{$('history').scrollTop=$('history').scrollHeight;latest();};
 $('text').addEventListener('input',()=>{drafts.set(current?.sessionId||'new',editor.value);composer();});
 $('insert-reference').onclick=()=>{editor.setValue(editor.value+(editor.value&&!/\s$/.test(editor.value)?' ':'')+'/');$('text').focus();$('text').dispatchEvent(new Event('input',{bubbles:true}));};
 const dataAudience=()=>client.view?.role==='kp'&&current?.accessLevel==='administrator'?'administrator':'player';
 const details=bindReferenceDetails($('history'),tokens=>client.aiResolve(tokens),{container:root,valid:()=>!dead&&!paused&&!!current,audience:dataAudience,renderReference});
 function clearChoices(){for(const row of messageRows.values())row.choice?.destroy();messageRows.clear();details.close();}
 function addChoices(answer,item,data){
  if(!item.choices)return;
  const sid=data.session.sessionId;
  const disabled=paused||!canChat||data.session.archived||data.session.owner!==client.view?.accountId||item!==data.items.at(-1)||!!item.knowledgeRequest||!!item.playerRequest;
  return mountChoices(answer,item.choices,{disabled,hintText:data.session.accessLevel==='player'?'申请按钮会提交申请（原需求）给 KP；其他选项仅填入输入框。':null,onSelect:option=>{
   if(dead||paused||busy||current?.sessionId!==sid||current.archived||current.owner!==client.view?.accountId||!canChat)return;
   if(option.id==='ask_kp_change'&&current.accessLevel==='player'){action(()=>forwardPlayerRequest(sid,item.requestId));return;}
   if(option.id==='ask_kp'&&current.accessLevel==='player'){action(async()=>{check(await client.aiCommand('ai.knowledge.request',{sessionId:sid,requestId:item.requestId}));await select(sid);$('status').textContent='申请已提交，等待 KP 选择可披露资料。';});return;}
   const draft=editor.value.trim();if(draft!==choiceDraft)choiceBase=draft;choiceDraft=(choiceBase?choiceBase+'\n':'')+option.text;
   setReply(item.requestId);editor.setValue(choiceDraft);composer();drafts.set(sid,choiceDraft);$('text').focus();$('status').textContent='选项已填入，可修改后发送。';
  }});
 }
 const titles={request_pending:'创作申请待接收',request_accepted:'KP 已接收，准备方案',request_rejected:'创作申请已拒绝',request_cancelled:'创作申请已取消',received:'等待 KP 处理',queued:'排队中',generating:'正在生成',validating:'正在校验',review_ready:'待审核',published:'已加载',completed:'已执行',cancelled:'已取消',failed:'失败',interrupted:'已中断',stale:'依据已变化',blocked:'检查未通过',needs_input:'需要补充信息'};
 function check(r){if(r.status!=='committed')throw Object.assign(new Error(r.code||r.status),{requestId:r.requestId});return r.result;}
 async function action(fn){if(busy||dead)return;busy=true;seq++;listSeq++;composer();$('status').classList.remove('error');$('status').textContent='正在处理…';try{await fn();}catch(e){if(!dead){$('status').classList.add('error');$('status').textContent=({RULING_AMBIGUOUS:'存在多项待裁决修改，请打开裁决队列选择。'}[e.code||e.message]||errorText(e.code||e.message))+((e.requestId||e.aiRequestId)?' · 请求 '+(e.requestId||e.aiRequestId):'');}}finally{busy=false;if(!dead)composer();}}
 function renderList(){const key=JSON.stringify([records.map(s=>[s.sessionId,s.title,s.pinned]),current?.sessionId]);if(listTarget&&key!==listKey){listKey=key;listTarget.replaceChildren();for(const s of records){const b=document.createElement('button');b.className='session-link'+(s.sessionId===current?.sessionId?' selected':'');b.textContent=(s.pinned?'★ ':'')+s.title;b.title=s.title;b.onclick=()=>action(()=>select(s.sessionId));listTarget.append(b);}}onChange(records);if(current)onSelect(current);}
 async function refresh(){const stamp=++listSeq,filter=archivedView;let data;try{data=await client.aiSessions(filter);}catch(e){if(!dead&&stamp===listSeq&&['PLAYER_AI_DISABLED','PERMISSION_DENIED','NOT_VISIBLE'].includes(e.code)){reset();canChat=false;renderList();onSelect(null);composer();if(e.code==='PLAYER_AI_DISABLED'){$('status').textContent='KP 尚未允许玩家使用 AI 对话';return;}}throw e;}if(dead||stamp!==listSeq)return;const access=data.access||await client.aiAccess();if(dead||stamp!==listSeq)return;canChat=access.canChat;accessPolicy=access;$('knowledge-notice').textContent=current?.accessLevel==='player'||client.view?.role!=='kp'?access.knowledge?.notice||'':'';if(!canChat){reset();$('send').disabled=true;$('status').textContent='KP 尚未允许玩家使用 AI 对话';return;}records=data.items;renderList();composer();if(!current&&!$('history').children.length)welcome();}
 function button(label,fn){const b=document.createElement('button');b.textContent=label;b.onclick=()=>action(fn);return b;}
 function render(data){
  if(current&&current.sessionId!==data.session.sessionId)clearChoices();
  lastData=data;const scrollStamp=scrollVersion;const history=$('history'),position=history.scrollTop,follow=!current||current.sessionId!==data.session.sessionId||history.scrollHeight-history.clientHeight-position<80;
  if(current?.sessionId!==data.session.sessionId)closeDebug();current=data.session;$('session-access').textContent=(current.accessLevel==='administrator'?'管理员':'玩家')+' · '+current.owner;
  if(root.activeElement!==$('rename'))$('rename').value=current.title;$('archive').textContent=current.archived?'恢复':'归档';
  const retained=new Set();let cursor=history.firstChild;active=false;
  for(const item of data.items){
   const id=item.requestId,key=JSON.stringify([item,current.renderMode,current.showDiagnostics,current.archived,current.owner,client.view?.role,canChat,accessPolicy.allowPlayerRequests,accessPolicy.allowKnowledgeRequests,paused,item.choices?item===data.items.at(-1):null]);
   let row=messageRows.get(id);
   if(!row||row.key!==key){
    row?.choice?.destroy();row?.nodes.forEach(n=>n.remove());if(cursor&&!history.contains(cursor))cursor=null;
    const userText=item.text||'我的需求',user=row?.userText===userText?row.nodes[0]:document.createElement('article');user.className='message user';if(row?.userText!==userText)renderReferenceText(user,userText);user.querySelector('.continuation-origin')?.remove();if(item.continuationOrigin){const origin=document.createElement('small');origin.className='continuation-origin';origin.textContent='发布后继续';origin.style.display='block';user.prepend(origin);}if(item.reviewSource){const old=user.querySelector('.ai-review-source');old?.remove();appendReviewSource(user,item.reviewSource,{onOpenSource,onOpenSession:id=>action(()=>select(id))});}const answer=document.createElement('article');answer.className='message assistant';answer.dataset.status=item.status;const state=document.createElement('small');state.textContent=titles[item.status]||item.status;answer.append(state);const response=item.response||(item.status==='received'?'需求已记录，等待 KP 转交 AI。':''),bodyKey=JSON.stringify([response,current.renderMode,response?null:item.status]),body=row?.bodyKey===bodyKey?row.body:document.createElement('div');if(row?.bodyKey!==bodyKey)renderMarkdown(body,response,{plainText:current.renderMode==='plain'});answer.append(body);if(item.sourceNotice){const notice=document.createElement('p');notice.className='history-source-notice';notice.textContent=item.sourceNotice;answer.append(notice);}if(!response&&['queued','generating','validating'].includes(item.status)){body.textContent={queued:'请求已排队，可以随时停止。',generating:'正在整理资料并生成回答…',validating:'正在校验方案与资料依据…'}[item.status];}const choice=addChoices(answer,item,data);if(current.accessLevel==='player'&&current.owner===client.view?.accountId){const note=document.createElement('p');if(item.knowledgeRequest){note.className='knowledge-request-status';note.textContent=({pending:'资料申请：等待 KP 处理',completed:'资料申请：已披露，可重新查询本人已知资料',rejected:'资料申请：KP 未批准',partial:'资料申请：执行未全部完成，请 KP 核对',unknown:'资料申请：结果待 KP 核对',executing:'资料申请：处理中',cancelled:'资料申请：已取消'}[item.knowledgeRequest.status]||'资料申请：待核对');answer.append(note);}else if(!item.playerRequest&&accessPolicy.allowKnowledgeRequests!==false&&!current.archived&&!item.choices?.options?.some(o=>o.id==='ask_kp')){answer.append(button('向 KP 申请披露',async()=>{check(await client.aiCommand('ai.knowledge.request',{sessionId:current.sessionId,requestId:item.requestId}));await select(current.sessionId);$('status').textContent='申请已提交，等待 KP 审核。';}));}}if(client.view?.role==='kp'&&current.showDiagnostics!==false)appendDiagnostics(answer,item);else if(item.error&&!['failed','interrupted'].includes(item.status))appendDiagnostics(answer,{error:item.error});appendProgress(answer,item);addPlayerRequest(answer,item);if(client.view?.role==='kp'&&item.status==='received')answer.append(button('转交 AI',async()=>{check(await client.aiCommand('ai.request.dispatch',{requestId:item.requestId}));await select(current.sessionId);}));if(item.batchId&&onReview)answer.append(button('查看执行批次',()=>onReview(null)));if(item.proposalId&&onReview){const b=button('查看配置裁决',()=>onReview(null));b.disabled=!['review_ready','blocked','approved','published','stale'].includes(item.status);answer.append(b);}if(['received','queued','generating','validating','review_ready','needs_input','blocked','request_pending'].includes(item.status))answer.append(button('取消',async()=>{check(await client.aiCommand('ai.request.cancel',{requestId:item.requestId}));await select(current.sessionId);}));
    user.querySelector('.message-time')?.remove();
    const stamp=(parent,value,label)=>{const time=document.createElement('time');time.className='message-time';if(typeof value==='number'&&Number.isFinite(value)&&value>=0){const date=new Date(value*1000);time.dateTime=date.toISOString();time.textContent=label+' · '+date.toLocaleString();time.title=date.toISOString();}else time.textContent=label+' · 时间未记录';parent.append(time);};
    stamp(user,item.sentAt??item.createdAt,'发送');if(item.response)stamp(state,item.responseAt,'回复');
    applyReferenceLabels(user,item.referenceLabels);applyReferenceLabels(body,item.referenceLabels);
    if(item.dependencyCheck?.canRegenerate&&current.owner===client.view?.accountId&&!current.archived){const regenerate=button('按最新资料重新生成',async()=>{setReply(item.requestId);editor.setValue(item.text||'');composer();$('text').focus();$('status').textContent='原需求已恢复；发送后将读取最新资料。原回答保留，不会自动执行候选。';});regenerate.className='regenerate-current';answer.append(regenerate);}
    if(response&&current.owner===client.view?.accountId&&!current.archived)answer.append(button('继续此请求',async()=>{setReply(item.requestId);$('text').focus();$('status').textContent='新消息将关联此前请求；待新方案完成检查后整理旧待审项。';}));
    if(response){const copy=button('复制回答',async()=>{try{await navigator.clipboard.writeText(body.innerText);$('status').textContent='回答已复制';}catch{$('status').textContent='无法自动复制，请选中回答后复制。';}});copy.className='copy-response';answer.append(copy);}if(['failed','interrupted','stale','blocked'].includes(item.status)&&!item.historicalReadOnly){const error=document.createElement('p');error.className='error-detail';error.textContent=item.status==='blocked'?'方案未通过检查。请打开配置裁决查看 A/B/C 报告，修改需求或候选后重新校验；当前未发布。':'本次未完成。'+(errorText(item.error)||'请检查服务状态后重试');answer.append(error,button('编辑后重试',async()=>{editor.setValue(item.text||'');composer();$('text').focus();$('status').textContent='原需求已恢复；确认内容后发送，不会自动重复执行。';}));}row={key,nodes:[user,answer],choice,userText,body,bodyKey};messageRows.set(id,row);
   }
   retained.add(id);for(const node of row.nodes){if(node===cursor)cursor=cursor.nextSibling;else history.insertBefore(node,cursor);}
   if(['queued','generating','validating'].includes(item.status))active=true;
  }
  for(const [id,row] of messageRows)if(!retained.has(id)){row.choice?.destroy();row.nodes.forEach(n=>n.remove());messageRows.delete(id);}
  for(const node of [...history.children])if(![...messageRows.values()].some(r=>r.nodes.includes(node)))node.remove();
  if(!data.items.length)welcome();
  const sid=current.sessionId,scope=identity;hydrateReferences(history,tokens=>client.aiResolve(tokens),()=>!dead&&current?.sessionId===sid&&identity===scope).then(()=>{if(!dead&&current?.sessionId===sid&&identity===scope&&follow&&scrollVersion===scrollStamp)history.scrollTop=history.scrollHeight;latest();});
  details.refresh();history.scrollTop=follow?history.scrollHeight:position;composer();latest();renderList();
  if(active&&!paused){clearTimeout(timer);timer=setTimeout(poll,900);}
 }
 async function select(id,{quiet=false}={}){const changed=id!==current?.sessionId;if(changed){setReply(null);pendingSubmission=null;pendingPlayerSubmission=null;drafts.set(current?.sessionId||'new',editor.value);refs.reset();$('reference-preview').hidden=true;}const token=++seq;const data=await client.aiSession(id);if(dead||paused||token!==seq)return;if(current?.sessionId===id&&current.revision>data.session.revision)return;if(changed)editor.setValue(drafts.get(id)||'');render(data);if(!quiet)$ ('status').textContent=current.archived?'会话已归档，可恢复后继续':'会话已就绪';}
 async function create(title='新会话',preserveDraft=false){
  const token=++seq,access=await client.aiAccess();if(dead||paused||token!==seq)throw new Error('VIEW_CHANGED');
  canChat=access.canChat;accessPolicy=access;if(!canChat)throw new Error('KP 尚未允许玩家使用 AI 对话');
  archivedView=false;drafts.set(current?.sessionId||'new',editor.value);refs.reset();
  setReply(null);pendingSubmission=null;pendingPlayerSubmission=null;const session=check(await client.aiCommand('ai.session.create',{title}));
  if(dead||paused||token!==seq)return session;
  if(!preserveDraft)editor.setValue('');render({session,items:[]});records=[{...session,requestCount:0},...records];renderList();
  $('text').focus();$('status').textContent='新会话已创建';return session;
 }
 async function forwardPlayerRequest(sid,requestId){
  check(await client.aiCommand('ai.player.request',{sessionId:sid,requestId}));
  if(current?.sessionId===sid)await select(sid);
  $('status').textContent='创作申请已提交；KP 接收后准备方案，修改仍需另行审核。';
 }
 function addPlayerRequest(answer,item){
  if(current?.accessLevel!=='player'||current.owner!==client.view?.accountId)return;
  if(item.playerRequest){const note=document.createElement('p');note.className='player-request-status';note.textContent=({pending:'创作申请：等待 KP 接收',accepted:'创作申请：KP 已接收，方案和修改另行审核',rejected:'创作申请：KP 未接受',cancelled:'创作申请：已取消'}[item.playerRequest.status]||'创作申请：待核对');answer.append(note);}
  else if(!current.archived&&accessPolicy.allowPlayerRequests!==false&&item.status!=='cancelled'&&!item.choices?.options?.some(o=>o.id==='ask_kp_change')){const sid=current.sessionId;answer.append(button('提交创作／配置申请',()=>forwardPlayerRequest(sid,item.requestId)));}
 }
 $('player-request').onclick=()=>action(async()=>{
  const text=editor.value.trim();if(!text)return;
  const session=current||await create(editor.displayText.trim().slice(0,36),true),sid=session.sessionId;
  const args={sessionId:sid,text},signature=JSON.stringify(args);
  if(pendingPlayerSubmission?.signature!==signature)pendingPlayerSubmission={signature,key:newSubmissionKey()};
  check(await client.aiCommand('ai.player.request',{...args,submissionKey:pendingPlayerSubmission.key}));
  pendingPlayerSubmission=null;
  if(current?.sessionId===sid){if(editor.value.trim()===text){editor.setValue('');drafts.delete(sid);}refs.reset();$('reference-preview').hidden=true;await select(sid);$('status').textContent='创作申请已提交，等待 KP 接收并准备方案。';}
  await refresh();
 });
 $('send').onclick=()=>action(async()=>{
  const text=editor.value.trim();if(!text)throw new Error('请输入需求');if(text.length>8000)throw new Error('需求最多 8000 字符（含引用标识）');if(!canChat)throw new Error('KP 尚未允许玩家使用 AI 对话');
  const session=current||await create(editor.displayText.trim().slice(0,36),true),sid=session.sessionId;
  const visible=()=>!dead&&!paused&&current?.sessionId===sid;
  const args={sessionId:sid,text,...(replyToRequestId?{replyToRequestId}:{})},signature=JSON.stringify(args);
  if(pendingSubmission?.signature!==signature)pendingSubmission={signature,key:newSubmissionKey()};
  const result=check(await client.aiCommand('ai.session.submit',{...args,submissionKey:pendingSubmission.key}));
  pendingSubmission=null;setReply(null);
  // A receipt belongs to its original session, even if the user is reading another one.
  if(visible()){
   if(editor.value.trim()===text){editor.setValue('');drafts.delete(sid);}
   refs.reset();$('reference-preview').hidden=true;await select(sid);
  }else if(drafts.get(sid)?.trim()===text)drafts.delete(sid);
  refresh().catch(()=>{});
  if(result.ruling){
   if(visible()){$('status').textContent=result.reviewRequired?'需在裁决队列填写风险决定':({completed:'修改已执行，重复批准不会重复执行',rejected:'该裁决已拒绝'}[result.ruling.status]||'裁决状态：'+result.ruling.status);if(result.reviewRequired&&onReview)await onReview(null);}return;
  }
  if(visible())$('status').textContent='需求已保存';
  if(client.view?.role==='kp'&&!result.taskId&&!result.awaitingKnowledge){check(await client.aiCommand('ai.request.dispatch',{requestId:result.requestId}));if(visible())await select(sid);}
 });
 $('text').addEventListener('keydown',e=>{if(!e.defaultPrevented&&!e.isComposing&&!editor.composing&&e.key==='Enter'&&!e.shiftKey&&(e.ctrlKey||e.metaKey||$('send-mode').value==='enter')){e.preventDefault();$('send').click();}});
 $('save').onclick=()=>action(async()=>{if(!current)return;current=check(await client.aiCommand('ai.session.update',{sessionId:current.sessionId,revision:current.revision,title:$('rename').value}));await refresh();$('status').textContent='名称已保存';});
 $('archive').onclick=()=>action(async()=>{if(!current)return;current=check(await client.aiCommand('ai.session.update',{sessionId:current.sessionId,revision:current.revision,archived:!current.archived}));await Promise.all([select(current.sessionId),refresh()]);});
 $('preview').onclick=()=>action(async()=>{const tokens=editor.value.match(/\[\[[^\]]+\]\]/g)||[];const data=await client.aiResolve(tokens);const box=$('reference-preview');box.replaceChildren();for(const item of data.items){const section=document.createElement('section'),title=document.createElement('strong'),text=document.createElement('pre');title.textContent=item.label;const value=item.value?.data||item.value;if(['event','ruling'].includes(item.kind)){const decisions=(value.rulings||[]).map(r=>(r.outcome==='deny'?'否决':r.status==='pending'?'待裁决':'已记录决定')+'：'+(r.reason||'未记录理由'));const executions=(value.executions||[]).map(r=>'执行：'+({completed:'已完成',committed:'已提交',none:'无需执行',unknown:'缺少完整回执'}[r.status||r.executionStatus]||r.status||r.executionStatus));text.textContent=[...(value.messages||[]).map(m=>m.text),...decisions,...executions,value.coverage?.status==='complete'?'已覆盖选定的可见资料':'资料不完整，不能推断未记录的过程'].join('\n');}else text.textContent=item.kind==='chat'?value.text:'';section.append(title, text.textContent?text:referenceView(item,{audience:dataAudience(),renderReference}));box.append(section);}box.hidden=false;$('status').textContent='以上为所选可见资料；外发开关、来源与权限将在生成前复验';});
 function reset(){setReply(null);pendingSubmission=null;pendingPlayerSubmission=null;closeDebug();listKey='';clearChoices();choiceDraft=null;choiceBase='';drafts.clear();seq++;listSeq++;lastData=null;refs.reset();current=null;records=[];active=false;listTarget?.replaceChildren();$('history').replaceChildren();editor.setValue('');$('reference-preview').replaceChildren();$('rename').value='新会话';$('latest').hidden=true;composer();}
 let identity=JSON.stringify([client.generation,client.connected,client.view?.accountId,client.view?.role,client.view?.authorityEpoch]);const unsub=client.subscribe(()=>{const next=JSON.stringify([client.generation,client.connected,client.view?.accountId,client.view?.role,client.view?.authorityEpoch]);if(next!==identity){identity=next;reset();}});
 async function poll(){try{if(!dead&&!paused&&!busy&&client.connected&&!document.hidden&&current)await select(current.sessionId,{quiet:true});}catch(e){if(!dead){if(['NOT_VISIBLE','PLAYER_AI_DISABLED','PERMISSION_DENIED'].includes(e.code)){reset();canChat=false;$('send').disabled=true;}$('status').textContent=e.code==='PLAYER_AI_DISABLED'?'KP 已关闭玩家 AI 对话':'连接或权限变化，请重试';}}finally{if(!dead&&!paused){clearTimeout(timer);timer=setTimeout(poll,active?1200:12000);}}}
 welcome();composer();$('stop').onclick=()=>action(async()=>{const pending=lastData?.items.filter(i=>['queued','generating','validating'].includes(i.status)).at(-1);if(!pending)return;const sid=current.sessionId;check(await client.aiCommand('ai.request.cancel',{requestId:pending.requestId}));if(current?.sessionId===sid){await select(sid);$('status').textContent='已请求停止生成';}});
 refresh().catch(e=>{$('status').textContent=e.code||e.message;});timer=setTimeout(poll,1200);
 async function applySessionChange(session){seq++;listSeq++;if(current?.sessionId===session.sessionId){if(session.deleted){closeDebug();clearChoices();drafts.delete(session.sessionId);current=null;lastData=null;$('history').replaceChildren();$('rename').value='新会话';editor.setValue('');onSelect(null);}else if(lastData)render({...lastData,session});}await refresh();}
 return {refresh,select,showDebug,applySessionChange,suspend(){closeDebug();paused=true;details.close();seq++;clearTimeout(timer);refs.reset();},async resume({sessionId}={}){if(dead)return;paused=false;const target=sessionId||current?.sessionId;await Promise.all([refresh(),target?select(target):Promise.resolve()]);clearTimeout(timer);timer=setTimeout(poll,active?1200:12000);},setDraft(text,references=[]){refs.reset();$('text').focus();editor.setValue(text,references);composer();},insertReference(item){refs.reset();editor.insertReference(item);composer();},newChat:()=>action(async()=>{await create();}),async showArchived(){archivedView=!archivedView;await refresh();return archivedView;},destroy(){dead=true;clearTimeout(timer);unsub();refs.destroy();reset();details.destroy();editor.destroy();debugButton.remove();debugDialog.remove();shell.remove();}};
}
