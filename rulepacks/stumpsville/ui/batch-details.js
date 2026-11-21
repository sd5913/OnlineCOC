import {rulingEscape as esc} from './ruling-card.js';

const operations={
  'entity.create':'创建实例','entity.patch':'修改名称','entity.update':'修改实例属性','entity.archive':'归档实例',
  'relation.set':'建立关系','relation.remove':'移除关系','progress.set':'设置进度','asset.attach':'关联资源','asset.remove':'移除资源',
  'flow.respond':'回答流程','flow.retry':'重试流程','flow.cancel':'取消流程','room.status':'设置房间状态',
  'member.add':'添加成员','member.update':'修改成员','notification.send':'通知玩家',
  'action.invoke':'执行规则行动','behavior.invoke':'执行绑定行为','chat.direct.open':'打开私聊',
  'chat.channel.create':'创建频道','chat.channel.update':'修改频道','chat.message.send':'发送消息',
  'chat.message.share':'分享执行记录','chat.message.edit':'修改消息','chat.message.retract':'撤回消息',
  'ai.session.create':'创建 AI 会话','ai.session.update':'修改 AI 会话','ai.session.delete':'删除 AI 会话',
  'ai.memory.create':'创建记忆','ai.memory.confirm':'确认记忆','ai.memory.revoke':'撤销记忆'
};
const rules={
  'sv.create':'生成建卡属性','sv.profile':'核准角色属性','sv.ready':'设置准备状态','sv.check':'属性检定',
  'sv.inventory':'操作背包物品','sv.grant':'发放物品','sv.remove':'移除物品','sv.transfer':'转交物品',
  'sv.damage':'结算伤害','sv.rest':'休息恢复','sv.morale':'士气检定','sv.travel':'设置地点',
  'sv.travel.auto':'移动到相邻地点','sv.world':'推进团务','sv.generate':'随机生成',
  'sv.adjudicate':'主持裁决','sv.scene.resolve':'结算场景行动'
};
const checks={passed:'检查通过',blocked:'检查不通过',unsupported:'不支持此事务范围',runtime_required:'需运行判定'};
const results={committed:'已提交',rolled_back:'已撤销，未生效',failed:'失败',not_executed:'未执行',unknown:'结果待核对',rejected:'已拒绝',pending:'等待回执'};
const ruleReasons={
  SV_ITEM_NO_USES_OR_MANUAL_SPELL:'该物品不支持直接消耗用量，或属于需单独处理的状态／法术。',
  SV_ITEM_EXHAUSTED:'该槽位物品的当前用量已经耗尽。',SV_EMPTY_SLOT:'指定槽位为空，或其物品编号无有效定义。',
  SV_SLOT:'槽位必须在1至20之间。',SV_TARGET_SLOT:'目标槽位无效，或与原槽位相同。',
  SV_SLOT_OCCUPIED:'目标槽位不可用；转交时还需核对原槽位确有物品。',
  SV_DEAD_CANNOT_REST:'角色已死亡，不能通过休息恢复。',SV_NOT_CHARACTER:'目标不是本包角色实例。',
  SV_NOT_READY:'角色尚未准备。',SV_NOT_APPROVED:'角色尚未审核通过。',SV_CANNOT_ACT:'角色当前状态不允许行动。',
  SV_SESSION_NOT_STARTED:'当前团务尚未开场。',SV_KP_RULING_REQUIRED:'自动结算已关闭，需使用主持裁决入口。',
  SV_NOT_LIGHT_SOURCE:'该物品不是可用光源，或用量已耗尽。',SV_NOT_LIT:'该槽位的物品当前未点燃。',
  SV_ROUND_CONFLICT:'提交的探索轮数与当前轮数不同。',SV_DOOR_CLOSED:'目标通路尚未开启。',
  SV_NOT_ADJACENT:'目标地点与当前位置不相邻。',SV_PROFILE_LOCKED:'角色已核准，不能重新套用初始建卡入口。'
};
const indexRows=rows=>new Map((Array.isArray(rows)?rows:[]).filter(r=>Number.isInteger(r?.index)&&r.index>=0).map(r=>[r.index,r]));

export function batchActionTitle(action={}){
  if(action.summary)return String(action.summary);
  const args=action.args||{},input=args.input||{};
  let title=action.op==='action.invoke'?(rules[args.actionId]||args.actionId||operations[action.op]):operations[action.op]||action.op||'指令';
  if(args.actionId==='sv.inventory')title=({use:'使用物品',move:'移动物品',light:'点燃物品',extinguish:'熄灭物品'})[input.operation]||title;
  if(args.actionId==='sv.rest')title=({short:'短休',long:'长休',full:'完全恢复'})[input.kind]||title;
  if(input.slot!==undefined)title+=' · 槽位 '+input.slot;
  if(action.op==='notification.send'&&Array.isArray(args.recipientAccountIds))title+=' · '+args.recipientAccountIds.join('、');
  return title;
}

function diagnostic(row){
  if(!row)return '';
  const reason=typeof row.reason==='string'?row.reason:typeof row.message==='string'?row.message:'';
  if(!reason&&!row.code&&!row.ruleCode&&!row.path)return '';
  const parts=[reason,row.ruleCode?(ruleReasons[row.ruleCode]||''):'',row.code&&!reason.includes(row.code)?row.code:'',row.ruleCode&&row.ruleCode!==row.code?row.ruleCode:'',row.path?'参数 '+row.path:'',row.ruleId?'规则 '+row.ruleId:''];
  return parts.filter(Boolean).join(' · ');
}

