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
   create:(title,id)=>ai('ai.session.create',{title},id),
   update:(sessionId,revision,changes,id)=>ai('ai.session.update',{...changes,sessionId,revision},id),
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
  usage:options=>client.aiUsage(options),
  settings:{get:()=>client.aiSettings(),update:(settings,id)=>ai('ai.settings.update',settings,id)},
  receipts:{ai:id=>client.aiReceipt(id),host:id=>client.receipt(id)},contracts:()=>client.aiContracts(),
  destroy(){dead=true;}
 };
}
