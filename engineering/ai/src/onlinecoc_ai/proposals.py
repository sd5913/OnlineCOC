"""Manual proposal workflow, reused later by the provider coordinator."""
import copy
import time
import uuid

from onlinecoc.publication import check_context
from .contracts import baseline_digest, candidate_digest, digest, validate
from .errors import require
from .pack import merge_changes
from .repository import Repository
from .validation.base import check_base
from .validation.common import validator_digest, world_digest
from .validation.gameplay import assess
from .validation.rules import check_rules


class Proposals:
    def __init__(self, host, pack, directory=None, *, repository=None):
        self.host, self.pack = host, pack
        self.repository = repository or Repository(directory or host.path / "ai", host.state()["aiControl"]["scopeId"])
        try:
            host.register_ai(self.prepared, {"contract": pack.contract, "digest": pack.digest, "validatorSetDigest": validator_digest()})
            self.reconcile()
        except BaseException:
            self.repository.close()
            raise

    def snapshot(self, account):
        with self.host.lock:
            self.host.kp(account)
            room = self.host.state()
            # No chat messages or sessions enter these local validation snapshots.
            fields = ("schemaVersion", "roomId", "entities", "relations", "members", "configurations", "progress", "flows", "waits", "collectionRevision")
            state = {key: copy.deepcopy(room[key]) for key in fields}
            artifact = room["artifacts"][room["activeRuleset"]]
            context = validate("ContextSnapshot", {"schemaVersion": 1, "scopeId": room["aiControl"]["scopeId"],
                "initiator": account, "reviewPrincipal": account, "authorityEpoch": self.host.epoch,
                "authorizationEpoch": room["members"][account]["authorizationEpoch"], "baseRuleset": artifact["revision"],
                "configDigest": digest(room["configurations"]), "contractDigest": self.pack.digest,
                "validatorSetDigest": validator_digest(), "worldDigest": world_digest(room),
                "sourceRefs": [], "memoryRefs": [], "includedSources": [], "omittedSources": [], "facts": {}, "createdAt": self.host.clock()})
            return context, state, artifact

    def create(self, account, text, delta, *, summary="人工配置草稿", snapshot=None, request=None, profile=None):
        from .access import policy
        require(policy(self.repository)['allowConfigurationChanges'], 'CONFIGURATION_CHANGES_DISABLED')
        context, state, artifact = snapshot or self.snapshot(account)
        from .history import require_current_evidence
        require_current_evidence(context,{'kind':'draft'})
        with self.host.lock:
            check_context(self.host, self.host.state(), account, context)
        changes = merge_changes(artifact, delta)
        request_id, proposal_id = (request["requestId"] if request else uuid.uuid4().hex), uuid.uuid4().hex
        request = request or validate("Request", {"schemaVersion": 1, "requestId": request_id, "scopeId": context["scopeId"],
            "sourceKind": "manual", "sourceId": request_id, "sourceRevision": "1", "initiator": account,
            "text": text, "intent": "configure", "dedupKey": digest({"scopeId": context["scopeId"], "sourceKind": "manual", "sourceId": request_id, "revision": "1"}), "status": "received", "createdAt": self.host.clock()})
        proposal = self._proposal(proposal_id, 1, request_id, context, changes, summary)
        if profile:
            proposal.update(profileRevision=str(profile["revision"]), model=profile["model"])
        self.host.ai_proposal_head(account, proposal_id, 1)
        def save(store):
            store["requests"][request_id] = request
            store["proposals"][proposal_id] = {"currentRevision": 1, "revisions": {"1": proposal}}
            self._save_snapshot(store, proposal, context, state, artifact)
            return proposal
        return self.repository.update(save)

    def _proposal(self, proposal_id, revision, request_id, context, changes, summary):
        return validate("Proposal", {"schemaVersion": 1, "proposalId": proposal_id, "revision": revision, "requestId": request_id,
            "scopeId": context["scopeId"], "contextRef": digest(context), "profileRevision": None, "model": None,
            "summary": summary, "alternatives": [], "changeSet": changes, "candidateDigest": candidate_digest(context, changes),
            "reportRefs": [], "status": "draft", "createdAt": self.host.clock()})

    def _save_snapshot(self, store, proposal, context, state, artifact):
        store["contexts"][proposal["contextRef"]] = context
        store["snapshots"][proposal["contextRef"]] = {"state": state, "artifact": artifact}

    def get(self, account, proposal_id, revision=None):
        with self.host.lock:
            self.host.kp(account)
        state = self.repository.state()
        record = state["proposals"].get(proposal_id)
        require(record is not None, "NOT_VISIBLE")
        proposal = record["revisions"].get(str(revision or record["currentRevision"]))
        require(proposal is not None, "NOT_VISIBLE")
        context = state["contexts"][proposal["contextRef"]]
        require(context["reviewPrincipal"] == account, "PERMISSION_DENIED")
        with self.host.lock:
            current = self.host.state()
            require(current["aiControl"]["scopeId"] == proposal["scopeId"], "SCOPE_MISMATCH")
            self.host.validate_ai_sources(current, account, context)
        return proposal

    def revise(self, account, proposal_id, expected_revision, delta, *, summary="修订配置草稿", snapshot=None):
        from .access import policy
        require(policy(self.repository)['allowConfigurationChanges'], 'CONFIGURATION_CHANGES_DISABLED')
        old = self.get(account, proposal_id)
        require(old["revision"] == expected_revision, "PROPOSAL_STALE")
        context, state, artifact = snapshot or self.snapshot(account)
        original_context = self.repository.state()['contexts'][old['contextRef']]
        if snapshot is None:
            for key in ('sourceRefs', 'memoryRefs', 'includedSources', 'omittedSources', 'facts'):
                context[key] = copy.deepcopy(original_context[key])
        with self.host.lock:check_context(self.host,self.host.state(),account,context)
        proposal = self._proposal(proposal_id, expected_revision + 1, old["requestId"], context, merge_changes(artifact, delta), summary)
        # Revoke before accepting an edit. A repository failure may leave a
        # conservative revoked approval, but never a publishable superseded one.
        self.host.ai_proposal_head(account, proposal_id, proposal["revision"])
        def save(store):
            record = store["proposals"][proposal_id]
            require(record["currentRevision"] == expected_revision, "PROPOSAL_STALE")
            record["currentRevision"] = proposal["revision"]
            record["revisions"][str(proposal["revision"])] = proposal
            self._save_snapshot(store, proposal, context, state, artifact)
            store["requests"][old["requestId"]]["status"] = "received"
            return proposal
        return self.repository.update(save)

    def validate(self, account, proposal_id, revision):
        proposal = self.get(account, proposal_id, revision)
        store = self.repository.state()
        require(store["proposals"][proposal_id]["currentRevision"] == revision, "PROPOSAL_STALE")
        context = store["contexts"][proposal["contextRef"]]
        snapshot = store["snapshots"][proposal["contextRef"]]
        args = (self.pack, snapshot["state"], snapshot["artifact"], context, proposal["changeSet"])
        # All potentially long-running operations happen without the Host lock.
        a, artifact = check_base(*args)
        reports = [a, check_rules(*args), assess(*args)]
        passed = all(r["status"] == "pass" for r in reports)
        bundle = None
        if passed:
            bundle = validate("PreparedBundle", {"schemaVersion": 1, "proposalId": proposal_id, "proposalRevision": revision,
                "scopeId": context["scopeId"], "context": context, "changeSet": proposal["changeSet"], "artifact": artifact,
                "reports": reports, "candidateDigest": proposal["candidateDigest"], "baselineDigest": baseline_digest(context), "createdAt": self.host.clock()})
        def save(current):
            record = current["proposals"][proposal_id]
            require(current["requests"][proposal["requestId"]]["status"] not in ("cancelled", "interrupted"), "CANCELLED")
            require(record["currentRevision"] == revision, "PROPOSAL_STALE")
            value = record["revisions"][str(revision)]
            for report in reports:
                current["reports"][report["reportId"]] = report
            value["reportRefs"] = [r["reportId"] for r in reports]
            value["status"] = "review_ready" if passed else "blocked"
            current["requests"][value["requestId"]]["status"] = value["status"]
            if bundle:
                current["prepared"][f"{proposal_id}:{revision}"] = bundle
            else:
                current["prepared"].pop(f"{proposal_id}:{revision}", None)
            return {"proposal": value, "reports": reports}
        return self.repository.update(save)

    def prepared(self, account, proposal_id, revision):
        from .access import policy
        require(policy(self.repository)['allowConfigurationChanges'], 'CONFIGURATION_CHANGES_DISABLED')
        proposal = self.get(account, proposal_id, revision)
        state = self.repository.state()
        require(state['requests'][proposal['requestId']]['status'] not in ('cancelled', 'interrupted'), 'REQUEST_CANCELLED')
        require(state["proposals"][proposal_id]["currentRevision"] == revision and proposal["status"] == "review_ready", "PROPOSAL_STALE")
        bundle = state["prepared"].get(f"{proposal_id}:{revision}")
        require(bundle is not None, "CHECKS_INCOMPLETE")
        return validate("PreparedBundle", bundle)

    def reconcile(self):
        with self.host.lock:
            publications = self.host.state()["aiControl"]["publications"]
            approvals = self.host.state()["aiControl"]["approvals"]
        def update(state):
            for publication in publications.values():
                approval = approvals[publication["approvalId"]]
                record = state["proposals"].get(approval["proposalId"])
                if record and str(approval["proposalRevision"]) in record["revisions"]:
                    proposal = record["revisions"][str(approval["proposalRevision"])]
                    proposal["status"] = "published"
                    state["requests"][proposal["requestId"]]["status"] = "published"
        before = self.repository.state()
        after = copy.deepcopy(before)
        update(after)
        if after != before:
            self.repository.commit(after)

    def close(self):
        if self.host.ai_prepared_resolver == self.prepared:
            self.host.ai_prepared_resolver = None
        self.repository.close()
