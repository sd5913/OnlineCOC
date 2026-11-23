"""Trusted package knowledge adapter, installed independently of the AI module.

No grants are created on reads or startup. KP commands bind policy and disclose;
successful host movement creates a new immutable observation in the same commit.
"""
import copy
import hashlib
import os
import threading
import json
from pathlib import Path
import importlib.util

# The host loads trusted plugins by absolute file path, without adding their
# directory to sys.path. Load only this fixed sibling, not a caller-supplied path.
_spec = importlib.util.spec_from_file_location('stumpsville_scene_knowledge', Path(__file__).with_name('scene_knowledge.py'))
scene_knowledge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scene_knowledge)

POLICY='stumpsville-personal-v1'
NAMESPACE='stumpsville'
PERSONAL_ACTIONS=frozenset(('sv.create','sv.ready','sv.check','sv.inventory','sv.travel.auto'))


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def descriptor():
    return {'policyId':POLICY,'namespace':NAMESPACE,'contractVersion':1,'mode':'required-personal',
        'providerId':'stumpsville-known-v2-'+scene_knowledge.POLICY_DIGEST,'selectors':[{'kind':'entity','configurationPrefix':'sv.'}],
        'facetSchemas':{
            'scene':{'schema':scene_knowledge.SCENE,'modes':['observed_snapshot'],'labelField':'name'},
            'identity':{'schema':scene_knowledge.IDENTITY,'modes':['observed_snapshot'],'labelField':'name'},
            'play':{'schema':scene_knowledge.PLAY,'modes':['live_scope'],'labelField':'name'},
            'sheet':{'schema':scene_knowledge.SHEET,'modes':['live_scope'],'labelField':'name','entityProjection':True}},
        'egress':{key:'filtered' for key in ('view','query','rules','receipts','assets','export','ai')}}


