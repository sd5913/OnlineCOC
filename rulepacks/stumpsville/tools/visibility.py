"""Package-owned sightings; only names and current locations reach the map."""
import copy
from ai_data import known_locations


class MapVisibility:
    def __init__(self, package):
        self.package = package
        self.state = package.state

    def sync(self, view):
        # Reads never fabricate new observations. The legacy location set is
        # retained only for a KP's explicit "disclose now" migration choices.
        players = {a['instanceId']: {'id': a['instanceId'], 'name': a['name'], 'kind': 'pc',
                                    'owner': a['owner'], 'location': a['numbers']['location']}
                   for a in self.package.entities(view, 'sv.character')
                   if view['role'] == 'kp' or a['owner'] == view['accountId']}
        if view['role'] != 'kp':
            players = {**{key: a for key, a in self.state.get('mapPlayerActors', {}).items() if a['owner'] != view['accountId']}, **players}
        if self.state.get('mapPlayerActors') != players:
            self.state['mapPlayerActors'] = players
            self.package.save()
        if view['role'] != 'kp':
            return
        actors = {a['instanceId']: {'id': a['instanceId'], 'name': a['name'], 'kind': 'npc',
                                  'location': a['numbers']['location']}
                  for a in self.package.entities(view, 'sv.npc')}
        if self.state.get('mapNpcActors') != actors:
            self.state['mapNpcActors'] = actors
            self.package.save()

    def catalog(self):
        actors = copy.deepcopy(self.state.get('mapNpcActors', {}))
        for template in self.package.game['npcs']:
            instance_id = self.state['npcs'].get(template['key'])
            if instance_id in actors and actors[instance_id]['name'] == template['name']:
                actors[instance_id]['nameKey'] = 'map.actor.' + template['key']
            # Narrative characters with unverified stats are map contacts only.
            if not template['verified']:
                key = 'story:' + template['key']
                location = 3 if template['key'] in {'roquefort', 'paneer'} and self.state['sceneState'].get('villagersFreed') else template['location']
                actors[key] = {'id': key, 'name': template['name'], 'kind': 'npc', 'location': location}
        if not any(a['location'] == 7 for a in actors.values()):
            for i in range(self.state.get('mapRatCount', 0)):
                key = 'story:rat-' + str(i + 1)
                actors[key] = {'id': key, 'name': 'Dedratz ' + str(i + 1), 'kind': 'npc', 'location': 7}
        return actors

    def discover_scene(self, owner, action, choice, result, view):
        self.sync(view)
        if result.get('outcome') == 'blocked':
            return
        keys = []
        if action == 'web-inspect':
            keys = ['spider1', 'spider2', 'roquefort', 'paneer']
        elif action == 'web-call':
            keys = ['roquefort', 'paneer'] + (['spider1', 'spider2'] if choice != 'whisper' else [])
        elif action == 'factory-equipment' and choice == 'inspect':
            keys = ['jack']
        elif action in {'cage-gate', 'cage-listen'}:
            keys = ['snake']
        elif action == 'cave-sleeper':
            keys = ['ernie']
        seen = self.state['actorDiscoveries'].setdefault(owner, {})
        for key in keys:
            seen[self.state['npcs'].get(key, 'story:' + key)] = True
        if action in {'hall-observe', 'hall-negotiate'}:
            world = next(iter(self.package.entities(view, 'sv.world')), None)
            self.state['mapRatCount'] = world['numbers'].get('rats', 0) if world else 0
            for key, actor in self.catalog().items():
                if actor['location'] == 7:
                    seen[key] = True

    def contacts(self, account, character, characters):
        if not character:
            return []
        location = character['numbers']['location']
        seen = dict(self.state.get('actorDiscoveries', {}).get(account, {}))
        players = [{'id': a['id'], 'name': a['name'], 'kind': 'pc', 'location': location,
                    'self': a['owner'] == account}
                   for a in self.state.get('mapPlayerActors', {}).values() if a['location'] == location
                   and (a['owner'] == account or seen.get(a['id'], True))]
        return players + [a for key, a in self.catalog().items() if a['location'] == location and seen.get(key) is True]
