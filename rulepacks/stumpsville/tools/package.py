"""Package composition and resumable public-API workflows. No host internals."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time

from client import HostError
import scenes
from chat import ScopedChat
from visibility import MapVisibility
from ai_data import known_locations
import knowledge_client
import action_errors
import scene_knowledge
import publication_sync

PACK = Path(__file__).resolve().parents[1]


def bundle():
    manifest = json.loads((PACK / 'manifest.json').read_text(encoding='utf-8'))
    return {'manifest': manifest,
            'sources': {name: (PACK / 'rules' / name).read_text(encoding='utf-8') for name in manifest['rules']},
            'data': {name: json.loads((PACK / 'config' / name).read_text(encoding='utf-8')) for name in manifest['data']},
            'configurations': json.loads((PACK / manifest['configurations']).read_text(encoding='utf-8'))}


class PackageError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PackageError(message)


class Job:
    def __init__(self, store, client, record):
        self.store, self.client, self.record = store, client, record

    def command(self, key, op, args):
        step = self.record['steps'].get(key)
        fresh = step is None
        if step is None:
            step = {'envelope': self.client.envelope(op, args)}
            self.record['steps'][key] = step
            self.store.save()
        if 'result' not in step:
            command_id = step['envelope']['payload']['commandId']
            # A just-created envelope has never been dispatched. Recovery still
            # queries the durable receipt before retrying an existing envelope.
            receipt = {'status': 'unknown'} if fresh else self.client.request('/receipts/' + command_id)
            if receipt['status'] == 'unknown':
                if not fresh:
                    current = self.client.request('/view')
                    old = step['envelope']['payload']
                    if old['authorityEpoch'] != current['authorityEpoch'] or old['runId'] != current['runId']:
                        require(old['rulesetRevision'] == current['catalog']['rulesetRevision'], '原行动未提交且规则已变更，请主持核查')
                        old.update(authorityEpoch=current['authorityEpoch'], runId=current['runId'], catalogRevision=current['catalog']['revision'])
                        self.store.save()
                receipt = self.client.send(step['envelope'])
            if receipt['status'] != 'committed':
                raise HostError(receipt)
            step['result'] = receipt.get('result')
            self.store.save()
        return step['result']

    def invoke(self, key, rule, **inputs):
        if key not in self.record['steps']:
            self.store.explain_preconditions(self, rule, inputs)
        return self.command(key, 'action.invoke', {'actionId': rule, 'input': inputs})

    def sync_numbers(self, key, entity, numbers):
        # Never skip a previously persisted envelope: its receipt may need recovery.
        # New no-op writes need neither a host transaction nor an entity revision.
        if key in self.record['steps'] or any(entity['numbers'].get(k) != v for k, v in numbers.items()):
            return self.command(key, 'entity.update', {'id': entity['instanceId'], 'numbers': numbers})


class Package:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        # Heartbeats contain account IDs and times only, never KP credentials.
        self.executor_seen = {}
        baseline = bundle()
        self.game = baseline['data']['game.json']
        self.diagnostic_sources = baseline['sources']
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding='utf-8'))
            require(self.state.get('format') == 2, '包侧存档格式不支持；当前仅接受格式 2')
            require(all(k in self.state for k in ('doors', 'roster', 'generatedCharacters', 'events', 'discoveries', 'sceneState', 'autoSceneQueue', 'ruleRevisions', 'encounters', 'loot', 'scopedChat', 'actorDiscoveries', 'mapPlayerActors', 'mapNpcActors', 'mapRatCount')), '包侧存档字段不完整')
        else:
            self.state = {'format': 2, 'revision': 0, 'jobs': {}, 'drafts': {}, 'requests': {},
                          'notes': {}, 'locations': {str(x['index']): copy.deepcopy(x) for x in self.game['locations']},
                          'published': {}, 'bindings': {}, 'npcs': {}, 'recap': '', 'recapDraft': '',
                          'recapPrivate': '', 'receipts': {}, 'initialized': False}
            self.state.update(doors={'1-2': 'open', '2-3': 'closed', '3-4': 'open', '3-5': 'open', '3-6': 'open',
                                     '3-7': 'open', '3-8': 'open', '7-8': 'locked', '8-9': 'closed', '9-10': 'closed'},
                              roster={}, generatedCharacters={}, events={}, discoveries={}, sceneState={}, autoSceneQueue={},
                              ruleRevisions={}, encounters=copy.deepcopy(self.game['encounters']), loot=['待主持依原版战利品表裁定'] * 20,
                              scopedChat={'messages': {}, 'reads': {}}, actorDiscoveries={}, mapPlayerActors={}, mapNpcActors={}, mapRatCount=0)
        active = self.state.get('activeRevision')
        if active in self.state['ruleRevisions']:
            self.game = self.state['ruleRevisions'][active]['data']['game.json']

    @staticmethod
    def edge(a, b):
        return '-'.join(str(x) for x in sorted((a, b)))

    def passable(self, a, b):
        return self.state['doors'].get(self.edge(a, b), 'closed') == 'open'

    def automation_ready(self, session):
        sources = self.state['ruleRevisions'].get(self.state.get('activeRevision'), {}).get('sources', {})
        return bool(session and 'autoResolve' in session['numbers'] and 'auto-travel.lua' in sources)

    def scene_definitions(self):
        return self.scene_content().get('actions', [])

    def scene_content(self):
        content = self.state['ruleRevisions'].get(self.state.get('activeRevision'), {})
        return content.get('data', {}).get('scene-actions.json', {})

    def scene_ready(self):
        content = self.state['ruleRevisions'].get(self.state.get('activeRevision'), {})
        return 'scene.lua' in content.get('sources', {}) and bool(self.state.get('sceneId')) and bool(self.scene_definitions())

    def current_scene_request(self, job, version):
        if version == scene_knowledge.VERSION:
            return True
        step = job.record['steps'].get('scene-act', {})
        if 'result' in step:
            return True
        if 'envelope' in step:
            receipt = job.client.request('/receipts/' + step['envelope']['payload']['commandId'])
            if receipt.get('status') == 'committed':
                step['result'] = receipt.get('result')
                self.save()
                return True
        return False

    def scene_executor(self, client):
        with self.lock:
            view = client.request('/view')
            require(view['role'] == 'kp', '需要主持权限')
            self.executor_seen[view['accountId']] = time.time()
            session = next(iter(self.entities(view, 'sv.session')), None)
            enabled = session and session['numbers'].get('autoResolve', 1) and view['status'] == 'active'
            tasks = [t for t in self.state['autoSceneQueue'].values() if t['status'] in {'queued', 'running', 'finishing'}
                     and (not t.get('executor') or t['executor'] == view['accountId'])]
            return {'jobs': [{'id': t['id'], 'commandId': t['commandId']} for t in tasks[:1]] if enabled else []}

    def queue_scene(self, view, character, job, definition, choice):
        key = job.record['requestKey']
        require(not any(t['account'] == view['accountId'] and t['status'] in {'queued', 'running', 'finishing'}
                        for t in self.state['autoSceneQueue'].values()), '请等待当前预设行动自动完成')
        task = {'id': key, 'account': view['accountId'], 'actor': character['instanceId'],
                'menuVersion': scene_knowledge.VERSION,
                'action': definition['id'], 'choice': choice, 'title': definition['label'], 'status': 'queued',
                'time': time.time(), 'commandId': 'scene-auto-' + hashlib.sha256(key.encode()).hexdigest()[:40]}
        self.state['autoSceneQueue'][key] = task
        return {'status': 'processing', 'jobId': key, 'sceneAction': definition['id'], 'title': definition['label'],
                'message': '行动已接收，等待自动执行端结算；无需主持逐项确认', 'outcome': 'queued',
                'narrative': ['预设行动已排入自动队列。KP 页面在线时会自动处理；尚未投骰或扣减资源。'],
                'checks': [], 'rolls': [], 'stateChanges': [], 'clues': [], 'process': '已提交 → 等待自动执行端'}

    def run_scene_queue(self, job, view, task_id):
        task = self.state['autoSceneQueue'].get(task_id)
        require(task is not None, '自动行动不存在')
        if task['status'] == 'completed':
            return task['result']
        require(not task.get('executor') or task['executor'] == view['accountId'], '请由原自动执行端恢复此行动')
        session = next(iter(self.entities(view, 'sv.session')))
        require(session['numbers'].get('autoResolve', 1) == 1, '自动裁决已关闭，自动队列暂缓执行')
        actor = view['entities'].get(task['actor'])
        task.update(status='running', executor=view['accountId'])
        self.save()
        try:
            require(self.current_scene_request(job,task.get('menuVersion')),
                    '行动菜单已更新，请按本人已知选项重新提交')
            require(actor and actor['owner'] == task['account'] and actor['lifecycle'] == 'active', '角色归属或状态已改变')
            result = self.execute_scene(job, view, actor, task['action'], task['choice'])
        except (PackageError, HostError) as error:
            if 'result' in job.record['steps'].get('scene-act', {}):
                raise  # Committed effects must finish publication through the same job.
            if isinstance(error, HostError) and error.response.get('status') != 'rejected':
                raise
            detail = self.failure_detail(error, job.record)
            detail.update(actionId=task_id.split(':', 1)[1], operation='scene.action')
            reason = detail['reason']
            result = {'status': 'completed', 'sceneAction': task['action'], 'title': task['title'], 'outcome': 'blocked',
                'message': '本次自动行动未执行', 'process': '执行前校验未通过，未产生本次行动的掷骰或资源效果',
                'narrative': [reason, detail['nextStep']], 'failure': detail, 'checks': [], 'rolls': [], 'stateChanges': [], 'clues': []}
            if self.state.get('scenePending') == job.record['requestKey']:
                self.state.pop('scenePending')
        task.update(status='finishing', result=result, completedAt=time.time())
        origin = self.state['jobs'][task_id]
        origin.update(result=result, executed=result)
        receipt_id = task_id.split(':', 1)[1]
        for receipt in self.state['receipts'].get(task['account'], []):
            if receipt['id'] == receipt_id:
                receipt['result'] = result
        return result

    def execute_scene(self, job, view, actor, action, choice):
        require(self.scene_ready(), '当前规则缺少场景预设；请检查已激活的规则修订')
        definition = next((x for x in self.scene_definitions() if x['id'] == action), None)
        require(definition and choice in {x['id'] for x in definition['choices']}, '预设行动或做法不存在')
        if 'sceneContext' not in job.record:
            require(actor and actor['numbers']['location'] == definition['location'], '只能执行当前地点的预设行动')
            job.record['sceneContext'] = {'actor': actor['instanceId'], 'action': action, 'choice': choice,
                                        'location': definition['location']}
            self.save()
        context = job.record['sceneContext']
        require(context['action'] == action and context['choice'] == choice, '原行动内容不可更改')
        require(view['role'] == 'kp', '场景结算必须由已经登录的主持执行端运行')
        authority = job.client
        privileged = authority.request('/view')
        require(privileged['role'] == 'kp', '场景执行服务没有主持权限')
        actual = privileged['entities'].get(context['actor'])
        require(actual and (view['role'] == 'kp' or actual['owner'] == view['accountId']), '角色归属已改变')
        self.state['scenePending'] = job.record['requestKey']
        self.save()
        # Shared stock updates and character effects happen in one host transaction.
        # Package publication is resumable through these exact persisted envelopes.
        work = Job(self, authority, job.record)
        if 'scene-act' not in job.record['steps']:
            work.sync_numbers('scene-sync', privileged['entities'][self.state['sceneId']], scenes.package_numbers(self.state))
        world = next(iter(self.entities(privileged, 'sv.world')))
        try:
            result = work.invoke('scene-act', 'sv.scene.resolve', actor=context['actor'], scene=self.state['sceneId'],
                                 world=world['instanceId'], action=action, choice=choice)
        except HostError as error:
            if error.response.get('status') == 'rejected':
                self.state.pop('scenePending', None)
                self.save()
            raise
        scenes.apply_numbers(self.state, result['sceneState'])
        for door in result['doors']:
            self.state['doors'][door['edge']] = door['status']
        public = copy.deepcopy(result['public'])
        for field in ('narrative', 'checks', 'rolls', 'stateChanges', 'clues'):
            if public.get(field) == {}:
                public[field] = []
        existing = {c['id'] for c in public['clues']}
        executed_revision = job.record['steps']['scene-act']['envelope']['payload']['rulesetRevision']
        executed = self.state['ruleRevisions'].get(executed_revision, {})
        public['clues'].extend(c for c in scene_knowledge.outcome_clues(
                               executed.get('data', {}).get('scene-actions.json', {}), action, choice, public,
                               executed.get('sources', {}).get('scene.lua'))
                               if c['id'] not in existing)
        owner = actual['owner']
        discovery = self.state['discoveries'].setdefault(owner, {})
        for clue in public['clues']:
            discovery[clue['id']] = clue
        after_scene = authority.request('/view')
        MapVisibility(self).discover_scene(owner, action, choice, public, after_scene)
        for index in result['reveals']:
            key = str(index)
            if key not in self.state['published']:
                place = self.state['locations'][key]
                entity = next(x for x in self.entities(privileged, 'sv.location') if x['numbers']['index'] == index)
                work.command('scene-reveal-' + key, 'entity.update', {'id': entity['instanceId'], 'visibility': 'public'})
                self.state['published'][key] = {k: copy.deepcopy(place[k]) for k in ('index', 'name', 'description', 'exits', 'features')}
                self.state['published'][key]['clues'] = []
                public['stateChanges'].append({'key': 'reveal' + key, 'label': '已知地点', 'before': '尚未揭示', 'after': place['name']})
        session = next(iter(self.entities(after_scene, 'sv.session')))
        work.sync_numbers('scene-doors', session, self.public_door_numbers())
        # Knowledge preview reads the on-disk package. Persist discoveries even
        # when there was no door update to save them as part of a command step.
        self.save()
        # Package transaction effects are disclosed explicitly by its KP executor.
        # This records current evidence now, never reconstructs a past snapshot.
        revealed=set(result['reveals'])|{actual['numbers']['location']}
        for index in revealed:
            entity=next(x for x in self.entities(privileged,'sv.location') if x['numbers']['index']==index)
            knowledge_client.disclose(work,owner,entity['instanceId'],'scene',key='scene-knowledge-'+str(index),reason='已执行场景行动向本人披露结果')
        public['status'] = 'completed'
        public['message'] = public['title'] + '：' + {'success': '已完成', 'failure': '已结算后果', 'blocked': '条件不满足'}[public['outcome']]
        return public

    def public_door_numbers(self, extra=None):
        visible = set(self.state['published'])
        if extra is not None:
            visible.add(str(extra))
        return {'door' + edge.replace('-', '_'): int(status == 'open' and all(x in visible for x in edge.split('-')))
                for edge, status in self.state['doors'].items()}

    def queue_request(self, view, character, request_id, kind, args, text, reason):
        key = view['accountId'] + ':' + request_id
        self.state['requests'][key] = {'id': key, 'account': view['accountId'], 'actor': character['instanceId'],
            'kind': kind, 'args': copy.deepcopy(args), 'text': text, 'status': 'pending', 'reason': reason,
            'location': character['numbers']['location'], 'time': time.time()}
        return {'message': '已请求 KP 裁决；尚未结算', 'requestId': key, 'status': 'pending', 'reason': reason}

    def finish_auto_travel(self, job):
        saved = job.record['autoTravel']
        if 'auto-travel' not in job.record['steps'] and not self.passable(saved['location'], saved['args']['destination']):
            action_errors.blocked('DOOR_CLOSED')
        result = job.invoke('auto-travel', 'sv.travel.auto', actor=saved['actor'], destination=saved['destinationId'])
        self.state['requests'][saved['id']] = {k: copy.deepcopy(v) for k, v in saved.items() if k != 'destinationId'}
        self.state['requests'][saved['id']].update(status='automatic', result=result, reason='已公开相邻地点且通路开启')
        return {'message': '自动裁决完成：已到达地点 ' + str(result['location']), 'requestId': saved['id'], 'status': 'automatic', **result}

    def sync_automation(self, job, session, enabled=None):
        numbers = {'autoResolve': int(enabled) if enabled is not None else session['numbers'].get('autoResolve', 1)}
        numbers.update(self.public_door_numbers())
        job.command('auto-session', 'entity.update', {'id': session['instanceId'], 'numbers': numbers})

    def validate_bundle(self, content):
        require(isinstance(content, dict) and isinstance(content.get('sources'), dict) and
                isinstance(content.get('data'), dict), '需要 sources 和 data 的配置文件')
        require(1 <= len(content['sources']) <= 64 and all(isinstance(k, str) and isinstance(v, str)
                and len(v) <= 50000 for k, v in content['sources'].items()), '规则源码格式不正确')
        data = content['data'].get('game.json', {})
        # Slot identities are save-game schema. Text/rules may change; migrations are separate work.
        require(isinstance(data, dict) and isinstance(data.get('items'), list), '缺少物品资料')
        for key in ('presets', 'rules', 'locations', 'npcs', 'encounters', 'sourceStatus'):
            require(key in data, '缺少资料字段：' + key)
        try:publication_sync.validate_game(self.game, data)
        except (publication_sync.SyncConflict,KeyError,TypeError) as error:
            raise PackageError('数据引用无效：'+str(error)) from error
        # This manual import path has no AI A/B/C validation of existing actors.
        identity=lambda item:tuple(item.get(k) for k in ('id','kind','slots','uses'))
        require([identity(x) for x in data['items'][:len(self.game['items'])]]==[identity(x) for x in self.game['items']],
                '手动导入不能迁移既有物品槽位和用量；请使用带存量校验的高危提案')
        return copy.deepcopy({'sources': content['sources'], 'data': content['data']})

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state['revision'] += 1
        temporary = self.path.with_suffix('.writing')
        with temporary.open('w', encoding='utf-8') as stream:
            stream.write(json.dumps(self.state, ensure_ascii=False, allow_nan=False))
            stream.flush()
            os.fsync(stream.fileno())
        # Windows indexers can briefly hold the destination without delete sharing.
        # Retry the same already-fsynced bytes; never fall back to a partial overwrite.
        for attempt in range(20):
            try:
                os.replace(temporary, self.path)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(.05)

    def entities(self, view, configuration):
        return [x for x in view['entities'].values() if (x['configurationId'] == configuration or configuration=='sv.npc' and x['configurationId'].startswith('sv.ext.npc.')) and x['lifecycle'] == 'active']

    def own_character(self, view):
        return next((x for x in self.entities(view, 'sv.character') if x['owner'] == view['accountId']), None)

    def public_location(self, entity):
        index = str(entity['numbers']['index'])
        location = self.state['published'].get(index)
        if location is None:
            return None
        return {**copy.deepcopy(location), 'entityId': entity['instanceId']}

    def sync_rules(self, client, view):
        """Recover publication bookkeeping from the authoritative host artifact."""
        revision=view['catalog']['rulesetRevision']
        if not self.state['initialized'] or revision==self.state.get('activeRevision'):return
        previous_game=self.game;previous_revision=self.state.get('activeRevision')
        key='publication-sync:'+revision
        record=self.state['jobs'].setdefault(key,{'steps':{},'requestKey':key})
        work=Job(self,client,record)
        try:
            artifact=client.request('/admin/artifacts/'+revision)['artifact']
            candidate=artifact['data']['game.json']
            merged=publication_sync.projection(self.state,self.game,candidate)
            existing={e['numbers']['index']:e for e in self.entities(view,'sv.location')}
            for place in candidate['locations']:
                step='location-'+str(place['index'])
                if step in record['steps'] or place['index'] not in existing:
                    work.command(step,'entity.create',{'configurationId':'sv.location',
                        'name':place['name'],'owner':view['accountId'],'visibility':'kp','numbers':{'index':place['index']}})
            self.state.update(merged)
            self.state['ruleRevisions'][revision]={'sources':artifact['sources'],'data':artifact['data']}
            self.state['activeRevision']=revision
            self.game=candidate
            self.state['publicationSync']={'status':'completed','revision':revision}
            self.save()
            return True
        except (publication_sync.SyncConflict,HostError,OSError) as error:
            # A host publication is final. Only its package projection is pending;
            # the same durable envelopes recover partially created map instances.
            pending={'status':'conflict' if isinstance(error,publication_sync.SyncConflict) else 'pending',
                'revision':revision,'message':str(error),'hostCommitted':True}
            self.game=previous_game;self.state['activeRevision']=previous_revision
            if self.state.get('publicationSync')!=pending:
                self.state['publicationSync']=pending
                self.save()

    def projection(self, client, preview=None, player_mode=False):
        with self.lock:
            view = client.request('/view')
            is_kp = view['role'] == 'kp'
            if is_kp:
                if self.sync_rules(client,view):view=client.request('/view')
            if preview:
                require(is_kp, '需要主持权限')
            account = preview or view['accountId']
            gm = is_kp and not preview and not player_mode
            characters = self.entities(view, 'sv.character')
            sight = MapVisibility(self)
            sight.sync(view)
            mine = next((x for x in characters if x['owner'] == account), None)
            visible = [x for x in self.entities(view, 'sv.location') if x['visibility'] == 'public']
            locations = [self.public_location(x) for x in visible]
            locations = [x for x in locations if x]
            ids = {x['index'] for x in locations}
            known_places=known_locations(self.state,view['entities'],account)
            for location in locations:
                location['exits'] = [x for x in location['exits'] if x in ids]
                location['doors'] = {str(x): self.state['doors'].get(self.edge(location['index'], x), 'closed') for x in location['exits']}
                known = {c['id'] for c in location['clues']}
                location['clues'].extend(copy.deepcopy(c) for c in self.state['discoveries'].get(account, {}).values()
                                        if c['location'] == location['index'] and c['id'] not in known)
                if not gm and str(location['index']) not in known_places:
                    # Navigation topology remains usable; undiscovered scene contents do not.
                    location.update(name='未探索地点',description='进入或由 KP 揭示后可查看。',features=[],clues=[])
            known_items=[]
            knowledge_status=client.request('/knowledge/capabilities')['status']
            if not gm:
                # A KP preview cannot impersonate another account's knowledge.
                if not is_kp and knowledge_status=='ready':known_items=knowledge_client.records(client)
                locations=knowledge_client.locations(known_items)
            session = next(iter(self.entities(view, 'sv.session')), None)
            if not gm:
                play=next((i['data'] for i in known_items if i['facetId']=='play'),None)
                session={'instanceId':play['entityId'],'numbers':play['numbers']} if play else None
            item_ids = set()
            for character in characters if gm else ([mine] if mine else []):
                item_ids.update(character['numbers'].get('item' + str(i), 0) for i in range(1, 21))
            # Item names and scenario secrets are not supplied as a full player catalog.
            items = {str(i): definition for i, definition in enumerate(self.game['items'], 1) if gm or i in item_ids}
            result = {'accountId': account, 'role': 'kp' if gm else 'player', 'roomStatus': view['status'],
                      'storageScope': hashlib.sha256(os.path.normcase(str(self.path.resolve())).encode('utf-8')).hexdigest(),
                      'knowledge':{'status':knowledge_status,'mode':'required-personal'},
                      'revision': self.state['revision'], 'initialized': self.state['initialized'],
                      'automation': {'enabled': bool(session and session['numbers'].get('autoResolve', 1)), 'ready': self.automation_ready(session)},
                      'sceneAutomation': {'ready': self.scene_ready(), 'executorOnline': any(time.time()-t < 20 for t in self.executor_seen.values())},
                      'autoSceneTasks': [{k: t[k] for k in ('id', 'title', 'status', 'time')} for t in self.state['autoSceneQueue'].values()
                                         if t['status'] != 'completed' and (gm or t['account'] == account)],
                      'sceneActions': [copy.deepcopy(x) for x in self.scene_definitions() if mine and x['location'] == mine['numbers']['location']],
                      'sceneStatus': scenes.public_state(self.state, mine['numbers']['location'], self.game['items']) if mine else {},
                      'character': mine, 'session': session, 'locations': locations, 'items': items,
                      'mapContacts': sight.contacts(account, mine, characters) if not gm else [],
                      'presets': self.game['presets'], 'rules': self.game['rules'],
                      'team': list(self.state['roster'].values()),
                      'generatedCharacter': self.state['generatedCharacters'].get(account),
                      'draft': self.state['drafts'].get(account), 'note': self.state['notes'].get(account, ''),
                      'requests': [x for x in self.state['requests'].values() if gm or x['account'] == account],
                      'recap': self.state['recap'], 'receipts': self.state['receipts'].get(account, [])[-100:],
                      'events': sorted((e for owner, events in self.state['events'].items() if gm or owner == account
                                        for e in events), key=lambda e: e['time'])[-200:],
                      'channels': {} if preview else {**view['chatChannels'], **ScopedChat(self).channels(view if gm else {**view, 'role': 'player'})},
                      'canManage': is_kp and not preview,
                      'preview': bool(preview), 'previewKind': '包侧公开投影' if preview else None}
            if gm:
                result['knowledgeGrants']=client.request('/knowledge/grants/query',{'policyId':knowledge_client.POLICY,'status':'active','limit':50})
                for grant in result['knowledgeGrants']['items']:
                    grant['label']=view['entities'].get(grant['resource']['id'],{}).get('name','已授权资料')
                result['legacyKnowledge']=copy.deepcopy(self.state.get('locationKnowledge',{}))
                result.update(roomId=view['roomId'], characters=characters, drafts=self.state['drafts'],
                              allLocations=self.state['locations'], npcs=self.entities(view, 'sv.npc'),
                              world=next(iter(self.entities(view, 'sv.world')), None),
                              members=client.request('/chat/members')['items'],
                              recapDraft=self.state['recapDraft'], recapPrivate=self.state['recapPrivate'],
                              sourceStatus=self.game['sourceStatus'], encounters=self.state['encounters'], loot=self.state['loot'],
                              npcTemplates=self.game['npcs'], doors=self.state['doors'], catalog=view['catalog'],
                              ruleRevisions=list(self.state['ruleRevisions']), published=self.state['published'],
                              publicationSync=self.state.get('publicationSync'))
                result['keeperWaits'] = [copy.deepcopy(w) for w in view.get('waits', {}).values() if w['role'] == 'kp' and w['status'] == 'waiting']
                result['keeperFlows'] = [copy.deepcopy(f) for f in view.get('flows', {}).values() if f['status'] == 'needs_attention']
                result['sceneDefinitions'] = self.scene_definitions()
                result['sceneKnowledge'] = scene_knowledge.catalog(self.scene_content())
                result['scenePlayerDefinitions'] = scene_knowledge.definitions(self.scene_content())
                result['mapNpcCatalog'] = list(sight.catalog().values())
                result['actorDiscoveries'] = copy.deepcopy(self.state.get('actorDiscoveries', {}))
            elif player_mode:
                personal_ops = {'draft', 'draft.roll', 'note', 'request', 'ready', 'check', 'inventory', 'chat', 'share.receipt', 'scene.action'}
                result['receipts'] = [r for r in result['receipts'] if r['operation'] in personal_ops]
            if not gm:
                # Package shared current lore cannot bypass the same personal
                # disclosure boundary used by the AI and normal known-data UI.
                result['mapContacts']=[]
                result['recap']=''
                result['sceneStatus']={}
                current_place=next((p for p in locations if mine and p['index']==mine['numbers']['location'] and p.get('known')),None)
                result['sceneActions']=copy.deepcopy(current_place.get('actions',[])) if current_place else []
                result['knowledgeRecords']=[{'label':i['label'],'mode':i['mode'],'observedAt':i['observedAt'],'ref':i['ref']}
                    for i in known_items if i['facetId']!='sheet']
            return result

    def action(self, client, body):
        require(isinstance(body, dict) and set(body) == {'id', 'operation', 'args'}, '行动格式不正确')
        require(isinstance(body['id'], str) and re.fullmatch(r'[a-zA-Z0-9-]{8,80}', body['id']), '行动编号不正确')
        require(isinstance(body['args'], dict), '行动参数不正确')
        with self.lock:
            view = client.request('/view')
            if view['role']=='kp':self.sync_rules(client,view)
            account = view['accountId']
            key = account + ':' + body['id']
            require(not self.state.get('scenePending') or self.state['scenePending'] == key or
                    body['operation'] in {'chat', 'note', 'draft', 'draft.roll', 'recap', 'share.receipt'},
                    '有场景结算尚待恢复，请发起者恢复原行动后再继续')
            fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            record = self.state['jobs'].get(key)
            if record:
                require(record['fingerprint'] == fingerprint, '同一行动编号不可更改内容')
                if record.get('failureResponse'):
                    raise HostError(record['failureResponse'])
                if record.get('done'):
                    return record['result']
            else:
                record = {'fingerprint': fingerprint, 'steps': {}, 'created': time.time()}
                self.state['jobs'][key] = record
                self.save()
            job = Job(self, client, record)
            record['requestKey'] = key
            if 'sourceMessages' in body['args'] and 'sourceMessages' not in record:
                sources=body['args']['sourceMessages']
                require(isinstance(sources,list) and len(sources)<=12,'聊天来源数量无效')
                checked=[]
                for ref in sources:
                    require(isinstance(ref,dict) and set(ref)=={'channelId','messageId','revision','sequence'} and
                            type(ref['sequence']) is int and 0<ref['sequence']<2**53,'聊天来源格式无效')
                    page=ScopedChat(self).history(client,{'channelId':ref['channelId'],'before':ref['sequence']+1,'limit':1})
                    message=next((m for m in page['items'] if m['messageId']==ref['messageId']),None)
                    require(message and not message['deleted'] and str(message['revision'])==str(ref['revision']),'聊天来源已变化')
                    checked.append(copy.deepcopy(ref))
                record['sourceMessages']=checked
            feedback_ops = {'session.start', 'ready', 'check', 'inventory', 'request', 'resolve', 'world', 'actor.update', 'scene.action', 'scene.autorun',
                            'rest', 'grant', 'damage', 'remove', 'stock.take', 'approve',
                            'automation.configure', 'room', 'location.publish'}
            feedback = body['operation'] in feedback_ops
            if feedback and 'before' not in record:
                record['before'] = {x['owner']: {'name': x['name'], 'numbers': x['numbers']}
                                    for x in self.entities(view, 'sv.character')}
                self.save()
            # Once a command reaches the host its envelope remains durable. Pure package
            # changes are only exposed after their action completes under this lock.
            if 'executed' not in record:
                try:
                    record['executed'] = self.execute(job, view, body['operation'], {k:v for k,v in body['args'].items() if k!='sourceMessages'}, body['id'])
                except (HostError, PackageError) as error:
                    if isinstance(error, HostError) and error.response.get('status') != 'rejected':
                        raise
                    detail = self.failure_detail(error, record)
                    detail.update(actionId=body['id'], operation=body['operation'])
                    code = error.response.get('code', 'ACTION_BLOCKED') if isinstance(error, HostError) else str(error)
                    response = {'code': code, 'status': 'rejected', 'failure': detail}
                    record['failureResponse'] = response
                    request = self.state['requests'].get(body['args'].get('requestId')) if body['operation']=='resolve' else None
                    audience = {account}
                    if request:
                        request['failure'] = detail
                        audience.add(request['account'])
                    for owner in audience:
                        events = self.state['events'].setdefault(owner, [])
                        events.append({'id': key, 'account': owner, 'operation': body['operation'], 'title': {'check':'检定未完成','inventory':'物品操作未完成','resolve':'裁决执行未完成','request':'行动申请未完成','scene.action':'场景行动未完成'}.get(body['operation'],'行动未完成'),
                            'status': 'blocked', 'mode': 'kp' if view['role']=='kp' else 'auto', 'time': time.time(),
                            'result': {'failure': detail}, 'changes': [], 'mechanical': False, 'receiptId': None})
                        del events[:-200]
                    self.save()
                    raise HostError(response) from error
                result=record['executed']
                if isinstance(result,dict) and result.get('requestId') in self.state['requests'] and record.get('sourceMessages'):
                    self.state['requests'][result['requestId']]['sourceMessageRefs']=record['sourceMessages']
                self.save()
            result = record['executed']
            after_view = client.request('/view') if feedback or view['role'] == 'kp' else None
            if after_view is not None:
                MapVisibility(self).sync(after_view)
            if feedback:
                self.record_feedback(view, after_view, body, record, result)
            record.update(done=True, result=result)
            if body['operation'] == 'scene.autorun':
                self.state['autoSceneQueue'][body['args']['jobId']]['status'] = 'completed'
            if self.state.get('scenePending') == key:
                self.state.pop('scenePending')
            command_ids = [step['envelope']['payload']['commandId'] for step in record['steps'].values()]
            self.state['receipts'].setdefault(account, []).append({'id': body['id'], 'operation': body['operation'], 'result': result,
                                                                 'commandIds': command_ids, 'time': time.time()})
            self.save()
            return result

    def failure_detail(self, error, record):
        if isinstance(error, HostError):
            detail = copy.deepcopy(error.response.get('failure') or action_errors.failure(error.response.get('code', 'UNKNOWN')))
        else:
            detail = {'code': 'PACKAGE_CONDITION', 'reason': str(error),
                      'nextStep': 'PL：按上述条件调整后重新提交；若需修改场景或他人资源，请申请 KP 裁决。KP：在对应管理页处理条件后重新批准。'}
        detail['partial'] = any('result' in step for key,step in record['steps'].items() if key != 'scene-sync')
        if detail['partial']:
            detail['nextStep'] += ' 此流程已有步骤完成：请先由 KP 核对原行动和回执，不要重复发起整个流程。'
        return detail

    def explain_preconditions(self, job, rule, inputs):
        if rule not in {'sv.check','sv.inventory','sv.ready','sv.adjudicate','sv.scene.resolve','sv.travel.auto','sv.grant','sv.remove','sv.transfer','sv.rest'}:
            return
        # Custom/imported rules may define different conditions. Never reject
        # them using assumptions about this pack's shipped rule implementation.
        sources = self.state['ruleRevisions'].get(self.state.get('activeRevision'), {}).get('sources')
        if sources != self.diagnostic_sources:
            return
        view = job.client.request('/view') if job.record['steps'] else getattr(job, 'view', None)
        if view is None: view = job.client.request('/view')
        session = next(iter(self.entities(view, 'sv.session')), getattr(job, 'session', None))
        action_errors.check(rule, inputs, view, self.game, session)

    def record_feedback(self, before_view, after_view, body, record, result):
        """Deliver only a character owner's changes; never copy a KP view into a PL event."""
        op, args, caller = body['operation'], body['args'], before_view['accountId']
        request_id = args.get('requestId') if op == 'resolve' else result.get('requestId') if isinstance(result, dict) else None
        request = self.state['requests'].get(request_id, {})
        if op == 'scene.autorun':
            task = self.state['autoSceneQueue'][args['jobId']]
            request = {'id': task['id'], 'account': task['account'], 'kind': 'scene', 'status': 'automatic',
                       'text': task['title'], 'reason': '按玩家选定的预设做法自动结算', 'result': result, 'time': task['time']}
            request_id = task['id']
        after = {x['owner']: {'name': x['name'], 'numbers': x['numbers']}
                 for x in self.entities(after_view, 'sv.character')}
        before = record['before']
        audience = {caller}
        audience.update(owner for owner in after if after[owner] != before.get(owner))
        if request:
            audience.add(request['account'])
        if op in {'session.start', 'world', 'automation.configure', 'room', 'location.publish'}:
            audience.update(after)
        titles = {'session.start': '房间开场', 'ready': '准备状态', 'check': '属性检定', 'inventory': '物品操作', 'request': '行动申请',
                  'scene.action': '场景行动',
                  'scene.autorun': '场景行动自动结果',
                  'resolve': 'KP 裁决回复', 'world': '探索进度', 'actor.update': '主持调整数值', 'rest': '休息恢复',
                  'grant': '获得物品', 'damage': '伤害结算', 'remove': '移除物品', 'stock.take': '领取物品',
                  'approve': '角色审核', 'automation.configure': '自动裁决设置', 'room': '房间状态', 'location.publish': '地点与线索发布'}
        kind = request.get('kind', op)
        title = titles.get(kind, {'travel': '地点移动', 'transfer': '物品转交', 'review': '事件复核',
                                 'free': '自由行动', 'interact': '场景互动'}.get(kind, titles[op]))
        for owner in audience:
            status = request.get('status', 'completed')
            if status == 'automatic':
                status = 'completed'
            if isinstance(result, dict) and result.get('status') == 'processing':
                status = 'processing'
            own_result = result if owner == caller else request.get('result', {}) if owner == request.get('account') else {}
            if op == 'damage' and owner != caller:
                target = after_view['entities'].get(args.get('actor'), {})
                if target.get('configurationId') == 'sv.character' and target.get('owner') == owner:
                    own_result = {key: copy.deepcopy(result[key]) for key in
                        ('damage', 'hp', 'overflow', 'attribute', 'remaining', 'save', 'critical', 'dead') if key in result}
            if owner != caller and op in {'session.start', 'world', 'automation.configure', 'room', 'location.publish'}:
                session = next(iter(self.entities(after_view, 'sv.session')), None)
                message = {'session.start': '房间已开场', 'world': '探索进度已更新 · 第 ' + str(session['numbers']['round']) + ' 回合',
                           'automation.configure': '自动裁决' + ('已开启' if session['numbers'].get('autoResolve', 1) else '已关闭'),
                           'room': '房间' + ('已暂停' if after_view['status'] == 'paused' else '已恢复'),
                           'location.publish': '主持发布了地点与线索，请查看已知地图和线索面板'}[op]
                own_result = {'message': message}
            if isinstance(own_result, dict) and 'result' in own_result and own_result['result']:
                own_result = own_result['result']
            event = {'id': caller + ':' + body['id'], 'account': owner, 'operation': op,
                     'title': title, 'text': request.get('text', '') if owner in {caller, request.get('account')} else '',
                     'status': status, 'mode': 'kp' if request.get('status') == 'pending' or op == 'resolve' or before_view['role'] == 'kp' else 'auto',
                     'requestId': request_id, 'receiptId': body['id'] if owner == caller else None,
                     'reason': request.get('reason', '') if owner in {caller, request.get('account')} else '',
                     'result': own_result, 'changes': self.character_changes(before.get(owner), after.get(owner)),
                     'time': time.time(), 'submittedAt': request.get('time', record['created'])}
            # Narrative approval records an answer; it does not imply a rule was run.
            event['mechanical'] = bool(record['steps']) and (not request or bool(request.get('resolution')) or kind in {'check', 'inventory', 'travel', 'transfer'})
            event['sourceMessageRefs']=copy.deepcopy(request.get('sourceMessageRefs',record.get('sourceMessages',[])))
            if op=='resolve':
                event['decider']=caller
                event['decidedAt']=time.time()
            if isinstance(own_result, dict) and own_result.get('sceneAction'):
                event['title'] = own_result['title']
                event['mechanical'] = own_result['outcome'] not in {'blocked', 'queued'}
            if op == 'scene.autorun':
                event['mode'] = 'auto'
                if owner == request['account']:
                    event['id'] = request['id']
                    event['receiptId'] = request['id'].split(':', 1)[1]
            events = self.state['events'].setdefault(owner, [])
            if op == 'scene.autorun' and owner == request['account']:
                # Complete the original submission card instead of leaving a stale
                # "waiting" event alongside its eventual result.
                events[:] = [e for e in events if e['id'] != event['id']]
            if not any(e['id'] == event['id'] for e in events):
                events.append(event)
                del events[:-200]

    def character_changes(self, previous, current):
        if not current:
            return []
        before, after = (previous or {}).get('numbers', {}), current['numbers']
        labels = {'hp': 'HP', 'maxHp': 'HP 上限', 'str': 'STR', 'dex': 'DEX', 'wil': 'WIL',
                  'strMax': 'STR 上限', 'dexMax': 'DEX 上限', 'wilMax': 'WIL 上限', 'armor': '基础护甲',
                  'pips': '钱币', 'xp': 'XP', 'level': '等级', 'grit': 'Grit', 'location': '所在地点',
                  'ready': '准备', 'incapacitated': '失能', 'litSlot': '光源槽位', 'conditionPending': '待整理状态'}
        changes = []
        def add(key, label, old, new):
            if old != new:
                changes.append({'key': key, 'label': label, 'before': old, 'after': new})
        for key, label in labels.items():
            old, new = before.get(key, 0), after.get(key, 0)
            if key == 'location':
                name = lambda value: self.state['published'].get(str(value), {}).get('name', '未公开地点' if value else '尚未入场')
                old, new = name(old), name(new)
            add(key, label, old, new)
        for slot in range(1, 21):
            def item(numbers):
                index = numbers.get('item' + str(slot), 0)
                if not index:
                    return '空'
                definition = self.game['items'][index - 1]
                value = definition['name']
                if definition['uses']:
                    value += ' · 用量 ' + str(numbers.get('uses' + str(slot), 0))
                return value
            add('slot' + str(slot), '槽位 ' + str(slot), item(before), item(after))
            add('ticks' + str(slot), '槽位 ' + str(slot) + '燃烧进度', before.get('ticks' + str(slot), 0), after.get('ticks' + str(slot), 0))
        return changes

    def execute(self, job, view, op, args, request_id):
        account = view['accountId']
        gm = view['role'] == 'kp'
        character = self.own_character(view)
        session = next(iter(self.entities(view, 'sv.session')), None)
        if not gm and session is None:
            play=next((i['data'] for i in knowledge_client.records(job.client) if i['facetId']=='play'),None)
            session={'instanceId':play['entityId'],'numbers':play['numbers']} if play else None
        world = next(iter(self.entities(view, 'sv.world')), None)
        job.view, job.session = view, session
        player_ops = {'draft', 'draft.roll', 'note', 'request', 'ready', 'check', 'inventory', 'chat', 'share.receipt', 'scene.action'}
        require(op in player_ops or gm, '需要主持权限')
        if op == 'initialize':
            return self.initialize(job)
        if op == 'session.start':
            require(not args, '开场不接受额外参数')
            require(view['status'] in {'active', 'paused'}, '归档房间不能开场')
            if session and session['numbers']['phase'] == 1 and view['status'] == 'active':
                return {'message': '房间已开场', 'phase': 1, 'round': session['numbers']['round']}
            require(not session or session['numbers']['phase'] != 2, '本场已结束，请使用新的房间槽位')
            if view['status'] == 'paused':
                job.command('opening-resume', 'room.status', {'status': 'active'})
            if not self.state['initialized']:
                self.initialize(job)
            current = job.client.request('/view')
            session = next(iter(self.entities(current, 'sv.session')))
            # Binding only restores sheet/play subscriptions; old scene observations stay sealed.
            self.execute(job, current, 'knowledge.enable', {}, request_id)
            if session['numbers']['phase'] != 1:
                job.invoke('opening-start', 'sv.world', actor=session['instanceId'], operation='start', value=0)
            return {'message': '房间已开场', 'phase': 1, 'round': session['numbers']['round']}
        require(self.state['initialized'], '请主持先安装配置包')
        if op == 'knowledge.enable':
            knowledge_client.bind(job)
            for entity in view['entities'].values():
                if entity['configurationId'] in ('sv.character','sv.draft') and entity['lifecycle']=='active':
                    knowledge_client.disclose(job,entity['owner'],entity['instanceId'],'sheet',live=True,
                        key='sheet-'+entity['instanceId'],reason='KP 明确持续告知本人角色状态')
            for m in job.client.request('/chat/members')['items']:
                if m['role']=='player' and session:
                    knowledge_client.disclose(job,m['accountId'],session['instanceId'],'play',live=True,key='play-'+m['accountId'])
            return {'message':'个人知识服务已启用；旧地点记录尚未披露，请逐项选择现在揭示'}
        require(view['status'] != 'archived', '房间已经归档，只能阅读')
        require(view['status'] == 'active' or op in {'note', 'draft', 'draft.roll', 'room', 'recap', 'backup', 'chat', 'automation.configure', 'request'}, '房间暂停或已归档')
        if op == 'location.reveal':
            require({'index','accounts'} <= set(args) <= {'index','accounts','knowledge'} and str(args['index']) in self.state['published'], '地点尚未发布或参数无效')
            owners={a['owner'] for a in self.entities(view,'sv.character')}
            require(isinstance(args['accounts'],list) and args['accounts'] and all(a in owners for a in args['accounts']), '受众无效')
            facts = {c['id']:c for c in scene_knowledge.catalog(self.scene_content()) if c['location']==args['index']}
            selected = args.get('knowledge',[])
            require(isinstance(selected,list) and all(isinstance(k,str) and k in facts for k in selected), '揭示内容无效')
            for owner in args['accounts']:
                # Explicit KP disclosure is a trusted source change, then an
                # idempotent host observation. It is never performed on reads.
                if selected:
                    self.state['discoveries'].setdefault(owner,{}).update({k:copy.deepcopy(facts[k]) for k in selected})
                    self.save()
                entity=next(x for x in self.entities(view,'sv.location') if x['numbers']['index']==args['index'])
                knowledge_client.disclose(job,owner,entity['instanceId'],'scene',key='scene-'+owner)
            return {'message':'已向指定玩家揭示地点'}
        if op == 'knowledge.revoke':
            require(set(args)=={'grantId','revision'},'撤回参数无效')
            job.command('revoke','knowledge.revoke',{'grantId':args['grantId'],'expectedRevision':args['revision'],'reason':'KP 撤回个人知识授权'})
            return {'message':'知识授权已撤回'}
        if op == 'knowledge.import-current':
            require(set(args)=={'items'} and isinstance(args['items'],list) and 0<len(args['items'])<=40,'请选择要现在揭示的旧地点记录')
            for i,item in enumerate(args['items']):
                require(set(item)=={'account','index'} and str(item['index']) in self.state.get('locationKnowledge',{}).get(item['account'],[]), '旧地点记录不匹配')
                require(str(item['index']) in self.state['published'],'请先发布所选地点的允许披露内容')
                entity=next(x for x in self.entities(view,'sv.location') if x['numbers']['index']==item['index'])
                knowledge_client.disclose(job,item['account'],entity['instanceId'],'scene',key='import-current-'+str(i),
                    reason='KP 选择旧地点记录并现在揭示当前内容；不代表历史观察')
            return {'message':'所选地点已按当前内容揭示，没有补造历史观察'}
        if op == 'actor.reveal':
            require(set(args) == {'id', 'accounts', 'visible'} and isinstance(args['visible'], bool), '揭示参数无效')
            sight = MapVisibility(self)
            sight.sync(view)
            ids = set(sight.catalog()) | {a['instanceId'] for a in self.entities(view, 'sv.character')}
            owners = {a['owner'] for a in self.entities(view, 'sv.character')}
            require(args['id'] in ids and isinstance(args['accounts'], list) and len(args['accounts']) > 0
                    and all(isinstance(a, str) and a in owners for a in args['accounts']), '角色或受众无效')
            for account_id in args['accounts']:
                if args['id'] in view['entities']:
                    if args['visible']:
                        knowledge_client.disclose(job,account_id,args['id'],'identity',key='contact-'+account_id)
                    else:knowledge_client.revoke_identity(job,account_id,args['id'])
                self.state['actorDiscoveries'].setdefault(account_id, {})[args['id']] = args['visible']
            return {'message': '角色发现状态已更新'}
        if op == 'scene.autorun':
            require(set(args) == {'jobId'}, '自动行动参数不正确')
            task = self.state['autoSceneQueue'].get(args['jobId'])
            require(task and request_id == task['commandId'], '自动行动编号不正确')
            return self.run_scene_queue(job, view, args['jobId'])
        if op == 'scene.action':
            require(set(args) <= {'action', 'choice', 'manual'} and {'action', 'choice'} <= set(args), '场景行动参数不正确')
            require(all(isinstance(args[k],str) and 0 < len(args[k]) <= 100 for k in ('action','choice')), '场景行动参数不正确')
            require(isinstance(args.get('manual', False), bool), '裁决方式无效')
            if not character: action_errors.blocked('NOT_APPROVED')
            available = self.scene_definitions()
            if not gm:
                places = knowledge_client.locations(knowledge_client.records(job.client))
                current = next((p for p in places if p['index']==character['numbers']['location'] and p.get('known')),None)
                available = current.get('actions',[]) if current else []
            definition = next((x for x in available if x['id'] == args['action']), None)
            require(definition and args['choice'] in {c['id'] for c in definition['choices']},
                    '此做法不在本人已知行动中，请先探索或向 KP 请求说明' if not gm else '预设行动不存在')
            if character['numbers']['ready'] != 1: action_errors.blocked('NOT_READY')
            if not session or session['numbers']['phase'] != 1: action_errors.blocked('NOT_STARTED')
            require('sceneContext' in job.record or character['numbers']['location'] == definition['location'], '只能执行当前地点的预设行动')
            if args.get('manual') or session['numbers'].get('autoResolve', 1) == 0:
                return self.queue_request(view, character, request_id, 'scene', {'action': args['action'], 'choice': args['choice'], 'menuVersion':scene_knowledge.VERSION},
                    definition['label'], '玩家主动申请' if args.get('manual') else '主持已关闭自动裁决')
            return self.queue_scene(view, character, job, definition, args['choice'])
        if op == 'automation.configure':
            require(isinstance(args.get('enabled'), bool) and set(args) == {'enabled'}, '自动裁决设置无效')
            require(self.automation_ready(session), '当前规则不支持自动裁决')
            self.sync_automation(job, session, args['enabled'])
            return {'message': '自动裁决已开启' if args['enabled'] else '自动裁决已关闭；行动交由 KP 裁决'}
        if op == 'chat':
            require(args.get('operation') in {'chat.direct.open', 'chat.channel.create', 'chat.channel.update', 'chat.message.send',
                'chat.message.share', 'chat.message.edit', 'chat.message.retract', 'chat.read'}, '聊天操作不支持')
            if str(args.get('input', {}).get('channelId', '')).startswith('sv-'):
                return ScopedChat(self).action(view, args['operation'], args.get('input', {}), account+'-'+request_id)
            return job.command('chat', args['operation'], args.get('input', {}))
        if op == 'share.receipt':
            receipt = next((x for x in self.state['receipts'].get(account, []) if x['id'] == args.get('receiptId')), None)
            require(receipt and receipt['operation'] in {'check', 'inventory', 'ready'}, '这项回执不可分享')
            result = receipt['result']
            require(result.get('status') != 'pending', '待裁决的行动尚未结算，不能分享结果')
            if receipt['operation'] == 'check':
                summary = f"{result['attribute'].upper()} {result['rolled']}/{result['target']} · " + ('成功' if result['passed'] else '失败')
            elif receipt['operation'] == 'ready':
                summary = '已准备' if result.get('ready') else '取消准备'
            else:
                summary = '物品操作 ' + result['operation'] + ' · 剩余用量 ' + str(result.get('uses', '—'))
            message = {'channelId': args['channelId'], 'text': '【树桩镇回执摘要】' + account + ' · ' + summary + '\n（包侧根据本人回执生成的文字摘要）'}
            if str(args['channelId']).startswith('sv-'):
                return ScopedChat(self).action(view, 'chat.message.send', message, account+'-'+request_id)
            return job.command('share', 'chat.message.send', message)
        if op == 'draft.roll':
            require(not character, '已有角色')
            # A dedicated owner entity provides an authenticated, persisted random draft.
            generated = next((x for x in self.entities(view, 'sv.draft') if x['owner'] == account), None)
            if generated is None and gm:
                entity = job.command('own-draft', 'entity.create', {'configurationId': 'sv.draft', 'name': '建角骰盘', 'owner': account, 'visibility': 'owner'})
                generated = {'instanceId': entity}
            require(generated is not None, '请主持先开放随机建角')
            values = job.invoke('roll', 'sv.create', actor=generated['instanceId'])
            self.state['generatedCharacters'][account] = values
            return values
        if op == 'draft':
            require(not character, '已有角色，请主持修改现有角色')
            name = str(args.get('name', '')).strip()
            require(1 <= len(name) <= 40, '角色名称应为1至40字')
            preset = next((x for x in self.game['presets'] if x['id'] == args.get('preset')), None)
            if args.get('preset') == 'random':
                generated = self.state['generatedCharacters'].get(account)
                require(generated is not None, '请先生成属性')
                preset = {**copy.deepcopy(self.game['presets'][0]), **generated, 'description': '随机建角；背景与起始物品由主持按 HP/钱币表核定'}
                swap = args.get('swap', '')
                require(swap in {'', 'str-dex', 'str-wil', 'dex-wil'}, '交换属性无效')
                if swap:
                    a, b = swap.split('-')
                    preset[a], preset[b] = preset[b], preset[a]
            require(preset is not None, '请选择预设或随机草稿')
            self.state['drafts'][account] = {**copy.deepcopy(preset), 'name': name, 'account': account, 'status': 'submitted', 'requestId': request_id, 'time': time.time()}
            return {'message': '角色草稿已提交主持审核'}
        if op == 'note':
            text = args.get('text', '')
            require(isinstance(text, str) and len(text) <= 8000, '手记最多8000字')
            self.state['notes'][account] = text
            return {'message': '手记已保存'}
        if op == 'host-flow':
            require(gm, '需要主持权限')
            require(args.get('operation') in {'flow.respond', 'flow.retry', 'flow.cancel'} and isinstance(args.get('input'), dict), '流程裁决格式不正确')
            return job.command('host-flow', args['operation'], args['input'])
        if op == 'approve':
            return self.approve(job, view, args)
        if op == 'request':
            require(character and character['numbers']['approved'] == 1, '请先完成角色审核')
            if 'autoTravel' in job.record:
                return self.finish_auto_travel(job)
            kind = args.get('kind', 'free')
            require(kind in {'travel', 'free', 'transfer', 'interact', 'review', 'check', 'inventory'}, '请求类型不支持')
            if kind != 'review':
                if view['status'] != 'active': action_errors.blocked('ROOM_PAUSED')
                if not session or session['numbers']['phase'] != 1: action_errors.blocked('NOT_STARTED')
                if character['numbers']['ready'] != 1: action_errors.blocked('NOT_READY')
            text = str(args.get('text', '')).strip()
            require(len(text) <= 2000, '请求文字过长')
            manual = args.get('manual', False)
            require(isinstance(manual, bool), '裁决方式无效')
            automatic = self.automation_ready(session) and session['numbers'].get('autoResolve', 1) == 1 and not manual
            if kind == 'review':
                require(bool(text), '请描述需要裁决的事件')
                receipt_id = args.get('receiptId')
                if receipt_id:
                    require(any(x['id'] == receipt_id for x in self.state['receipts'].get(account, [])), '只能复核本人的行动回执')
                return self.queue_request(view, character, request_id, kind, {'receiptId': receipt_id}, text, '玩家主动申请；复核不重复执行原行动')
            if kind in {'check', 'inventory'}:
                params = args.get('input', {})
                allowed = {'check': {'attribute', 'mode'}, 'inventory': {'operation', 'slot', 'value'}}[kind]
                require(isinstance(params, dict) and set(params) == allowed, '行动参数不正确')
                return self.queue_request(view, character, request_id, kind, params, text or ('请求裁决：' + kind), '玩家主动申请')
            if kind == 'travel':
                destination = args.get('destination')
                known=knowledge_client.locations(knowledge_client.records(job.client)) if not gm else [self.public_location(x) for x in self.entities(view,'sv.location') if self.public_location(x)]
                current=next((p for p in known if p['index']==character['numbers']['location']),None)
                target=next((p for p in known if p['index']==destination),None)
                require(current and destination in current['exits'] and target and target.get('entityId'), '本人已知记录没有该通路，请向 KP 请求说明')
                if automatic:
                    job.record['autoTravel'] = {'id': account + ':' + request_id, 'account': account, 'actor': character['instanceId'],
                        'kind': kind, 'args': {'destination': destination}, 'text': text or '移动到地点 ' + str(destination),
                        'location': current['index'], 'destinationId': target['entityId'], 'time': time.time()}
                    self.save()
                    return self.finish_auto_travel(job)
            if kind == 'transfer':
                target = self.state['roster'].get(args.get('targetAccount'))
                require(target and target['account'] != account, '请选择队友')
                args = {**args, 'target': target['id']}
            reason = '玩家主动申请' if manual else '自动裁决已关闭' if not automatic else '事件需要主持判断或涉及其他角色资源'
            return self.queue_request(view, character, request_id, kind, args, text, reason)
        if op in {'ready', 'check', 'inventory'}:
            require(character is not None, '未分配角色')
            allowed = {'ready': {'ready'}, 'check': {'attribute', 'mode'}, 'inventory': {'operation', 'slot', 'value'}}[op]
            require(set(args) == allowed, '参数与行动不符')
            if op in {'check', 'inventory'} and session['numbers'].get('autoResolve', 1) == 0:
                return self.queue_request(view, character, request_id, op, args, '请求裁决：' + op, '自动裁决已关闭')
            return job.invoke('action', 'sv.' + op, actor=character['instanceId'], **args)
        if op == 'resolve':
            require(type(args.get('approve')) is bool, '请选择批准或拒绝')
            request = self.state['requests'].get(args.get('requestId'))
            require(request is not None, '请求不存在')
            if request['status'] != 'pending':
                return {'message': '此请求已经处理', 'status': request['status']}
            reason = str(args.get('reason', '')).strip()
            require(len(reason) <= 2000, '裁定说明过长')
            if args.get('approve'):
                current_actor = view['entities'].get(request['actor'])
                require(current_actor and current_actor['lifecycle'] == 'active' and current_actor['owner'] == request['account'], '角色归属已经改变')
                resolution = args.get('resolution')
                if resolution is not None:
                    require(request['kind'] in {'free', 'interact', 'review'}, '结构化申请必须执行原行动')
                    require(isinstance(resolution, dict) and set(resolution) == {'operation', 'input'}, '执行配置无效')
                    operation, inputs = resolution['operation'], resolution['input']
                    fields = {'check': {'attribute', 'mode'}, 'damage': {'amount', 'attribute'},
                              'rest': {'kind', 'attribute'}, 'grant': {'item', 'slot', 'uses'}}
                    require(isinstance(operation, str) and operation in fields and isinstance(inputs, dict) and set(inputs) == fields[operation], '不支持的裁决执行动作')
                    if operation == 'check':
                        outcome = job.invoke('resolution', 'sv.adjudicate', actor=request['actor'], kind='check',
                                             operation='move', slot=0, value=0, **inputs)
                    else:
                        outcome = job.invoke('resolution', 'sv.' + operation, actor=request['actor'], **inputs)
                    request['result'] = outcome
                    request['resolution'] = copy.deepcopy(resolution)
                if request['kind'] == 'scene':
                    require(self.current_scene_request(job,request['args'].get('menuVersion')),
                            '行动菜单已更新，请让玩家按本人已知选项重新提交')
                    request['result'] = self.execute_scene(job, view, current_actor, request['args']['action'], request['args']['choice'])
                if request['kind'] in {'check', 'inventory'}:
                    params = {'attribute': 'dex', 'mode': 'normal', 'operation': 'move', 'slot': 0, 'value': 0, **request['args']}
                    request['result'] = job.invoke('ruling', 'sv.adjudicate', actor=request['actor'], kind=request['kind'], **params)
                if request['kind'] == 'travel':
                    destination = request['args']['destination']
                    current_actor = view['entities'].get(request['actor'])
                    require(current_actor and current_actor['owner'] == request['account'], '角色归属已经改变')
                    allowed = self.state['locations'][str(current_actor['numbers']['location'])]['exits']
                    require(destination in allowed and self.passable(current_actor['numbers']['location'], destination), '角色位置或门状态变化，请重新请求')
                    request['result'] = job.invoke('travel', 'sv.travel', actor=request['actor'], location=destination)
                elif request['kind'] == 'transfer':
                    params = request['args']
                    source, target = view['entities'].get(request['actor']), view['entities'].get(params['target'])
                    require(source and target and source['owner'] == request['account'] and source['numbers']['location'] == target['numbers']['location'], '角色归属或位置变化，请重新请求')
                    request['result'] = job.invoke('transfer', 'sv.transfer', actor=request['actor'], target=params['target'], slot=params['slot'], destination=params['destination'])
                request['status'] = 'approved'
            else:
                request['status'] = 'rejected'
            request.pop('failure', None)
            request['reason'] = reason
            return {'message': '裁定已保存', 'status': request['status'], 'result': request.get('result')}
        if op == 'location.save':
            index = str(args.get('index'))
            require(index in self.state['locations'], '地点不存在')
            require(args.get('revision') == self.state['locations'][index].get('revision', 0), '地点版本冲突，请刷新')
            location = self.state['locations'][index]
            updated = {}
            for field in ('description', 'truth'):
                value = args.get(field, '')
                require(isinstance(value, str) and len(value) <= 6000, '地点文字过长')
                updated[field] = value
            location.update(updated)
            location['revision'] = location.get('revision', 0) + 1
            return {'message': '地点草稿已保存'}
        if op == 'location.publish':
            index = str(args.get('index'))
            require(index in self.state['locations'], '地点不存在')
            location = self.state['locations'][index]
            entity = next(x for x in self.entities(view, 'sv.location') if str(x['numbers']['index']) == index)
            public = {k: copy.deepcopy(location[k]) for k in ('index', 'name', 'description', 'exits', 'features')}
            chosen = args.get('clues', [])
            require(isinstance(chosen, list), '线索选择格式错误')
            public['clues'] = [copy.deepcopy(x) for x in location['clues'] if x['id'] in chosen]
            job.command('publish', 'entity.update', {'id': entity['instanceId'], 'visibility': 'public'})
            if 'autoResolve' in session['numbers']:
                job.command('public-doors', 'entity.update', {'id': session['instanceId'], 'numbers': self.public_door_numbers(index)})
            self.state['published'][index] = public
            return {'message': '地点公开内容已发布'}
        if op == 'door':
            key = args.get('edge')
            require(key in self.state['doors'] and args.get('status') in {'open', 'closed', 'locked'}, '通路设置无效')
            if 'autoResolve' in session['numbers']:
                public_open = args['status'] == 'open' and all(x in self.state['published'] for x in key.split('-'))
                job.command('door', 'entity.update', {'id': session['instanceId'], 'numbers': {'door' + key.replace('-', '_'): int(public_open)}})
            self.state['doors'][key] = args['status']
            return {'message': '通路状态已更新'}
        if op == 'stock.take':
            location = self.state['locations'].get(str(args.get('index')))
            actor = view['entities'].get(args.get('actor'))
            require(location and actor and actor['configurationId'] == 'sv.character' and actor['numbers']['location'] == location['index'], '角色不在此地点')
            stock = next((x for x in location['stock'] if x['item'] == args.get('item')), None)
            require(stock and stock['count'] > 0, '库存不足')
            definition = self.game['items'][stock['item'] - 1]
            job.invoke('grant', 'sv.grant', actor=actor['instanceId'], item=stock['item'], slot=args['slot'], uses=definition['uses'])
            stock['count'] -= 1
            return {'message': '物品已领取，地点库存已扣减', 'remaining': stock['count']}
        if op == 'world':
            operation = args.get('operation')
            return job.invoke('world', 'sv.world', actor=session['instanceId'], operation=operation, value=args.get('round', 0))
        if op == 'generate':
            kind = args['kind']
            result = job.invoke('generate', 'sv.generate', actor=world['instanceId'], kind=kind)
            if kind == 'pots':
                self.state['locations']['4']['stock'] = [{'item': 8, 'count': result['count']}]
            if kind == 'rats':
                for i in range(result['count']):
                    job.command('rat-' + str(i), 'entity.create', {'configurationId': 'sv.npc', 'name': 'Dedratz ' + str(i + 1) + '（待核数值）',
                        'owner': 'kp', 'visibility': 'kp', 'numbers': {'location': 7}})
            if kind == 'encounter':
                result['message'] = '遭遇' if result['rolled'] == 1 else '征兆' if result['rolled'] == 2 else '没有遭遇'
            if kind == 'encounter-table':
                result['entry'] = self.state['encounters'][result['rolled'] - 1]
            if kind == 'loot':
                result['entry'] = self.state['loot'][result['rolled'] - 1]
            return result
        if op == 'tables.save':
            for key, length in [('encounters', 6), ('loot', 20)]:
                rows = args.get(key)
                require(isinstance(rows, list) and len(rows) == length and all(isinstance(x, str) and len(x) <= 2000 for x in rows), '随机表行数或文字无效')
            self.state['encounters'], self.state['loot'] = args['encounters'], args['loot']
            return {'message': '主持随机表已保存'}
        if op in {'damage', 'rest', 'grant', 'remove', 'morale'}:
            target = view['entities'].get(args.get('actor'))
            require(target and (target['configurationId'] in {'sv.character', 'sv.npc'} or target['configurationId'].startswith('sv.ext.npc.')), '目标角色不存在')
            return job.invoke(op, 'sv.' + op, **args)
        if op == 'npc.create':
            name = str(args.get('name', '')).strip()
            require(1 <= len(name) <= 60, '名称应为1至60字')
            numbers = args.get('numbers', {})
            require(set(numbers) == {'str', 'dex', 'wil', 'hp', 'armor', 'location'}, '请填写完整数值')
            require(all(isinstance(x, int) and not isinstance(x, bool) and 0 <= x <= 100 for x in numbers.values()) and str(numbers['location']) in self.state['locations'], 'NPC 数值无效')
            numbers = {**numbers, 'strMax': numbers['str'], 'dexMax': numbers['dex'], 'wilMax': numbers['wil'], 'maxHp': numbers['hp']}
            entity = job.command('npc', 'entity.create', {'configurationId': 'sv.npc', 'name': name, 'owner': 'kp', 'visibility': 'kp', 'numbers': numbers})
            return {'message': '主持生物已创建', 'id': entity}
        if op == 'actor.update':
            target = view['entities'].get(args.get('id'))
            require(target and (target['configurationId'] in {'sv.character', 'sv.npc'} or target['configurationId'].startswith('sv.ext.npc.')), '角色不存在')
            allowed = {'armor', 'str', 'dex', 'wil', 'hp', 'strMax', 'dexMax', 'wilMax', 'maxHp', 'xp', 'level', 'grit', 'pips', 'incapacitated'}
            numbers = args.get('numbers', {})
            require(isinstance(numbers, dict) and set(numbers) <= allowed, '数值字段不支持')
            require(all(isinstance(x, int) and not isinstance(x, bool) and 0 <= x <= 100000 for x in numbers.values()), '数值无效')
            merged = {**target['numbers'], **numbers}
            require(all(merged[x] <= merged[x + 'Max'] for x in ('str', 'dex', 'wil')) and merged['hp'] <= merged['maxHp'], '当前值不能超过上限')
            return job.command('update', 'entity.update', {'id': target['instanceId'], 'numbers': numbers})
        if op == 'room':
            require(args.get('status') in {'active', 'paused'}, '房间状态不支持')
            return job.command('room', 'room.status', args)
        if op == 'recap':
            updated = {}
            for field in ('recapDraft', 'recapPrivate'):
                value = args.get(field, '')
                require(isinstance(value, str) and len(value) <= 8000, '回顾文字过长')
                updated[field] = value
            self.state.update(updated)
            if args.get('publish'):
                self.state['recap'] = self.state['recapDraft']
            return {'message': '场次回顾已保存'}
        if op == 'backup':
            backup = job.client.request('/backup', {})
            folder = self.path.parent / 'package-backups'
            folder.mkdir(exist_ok=True)
            destination = folder / (request_id + '.json')
            destination.write_text(json.dumps({'hostBackup': backup, 'package': self.state}, ensure_ascii=False), encoding='utf-8')
            return {'host': backup, 'packageFile': str(destination), 'message': '宿主备份与包侧记录均已保存'}
        if op == 'rules.stage':
            content = self.validate_bundle(args.get('bundle'))
            revision = job.command('stage', 'rule.stage', content)
            self.state['ruleRevisions'][revision] = content
            return {'revision': revision, 'message': '检查通过，尚未激活'}
        if op == 'rules.preview':
            require(args.get('revision') in self.state['ruleRevisions'], '修订不存在')
            return job.client.request('/preview', {'revision': args['revision'], 'rule': args.get('rule', 'sv.layout'), 'input': args.get('input', {})})
        if op == 'rules.activate':
            revision = args.get('revision')
            require(revision in self.state['ruleRevisions'], '修订不存在')
            job.command('activate', 'rule.activate', {'revision': revision})
            self.sync_rules(job.client,job.client.request('/view'))
            return {'revision': revision, 'message': '规则修订已激活', 'packageSync':self.state.get('publicationSync')}
        raise PackageError('未知行动')

    def initialize(self, job):
        knowledge_client.bind(job)
        if self.state['initialized']:
            return {'message': '配置包已安装'}
        content = bundle()
        revision = job.command('stage', 'rule.stage', {'sources': content['sources'], 'data': content['data']})
        job.command('activate', 'rule.activate', {'revision': revision})
        self.state['ruleRevisions'][revision] = {'sources': content['sources'], 'data': content['data']}
        self.state['activeRevision'] = revision
        for config in content['configurations']:
            job.command(config['configurationId'], 'configuration.put', config)
        session_id=job.command('session', 'entity.create', {'configurationId': 'sv.session', 'name': '树桩镇探索', 'owner': 'kp', 'visibility': 'public'})
        job.command('world', 'entity.create', {'configurationId': 'sv.world', 'name': '主持世界记录', 'owner': 'kp', 'visibility': 'kp'})
        values = {**scenes.DEFAULTS, **scenes.package_numbers(self.state)}
        self.state['sceneId'] = job.command('scene', 'entity.create', {'configurationId': 'sv.scene',
            'name': '树桩镇机关与有限库存', 'owner': 'kp', 'visibility': 'kp', 'numbers': values})
        self.state['sceneState'] = values
        for location in self.game['locations']:
            job.command('location-' + str(location['index']), 'entity.create', {'configurationId': 'sv.location',
                'name': location['name'], 'owner': 'kp', 'visibility': 'public' if location['index'] == 1 else 'kp', 'numbers': {'index': location['index']}})
        first = self.state['locations']['1']
        self.state['published']['1'] = {k: copy.deepcopy(first[k]) for k in ('index', 'name', 'description', 'exits', 'features', 'clues')}
        for npc in self.game['npcs']:
            if not npc['verified']:
                continue
            numbers = {k: npc[k] for k in ('str', 'dex', 'wil', 'hp', 'armor', 'location')}
            numbers.update(strMax=npc['str'], dexMax=npc['dex'], wilMax=npc['wil'], maxHp=npc['hp'])
            entity = job.command('npc-' + npc['key'], 'entity.create', {'configurationId': 'sv.npc', 'name': npc['name'], 'owner': 'kp', 'visibility': 'kp', 'numbers': numbers})
            self.state['npcs'][npc['key']] = entity
        for member in job.client.request('/chat/members')['items']:
            if member['role'] == 'player':
                knowledge_client.disclose(job,member['accountId'],session_id,'play',live=True,key='play-knowledge-'+member['accountId'],reason='KP 明确持续告知公共回合、开场和自动裁决状态')
                draft_id=job.command('draft-' + member['accountId'], 'entity.create', {'configurationId': 'sv.draft', 'name': '建角骰盘',
                    'owner': member['accountId'], 'visibility': 'owner'})
                knowledge_client.disclose(job,member['accountId'],draft_id,'sheet',live=True,key='draft-knowledge-'+member['accountId'])
        self.state['initialized'] = True
        return {'message': '十地点与规则已安装', 'revision': revision}

    def approve(self, job, view, args):
        account = args.get('account')
        draft = self.state['drafts'].get(account)
        require(draft is not None, '未找到角色草稿')
        if args.get('reject'):
            draft['status'] = 'rejected'
            draft['reason'] = str(args.get('reason', '请修改草稿'))[:2000]
            return {'message': '已退回草稿'}
        existing = next((x for x in self.entities(view, 'sv.character') if x['owner'] == account), None)
        if existing and 'create' not in job.record['steps']:
            raise PackageError('该玩家已有角色')
        entity = job.command('create', 'entity.create', {'configurationId': 'sv.character', 'name': draft['name'], 'owner': account, 'visibility': 'owner'})
        job.invoke('profile', 'sv.profile', actor=entity, strength=draft['str'], dexterity=draft['dex'], will=draft['wil'], hp=draft['hp'], pips=draft['pips'])
        for position, item in enumerate(draft['items']):
            definition = self.game['items'][item['item'] - 1]
            job.invoke('item-' + str(position), 'sv.grant', actor=entity, item=item['item'], slot=item['slot'], uses=definition['uses'])
        session = next(iter(self.entities(view, 'sv.session')))
        job.command('source', 'relation.set', {'sourceId': entity, 'targetId': session['instanceId'], 'relationType': 'source'})
        job.command('reference', 'relation.set', {'sourceId': session['instanceId'], 'targetId': entity, 'relationType': 'references'})
        knowledge_client.disclose(job,account,entity,'sheet',live=True,key='character-knowledge',reason='角色批准后持续告知本人角色状态')
        self.state['bindings'][account] = entity
        self.state['roster'][account] = {'account': account, 'id': entity, 'name': draft['name']}
        draft['status'] = 'approved'
        return {'message': '角色审核通过', 'character': entity}
