"""Read-only package evidence adapter. Uses documented room fields, no engine imports."""
import hashlib
import copy
import json
import os
import threading
from pathlib import Path

# Only game facts enter broad configuration queries. Operational containers
# have their own explicit chat/event/ruling projections below; a new storage
# field must not silently become an AI fact or invalidate unrelated proposals.
GAME_FACT_ROOTS = frozenset({
    'locations', 'published', 'notes', 'discoveries', 'actorDiscoveries',
    'doors', 'recap', 'recapDraft', 'recapPrivate', 'sceneState', 'encounters',
    'loot', 'roster', 'npcs', 'bindings', 'locationKnowledge', 'mapPlayerActors',
    'mapNpcActors', 'mapRatCount', 'ruleRevisions', 'activeRevision',
})

def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()


def known_locations(state, entities, account):
    """Personal visits or explicit disclosure; never global publish or inferred from a clue."""
    known=set(state.get('locationKnowledge',{}).get(account,[]))
    known.update(str(v['numbers']['location']) for v in entities.values()
        if v['configurationId']=='sv.character' and v['owner']==account and v['lifecycle']=='active')
    return known


class Adapter:
    kinds=("channel","chat","event","ruling","config")
    def __init__(self,path):
        self.path=Path(path)
        self._label_lock=threading.RLock()
        self._label_signature=None
        self._binding_labels={}

    def _labels(self):
        # Only presentation labels are retained, never evidence or permissions.
        # Package publication uses atomic replacement; inode and timestamps
        # also invalidate a same-sized replacement or an in-place edit.
        def signature(value):
            # Windows stat() and fstat() expose different ctime semantics.
            return (value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns)
        with self._label_lock:
            try:current=signature(self.path.stat())
            except FileNotFoundError:
                self._label_signature=None;self._binding_labels={};return {}
            if current!=self._label_signature:
                with self.path.open('rb') as stream:
                    raw=stream.read(8*1024*1024+1)
                    loaded=signature(os.fstat(stream.fileno()))
                if len(raw)>8*1024*1024:raise ValueError('PACKAGE_DATA_LIMIT')
                state=json.loads(raw);labels={}
                if state.get('format')==2:
                    for account,actor in state.get('bindings',{}).items():labels.setdefault(actor,account)
                self._binding_labels=labels;self._label_signature=loaded
            return self._binding_labels

    def reference_label(self,kind,key,fallback):
        labels={'sv.npc':'NPC 模板','sv.character':'角色模板','sv.location':'地点模板','sv.scene':'场景状态模板'}
        if kind=='config':return labels.get(key,fallback)
        if kind=='entity':
            owner=self._labels().get(key)
            if owner:return f'{fallback}（{owner} 的树桩镇角色）'[:160]
        return fallback

    def known_configurations(self,room,account):
        # Seeing a contact's name never discloses its NPC template or default stats.
        return {v['configurationId'] for v in room['entities'].values() if v['owner']==account and v['lifecycle']=='active'}

    def entities(self, room, account):
        """Same player boundary as the package UI: own sheet and disclosed map facts."""
        if not self.path.exists():return {}
        raw=self.path.read_bytes()
        if len(raw)>8*1024*1024:raise ValueError('PACKAGE_DATA_LIMIT')
        state=json.loads(raw)
        if state.get('format')!=2 or state.get('sceneId') not in room['entities']:return {}
        all_entities=room['entities'];mine=[v for v in all_entities.values() if v['configurationId']=='sv.character' and v['owner']==account and v['lifecycle']=='active']
        locations={v['numbers']['location'] for v in mine};seen=state.get('actorDiscoveries',{}).get(account,{})
        known=known_locations(state,all_entities,account)
        result={}
        for key,value in all_entities.items():
            if value['lifecycle']!='active':continue
            cid=value['configurationId'];out=None
            if value['owner']==account:
                out=copy.deepcopy(value)
            elif cid=='sv.location' and value['visibility']=='public' and str(value['numbers'].get('index')) in known:
                disclosed=state.get('published',{}).get(str(value['numbers'].get('index')))
                if disclosed:
                    out=copy.deepcopy(value);out.update(numbers={'index':value['numbers']['index']},rules={},metadata={'known':copy.deepcopy(disclosed)},components={},tags=[])
                    out['metadata']['known']['exits']=[i for i in disclosed.get('exits',[]) if str(i) in known]
                    out['metadata']['discoveries']=[v for v in state.get('discoveries',{}).get(account,{}).values() if v.get('location')==value['numbers']['index']]
            elif (cid in ('sv.character','sv.npc') or cid.startswith('sv.ext.npc.')) and value['numbers'].get('location') in locations and (seen.get(key, cid=='sv.character')):
                out=copy.deepcopy(value);out.update(numbers={'location':value['numbers']['location']},rules={},metadata={},components={},tags=[],visibility='public')
            if out:
                out['metadata'].pop('secret',None);result[key]=out
        return result

    def read(self,room,account):
        return self.read_scoped(room,account)

    def read_scoped(self,room,account,*,read_scope=None):
        if not self.path.exists():return []
        with self.path.open('rb') as stream:raw=stream.read(8*1024*1024+1)
        if len(raw)>8*1024*1024:raise ValueError('PACKAGE_DATA_LIMIT')
        state=json.loads(raw)
        if state.get('format')!=2:raise ValueError('PACKAGE_FORMAT_UNSUPPORTED')
        # Bind the package to this room through its actual scene entity, not a caller-supplied ID.
        if state.get('sceneId') not in room['entities']:return []
        member=room['members'].get(account,{})
        kp=member.get('role')=='kp'
        full=kp and read_scope=='kp-room'
        actors=[v for v in room['entities'].values() if v['configurationId']=='sv.character' and v['lifecycle']=='active']
        mine=[v for v in actors if v['owner']==account]
        locations={v['numbers']['location'] for v in (actors if kp else mine)}
        channels={'sv-scene-'+str(n) for n in locations}
        if kp or mine:channels.add('sv-party')
        if full:channels.update(state.get('scopedChat',{}).get('messages',{}))
        values=[]
        def add(kind,key,label,data):
            values.append({'sourceId':'stumpsville','kind':kind,'id':key,'revision':fingerprint(data),
                           'label':label,'data':data,'visibility':'private'})
        if full:
            labels={'locations':'地图地点与主持秘密','published':'已发布地点资料','notes':'玩家手记',
                'discoveries':'玩家个人线索','actorDiscoveries':'人物发现记录','ruleRevisions':'规则与配置修订',
                'doors':'地图通道状态','recapPrivate':'主持私密回顾',
                'sceneState':'场景机关状态','encounters':'遭遇表','roster':'人物名册','npcs':'主持生物'}
            def emit(path,value,label):
                raw=json.dumps(value,ensure_ascii=False)
                if len(raw)>5000 and isinstance(value,(dict,list)):
                    entries=value.items() if isinstance(value,dict) else enumerate(value)
                    for key,child in entries:emit(path+'/'+str(key),child,label+' / '+str(key))
                    return
                if isinstance(value,str) and len(raw)>5000:
                    for offset in range(0,len(value),750):
                        emit(path+'/text:'+str(offset),{'offset':offset,'text':value[offset:offset+750],'totalCharacters':len(value)},label+' 正文片段 '+str(offset))
                    return
                values.append({'sourceId':'stumpsville','kind':'config','id':'package-state:'+hashlib.sha256(path.encode()).hexdigest(),
                    'revision':fingerprint(value),'label':label,'data':{'path':path,'value':copy.deepcopy(value)},'visibility':'kp'})
            for key,value in state.items():
                if key in GAME_FACT_ROOTS:emit('/'+key,value,labels.get(key,'包内资料 '+key))
        for cid,messages in state.get('scopedChat',{}).get('messages',{}).items():
            if cid not in channels:continue
            add('channel',cid,cid,{'channelId':cid,'lastSequence':messages[-1]['sequence'] if messages else 0})
            for message in messages:
                if not message['deleted']:add('chat',message['messageId'],message['text'][:80],message)
        # Use the package's existing per-recipient feedback. Never export the complete KP view.
        events=[(owner,e) for owner,items in state.get('events',{}).items() if kp or owner==account for e in items]
        for owner,event in events:
            request=state.get('requests',{}).get(event.get('requestId'),{})
            request_visible=request and (kp or request.get('account')==account)
            status=event['status']
            decided=status in ('approved','rejected','completed') and (event['operation']=='resolve' or event.get('mode')=='auto')
            decision={'status':'confirmed' if decided else 'pending',
                      'outcome':'deny' if status=='rejected' else 'allow' if decided else None,
                      'reason':event.get('reason',''),'actor':event.get('decider'),'decidedAt':event.get('decidedAt'),'authority':'package-record'}
            execution='none' if decided and (status=='rejected' or not event.get('mechanical')) else 'unknown'
            receipt=next((r for r in state.get('receipts',{}).get(owner,[]) if r['id']==event.get('receiptId')),None)
            if receipt and event.get('mechanical'):
                records=[room['commands'].get(owner+':'+cid) for cid in receipt.get('commandIds',[])]
                if records and all(r and r['status']=='committed' for r in records):execution='completed'
            # Sources not recorded by old versions stay missing; no fabricated chat association or KP identity.
            bundle={'messages':[], 'actions':[request] if request_visible else [], 'rulings':[decision],
                    'executions':[{'status':execution,'result':event.get('result'), 'recordedChanges':event.get('changes',[])}],
                    'links':[], 'coverage':{'status':'partial','reason':'CHAT_LINK_AND_DECIDER_NOT_RECORDED'},
                    'eventId':event['id'],'requestId':event.get('requestId'),'recordedAt':event['time']}
            if request_visible:
                # Do not leak source IDs from a different scene/channel in the request payload.
                bundle['actions']=[{k:v for k,v in request.items() if k!='sourceMessageRefs'}]
                bundle['links'].append({'type':'decides' if decided else 'requests','from':event['id'],'to':request['id']})
            for ref in event.get('sourceMessageRefs',[]):
                cid=ref['channelId']
                if cid.startswith('sv-'):
                    if cid not in channels:continue
                    messages=state.get('scopedChat',{}).get('messages',{}).get(cid,[])
                else:
                    channel=room['chat']['channels'].get(cid)
                    if not channel or not (full or channel['kind']=='room' or account in channel['participants']):continue
                    messages=room['chat']['messages'].get(cid,[])
                message=next((m for m in messages if m['messageId']==ref['messageId'] and not m['deleted'] and str(m['revision'])==str(ref['revision'])),None)
                if message:
                    bundle['messages'].append(message)
                    bundle['links'].append({'type':'describes','from':message['messageId'],'to':event['id']})
            if bundle['messages'] and event.get('decider'):
                bundle['coverage']={'status':'partial' if execution=='unknown' else 'complete','within':'recorded-authorized-sources'}
            add('event',owner+':'+event['id'],event['title'],bundle)
            if decided:add('ruling',owner+':'+event['id'],event['title'],bundle)
        return values


def create_adapter(data_path):return Adapter(data_path)
