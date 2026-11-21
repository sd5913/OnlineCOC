"""Bounded, permission-filtered data references. No filesystem or write commands."""
import copy
import re
from onlinecoc.model import member, visible
from .contracts import canonical
from .errors import require

TOKEN = re.compile(r'\[\[(config|entity|data|chat|event|ruling|knowledge):([A-Za-z0-9_.-]{1,1500})@([A-Za-z0-9_.-]{1,200})\]\]')

class References:
    def __init__(self, host):self.host = host

    def label(self, kind, key, fallback):
        adapter=getattr(self.host,'ai_data_adapter',None)
        if adapter and hasattr(adapter,'reference_label'):
            try:label=adapter.reference_label(kind,key,fallback)
            except Exception:return fallback
            if type(label) is str and 1<=len(label.strip())<=160:return label
        return fallback

    def _items(self, room, account, kind):
        kp = member(room, account)['role'] == 'kp'
        if kind == 'knowledge':
            from .knowledge import service
            from .known_answers import reference_token
            page=service(self.host,account,room).search(account,{'limit':50},state=room,player=True)
            return [(TOKEN.fullmatch(reference_token(v['ref']))[2],v['label'],'1','private',v) for v in page['items']]
        require(kp,'REFERENCE_NOT_VISIBLE')
        if kind in ('chat','event','ruling'):
            from onlinecoc.data_queries import rows
            return [(v['ref']['id'],v['label'],v['ref']['digest'],v['visibility'],v)
                    for v in rows(self.host,room,account,kinds=[kind]) if v['ref']['kind']==kind]
        if kind == 'config':
            from onlinecoc.data_queries import configuration_projection
            return [(key, self.label(kind,key,value.get('name', key)), str(value['revision']), 'public', value) for key, value in configuration_projection(self.host,room,account).items()]
        if kind == 'entity':
            result = []
            from onlinecoc.data_queries import entity_projection
            for key, value in entity_projection(self.host,room,account).items():
                if value['lifecycle'] != 'active' and not kp:continue
                value = copy.deepcopy(value)
                if not kp:value['metadata'].pop('secret', None)
                result.append((key, value['name'], str(value['revision']), 'private' if value['visibility'] == 'owner' else value['visibility'], value))
            return result
        require(kind == 'data', 'REFERENCE_KIND_INVALID')
        if not kp:return []
        artifact = room['artifacts'][room['activeRuleset']]
        return [(key, key, room['activeRuleset'], 'kp', value) for key, value in artifact['data'].items()]

    def search(self, account, kind='config', q=''):
        require(type(q) is str and len(q) <= 120, 'INPUT_INVALID')
        with self.host.lock:
            room = self.host.state()
            if kind=='knowledge':
                from .knowledge import service
                from .known_answers import reference_token
                page=service(self.host,account,room).search(account,{'query':q,'limit':20},state=room,player=True)
                return {'items':[{'kind':kind,'id':TOKEN.fullmatch(reference_token(v['ref']))[2],
                    'label':v['label'],'revision':'1','visibility':'private','token':reference_token(v['ref'])} for v in page['items']],
                    'hasMore':page['nextCursor'] is not None}
            matches = [x for x in self._items(room, account, kind) if q.casefold() in (x[0] + ' ' + str(x[1])).casefold()]
            return {'items': [{'kind': kind, 'id': key, 'label': label, 'revision': rev, 'visibility': scope,
                'token': f'[[{kind}:{key}@{rev}]]'} for key, label, rev, scope, _ in matches[:20]], 'hasMore': len(matches) > 20}

    def resolve(self, account, tokens, *, room=None, external_policy=None, initiator=None):
        require(type(tokens) is list and len(tokens) <= 12 and all(type(t) is str for t in tokens), 'REFERENCE_LIMIT')
        with self.host.lock:
            room = room or self.host.state();member(room, account)
            result = []
            for token in dict.fromkeys(tokens):
                parsed = TOKEN.fullmatch(token);require(parsed is not None, 'REFERENCE_INVALID')
                kind, key, revision = parsed.groups()
                if kind=='knowledge':
                    from .knowledge import service
                    from .known_answers import decode_reference
                    ref=decode_reference(key,revision)
                    if external_policy is not None:require(external_policy['private'],'EXTERNAL_SCOPE_DISABLED')
                    value=service(self.host,account,room).read(account,{'refs':[ref]},state=room,player=True)['items'][0]
                    if initiator and initiator!=account:
                        service(self.host,initiator,room).read(initiator,{'refs':[ref]},state=room,player=True)
                    result.append({'kind':kind,'id':key,'label':value['label'],'revision':'1','visibility':'private','value':value})
                    continue
                require(len(key)<=200,'REFERENCE_INVALID')
                candidates = {x[0]: x for x in self._items(room, account, kind)}
                require(key in candidates, 'REFERENCE_NOT_VISIBLE')
                if initiator:
                    require(key in {x[0] for x in self._items(room, initiator, kind)}, 'REFERENCE_NOT_VISIBLE')
                _, label, current, scope, value = candidates[key]
                require(revision == current, 'REFERENCE_STALE')
                if external_policy is not None:
                    require(external_policy[scope], 'EXTERNAL_SCOPE_DISABLED')
                    if kind == 'entity' and not external_policy['kp']:
                        value = copy.deepcopy(value);value['metadata'].pop('secret', None)
                result.append({'kind': kind, 'id': key, 'label': label, 'revision': current, 'visibility': scope, 'value': value})
            require(len(canonical(result)) <= 32 * 1024, 'REFERENCE_LIMIT')
            return {'items': result}

    def from_text(self, account, text, **kwargs):
        tokens = [m.group(0) for m in TOKEN.finditer(text)]
        # An incomplete/forged explicit marker must not silently lose binding.
        require(len(re.findall(r'\[\[(?:config|entity|data|chat|event|ruling|knowledge):', text)) == len(tokens), 'REFERENCE_INVALID')
        return self.resolve(account, tokens, **kwargs)['items']
