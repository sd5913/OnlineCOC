// A received client-error response is a refusal, not a lost write result.
// Timeouts, server errors and transport failures still require the original receipt.
export function definiteAIRejection(error){
  const status=error?.status??error?.httpStatus;
  return Number.isInteger(status)&&status>=400&&status<500&&status!==408;
}

export function explainAIError(value){
  const reasons={
    STALE_AUTHORITY:'房间已重启或执行权限已换代，旧方案的审批依据已失效。请重新检查方案，再确认执行',
    RECHECK_BASELINE_CHANGED:'方案涉及的配置已发生变化，不能直接沿用旧内容。请转 AI 处理，基于当前资料重新准备方案',
    RECHECK_STATE_BLOCKED:'检查已完成，但裁决尚未恢复为待确认。请核对原回执，并确认房间服务已加载修复版本',
    BASELINE_STALE:'房间资料或规则已变化，请重新读取并准备方案',
    RULING_STALE:'裁决版本已变化，请刷新后重新打开',
    SOURCE_STALE:'原引用资料已变化，请重新读取并准备方案',
    CONSULTATION_ONLY:'当前方案仍受来源限制；KP请重新检查取得参考资料评估后再裁决，玩家可申请KP处理',
    CONSULTATION_REVIEW_REQUIRED:'请先查看参考资料评估，再由KP明确决定是否采用',
    COMPRESSION_INVALID:'上下文摘要未通过格式检查，原文仍保留；请查看该任务的压缩过程与错误定位',
    COMPRESSION_PROVENANCE_INVALID:'摘要的原文引用未通过核验，不能继续作为生成依据；请查看具体定位',
    COMPRESSION_RESULT_LIMIT:'压缩后的内容仍超过本次预算，原文仍保留；请查看过程中的体积记录',
    COMPRESSION_NOT_REDUCED:'本次摘要未能有效缩小上下文，原文仍保留；请查看压缩过程',
    COMPRESSION_LIMIT:'本任务已达到压缩次数上限，原文仍保留；请查看已完成步骤和剩余需求',
    HISTORY_PROVENANCE_INCOMPLETE:'旧记录缺少可核验的来源标识，无法确认当前读取权限；请重新查询相关资料后继续',
    QUEUE_VERSION_CONFLICT:'该条目的状态已变化，请刷新后重新操作',
    QUEUE_ITEM_PROTECTED:'该条目正在处理或已有执行结果，请核对原回执，不能用归档代替处理',
    QUEUE_ITEM_INACTIVE:'该方案已归档或被后续方案替代，请查看其整理记录和后续方案',
    SUBMISSION_KEY_CONFLICT:'本次提交定位已绑定另一份内容，请刷新并核对原请求',
    VALIDATOR_STALE:'配置包或检查规则已更新，请基于当前配置包重新准备方案'
  };
  return reasons[value]?reasons[value]+'（'+value+'）':String(value||'未提供详细原因');
}

// Preserve the actual response status: the generic component transport only
// copies the JSON body, which may contain a code without an HTTP status.
export function packageAITransport(base){
  const endpoint=new URL(base,location.href);
  if(endpoint.origin!==location.origin)throw Error('CUSTOM_TRANSPORT_REQUIRED');
  return {async request(path,{method='GET',body,csrf}={}){
    const response=await fetch(new URL(path,endpoint),{method,credentials:'same-origin',
      headers:{...(body!==undefined?{'Content-Type':'application/json'}:{}),...(csrf?{'X-CSRF-Token':csrf}:{})},
      body:body===undefined?undefined:JSON.stringify(body)});
    let value;
    try{value=await response.json();}catch(error){
      if(!response.ok)throw Object.assign(Error('HTTP_'+response.status),{status:response.status});
      throw error;
    }
      if(!response.ok)throw Object.assign(Error(value?.code||'REQUEST_FAILED'),value,{status:response.status});
    return value;
  }};
}
