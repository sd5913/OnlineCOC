import {guardedClient} from './guard.js';
import {referenceCommands} from './reference-commands.js';
import {referenceToken} from './reference-editor.js';

/** Headless assembly helpers. Mutations return receipts, never silently approve or retry. */
export function createAITools(rawClient){
 let dead=false;
 const client=guardedClient(rawClient,()=>dead);
 const ai=(op,args,id)=>{if(dead)throw new Error('TOOLS_DESTROYED');return client.aiCommand(op,args,id);};
 const host=(op,args,id)=>{if(dead)throw new Error('TOOLS_DESTROYED');return client.command(op,args,id);};
 return {
  sessions:{list:(archived=false)=>client.aiSessions(archived),get:id=>client.aiSession(id),
   create:(title,id,accessLevel)=>ai('ai.session.create',{title,...(accessLevel?{accessLevel}:{})},id),
   update:(sessionId,revision,changes,id)=>ai('ai.session.update',{...changes,sessionId,revision},id),
   delete:(sessionId,revision,id)=>ai('ai.session.delete',{sessionId,revision},id),
   submit:(sessionId,text,id)=>ai('ai.session.submit',{sessionId,text},id)},
  requests:{list:options=>client.aiTasks(options),submit:(text,id)=>ai('ai.request.create',{sourceKind:'manual',text},id),
   dispatch:(requestId,id)=>ai('ai.request.dispatch',{requestId},id),cancel:(requestId,id)=>ai('ai.request.cancel',{requestId},id)},
  references:{commands:()=>referenceCommands(client.view?.role),token:referenceToken,
   search:(kind,q='')=>client.aiReferences(kind,q),resolve:tokens=>client.aiResolve(tokens)},
  data:{search:args=>client.aiData('search',args),read:args=>client.aiData('read',args),
   chat:args=>client.aiData('chat',args),case:args=>client.aiData('case',args)},
  review:{get:id=>client.aiProposal(id),
   validate:(proposalId,revision,id)=>ai('ai.proposal.validate',{proposalId,revision},id),
   approve:(proposalId,proposalRevision,riskDecisions,id)=>host('ai.proposal.approve',{proposalId,proposalRevision,riskDecisions},id),
   apply:(approvalId,id)=>host('publication.apply',{approvalId},id),revoke:(approvalId,id)=>host('ai.proposal.revoke',{approvalId},id)},
  playerRequests:{submit:(value,id)=>ai('ai.player.request',value,id)},
  knowledgeRequests:{submit:(sessionId,requestId,id)=>ai('ai.knowledge.request',{sessionId,requestId},id),reconcile:(value,id)=>ai('ai.knowledge.reconcile',value,id)},
  access:{get:()=>client.aiAccess(),update:(value,id)=>ai('ai.access.update',value,id)},
  rulings:{list:()=>client.aiRulings(),decide:(value,id)=>ai('ai.ruling.decide',value,id)},
  batches:{list:()=>client.aiBatches(),approve:(batchId,digest,id)=>ai('ai.batch.approve',{batchId,digest},id),reject:(batchId,digest,id)=>ai('ai.batch.reject',{batchId,digest},id),reconcile:(batchId,digest,id)=>ai('ai.batch.reconcile',{batchId,digest},id)},
  debug:options=>client.aiDebug(options),
  review:(source,instruction,id)=>ai('ai.review.create',{source,...(instruction?{instruction}:{})},id),
  usage:options=>client.aiUsage(options),
  settings:{get:()=>client.aiSettings(),update:(settings,id)=>ai('ai.settings.update',settings,id)},
  receipts:{ai:id=>client.aiReceipt(id),host:id=>client.receipt(id)},contracts:()=>client.aiContracts(),
  destroy(){dead=true;}
 };
}