class Provider:
    def __init__(self, path):
        self.path = Path(path) if path else None
        self.file_lock = threading.Lock()
        self.file_version = None
        self.scene_data = None
        self.file_digest = None
        self.scene_revision = None

    def read_scene_file(self, check_contents):
        if self.path is None:
            raise ValueError('PACKAGE_DATA_REQUIRED')
        with self.file_lock, self.path.open('rb') as stream:
            st = os.fstat(stream.fileno())
            version = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
            if check_contents or st.st_ino == 0 or self.file_version != version:
                raw = stream.read(8*1024*1024+1)
                if len(raw) > 8*1024*1024:
                    raise ValueError('PACKAGE_DATA_LIMIT')
                digest = hashlib.sha256(raw).digest()
                if self.file_digest != digest:
                    # Clear the metadata fast path before parsing potentially corrupt bytes.
                    self.file_version = None
                    parsed = json.loads(raw)
                    fields = ('format', 'sceneId', 'locations', 'published', 'discoveries', 'doors')
                    source = {k: parsed[k] for k in fields if k in parsed}
                    revision = parsed.get('activeRevision')
                    authored = parsed.get('ruleRevisions',{}).get(revision,{}).get('data',{}).get('scene-actions.json',{})
                    source['authoredActions'] = authored
                    encoded = json.dumps(source, sort_keys=True, separators=(',', ':')).encode()
                    self.scene_revision = hashlib.sha256(encoded).hexdigest()
                    self.scene_data = source
                    self.file_digest = digest
                self.file_version = version
            return self.scene_data, self.scene_revision

    def projection_revision(self):
        # Host generation covers actors, grants and rules. This token covers every
        # external file input to pin(), even for an in-place equal-stat edit.
        source, revision = self.read_scene_file(True)
        if source.get('format') not in (2,3) or not source.get('sceneId'):
            raise ValueError('PACKAGE_ROOM_MISMATCH')
        return revision

    def package(self,context):
        cache=context.setdefault('cache',{})
        cache_key=('stumpsville-package',str(self.path))
        if cache_key in cache:return cache[cache_key]
        data, _ = self.read_scene_file(False)
        if data.get('format') not in (2,3) or data.get('sceneId') not in context['state']['entities']:
            raise ValueError('PACKAGE_ROOM_MISMATCH')
        cache[cache_key]=data
        return data

    def pin(self,resource,facets,context):
        entity=context['state']['entities'].get(resource['id'])
        if not entity or not entity['configurationId'].startswith('sv.') or entity['lifecycle']!='active':
            raise ValueError('RESOURCE_UNAVAILABLE')
        values={};versions={}
        for facet in facets:
            if facet=='scene' and entity['configurationId']=='sv.location':
                data=self.package(context);index=str(entity['numbers']['index'])
                place=data['published'].get(index) or data['locations'][index]
                # Published choices define clues. Entering an unpublished scene
                # reveals only its ordinary description, not its hidden clues.
                value={k:copy.deepcopy(place[k]) for k in ('index','name','description','exits','features')}
                value['clues']=copy.deepcopy(data['published'].get(index,{}).get('clues',[]))
                known_ids={c['id'] for c in value['clues']}
                value['clues'].extend(copy.deepcopy(c) for c in data.get('discoveries',{}).get(context['accountId'],{}).values()
                    if str(c.get('location'))==index and c['id'] not in known_ids)
                artifact=context['state']['artifacts'][context['state']['activeRuleset']]
                definitions=scene_knowledge.presentation(artifact['data'].get('scene-actions.json',{}),data.get('authoredActions'))
                value['actions']=scene_knowledge.menu(definitions,int(index),value['clues'])
                entities = context['state']['entities']
                flags = dict(entities[data['sceneId']]['numbers'])
                for edge, field in [('2-3','gateOpen'), ('8-9','ironOpen'), ('9-10','caveOpen')]:
                    if edge in data.get('doors', {}):
                        flags[field] = int(data['doors'][edge] == 'open')
                session = next((e for e in entities.values() if e['configurationId'] == 'sv.session'), None)
                scene_knowledge.describe_events(value, definitions, flags, session['numbers']['round'] if session else 0)
                location = data['locations'][index]
                stock = {row['item']: row['count'] for row in location['stock']}
                game = artifact['data'].get('game.json', {})
                if game.get('stormStocks'):
                    scene_knowledge.describe_stock(value, stock, location.get('pips', 0), game)
                value['features']=[a['label'] for a in value['actions']]
                value['entityId']=entity['instanceId']
                value['doors']={str(target):data.get('doors',{}).get('-'.join(map(str,sorted((int(index),target)))),'unknown')
                    for target in value['exits']}
                value['navigation']={str(e['numbers']['index']):e['instanceId'] for e in context['state']['entities'].values()
                    if e['configurationId']=='sv.location' and e['numbers']['index'] in value['exits']}
                values[facet]=value
                # Preview runs as KP; pin runs as the recipient. The source
                # version must describe authoritative inputs independently of
                # their projections, including personal discoveries but not
                # volatile job/receipt writes between preview and command.
                versions[facet]={'place':place,'stock':stock,'pips':location.get('pips',0),'discoveries':data.get('discoveries',{}),
                    'definitions':definitions,'presentation':scene_knowledge.POLICY_DIGEST,
                    'navigation':value['navigation'],'doors':value['doors']}
            elif facet=='identity' and (entity['configurationId'] in ('sv.character','sv.npc') or entity['configurationId'].startswith('sv.ext.npc.')):
                values[facet]={'name':entity['name'],'location':entity['numbers'].get('location'),'entityId':entity['instanceId']}
            elif facet=='sheet' and entity['configurationId'] in ('sv.character','sv.draft') and entity['owner']==context['accountId']:
                value=copy.deepcopy(entity)
                value.update(metadata={},tags=[],components={},rules={})
                if entity['configurationId']=='sv.character':
                    # Intrinsic descriptions of held items only; never export the item catalog
                    # or copy caller-controlled entity metadata into personal knowledge.
                    artifact=context['state']['artifacts'][context['state']['activeRuleset']]
                    definitions=artifact['data'].get('game.json',{}).get('items',[])
                    inventory=[]
                    for slot in range(1,21):
                        index=entity['numbers'].get('item'+str(slot),0)
                        if type(index) not in (int,float) or index!=int(index) or not 1<=index<=len(definitions):continue
                        item=definitions[int(index)-1]
                        shown={k:copy.deepcopy(item[k]) for k in ('id','name','kind','slots','description','damage','armor','light','useDie') if k in item}
                        shown.update(slot=slot,itemIndex=int(index),uses=entity['numbers'].get('uses'+str(slot),0),maxUses=item.get('uses',0),ticks=entity['numbers'].get('ticks'+str(slot),0))
                        inventory.append(shown)
                    value['metadata']['inventory']=inventory
                values[facet]=value
            elif facet=='play' and entity['configurationId']=='sv.session':
                values[facet]={'name':'场次状态','entityId':entity['instanceId'],
                    'numbers':{k:v for k,v in entity['numbers'].items() if k in ('phase','round','autoResolve')}}
            else:raise ValueError('FACET_UNAVAILABLE')
        return {'sourceRevision':digest({k:versions.get(k,v) for k,v in values.items()}),'facets':values,
            'sourceGuard':{'entityId':entity['instanceId'],'configurationId':entity['configurationId'],
                           'projectionVersion':scene_knowledge.VERSION,'presentation':scene_knowledge.POLICY_DIGEST}}

    def read_live(self,resource,facets,context):
        if facets not in (['sheet'],['play']):raise ValueError('LIVE_SCENE_NOT_SUPPORTED')
        return self.pin(resource,facets,context)

    def check_guard(self,guard,context):
        value=context['state']['entities'].get(guard.get('entityId'))
        return bool(guard.get('projectionVersion')==scene_knowledge.VERSION and guard.get('presentation')==scene_knowledge.POLICY_DIGEST
                    and value and value['configurationId']==guard.get('configurationId') and not value['metadata'].get('knowledgeRevoked'))

    def derive_observations(self,outcome,context):
        operation=outcome['operation'];inputs=outcome.get('input',{})
        if operation in ('sv.profile','sv.travel','sv.travel.auto'):
            key=inputs.get('actor')
        elif operation in ('entity.update','entity.patch') and 'location' in inputs.get('numbers',{}):key=inputs.get('id')
        else:return []
        actor=context['state']['entities'].get(key)
        if not actor or actor['configurationId']!='sv.character' or actor['numbers'].get('approved')!=1:return []
        previous=context.get('previousState',{}).get('entities',{}).get(key)
        if operation in ('entity.update','entity.patch') and previous and previous['numbers'].get('location')==actor['numbers']['location']:return []
        owner=context['state']['members'].get(actor['owner'])
        if not owner or not owner['active']:return []
        location=next((e for e in context['state']['entities'].values() if e['configurationId']=='sv.location'
            and e['numbers']['index']==actor['numbers']['location'] and e['lifecycle']=='active'),None)
        if not location:return []
        return [{'subjectMemberId':owner['memberId'],'resource':{'namespace':NAMESPACE,'kind':'entity','id':location['instanceId']},'facetIds':['scene']}]

    def authorize_operation(self,operation,args,context):
        actor=context['state']['entities'].get(args.get('actor'))
        return operation in PERSONAL_ACTIONS and bool(actor and actor['owner']==context['accountId']
            and actor['configurationId'] in ('sv.character','sv.draft') and actor['lifecycle']=='active')

    def project_operation(self,operation,result,reads,context):
        if operation not in PERSONAL_ACTIONS or not isinstance(result,dict):return None
        # The rules expose only the invoking player's check/status values.
        fields={'sv.create':('str','dex','wil','hp','pips'), 'sv.ready':('ready',),
            'sv.check':('first','second','rolled','target','passed','attribute','mode'),
            'sv.inventory':('operation','slot','target','uses','overloaded','dropped'), 'sv.travel.auto':('location','automatic')}
        return {key:copy.deepcopy(result[key]) for key in fields[operation] if key in result}

    def project_catalog(self,actions,context):
        if isinstance(actions,dict):return {key:value for key,value in actions.items() if key in PERSONAL_ACTIONS}
        return [value for value in actions if value.get('actionId',value.get('id')) in PERSONAL_ACTIONS]


def install(host,path=None):
    return host.register_knowledge_provider(descriptor(),Provider(path))
