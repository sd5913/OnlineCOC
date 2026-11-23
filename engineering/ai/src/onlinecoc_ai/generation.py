"""Sending-time read snapshot. Never grants authority to execute a candidate."""
import copy
import threading
from contextlib import contextmanager
from types import SimpleNamespace

from onlinecoc.model import member, visible
from .contracts import digest
from .errors import require


class ReadRepository:
    def __init__(self, value):
        self.value = value
        self.lock = threading.RLock()

    def state(self):return copy.deepcopy(self.value)
    def read_state(self):return self.value
    @contextmanager
    def read_scope(self):yield
    def update(self, callback):return copy.deepcopy(callback(self.value))


def clone(part, host, repository, app=None, proposals=None):
    result = copy.copy(part)
    for name, value in [('host',host),('repository',repository),('app',app),('application',app),('proposals',proposals)]:
        if hasattr(result,name) and value is not None:setattr(result,name,value)
    if hasattr(result,'lock'):result.lock=threading.RLock()
    return result


class Generation:
    def __init__(self, coordinator, account, request):
        self.live, self.account = coordinator, account
        with coordinator.host.lock, coordinator.repository.lock:
            self.room = coordinator.host.state()
            self.repository = ReadRepository(coordinator.repository.state())
            self.host = copy.copy(coordinator.host)
            self.host.lock = threading.RLock()
            self.host.state = lambda: copy.deepcopy(self.room)
            self.host.clock = lambda: self.at
            self.at = coordinator.host.clock()
            # A frozen tool cannot write through a copied host to its live store.
            def deny(*args,**kwargs):require(False,'GENERATION_READ_ONLY')
            for name in ('commit','command','ai_proposal_head'):setattr(self.host,name,deny)
            from .access import validate_context, policy
            if callable(getattr(coordinator.host,'ai_access_validator',None)):
                self.host.ai_access_validator=lambda room,context:validate_context(self.host,self.repository,room,context)
            if callable(getattr(coordinator.host,'ai_room_read_authorizer',None)):
                self.host.ai_room_read_authorizer=lambda principal:member(self.room,principal)['role']=='kp' and policy(self.repository)['allowAdminRoomRead']
            self._freeze_adapter(request)
            if getattr(self.host,'knowledge',None):
                self.host.knowledge=copy.copy(self.host.knowledge)
                self.host.knowledge.host=self.host
                self.host.knowledge.cursors={}
                rows={}
                # Providers may read independent package storage. Materialize
                # authorized rows now, never call those providers mid-generation.
                for principal in set((account,request['initiator'])):
                    for player in (False,True):
                        try:rows[principal,player]=self.host.knowledge._items(self.room,principal,player)
                        except Exception as exc:rows[principal,player]=exc
                def items(state,principal,player=False):
                    value=rows.get((principal,player))
                    require(value is not None,'NOT_VISIBLE')
                    if isinstance(value,Exception):raise value
                    return copy.deepcopy(value)
                self.host.knowledge._items=items
            self.proposals=clone(coordinator.proposals,self.host,self.repository)
            self.context=clone(coordinator.context,self.host,self.repository,proposals=self.proposals)
            if hasattr(self.context,'memory'):self.context.memory=clone(self.context.memory,self.host,self.repository,proposals=self.proposals)
            self.app=None
            if hasattr(coordinator,'application'):
                self.app=clone(coordinator.application,self.host,self.repository,proposals=self.proposals)
                for name in ('memory','reviews','sessions','batches','rulings','queue','player_requests','knowledge_requests'):
                    setattr(self.app,name,clone(getattr(self.app,name),self.host,self.repository,self.app,self.proposals))
            self.snapshot,self.payload=self.context.capture(account,request)
            self.snapshot[0]['facts']['generationSnapshot']=1
            if self.app:
                access=self.snapshot[0]['facts'].get('sessionAccess',{})
                if access.get('level')=='administrator':
                    review=self.app.reviews.payload(access['sessionId'])
                    if review:self.payload['reviewSource']=review
                    if self.room['aiControl']['settings']['externalSources']['kp']:
                        from .execution_ledger import capture
                        self.payload['executionLedger']=capture(self.app,account,access['sessionId'],request,self.snapshot[0])

    def _freeze_adapter(self, request):
        original=getattr(self.host,'ai_data_adapter',None)
        if original is None:return
        principals=set((self.account,request['initiator']));cache={}
        from onlinecoc.data_queries import KINDS
        adapter=SimpleNamespace(kinds=getattr(original,'kinds',KINDS))
        for principal in principals:
            for scope in (None,'kp-room'):
                try:
                    read=getattr(original,'read_scoped',None)
                    cache[principal,scope]=copy.deepcopy(read(self.room,principal,read_scope=scope) if callable(read) else original.read(self.room,principal))
                except Exception as exc:cache[principal,scope]=exc
        def read(state,principal,read_scope=None):
            value=cache.get((principal,read_scope));require(value is not None,'NOT_VISIBLE')
            if isinstance(value,Exception):raise value
            return copy.deepcopy(value)
        adapter.read_scoped=read;adapter.read=lambda state,principal:read(state,principal)
        for name in ('entities','known_configurations'):
            if hasattr(original,name):
                values={p:copy.deepcopy(getattr(original,name)(self.room,p)) for p in principals}
                setattr(adapter,name,lambda state,p,values=values:copy.deepcopy(values[p]))
        if callable(getattr(original,'reference_label',None)):
            labels={}
            for key,value in self.room['entities'].items():
                try:labels['entity',key]=original.reference_label('entity',key,value['name'])
                except Exception:pass
            adapter.reference_label=lambda kind,key,label:labels.get((kind,key),label)
        # No dynamic package callback is retained.
        self.host.ai_data_adapter=adapter

    def guard(self, context=None, seen=None, _room=None):
        """Recheck authority, not business revisions, before every external call."""
        c=self.live;primary=context is None;context=context or self.snapshot[0];facts=context['facts']
        seen=set() if seen is None else seen;key=digest(context)
        if key in seen:return
        require(len(seen)<100,'SOURCE_STALE');seen.add(key)
        with c.host.lock,c.repository.read_scope():
            room=c.host.state() if _room is None else _room
            require(room['aiControl']['scopeId']==context['scopeId'] and (not primary or c.host.epoch==context['authorityEpoch']),'STALE_AUTHORITY')
            require(room['aiControl']['settings']['externalSources']==self.room['aiControl']['settings']['externalSources'],'EXTERNAL_SCOPE_CHANGED')
            for principal in set((self.account,context['initiator'],facts.get('sessionAccess',{}).get('owner',self.account))):
                current=member(room,principal);old=member(self.room,principal)
                require(all(current[k]==old[k] for k in ('memberId','role','authorizationEpoch')),'PERMISSION_DENIED')
            from .access import validate_context
            safe=copy.deepcopy(context)
            safe['facts']={k:v for k,v in facts.items() if k in ('sessionAccess','aiPolicyRevision','aiReadScope','intentRequests')}
            validate_context(c.host,c.repository,room,safe)
            dependencies=list(facts.get('historyContexts',[]))+[item['contextRef'] for item in facts.get('historyIntents',[])]
            for ref in dependencies:
                previous=self.repository.read_state()['contexts'].get(ref)
                require(previous is not None,'HISTORY_PROVENANCE_INCOMPLETE')
                self.guard(previous,seen,room)
            for ref in context['sourceRefs']:
                if ref['kind']=='entity' and ref['id'] in room['entities']:
                    require(visible(room,context['initiator'],room['entities'][ref['id']]),'PERMISSION_DENIED')
                if ref['kind']=='message':
                    from onlinecoc import chat
                    require(chat.can_read(room,context['initiator'],room['chat']['channels'].get(ref['channelId'])),'PERMISSION_DENIED')
            if facts.get('strictPlayer'):
                from .knowledge import service
                owner=facts['sessionAccess']['owner'];port=service(c.host,owner,room)
                current=port.capture(owner,state=room,player=True)
                require(all(current[k]==facts['knowledgeProofs'][0][k] for k in current if k!='refs'),'SESSION_ACCESS_CHANGED')
                current_rows={row['ref']['id']:row for row in port._items(room,owner,True)}
                old_rows={row['ref']['id']:row for row in self.host.knowledge._items(self.room,owner,True)}
                from .history import _retained_nodes
                for proof in facts['knowledgeProofs']:
                    for ref in proof['refs']:
                        row=current_rows.get(ref['id']);require(row is not None,'NOT_VISIBLE')
                        require(_retained_nodes(old_rows[ref['id']]['data'],row['data']),'PERMISSION_DENIED')
            if facts.get('dataQueries'):
                from onlinecoc.data_queries import rows
                from .history import identity,_retained_nodes
                for proof in facts['dataQueries']:
                    witnesses=proof.get('readRefs',[])
                    if not witnesses:continue
                    options=dict(initiator=proof.get('initiator'),external=True,kinds=list({w['ref']['kind'] for w in witnesses}),read_scope=proof.get('readScope'))
                    if proof['args'].get('roomMode')=='state' or any(w['ref']['sourceId']=='host-room-state' for w in witnesses):options['room_mode']='state'
                    present={identity(r['ref']):r for r in rows(c.host,room,self.account,**options)}
                    old={identity(r['ref']):r for r in rows(self.host,self.room,self.account,**options)}
                    for witness in witnesses:
                        ref=witness['ref'];key=identity(ref);row=present.get(key)
                        if ref['sourceId'] not in ('host','host-room','host-room-state'):
                            require(row is not None and _retained_nodes(old[key]['data'],row['data']),'PERMISSION_DENIED')
                        if row:require(row['visibility']==witness['visibility'],'PERMISSION_DENIED')
            for ref in context['memoryRefs']:
                entry=c.repository.read_state()['memory'].get(ref['id'])
                require(entry and entry.get('status')!='revoked','PERMISSION_DENIED')

    def check(self):
        """Concrete read dependencies changed since send; output is retained."""
        self.guard();c=self.live;context=self.snapshot[0];facts=context['facts'];changes=[]
        with c.host.lock,c.repository.read_scope():
            room=c.host.state();stored=c.repository.read_state()
            def add(kind,key,code='DEPENDENCY_CHANGED'):
                value={'kind':kind,'id':str(key),'code':code,'summary':'发送后该资料已变化，请核对候选是否仍适用。'}
                if value not in changes:changes.append(value)
            for ref in context['sourceRefs']:
                values=room['entities'] if ref['kind']=='entity' else room['configurations'] if ref['kind']=='configuration' else {}
                value=values.get(ref['id'])
                if ref['kind']=='message':value=next((m for m in room['chat']['messages'].get(ref['channelId'],[]) if m['messageId']==ref['id']),None)
                if digest(value)!=ref['digest']:add(ref['kind'],ref['id'],'DEPENDENCY_REMOVED' if value is None else 'DEPENDENCY_CHANGED')
            for section,keys in facts.get('managementReadKeys',{}).items():
                old={k:self.room[k] for k in ('roomId','name','runId','status','activeRuleset')} if section=='room' else self.room[section]
                now={k:room[k] for k in old} if section=='room' else room[section]
                for key in keys:
                    if old.get(key)!=now.get(key):add(section,key,'DEPENDENCY_REMOVED' if key not in now else 'DEPENDENCY_CHANGED')
            for sid,revision in facts.get('sessionReads',{}).items():
                if stored['settings'].get('sessions',{}).get(sid,{}).get('revision')!=revision:add('session',sid)
            from .data_edits import node
            for proof in facts.get('configDataReads',[]):
                try:changed=digest(node(room['artifacts'][room['activeRuleset']]['data'][proof['file']],proof['path']))!=proof['targetDigest']
                except Exception:changed=True
                if changed:add('config-data',proof['file']+'/'+'/'.join(map(str,proof['path'])))
            from .data_queries import DataQueryService
            for proof in facts.get('dataQueries',[]):
                try:
                    value=DataQueryService(c.host).execute(self.account,proof['operation'],proof['args'],initiator=proof.get('initiator'),external=True,player=proof.get('player'),read_scope=proof.get('readScope'))
                    changed=digest(value)!=proof['digest']
                except Exception:changed=True
                if changed:
                    for ref in proof.get('readRefs',[]):add(ref['ref']['kind'],ref['ref']['id'])
                    if not proof.get('readRefs'):add('query',proof['operation'])
            if facts.get('strictPlayer'):
                owner=facts['sessionAccess']['owner'];now={r['ref']['id']:r['ref'] for r in c.host.knowledge._items(room,owner,True)}
                for proof in facts['knowledgeProofs']:
                    for ref in proof['refs']:
                        if now.get(ref['id'])!=ref:add('knowledge',ref['id'])
            if room['activeRuleset']!=context['baseRuleset'] and not facts.get('strictPlayer'):add('ruleset',context['baseRuleset'])
            return {'snapshotAt':self.at,'checkedAt':c.host.clock(),'status':'changed' if changes else 'unchanged',
                    'changes':changes[:100],'totalChanges':len(changes),'canRegenerate':bool(changes)}
