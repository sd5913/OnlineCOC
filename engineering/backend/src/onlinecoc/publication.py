"""Small host transactions. No Lua, model network call or AI-store access here."""
import copy
import uuid

from .ai_contracts import (approval_digest, baseline_digest, candidate_digest, digest, validate_ai,
                           validate_artifact, validate_bundle, validator_digest, world_digest)
from .errors import require
from .model import member


def check_context(host, state, account, context):
    control = state["aiControl"]
    if context.get('facts',{}).get('strictPlayer'):
        facts=context['facts']; access=facts.get('sessionAccess',{})
        require(access.get('level')=='player' and access.get('owner')==context['reviewPrincipal'],'PERMISSION_DENIED')
        owner=access['owner']; m=member(state,owner); member(state,account)
        require(context['authorizationEpoch']==m['authorizationEpoch'],'PERMISSION_DENIED')
        require(context['scopeId']==control['scopeId'],'SCOPE_MISMATCH')
        require(context['authorityEpoch']==host.epoch,'STALE_AUTHORITY')
        binding=control['packBinding']
        require(binding and context['contractDigest']==binding['digest'],'SOURCE_STALE')
        proofs=facts.get('knowledgeProofs')
        require(isinstance(proofs,list) and 1<=len(proofs)<=100,'SOURCE_STALE')
        for proof in proofs:
            require(proof.get('accountId')==owner and proof.get('player') is True,'PERMISSION_DENIED')
        host.knowledge.recheck_many(owner,proofs,state=state)
        host.validate_ai_sources(state,owner,context)
        return
    m = member(state, account)
    require(m["role"] == "kp" and context["reviewPrincipal"] == account, "PERMISSION_DENIED")
    require(context["authorizationEpoch"] == m["authorizationEpoch"], "PERMISSION_DENIED")
    require(context["scopeId"] == control["scopeId"], "SCOPE_MISMATCH")
    require(context["authorityEpoch"] == host.epoch, "STALE_AUTHORITY")
    binding = control["packBinding"]
    require(binding and context["contractDigest"] == binding["digest"] and
            context["validatorSetDigest"] == binding["validatorSetDigest"] == validator_digest(), "VALIDATOR_STALE")
    require(context["baseRuleset"] == state["activeRuleset"] and context["configDigest"] == digest(state["configurations"]) and
            context["worldDigest"] == world_digest(state), "BASELINE_STALE")
    # Source checks live in the host and do not require an open AI repository.
    host.validate_ai_sources(state, account, context)


def approve(host, state, account, args, prepared):
    require(prepared is not None, "AI_SERVICE_UNAVAILABLE")
    validate_bundle(prepared)
    require(not prepared['context']['facts'].get('consultationOnly') and not prepared['context']['facts'].get('strictPlayer'), 'CONSULTATION_ONLY')
    require(prepared["proposalId"] == args["proposalId"] and prepared["proposalRevision"] == args["proposalRevision"], "PROPOSAL_STALE")
    control = state["aiControl"]
    require(control["proposalHeads"].get(args["proposalId"]) == args["proposalRevision"], "PROPOSAL_STALE")
    check_context(host, state, account, prepared["context"])
    policy = control["packBinding"]["contract"]["reviewPolicy"]
    items = {item["id"]: item for item in policy["items"]}
    needed = {key for key, value in items.items() if value["required"]}
    allowed = set(items)
    if any(r["risk"] in ("medium", "high", "unknown") for r in prepared["reports"]):
        needed.add("gameplay-risk")
        allowed.add("gameplay-risk")
    decisions = args["riskDecisions"]
    require(needed <= set(decisions) <= allowed and all(len(value.strip()) >= 3 for value in decisions.values()), "RISK_REVIEW_REQUIRED")
    identifier = uuid.uuid4().hex
    context = prepared["context"]
    value = {"schemaVersion": 1, "approvalId": identifier, "proposalId": prepared["proposalId"],
        "proposalRevision": prepared["proposalRevision"], "scopeId": control["scopeId"],
        "candidateDigest": prepared["candidateDigest"], "baselineDigest": prepared["baselineDigest"],
        "contextDigest": digest(context), "contractDigest": context["contractDigest"], "validatorSetDigest": context["validatorSetDigest"],
        "reviewer": account, "riskDecisions": copy.deepcopy(decisions), "expiresAt": host.clock() + policy["approvalTtlSeconds"],
        "status": "approved", "artifactRevision": prepared["artifact"]["revision"],
        "changeSet": copy.deepcopy(prepared["changeSet"]), "context": copy.deepcopy(context),
        "reports": copy.deepcopy(prepared["reports"]), "createdAt": host.clock()}
    value["approvalDigest"] = approval_digest(value)
    validate_ai("Approval", value)
    state["artifacts"][value["artifactRevision"]] = copy.deepcopy(prepared["artifact"])
    control["approvals"][identifier] = value
    return {"approvalId": identifier, "expiresAt": value["expiresAt"], "candidateDigest": value["candidateDigest"]}


