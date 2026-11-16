"""Confirmed memory is sourced, versioned and re-authorized on every read."""
import copy
import uuid

from onlinecoc.ai_sources import check_sources, check_memory
from onlinecoc.errors import DomainError
from .contracts import validate
from .errors import require


class Memory:
    def __init__(self, proposals):
        self.proposals, self.host, self.repository = proposals, proposals.host, proposals.repository

    def create(self, account, content, sources, *, kind='summary', visibility='kp', valid_until=None):
        with self.host.lock:
            self.host.kp(account)
            state = self.host.state()
            require(bool(sources), 'MEMORY_SOURCE_REQUIRED')
            check_sources(self.host, state, account, sources)
            private = any(s['visibility'] == 'private' for s in sources)
            secret = any(s['visibility'] == 'kp' or (s['kind'] == 'entity' and
                state['entities'][s['id']]['metadata'].get('secret')) for s in sources)
            require(not private or visibility == 'private', 'MEMORY_VISIBILITY_CONFLICT')
            require(not secret or visibility in ('kp', 'private'), 'MEMORY_VISIBILITY_CONFLICT')
            entry = validate('MemoryEntry', {'schemaVersion': 1, 'memoryId': uuid.uuid4().hex,
                'scopeId': state['aiControl']['scopeId'], 'kind': kind, 'content': content, 'sourceRefs': sources,
                'visibility': visibility, 'owner': account, 'status': 'draft', 'validUntil': valid_until,
                'supersedes': None, 'revision': 1, 'createdAt': self.host.clock()})
        self.repository.update(lambda data: data['memory'].update({entry['memoryId']: entry}))
        return entry

    def confirm(self, account, key, revision):
        entry = self.repository.state()['memory'].get(key)
        require(entry and entry['owner'] == account and entry['revision'] == revision and entry['status'] == 'draft', 'MEMORY_STALE')
        with self.host.lock:
            self.host.kp(account)
            state = self.host.state()
            require(entry['scopeId'] == state['aiControl']['scopeId'], 'SCOPE_MISMATCH')
            # Room is authoritative after confirmation. A stale AI-store draft
            # (concurrency or reply loss) must not resurrect a revoked memory.
            require(key not in state['aiControl'].get('memoryFacts', {}), 'MEMORY_STALE')
            check_sources(self.host, state, account, entry['sourceRefs'])
            require(entry['validUntil'] is None or entry['validUntil'] > self.host.clock(), 'MEMORY_EXPIRED')
            entry.update(status='confirmed', revision=revision + 1)
            state['aiControl'].setdefault('memoryFacts', {})[key] = copy.deepcopy(entry)
            self.host.commit(state)
        self.repository.update(lambda data: data['memory'].update({key: entry}))
        return entry

    def revoke(self, account, key, revision):
        with self.host.lock:
            self.host.kp(account)
            state = self.host.state()
            entry = state['aiControl'].get('memoryFacts', {}).get(key)
            require(entry and entry['owner'] == account and entry['revision'] == revision, 'MEMORY_STALE')
            entry.update(status='revoked', revision=revision + 1)
            self.host.commit(state)
        self.repository.update(lambda data: data['memory'].update({key: copy.deepcopy(entry)}))
        return entry

    def search(self, account, query='', limit=20):
        require(isinstance(query, str) and len(query) <= 1000 and type(limit) is int and 1 <= limit <= 100, 'INPUT_INVALID')
        with self.host.lock:
            state = self.host.state()
            from onlinecoc.model import member
            member(state, account)
            results = []
            for entry in state['aiControl'].get('memoryFacts', {}).values():
                if query.casefold() not in entry['content'].casefold():
                    continue
                try:
                    check_memory(self.host, state, account, entry['memoryId'], entry['revision'], set())
                except DomainError:
                    continue
                results.append(copy.deepcopy(entry))
            return sorted(results, key=lambda e: e['createdAt'], reverse=True)[:limit]
