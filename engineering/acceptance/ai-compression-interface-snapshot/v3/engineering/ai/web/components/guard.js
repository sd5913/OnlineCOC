/** Discard delayed private responses after logout, role change or unmount. */
export function guardedClient(client,disposed=()=>false){
 const stamp=()=>JSON.stringify([client.generation,client.connected,client.view?.accountId,client.view?.role,client.view?.authorityEpoch]);
 const asyncMethods=new Set(['aiDebug','aiReview','aiContracts','aiTasks','aiProposal','aiSettings','aiAccess','aiBatches','aiRulings','aiUsage','aiSessions','aiSession','aiCommand','aiReceipt','aiReferences','aiResolve','aiData','command','receipt']);
 return new Proxy(client,{get(target,key){const value=target[key];if(typeof value!=='function'||key==='onChange')return value;if(!asyncMethods.has(key))return value.bind(target);return async(...args)=>{if(disposed())throw new Error('VIEW_CHANGED');const before=stamp();const result=await value.apply(target,args);if(disposed()||before!==stamp())throw new Error('VIEW_CHANGED');return result;};}});
}
