"""Authoritative disclosure, projection and dependency-scoped read evidence.

Public methods acquire the host lock. Provider calls receive a single copied
room snapshot plus a per-request cache. They must not commit or call networks.
"""
import copy
import uuid
from jsonschema import Draft202012Validator
from onlinecoc_data import canonical
from ..errors import DomainError, require
from ..model import member
from .models import check, digest, descriptor_digest, validate

def uid():
    return str(uuid.uuid4())

class KnowledgeService:
    def __init__(self, host):
        self.host = host
        self.providers = {}
        self.descriptors = {}
        self.cursors = {}
        self.registration_revision = 0

    def register(self, descriptor, provider):
        with self.host.lock:
            check('models', 'Descriptor', descriptor)
            value = copy.deepcopy(descriptor)
            value['descriptorDigest'] = descriptor_digest(value)
            require(not descriptor.get('descriptorDigest') or descriptor['descriptorDigest'] == value['descriptorDigest'], 'INPUT_INVALID')
            for name in ('pin', 'read_live', 'check_guard'):
                require(callable(getattr(provider, name, None)), 'INPUT_INVALID')
            for facet in value['facetSchemas'].values():
                Draft202012Validator.check_schema(facet['schema'])
                require(not facet.get('entityProjection') or facet['modes']==['live_scope'],'KNOWLEDGE_MODE_UNSUPPORTED')
            require(all(self._valid_selector(s) for s in value['selectors']), 'INPUT_INVALID')
            self.descriptors[value['policyId']] = value
            self.providers[value['providerId']] = provider
            self.registration_revision += 1
            return copy.deepcopy(value)

    def projection_revision(self, policies):
        """Opt-in external invalidation; unknown providers keep the uncached path.

        A trusted provider's zero-argument projection_revision() must return a
        nonempty string changing whenever ANY external data/eligibility changes.
        It must check its source on each call, including replacement/deletion.
        Room-owned changes are separately bound to the store generation.
        """
        revisions=[self.registration_revision]
        try:
            for key,policy in sorted(policies.items()):
                provider=self._provider(policy)
                revision=getattr(provider,'projection_revision',None)
                if not callable(revision):return None
                token=self._invoke(provider,'projection_revision')
                if type(token) is not str or not 0<len(token)<=4096:return None
                revisions.append((key,token))
        except DomainError:return None
        return tuple(revisions)

    @staticmethod
    def _valid_selector(s):
        keys = set(s) - {'kind', 'resourceKind'}
        return (s['kind'] == 'entity' and keys in ({'configurationId'}, {'configurationPrefix'}, {'id'})) or (s['kind'] in ('asset', 'package') and keys == {'id'})

    def _context(self, s, account, player=False):
        m = member(s, account)
        return dict(state=s, accountId=account, memberId=m['memberId'], player=player or m['role'] != 'kp', cache={}, host=self.host)

    def _provider(self, policy):
        installed = self.descriptors.get(policy['policyId'])
        require(installed and installed['descriptorDigest'] == policy['descriptorDigest'], 'KNOWLEDGE_UNAVAILABLE')
        provider = self.providers.get(policy['providerId'])
        require(provider is not None, 'KNOWLEDGE_UNAVAILABLE')
        return provider

    def _invoke(self, provider, name, *args):
        try:
            return getattr(provider, name)(*args)
        except DomainError:
            raise
        except Exception:
            raise DomainError('KNOWLEDGE_UNAVAILABLE') from None

    def ready(self, s):
        require(s['knowledge']['policies'], 'KNOWLEDGE_UNAVAILABLE')
        for policy in s['knowledge']['policies'].values():
            self._provider(policy)

    def strict(self, s, account, player=False):
        return bool(s['knowledge']['policies']) and (player or member(s, account)['role'] != 'kp')

    @staticmethod
    def _matches(selector, kind, key, value=None):
        if selector['kind'] != kind:
            return False
        if 'id' in selector:
            return key == selector['id']
        config = (value or {}).get('configurationId', '')
        return config == selector.get('configurationId') or ('configurationPrefix' in selector and config.startswith(selector['configurationPrefix']))

    def managed(self, s, kind, key, value=None):
        return any(self._matches(selector, kind, key, value) for policy in s['knowledge']['policies'].values() for selector in policy['selectors'])

    def protected_asset(self, s, key):
        return self.managed(s,'asset',key) or any(key in e['components'].get('core.assets',[]) and self.managed(s,'entity',eid,e) for eid,e in s['entities'].items())

    def _resource(self, s, policy, resource):
        require(resource['namespace'] == policy['namespace'], 'NOT_VISIBLE')
        for selector in policy['selectors']:
            if resource['kind'] != selector.get('resourceKind', selector['kind']):
                continue
            value = s['entities'].get(resource['id']) if selector['kind'] == 'entity' else None
            if self._matches(selector, selector['kind'], resource['id'], value):
                return
        raise DomainError('NOT_VISIBLE')

    def _policy(self, s, key):
        p = s['knowledge']['policies'].get(key)
        require(p, 'NOT_VISIBLE')
        return p

    def _pin(self, s, policy, resource, facets, context, mode):
        self._resource(s, policy, resource)
        for facet in facets:
            schema = policy['facetSchemas'].get(facet)
            require(schema, 'NOT_VISIBLE')
            require(mode in schema['modes'], 'KNOWLEDGE_MODE_UNSUPPORTED')
        value = self._invoke(self._provider(policy), 'pin' if mode == 'observed_snapshot' else 'read_live', resource, facets, context)
        require(isinstance(value, dict) and isinstance(value.get('sourceRevision'), str) and value['sourceRevision'], 'KNOWLEDGE_UNAVAILABLE')
        require(set(value.get('facets', {})) == set(facets) and isinstance(value.get('sourceGuard'), dict), 'KNOWLEDGE_UNAVAILABLE')
        for facet, data in value['facets'].items():
            require(not next(Draft202012Validator(policy['facetSchemas'][facet]['schema']).iter_errors(data), None), 'KNOWLEDGE_UNAVAILABLE')
            require(len(canonical(data)) <= 8192, 'KNOWLEDGE_LIMIT')
        require(len(canonical(value)) <= 32768, 'KNOWLEDGE_LIMIT')
        return copy.deepcopy(value)

    def capabilities(self, account, *, state=None, player=False):
        with self.host.lock:
            s = self.host.state() if state is None else state
            ctx = self._context(s, account, player)
            result = dict(schemaVersion=1, subjectModes=['account'], modes=['observed_snapshot', 'live_scope'], status='unavailable')
            try:
                self.ready(s)
                result['status'] = 'ready'
            except DomainError:
                if s['knowledge']['policies']:
                    result['status'] = 'blocked'
            if not ctx['player']:
                result['descriptors'] = copy.deepcopy(list(self.descriptors.values()))
                result['policies'] = copy.deepcopy(list(s['knowledge']['policies'].values()))
            return result

    def preview(self, account, args):
        with self.host.lock:
            check('queries', 'preview', args)
            s = self.host.state(); require(member(s, account)['role'] == 'kp', 'PERMISSION_DENIED')
            policy = self._policy(s, args['policyId'])
            pin = self._pin(s, policy, args['resource'], args['facetIds'], self._context(s, account), 'observed_snapshot')
            return dict(policyRevision=policy['revision'], sourceRevision=pin['sourceRevision'], preview=pin['facets'], digest=digest(pin['facets']), capturedAt=self.host.clock())

    @staticmethod
    def _overlap(a, b):
        if a['kind'] != b['kind']:
            return False
        if 'id' in a and 'id' in b:
            return a['id'] == b['id']
        if 'id' in a or 'id' in b:
            return True  # Conservative: future reconfiguration cannot create overlap.
        x = a.get('configurationId', a.get('configurationPrefix'))
        y = b.get('configurationId', b.get('configurationPrefix'))
        if 'configurationId' in a and 'configurationId' in b:
            return x == y
        return x.startswith(y) or y.startswith(x)

    def apply(self, s, account, op, args, command_id=None):
        check('commands', op, args)
        require(member(s, account)['role'] == 'kp', 'PERMISSION_DENIED')
        k = s['knowledge']
        if op == 'knowledge.policy.bind':
            descriptor = self.descriptors.get(args['policyId'])
            require(descriptor and descriptor['descriptorDigest'] == args['descriptorDigest'], 'KNOWLEDGE_UNAVAILABLE')
            current = k['policies'].get(args['policyId'])
            require(args['expectedRevision'] == (current['revision'] if current else 0), 'VERSION_CONFLICT')
            for key, p in k['policies'].items():
                if key != args['policyId']:
                    require(not any(self._overlap(a, b) for a in p['selectors'] for b in descriptor['selectors']), 'KNOWLEDGE_POLICY_CONFLICT')
            policy = copy.deepcopy(descriptor); policy['revision'] = args['expectedRevision'] + 1
            k['policies'][args['policyId']] = policy
            result = dict(policyId=policy['policyId'], revision=policy['revision'])
        elif op == 'knowledge.revoke':
            grant = k['grants'].get(args['grantId'])
            require(grant, 'NOT_VISIBLE'); require(grant['revision'] == args['expectedRevision'], 'VERSION_CONFLICT')
            require(grant['status'] == 'active', 'VERSION_CONFLICT')
            grant.update(status='revoked', revision=grant['revision'] + 1, revokedAt=self.host.clock(), revokedBy=account, reason=args['reason'])
            self._bump(k, grant['subject']['memberId'])
            result = dict(grantId=grant['grantId'], revision=grant['revision'])
        else:
            policy = self._policy(s, args['policyId'])
            require(policy['revision'] == args['expectedPolicyRevision'], 'VERSION_CONFLICT')
            target = next((m for m in s['members'].values() if m['memberId'] == args['subjectMemberId'] and m['active']), None)
            require(target, 'NOT_VISIBLE')
            mode = 'observed_snapshot' if op == 'knowledge.observe' else 'live_scope'
            context = self._context(s, target['accountId'], True)
            pin = self._pin(s, policy, args['resource'], args['facetIds'], context, mode)
            if mode == 'observed_snapshot':
                require(pin['sourceRevision'] == args['expectedSourceRevision'], 'SOURCE_STALE')
            provenance = dict(kind='kp-disclosure', actor=account, at=self.host.clock(), reason=args['reason'])
            result = self._record(s, policy, target, args['resource'], args['facetIds'], mode, pin, provenance)
        k['revision'] += 1
        validate(k)
        return result

    @staticmethod
    def _bump(k, member_id):
        k['subjectEpochs'][member_id] = k['subjectEpochs'].get(member_id, 0) + 1

    def _record(self, s, policy, target, resource, facets, mode, pin, provenance):
        k = s['knowledge']; observation_id = None
        require(len(k['grants']) < 50000, 'KNOWLEDGE_LIMIT')
        if mode == 'observed_snapshot':
            require(len(k['observations']) < 10000, 'KNOWLEDGE_LIMIT')
            observation_id = uid()
            obs = dict(observationId=observation_id, resource=copy.deepcopy(resource), policyId=policy['policyId'], policyDigest=policy['descriptorDigest'],
                       sourceRevision=pin['sourceRevision'], sourceGuard=pin['sourceGuard'], observedAt=provenance['at'], sequence=k['revision'],
                       facets={f: dict(data=pin['facets'][f], digest=digest(pin['facets'][f])) for f in facets}, provenance=copy.deepcopy(provenance))
            k['observations'][observation_id] = obs
        grant_id = uid()
        grant = dict(grantId=grant_id, revision=1, subject=dict(kind='account', accountId=target['accountId'], memberId=target['memberId']),
                     resource=copy.deepcopy(resource), policyId=policy['policyId'], facetIds=list(facets), mode=mode,
                     observationId=observation_id, status='active', createdAt=provenance['at'], createdBy=provenance['actor'], provenance=copy.deepcopy(provenance))
        k['grants'][grant_id] = grant; self._bump(k, target['memberId'])
        return dict(grantId=grant_id, revision=1, observationId=observation_id)

    def derive(self, s, account, command_id, outcome, previous=None):
        """Trusted provider events, called inside the native host commit only."""
        for p in s['knowledge']['policies'].values():
            provider = self._provider(p)
            if not callable(getattr(provider, 'derive_observations', None)):
                continue
            context = self._context(s, account)
            context['previousState'] = previous
            events = self._invoke(provider, 'derive_observations', outcome, context)
            require(isinstance(events, list) and len(events) <= 32, 'KNOWLEDGE_LIMIT')
            for i, event in enumerate(events):
                event_key = f'{command_id}:{p["providerId"]}:{i}'
                if any(o['provenance'].get('eventKey') == event_key for o in s['knowledge']['observations'].values()):
                    continue
                target = next((m for m in s['members'].values() if m['memberId'] == event['subjectMemberId'] and m['active']), None)
                require(target, 'NOT_VISIBLE')
                pin = self._pin(s, p, event['resource'], event['facetIds'], self._context(s, target['accountId'], True), 'observed_snapshot')
                provenance = dict(kind='host-command', actor=account, at=self.host.clock(), reason='宿主已提交动作观察', eventKey=event_key)
                self._record(s, p, target, event['resource'], event['facetIds'], 'observed_snapshot', pin, provenance)
                s['knowledge']['revision'] += 1
        validate(s['knowledge'])

    def _items(self, s, account, player=False):
        self.ready(s)
        ctx = self._context(s, account, player); k = s['knowledge']; rows = {}; pins = {}
        for grant in k['grants'].values():
            if grant['status'] != 'active' or grant['subject'] != dict(kind='account', accountId=account, memberId=ctx['memberId']):
                continue
            p = self._policy(s, grant['policyId']); provider = self._provider(p)
            try:
                if grant['mode'] == 'observed_snapshot':
                    obs = k['observations'][grant['observationId']]
                    if obs['policyDigest'] != p['descriptorDigest']:
                        continue
                    if not self._invoke(provider, 'check_guard', obs['sourceGuard'], ctx):
                        continue
                    facets = obs['facets']; revision = obs['sourceRevision']; observed = obs['observedAt']; sequence = obs['sequence']
                    identity = obs['observationId']
                else:
                    cache_key = digest([p['policyId'], grant['resource'], sorted(grant['facetIds'])])
                    if cache_key not in pins:
                        pins[cache_key] = self._pin(s, p, grant['resource'], grant['facetIds'], ctx, 'live_scope')
                    pin = pins[cache_key]; facets = {f: dict(data=d, digest=digest(d)) for f, d in pin['facets'].items()}
                    revision = pin['sourceRevision']; observed = None; sequence = 2 ** 63
                    identity = digest([p['policyId'], grant['resource'], 'live_scope'])
                for facet in grant['facetIds']:
                    if facet not in p['facetSchemas']:
                        continue
                    value = facets[facet]
                    ref_id = digest([k['scopeId'], grant['subject'], p['descriptorDigest'], identity, facet])
                    ref = dict(schemaVersion=1, scopeId=k['scopeId'], id=ref_id, revision=str(revision), digest=value['digest'])
                    label_field = p['facetSchemas'][facet].get('labelField')
                    label = value['data'].get(label_field) if label_field and isinstance(value['data'], dict) else None
                    rows[ref_id] = dict(ref=ref, label=label[:200] if isinstance(label, str) and label else '已授权资料', facetId=facet,
                                        mode=grant['mode'], observedAt=observed, data=copy.deepcopy(value['data']), visibility='private', provenance={'kind': grant['provenance']['kind']},
                                        _resource=grant['resource'], _sequence=sequence, _policyId=p['policyId'])
            except DomainError as error:
                if error.code not in ('NOT_VISIBLE', 'PERMISSION_DENIED', 'SOURCE_STALE'):
                    raise
        return list(rows.values())

    def _full_entities(self, s, account, rows):
        from ..contracts import validate_model
        result = {}
        for row in rows:
            p=s['knowledge']['policies'][row['_policyId']]
            if p['egress']['view']!='filtered':continue
            if row['mode']!='live_scope' or not p['facetSchemas'][row['facetId']].get('entityProjection'):
                continue
            data=row['data'];key=row['_resource']['id'];original=s['entities'].get(key)
            require(original and isinstance(data,dict),'KNOWLEDGE_UNAVAILABLE')
            validate_model('Entity',data)
            require(data['owner']==account and data['lifecycle']=='active','NOT_VISIBLE')
            require(all(data[k]==original[k] for k in ('instanceId','revision','roomId','configurationId','configurationRevision','typeRef','owner','lifecycle')),'KNOWLEDGE_UNAVAILABLE')
            result[key]=(copy.deepcopy(data),row['ref'])
        return result

    def full_entities(self, s, account):
        return self._full_entities(s,account,self._items(s,account))

    def projection(self, s, account):
        rows=self._items(s,account)
        full=self._full_entities(s,account,rows)
        latest={}
        for row in rows:
            key=digest([row['_resource'],row['facetId']])
            if key not in latest or (row['_sequence'],row['ref']['id'])>(latest[key]['_sequence'],latest[key]['ref']['id']):latest[key]=row
        summaries=sorted(latest.values(),key=lambda r:(r['label'],r['facetId'],r['ref']['id']))
        page=self._page(summaries,{'limit':50},account,s['knowledge']['scopeId'])
        return full,dict(schemaVersion=1,scopeId=s['knowledge']['scopeId'],viewRevision=page['viewRevision'],items=page['items'],hasMore=page['nextCursor'] is not None)

    def _page(self, rows, args, account, scope, *, include_data=False):
        view = digest(rows)
        signature = digest([scope, account, {k: v for k, v in args.items() if k != 'cursor'}, view])
        offset = 0
        if args.get('cursor'):
            cursor = self.cursors.get(args['cursor'])
            require(cursor and cursor[0] == signature, 'SOURCE_STALE')
            offset = cursor[1]
        size = args.get('limit', 20); selected = rows[offset:offset + size]; next_cursor = None
        if offset + size < len(rows):
            if len(self.cursors) >= 2048:
                self.cursors.pop(next(iter(self.cursors)))
            next_cursor = uid(); self.cursors[next_cursor] = (signature, offset + size)
        items = [{k: v for k, v in r.items() if not k.startswith('_') and (include_data or k != 'data')} for r in selected]
        result = dict(schemaVersion=1, items=items, nextCursor=next_cursor, coverage='authorized-query', viewRevision=view)
        require(len(canonical(result)) <= 65536, 'KNOWLEDGE_LIMIT')
        return result

    def search(self, account, args, *, state=None, player=False):
        with self.host.lock:
            check('queries', 'search', args)
            s = self.host.state() if state is None else state
            rows = self._items(s, account, player)
            if not args.get('includeHistory', False):
                latest = {}
                for row in rows:
                    key = digest([row['_resource'], row['facetId']])
                    if key not in latest or (row['_sequence'], row['ref']['id']) > (latest[key]['_sequence'], latest[key]['ref']['id']):
                        latest[key] = row
                rows = list(latest.values())
            rows = [r for r in rows if (not args.get('namespace') or r['_resource']['namespace'] == args['namespace']) and
                    (not args.get('kinds') or r['_resource']['kind'] in args['kinds']) and
                    (not args.get('query') or args['query'].casefold() in canonical(r['data']).decode('utf-8').casefold())]
            rows.sort(key=lambda r: (r['label'], r['facetId'], r['ref']['id']))
            return self._page(rows, args, account, s['knowledge']['scopeId'])

    def read(self, account, args, *, state=None, player=False):
        with self.host.lock:
            check('queries', 'read', args)
            s = self.host.state() if state is None else state
            rows = {r['ref']['id']: r for r in self._items(s, account, player)}; selected = []
            for ref in args['refs']:
                row = rows.get(ref['id'])
                require(row and row['ref'] == ref, 'NOT_VISIBLE')
                selected.append(row)
            return self._page(selected, {'limit': 50}, account, s['knowledge']['scopeId'], include_data=True)

    def grants(self, account, args, *, state=None):
        with self.host.lock:
            check('queries', 'grants', args)
            s = self.host.state() if state is None else state; require(member(s, account)['role'] == 'kp', 'PERMISSION_DENIED')
            rows = [g for g in s['knowledge']['grants'].values() if (not args.get('subjectMemberId') or g['subject']['memberId'] == args['subjectMemberId'])
                    and (not args.get('policyId') or g['policyId'] == args['policyId']) and (not args.get('status') or g['status'] == args['status'])]
            rows.sort(key=lambda g: g['grantId'])
            return self._page(rows, args, account, s['knowledge']['scopeId'], include_data=True)

    def capture(self, account, *, state=None, player=False):
        with self.host.lock:
            s = self.host.state() if state is None else state; m = member(s, account); self.ready(s)
            return dict(schemaVersion=1, scopeId=s['knowledge']['scopeId'], accountId=account, memberId=m['memberId'],
                        authorizationEpoch=m['authorizationEpoch'], player=player or m['role'] != 'kp',
                        policies={key: p['descriptorDigest'] for key, p in s['knowledge']['policies'].items()}, refs=[])

    def evidence(self, account, refs, *, state=None, player=False):
        with self.host.lock:
            s = self.host.state() if state is None else state
            proof = self.capture(account, state=s, player=player)
            proof['refs'] = copy.deepcopy(refs); check('models', 'ReadProof', proof)
            self._verify_refs(s,account,refs,player)
            return proof

    def recheck(self, account, proof, *, state=None):
        return self.recheck_many(account,[proof],state=state)

    def _verify_refs(self,s,account,refs,player):
        if not refs:return
        rows={row['ref']['id']:row['ref'] for row in self._items(s,account,player)}
        for ref in refs:require(rows.get(ref['id'])==ref,'NOT_VISIBLE')

    def recheck_many(self,account,proofs,*,state=None):
        """One provider context per dependency set, regardless of tool count."""
        with self.host.lock:
            require(isinstance(proofs,list) and 1<=len(proofs)<=100,'INPUT_INVALID')
            for proof in proofs:check('models','ReadProof',proof)
            s = self.host.state() if state is None else state
            current=self.capture(account,state=s,player=proofs[0]['player']);refs={}
            for proof in proofs:
                require(all(proof[k]==current[k] for k in current if k!='refs'),'SOURCE_STALE')
                for ref in proof['refs']:refs[digest(ref)]=ref
            require(len(refs)<=1000,'KNOWLEDGE_LIMIT')
            self._verify_refs(s,account,list(refs.values()),current['player'])
            return True

    def entity_query_allowed(self,s,key,value):
        return all(p['egress']['query']=='filtered' for p in s['knowledge']['policies'].values()
                   if any(self._matches(selector,'entity',key,value) for selector in p['selectors']))

    def require_egress(self,account,egress,*,state=None):
        with self.host.lock:
            s=self.host.state() if state is None else state;member(s,account);self.ready(s)
            require(egress in ('view','query','rules','receipts','assets','export','ai'),'INPUT_INVALID')
            require(all(p['egress'][egress]=='filtered' for p in s['knowledge']['policies'].values()),'PERMISSION_DENIED')

    def authorize_operation(self, s, account, operation, args):
        if not self.strict(s, account):
            return
        self.ready(s)
        context = self._context(s, account)
        for p in s['knowledge']['policies'].values():
            provider = self._provider(p)
            require(p['egress']['rules']=='filtered','PERMISSION_DENIED')
            require(callable(getattr(provider, 'authorize_operation', None)), 'PERMISSION_DENIED')
            require(self._invoke(provider, 'authorize_operation', operation, args, context) is True, 'PERMISSION_DENIED')

    def project_result(self, s, account, operation, result, reads, *, egress='receipts'):
        if not self.strict(s, account):
            return result
        try:
            self.ready(s)
            context = self._context(s, account)
            projected = copy.deepcopy(result)
            for p in s['knowledge']['policies'].values():
                provider = self._provider(p)
                if p['egress'][egress]!='filtered':return None
                if not callable(getattr(provider, 'project_operation', None)):
                    return None
                projected = self._invoke(provider, 'project_operation', operation, projected, reads, context)
                if projected is None:
                    return None
            return projected
        except DomainError:
            return None

    def project_catalog(self, s, account, actions):
        if not self.strict(s, account):
            return actions
        try:
            self.ready(s)
            result = copy.deepcopy(actions)
            for p in s['knowledge']['policies'].values():
                provider = self._provider(p)
                if p['egress']['rules']!='filtered':return []
                if not callable(getattr(provider, 'project_catalog', None)):
                    return []
                result = self._invoke(provider, 'project_catalog', result, self._context(s, account))
            return result
        except DomainError:
            return []