def revoke(state, account, args):
    require(member(state, account)["role"] == "kp", "PERMISSION_DENIED")
    approval = state["aiControl"]["approvals"].get(args["approvalId"])
    require(approval is not None, "NOT_VISIBLE")
    require(approval["status"] != "consumed", "ALREADY_PUBLISHED")
    approval["status"] = "revoked"
    return {"approvalId": args["approvalId"], "status": "revoked"}


def apply(host, state, account, args, command_id):
    control = state["aiControl"]
    require(member(state, account)["role"] == "kp", "PERMISSION_DENIED")
    approval = control["approvals"].get(args["approvalId"])
    require(approval is not None and approval["reviewer"] == account, "NOT_VISIBLE")
    require(not approval['context']['facts'].get('strictPlayer'),'CONSULTATION_ONLY')
    if approval["status"] == "consumed":
        publication = next(p for p in control["publications"].values() if p["approvalId"] == approval["approvalId"])
        return copy.deepcopy(publication)
    require(approval["status"] == "approved", "APPROVAL_REVOKED")
    require(approval["approvalDigest"] == approval_digest(approval), "DIGEST_MISMATCH")
    require(host.clock() < approval["expiresAt"], "APPROVAL_EXPIRED")
    require(control["proposalHeads"].get(approval["proposalId"]) == approval["proposalRevision"], "PROPOSAL_STALE")
    artifact = state["artifacts"].get(approval["artifactRevision"])
    require(artifact is not None, "ARTIFACT_MISSING")
    bundle = {k: copy.deepcopy(approval[k]) for k in ("schemaVersion", "proposalId", "proposalRevision", "scopeId", "context", "changeSet", "reports", "candidateDigest", "baselineDigest", "createdAt")}
    bundle["artifact"] = artifact
    validate_bundle(bundle)
    require(approval["contextDigest"] == digest(approval["context"]) and approval["contractDigest"] == approval["context"]["contractDigest"] and
            approval["validatorSetDigest"] == approval["context"]["validatorSetDigest"], "DIGEST_MISMATCH")
    check_context(host, state, account, approval["context"])
    previous = state["activeRuleset"]
    revisions = {}
    for change in approval["changeSet"]["configurations"]:
        old = state["configurations"].get(change["id"])
        require((old is None if change["kind"] == "add" else old and old["revision"] == change["expectedRevision"] and
                old["typeRef"] == change["value"]["typeRef"] and old["revision"] != change["value"]["revision"]), "VERSION_CONFLICT")
        for ref in change["value"].get("behaviors", {}).values():
            require(ref["ruleId"] in artifact["metadata"], "REFERENCE_CONFLICT")
        state["configurations"][change["id"]] = copy.deepcopy(change["value"])
        revisions[change["id"]] = change["value"]["revision"]
        host.hit("after_publication_configuration")
    state["activeRuleset"] = artifact["revision"]
    approval["status"] = "consumed"
    identifier = uuid.uuid4().hex
    publication = {"schemaVersion": 1, "publicationId": identifier, "approvalId": approval["approvalId"], "scopeId": control["scopeId"],
        "commandId": command_id, "accountId": account, "candidateDigest": approval["candidateDigest"], "previousRuleset": previous,
        "ruleset": artifact["revision"], "configurationRevisions": revisions, "createdAt": host.clock()}
    validate_ai("Publication", publication)
    control["publications"][identifier] = publication
    return copy.deepcopy(publication)
