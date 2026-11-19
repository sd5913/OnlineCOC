"""Independent AI history; never the authority for loaded game state."""
import copy
import threading
import re
from contextlib import contextmanager

from onlinecoc_data import FileDataStore
from .contracts import canonical, validate, digest
from .errors import require


def initial(scope_id):
    return {"schemaVersion": 1, "scopeId": scope_id, "requests": {}, "proposals": {}, "contexts": {},
            "snapshots": {}, "reports": {}, "prepared": {}, "memory": {}, "commands": {}, "dedup": {},
            "budgets": {}, "settings": {}, "tasks": {}}


class Repository:
    def __init__(self, directory, scope_id, *, store_factory=FileDataStore):
        self.lock = threading.RLock()
        self.pending = None
        self.store = store_factory(directory)
        try:
            if self.store.snapshot()[1] is None:
                self.store.commit(0, initial(scope_id))
            state = self.state()
            if "tasks" not in state:
                state["tasks"] = {}
                self.store.commit(self.store.generation, state)
            require(state["schemaVersion"] == 1 and state["scopeId"] == scope_id, "SCOPE_MISMATCH")
            self.verify(state)
            interrupted = False
            for key, command in state['commands'].items():
                if key.startswith('api:') and command.get('receipt', {}).get('status') == 'pending':
                    command['receipt'].update(status='unknown', code='PROCESS_RESTARTED')
                    interrupted = True
            for task in state["tasks"].values():
                if task["status"] in ("queued", "generating", "validating"):
                    task.update(status="interrupted", error="PROCESS_RESTARTED", lease=None)
                    state["requests"][task["requestId"]]["status"] = "interrupted"
                    interrupted = True
            for batch in state['settings'].get('batches',{}).values():
                if batch['status']=='executing':batch['status']='unknown';interrupted=True
            for request in state["requests"].values():
                if request["status"] in ("generating", "validating", "publishing"):
                    request["status"] = "interrupted"
                    interrupted = True
            if interrupted:
                self.commit(state)
        except BaseException:
            self.close()
            raise

    def state(self):
        with self.lock:
            if self.pending is not None:return copy.deepcopy(self.pending)
            return self.store.snapshot()[1]

    @contextmanager
    def transaction(self):
        """Only for self-contained AI-store commands, never host publication."""
        with self.lock:
            require(self.pending is None, 'TRANSACTION_NESTED')
            self.pending = self.store.snapshot()[1]
            initial = self.pending
            try:
                yield
                if self.pending != initial:
                    self.verify(self.pending)
                    self.store.commit(self.store.generation, self.pending)
            finally:self.pending = None

    def verify(self, state):
        canonical(state)
        require(set(state) == set(initial(state["scopeId"])) and state["schemaVersion"] == 1, "SCHEMA_UNSUPPORTED")
        sessions = state['settings'].get('sessions', {})
        from .answers import validate_choices
        for task in state['tasks'].values():
            if task.get('choices') is not None:validate_choices(task['choices'])
        require(type(sessions) is dict and len(sessions) <= 5000, 'SESSION_STATE_INVALID')
        access = state['settings'].get('accessPolicy', {})
        require(type(access) is dict and not set(access)-{'revision','allowPlayerChat','autoApproveBatches','autoApproveConfigurations','principal'}, 'SESSION_STATE_INVALID')
        require(type(access.get('revision',1)) is int and access.get('revision',1)>0 and all(type(access.get(k,False)) is bool for k in ('allowPlayerChat','autoApproveBatches','autoApproveConfigurations')), 'SESSION_STATE_INVALID')
        require(access.get('principal') is None or type(access['principal']) is str, 'SESSION_STATE_INVALID')
        batches=state['settings'].get('batches',{})
        require(type(batches) is dict and len(batches)<=1000,'BATCH_STATE_INVALID')
        for key,batch in batches.items():
            require(type(batch) is dict and key==batch.get('batchId') and re.fullmatch('[a-f0-9]{32}',key) and
                batch.get('status') in ('pending','executing','completed','rejected','partial','unknown') and
                type(batch.get('actions')) is list and 1<=len(batch['actions'])<=8 and type(batch.get('receipts')) is list and
                len(batch['receipts'])<=len(batch['actions']),'BATCH_STATE_INVALID')
            require(batch['digest']==digest({k:batch[k] for k in ('batchId','sessionId','requestId','creator','actions','context','baseline','authorityEpoch')}),'BATCH_STATE_INVALID')
            validate('ContextSnapshot',batch['context'])
        linked = set()
        for key, session in sessions.items():
            required={'sessionId', 'owner', 'title', 'revision', 'archived', 'createdAt', 'updatedAt', 'requestIds'}
            require(type(session) is dict and required <= set(session) <= required | {'pinned','historyTurns','renderMode','showDiagnostics','accessLevel','deleted'}, 'SESSION_STATE_INVALID')
            require(type(session.get('pinned',False)) is bool and type(session.get('showDiagnostics',True)) is bool and
                    type(session.get('historyTurns',4)) is int and 0<=session.get('historyTurns',4)<=4 and
                    session.get('renderMode','formatted') in ('formatted','plain'), 'SESSION_STATE_INVALID')
            require(re.fullmatch('[a-f0-9]{32}', key) and session['sessionId'] == key and
                type(session['owner']) is str and session['owner'] and type(session['title']) is str and 1 <= len(session['title'].strip()) <= 120 and
                type(session['revision']) is int and session['revision'] >= 1 and type(session['archived']) is bool and
                all(type(session[k]) in (int, float) and session[k] >= 0 for k in ('createdAt', 'updatedAt')), 'SESSION_STATE_INVALID')
            require(session.get('accessLevel', 'player') in ('administrator','player') and type(session.get('deleted',False)) is bool, 'SESSION_STATE_INVALID')
            ids = session['requestIds']
            require(type(ids) is list and len(ids) <= 100 and all(type(i) is str for i in ids) and len(ids) == len(set(ids)), 'SESSION_STATE_INVALID')
            require(not linked.intersection(ids) and all(i in state['requests'] and state['requests'][i]['initiator'] == session['owner'] and
                state['requests'][i]['sourceKind'] == 'manual' for i in ids), 'REFERENCE_CONFLICT')
            linked.update(ids)
        for group, kind in (("requests", "Request"), ("contexts", "ContextSnapshot"), ("reports", "ValidationReport"), ("prepared", "PreparedBundle"), ("memory", "MemoryEntry")):
            require(type(state[group]) is dict and len(state[group]) <= 5000, "LIMIT_EXCEEDED")
            for value in state[group].values():
                validate(kind, value)
                if "scopeId" in value:
                    require(value["scopeId"] == state["scopeId"], "SCOPE_MISMATCH")
        for record in state["proposals"].values():
            require(str(record["currentRevision"]) in record["revisions"], "PROPOSAL_STALE")
            for proposal in record["revisions"].values():
                validate("Proposal", proposal)
                require(proposal["scopeId"] == state["scopeId"] and proposal["contextRef"] in state["contexts"] and proposal["contextRef"] in state["snapshots"] and proposal["requestId"] in state["requests"], "REFERENCE_CONFLICT")
                require(set(proposal["reportRefs"]) <= set(state["reports"]), "REFERENCE_CONFLICT")
        for key, bundle in state["prepared"].items():
            require(key == f'{bundle["proposalId"]}:{bundle["proposalRevision"]}' and bundle["proposalId"] in state["proposals"], "REFERENCE_CONFLICT")
            proposal = state["proposals"][bundle["proposalId"]]["revisions"].get(str(bundle["proposalRevision"]))
            require(proposal and proposal["candidateDigest"] == bundle["candidateDigest"] and proposal["changeSet"] == bundle["changeSet"] and
                    state["contexts"][proposal["contextRef"]] == bundle["context"] and proposal["reportRefs"] == [r["reportId"] for r in bundle["reports"]], "REFERENCE_CONFLICT")
            require(all(state["reports"].get(r["reportId"]) == r for r in bundle["reports"]), "REFERENCE_CONFLICT")

    def commit(self, state):
        with self.lock:
            if self.pending is not None:
                self.pending = copy.deepcopy(state)
                return self.store.generation
            self.verify(state)
            return self.store.commit(self.store.generation, state)

    def update(self, mutation):
        with self.lock:
            state = self.state()
            result = mutation(state)
            self.commit(state)
            return copy.deepcopy(result)

    def close(self):
        self.store.close()
