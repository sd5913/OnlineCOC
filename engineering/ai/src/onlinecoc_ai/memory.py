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

    def transition_fact(self, account, key, revision, status):
        """Prepare one authorized next fact without writing either store."""
        require(status in ('confirmed','revoked'),'INPUT_INVALID')
        with self.host.lock:
            self.host.kp(account);state=self.host.state()
            if status=='revoked':
                entry=copy.deepcopy(state['aiControl'].get('memoryFacts',{}).get(key))
                require(entry and entry['owner']==account and entry['revision']==revision,'MEMORY_STALE')
                entry.update(status='revoked',revision=revision+1)
                return entry,revision
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
            return entry,0

    def transition(self, account, key, revision, status, *, command_id=None):
        command_id=command_id or 'ai-memory:'+uuid.uuid4().hex
        with self.host.lock:
            self.host.kp(account)
            receipt=self.host.receipt(account,command_id)
            if receipt['status']!='committed':
                require(receipt['status']=='unknown','MEMORY_RESULT_UNKNOWN')
                fact,expected=self.transition_fact(account,key,revision,status)
                receipt=self.host.commit_memory_fact(account,fact,command_id=command_id,expected_revision=expected)
            require(receipt['status']=='committed',receipt.get('code','MEMORY_RESULT_UNKNOWN'))
            fact=receipt.get('result',{}).get('memory')
            require(fact and fact['memoryId']==key and fact['owner']==account and fact['status']==status,'MEMORY_RESULT_UNKNOWN')
            self.mirror_fact(fact)
            return fact

    def mirror_fact(self,fact):
        """An older successful receipt cannot overwrite a later revocation."""
        current=self.host.state()['aiControl'].get('memoryFacts',{}).get(fact['memoryId'])
        require(current and current['owner']==fact['owner'] and current['revision']>=fact['revision'],'MEMORY_RESULT_UNKNOWN')
        self.repository.update(lambda data:data['memory'].update({fact['memoryId']:copy.deepcopy(current)}))

    def confirm(self,account,key,revision,*,command_id=None):
        return self.transition(account,key,revision,'confirmed',command_id=command_id)

    def revoke(self,account,key,revision,*,command_id=None):
        return self.transition(account,key,revision,'revoked',command_id=command_id)

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