function ruleResult(row){
  if(row?.status!=='committed')return '';
  if(row?.businessResult)return row.businessResult;
  const result=row?.result,publicResult=result?.public||result;
  if(publicResult?.outcome==='blocked')return '条件不足，目标未完成；请查看原行动结果。';
  if(publicResult?.outcome==='failure'||result?.passed===false)return '判定未通过，规则已正常结算；不会自动重掷。';
  if(result?.passed===true)return '检定通过。';
  return '';
}

// Status comes only from server fields. Missing rows never mean a successful execution.
export function batchDetailsHTML(item={}){
  const actions=Array.isArray(item.actions)?item.actions:[];
  if(!actions.length)return '';
  const before=indexRows(item.preflight?.items),after=indexRows(item.execution?.items);
  const legacy=indexRows((item.receipts||[]).map((row,index)=>({...row,index:row.index??index,commandId:row.commandId||row.id})));
  const stoppedLegacy=!item.execution&&item.status==='partial'&&[...legacy.values()].some(row=>row.receipt?.status==='rejected');
  const rows=actions.map((action,index)=>{
    const check=before.get(index),run=after.get(index)||legacy.get(index);
    const receipt=run?.receipt||run;
    const checkText=checks[check?.status]||'未提供预检查';
    const runText=receipt?(results[receipt.status]||receipt.status||'未提供执行结果'):stoppedLegacy?'未执行':['pending','draft'].includes(item.status)?'尚未执行':'未提供执行回执';
    const cause=(run?[diagnostic(receipt)]:[diagnostic(check)]).filter(Boolean);
    const problem=['blocked','unsupported','failed','rejected'].includes((receipt||check)?.status);
    const checkLabel=item.execution?'执行前检查':'预检查';
    const business=ruleResult(receipt);
    const details=action.args?`<details><summary>指令参数</summary><pre class="data-detail">${esc(JSON.stringify({target:action.target,op:action.op,args:action.args},null,2))}</pre></details>`:'';
    const commandId=run?.commandId||receipt?.commandId;
    return `<li data-batch-action="${index}"><strong>${esc(batchActionTitle(action))}</strong><p class="batch-action-state"><span>${checkLabel}：${esc(checkText)}</span><span>执行：${esc(runText)}</span></p>${business?`<p class="batch-business-result">规则结果：${esc(business)}</p>`:''}${cause.length?`<p class="${problem?'batch-action-reason':'batch-action-info'}">${esc([...new Set(cause)].join('；'))}</p>`:''}${commandId?`<small class="batch-command-id">指令定位：${esc(commandId)}</small>`:''}${details}</li>`;
  }).join('');
  const execution=item.execution||(stoppedLegacy?{committedCount:[...legacy.values()].filter(r=>r.receipt?.status==='committed').length,failedCount:[...legacy.values()].filter(r=>r.receipt?.status==='rejected').length,notExecutedCount:actions.length-legacy.size}:null);
  const counts=execution&&['committedCount','failedCount','notExecutedCount'].every(k=>Number.isInteger(execution[k]))?`<p class="batch-counts">已提交 ${execution.committedCount} · 失败 ${execution.failedCount} · 未执行 ${execution.notExecutedCount}${Number.isInteger(execution.rolledBackCount)?' · 已撤销 '+execution.rolledBackCount:''}</p>`:'';
  const scope=!item.execution&&checks[item.preflight?.status];
  return `<section class="batch-details" aria-label="逐项指令与执行结果"><p><strong>指令清单 · ${actions.length} 项</strong>${scope?' · '+esc(scope):''}</p>${counts}<ol class="batch-action-list">${rows}</ol>${!item.execution&&legacy.size?'<p class="batch-check-note">旧记录为逐项执行，没有整批原子撤销证明。</p>':''}<p class="batch-check-note">预检查基于所查资料；执行时会再次核对。正常检定未通过属于游戏结果。</p></section>`;
}

// Persist only the display fields in the local notification; the original ruling is authoritative.
export function batchNoticeSnapshot(item={}){
  if(!Array.isArray(item.actions)||!item.actions.length)return undefined;
  const pick=row=>({...Object.fromEntries(['index','target','op','status','commandId','code','reason','message','path','ruleId','ruleCode'].filter(k=>row[k]!==undefined).map(k=>[k,row[k]])),...(ruleResult(row)?{businessResult:ruleResult(row)}:{})});
  const block=value=>value?{status:value.status,...Object.fromEntries(['committedCount','failedCount','notExecutedCount','rolledBackCount'].filter(k=>Number.isInteger(value[k])).map(k=>[k,value[k]])),items:(value.items||[]).map(pick)}:undefined;
  return {status:item.status,actions:item.actions.map(action=>({target:action.target,op:action.op,summary:batchActionTitle(action)})),preflight:block(item.preflight),execution:block(item.execution),receipts:(item.receipts||[]).map((row,index)=>({...pick(row),index:row.index??index,commandId:row.commandId||row.id,...(row.receipt?{receipt:pick(row.receipt)}:{})}))};
}
