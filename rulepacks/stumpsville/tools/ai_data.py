"""Read-only package evidence adapter. Uses documented room fields, no engine imports."""
import hashlib
import copy
import json
from pathlib import Path


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()


def known_locations(state, entities, account):
    """Personal visits or explicit disclosure; never global publish or inferred from a clue."""
    known=set(state.get('locationKnowledge',{}).get(account,[]))
    known.update(str(v['numbers']['location']) for v in entities.values()
        if v['configurationId']=='sv.character' and v['owner']==account and v['lifecycle']=='active')
    return known


class Adapter:
    kinds=("channel","chat","event","ruling")
    def __init__(self,path):self.path=Path(path)

    def reference_label(self,kind,key,fallback):
        labels={'sv.npc':'NPC 模板','sv.character':'角色模板','sv.location':'地点模板','sv.scene':'场景状态模板'}
        return labels.get(key,fallback) if kind=='config' else fallback

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
        if not self.path.exists():return []
        with self.path.open('rb') as stream:raw=stream.read(8*1024*1024+1)
        if len(raw)>8*1024*1024:raise ValueError('PACKAGE_DATA_LIMIT')
        state=json.loads(raw)
        if state.get('format')!=2:raise ValueError('PACKAGE_FORMAT_UNSUPPORTED')
        # Bind the package to this room through its actual scene entity, not a caller-supplied ID.
        if state.get('sceneId') not in room['entities']:return []
        member=room['members'].get(account,{})
        kp=member.get('role')=='kp'
        actors=[v for v in room['entities'].values() if v['configurationId']=='sv.character' and v['lifecycle']=='active']
        mine=[v for v in actors if v['owner']==account]
        locations={v['numbers']['location'] for v in (actors if kp else mine)}
        channels={'sv-scene-'+str(n) for n in locations}
        if kp or mine:channels.add('sv-party')
        values=[]
        def add(kind,key,label,data):
            values.append({'sourceId':'stumpsville','kind':kind,'id':key,'revision':fingerprint(data),
                           'label':label,'data':data,'visibility':'private'})
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
                    if not channel or not (channel['kind']=='room' or account in channel['participants']):continue
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
