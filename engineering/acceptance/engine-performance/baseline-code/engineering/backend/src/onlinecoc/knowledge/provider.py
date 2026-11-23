"""Trusted example provider; field maps are installed Python, never user input.

Fields use dotted paths into an authoritative Entity. A facet's output is a
dictionary mapping friendly keys to these fields. No JSONPath/eval is used.
"""
import copy
from ..errors import require

class HostStateProvider:
    def __init__(self, facets, *, live_facets=(), live_public=False):
        self.facets = copy.deepcopy(facets)
        self.live_facets = frozenset(live_facets)
        self.live_public = live_public

    def _entity(self, resource, context):
        value = context['state']['entities'].get(resource['id'])
        require(value is not None, 'NOT_VISIBLE')
        return value

    def pin(self, resource, facet_ids, context):
        value = self._entity(resource, context)
        require(value['lifecycle'] == 'active' and not value['metadata'].get('knowledgeRevoked'), 'NOT_VISIBLE')
        facets = {}
        for facet in facet_ids:
            require(facet in self.facets, 'NOT_VISIBLE')
            data = {}
            for key, path in self.facets[facet].items():
                selected = value
                for part in path.split('.'):
                    require(isinstance(selected, dict) and part in selected, 'NOT_VISIBLE')
                    selected = selected[part]
                data[key] = copy.deepcopy(selected)
            facets[facet] = data
        return dict(sourceRevision=str(value['revision']), facets=facets,
                    sourceGuard={'entityId': value['instanceId'], 'configurationId': value['configurationId']})

    def read_live(self, resource, facet_ids, context):
        value = self._entity(resource, context)
        require(set(facet_ids) <= self.live_facets, 'KNOWLEDGE_MODE_UNSUPPORTED')
        require(value['owner'] == context['accountId'] or (self.live_public and value['visibility'] == 'public'), 'NOT_VISIBLE')
        return self.pin(resource, facet_ids, context)

    def check_guard(self, guard, context):
        value = context['state']['entities'].get(guard.get('entityId'))
        return bool(value and value['configurationId'] == guard.get('configurationId')
                    and not value['metadata'].get('knowledgeRevoked'))
