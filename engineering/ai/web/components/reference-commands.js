/** Public metadata for custom command menus; visibility is still server enforced. */
export const REFERENCE_COMMANDS=Object.freeze([
 Object.freeze({kind:'knowledge',label:'已知资料',hint:'引用本人观察或 KP 明确揭示的记录'}),
 Object.freeze({kind:'config',label:'配置',hint:'引用配置模板与规则参数'}),
 Object.freeze({kind:'entity',label:'实体',hint:'引用角色、物品等运行时对象'}),
 Object.freeze({kind:'data',label:'运行数据',hint:'引用活动工件数据 · KP'}),
 Object.freeze({kind:'chat',label:'聊天',hint:'附带有来源的聊天片段'}),
 Object.freeze({kind:'event',label:'事件',hint:'引用行动、裁决与执行资料'}),
 Object.freeze({kind:'ruling',label:'裁决',hint:'引用已记录的决定及结果'})
]);
export function referenceCommands(role){return REFERENCE_COMMANDS.filter(item=>role==='kp'||item.kind==='knowledge');}
