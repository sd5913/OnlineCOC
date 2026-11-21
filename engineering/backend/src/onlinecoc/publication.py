"""Small host transactions. No Lua, model network call or AI-store access here."""
import copy
import uuid

from .ai_contracts import (approval_digest, baseline_digest, candidate_digest, digest, validate_ai,
                           validate_artifact, validate_bundle, validate_c_assessment, validator_digest, world_digest)
from .errors import require
from .model import member


def consultation_source_digest(context):
    """Bind KP acceptance to the exact source evidence, not a UI boolean."""
    return digest(context)


def consultation_assessment(context):
    foreign={digest(row['ref']) for proof in context['facts'].get('dataQueries',[]) for row in proof.get('readRefs',[])
             if row['ref']['sourceId'] not in ('host','host-room','host-room-state')}
    return {'requiresAcceptance':bool(foreign or context['facts'].get('consultationOnly')),
            'sourceCount':len(foreign),'sourceDigest':consultation_source_digest(context),
            'notice':'独立包资料用于方案依据，可能不具备跨存储原子保证。请核对当前目标、完整变更及检查结果后决定；摘要或资料本身不授权执行。'}


def check_consultation_review(context, decisions, review):
    assessment=consultation_assessment(context)
    if assessment['requiresAcceptance']:
        require(len(decisions.get('consultation-source','').strip())>=3,'RISK_REVIEW_REQUIRED')
        require(review=={'sourceDigest':assessment['sourceDigest']},'CONSULTATION_REVIEW_REQUIRED')
    elif review is not None:
        require(review=={'sourceDigest':assessment['sourceDigest']},'DIGEST_MISMATCH')
    return assessment


def is_high_risk(state, changes, contract):
    current = state['artifacts'][state['activeRuleset']]
    if changes['sources'] != current['sources'] or changes['data'] != current['data']:
        return True
    policy = contract.get('highRisk', {})
    identifiers = set(policy.get('configurationIds', []))
    prefixes = tuple(policy.get('configurationPrefixes', []))
    for change in changes['configurations']:
        value = change.get('value') or state['configurations'].get(change['id'], {})
        if (change['kind'] == 'remove' or value.get('typeRef') in ('item', 'weapon', 'bag')
                or change['id'] in identifiers or (prefixes and change['id'].startswith(prefixes))):
            return True
    return False


def candidate_configurations(state, changes, artifact):
    """Validate the entire resulting graph before staging or publishing it.

    Existing instances keep their own values/revisions. Deletes never cascade,
    including references held by archived instances. In-flight flows keep their
    original artifact; only current object bindings target the new artifact.
    """
    from .contracts import validate_model
    from .registry import check_graph
    configurations = copy.deepcopy(state['configurations'])
    seen = set()
    for change in changes['configurations']:
        key, kind = change['id'], change['kind']
        require(key not in seen, 'AI_INPUT_INVALID'); seen.add(key)
        old = configurations.get(key)
        if kind == 'add':
            require(old is None and change['expectedRevision'] is None, 'VERSION_CONFLICT')
        else:
            require(kind in ('replace', 'remove'), 'AI_INPUT_INVALID')
            require(old is not None and old['revision'] == change['expectedRevision'], 'VERSION_CONFLICT')
        if kind == 'remove':
            require(not any(e['configurationId'] == key for e in state['entities'].values()), 'REFERENCE_CONFLICT')
            del configurations[key]
            continue
        value = change['value']
        validate_model('Configuration', value)
        require(value['configurationId'] == key, 'AI_INPUT_INVALID')
        if old:
            require(value['typeRef'] == old['typeRef'], 'REFERENCE_CONFLICT')
            require(value['revision'] != old['revision'], 'VERSION_CONFLICT')
        configurations[key] = copy.deepcopy(value)
    metadata = artifact['metadata']
    check_graph({key:list(value.get('dependencies', [])) for key,value in metadata.items()})
    for configuration in configurations.values():
        for binding in configuration.get('behaviors', {}).values():
            require(binding['ruleId'] in metadata, 'REFERENCE_CONFLICT')
    for entity in state['entities'].values():
        require(entity['configurationId'] in configurations, 'REFERENCE_CONFLICT')
        for binding in entity.get('rules', {}).values():
            require(binding['ruleId'] in metadata, 'REFERENCE_CONFLICT')
    return configurations


def check_context(host, state, account, context):
    """Validate current execution/approval authority, including the host epoch."""
    _check_context(host, state, account, context, history=False)


def check_history_context(host, state, account, context):
    """Revalidate persisted read-only evidence without renewing execution authority.

    Call under the host lock with its current state. A process restart or a
    changed execution validator does not revoke read access. All principal,
    scope, contract, baseline and source checks still apply. Neither the old
    context nor the room is rewritten; success is not approval to execute it.
    """
    validate_ai('ContextSnapshot', context)
    _check_context(host, state, account, context, history=True)


def _check_context(host, state, account, context, *, history):
    control = state["aiControl"]
    if context.get('facts',{}).get('strictPlayer'):
        facts=context['facts']; access=facts.get('sessionAccess',{})
        require(access.get('level')=='player' and access.get('owner')==context['reviewPrincipal'],'PERMISSION_DENIED')
        owner=access['owner']; m=member(state,owner); member(state,account)
        require(context['authorizationEpoch']==m['authorizationEpoch'],'PERMISSION_DENIED')
        require(context['scopeId']==control['scopeId'],'SCOPE_MISMATCH')
        if not history:
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
    if not history:
        require(context["authorityEpoch"] == host.epoch, "STALE_AUTHORITY")
    binding = control["packBinding"]
    require(binding and context["contractDigest"] == binding["digest"], "VALIDATOR_STALE")
    if not history:
        require(context["validatorSetDigest"] == binding["validatorSetDigest"] == validator_digest(), "VALIDATOR_STALE")
    require(context["baseRuleset"] == state["activeRuleset"] and context["configDigest"] == digest(state["configurations"]) and
            context["worldDigest"] == world_digest(state), "BASELINE_STALE")
    # Source checks live in the host and do not require an open AI repository.
    host.validate_ai_sources(state, account, context)


def check_c_basis(host, bundle, c_review=None):
    proof = validate_c_assessment(bundle)
    resolver = host.ai_c_basis_resolver
    if proof is None:
        require(resolver is None, 'C_BASIS_STALE')
        require(c_review is None, 'DIGEST_MISMATCH')
        return
    require(resolver is not None, 'AI_SERVICE_UNAVAILABLE')
    current = resolver()
    require(current == {key:proof[key] for key in ('basisRevision','basisDigest')}, 'C_BASIS_STALE')
    if bundle['cAssessment']['requiresAcceptance']:
        require(c_review == proof, 'C_REVIEW_REQUIRED')
    elif c_review is not None:
        require(c_review == proof, 'DIGEST_MISMATCH')


def approve(host, state, account, args, prepared):
    require(prepared is not None, "AI_SERVICE_UNAVAILABLE")
    validate_bundle(prepared)
    check_c_basis(host, prepared, args.get('cReview'))
    facts=prepared['context']['facts']
    require(not facts.get('strictPlayer') and facts.get('sessionAccess',{}).get('level')!='player', 'CONSULTATION_ONLY')
    require(prepared["proposalId"] == args["proposalId"] and prepared["proposalRevision"] == args["proposalRevision"], "PROPOSAL_STALE")
    control = state["aiControl"]
    require(control["proposalHeads"].get(args["proposalId"]) == args["proposalRevision"], "PROPOSAL_STALE")
    check_context(host, state, account, prepared["context"])
    candidate_configurations(state, prepared['changeSet'], prepared['artifact'])
    high_risk = is_high_risk(state, prepared['changeSet'], control['packBinding']['contract'])
    if high_risk:
        require(args.get('explicitHighRiskDigest') == prepared['candidateDigest'], 'HIGH_RISK_REVIEW_REQUIRED')
    elif 'explicitHighRiskDigest' in args:
        require(args['explicitHighRiskDigest'] == prepared['candidateDigest'], 'DIGEST_MISMATCH')
    policy = control["packBinding"]["contract"]["reviewPolicy"]
    items = {item["id"]: item for item in policy["items"]}
    needed = {key for key, value in items.items() if value["required"]}
    allowed = set(items)
    if consultation_assessment(prepared['context'])['requiresAcceptance']:
        needed.add('consultation-source');allowed.add('consultation-source')
    if high_risk:
        needed.add('high-risk'); allowed.add('high-risk')
    if any(r["risk"] in ("medium", "high", "unknown") for r in prepared["reports"]) or prepared.get('cAssessment',{}).get('requiresAcceptance'):
        needed.add("gameplay-risk")
        allowed.add("gameplay-risk")
    decisions = args["riskDecisions"]
    require(needed <= set(decisions) <= allowed and all(len(value.strip()) >= 3 for value in decisions.values()), "RISK_REVIEW_REQUIRED")
    consultation=check_consultation_review(prepared['context'],decisions,args.get('consultationReview'))
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
    if high_risk:
        value['explicitHighRiskDigest'] = args['explicitHighRiskDigest']
    for key in ('cAssessment',):
        if key in prepared:value[key] = copy.deepcopy(prepared[key])
    if 'cReview' in args:value['cReview'] = copy.deepcopy(args['cReview'])
    if consultation['requiresAcceptance'] or 'consultationReview' in args:
        value['consultationAssessment']=consultation
        value['consultationReview']=copy.deepcopy(args['consultationReview'])
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
    facts=approval['context']['facts']
    require(not facts.get('strictPlayer') and facts.get('sessionAccess',{}).get('level')!='player','CONSULTATION_ONLY')
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
    if 'cAssessment' in approval:bundle['cAssessment'] = copy.deepcopy(approval['cAssessment'])
    validate_bundle(bundle)
    check_c_basis(host, bundle, approval.get('cReview'))
    consultation=check_consultation_review(approval['context'],approval['riskDecisions'],approval.get('consultationReview'))
    if 'consultationAssessment' in approval:
        require(approval['consultationAssessment']==consultation,'DIGEST_MISMATCH')
    if bundle.get('cAssessment',{}).get('requiresAcceptance'):
        require(len(approval['riskDecisions'].get('gameplay-risk','').strip()) >= 3, 'RISK_REVIEW_REQUIRED')
    require(approval["contextDigest"] == digest(approval["context"]) and approval["contractDigest"] == approval["context"]["contractDigest"] and
            approval["validatorSetDigest"] == approval["context"]["validatorSetDigest"], "DIGEST_MISMATCH")
    check_context(host, state, account, approval["context"])
    if is_high_risk(state, approval['changeSet'], control['packBinding']['contract']):
        require(approval.get('explicitHighRiskDigest') == approval['candidateDigest'], 'HIGH_RISK_REVIEW_REQUIRED')
        require(len(approval['riskDecisions'].get('high-risk', '').strip()) >= 3, 'RISK_REVIEW_REQUIRED')
    previous = state["activeRuleset"]
    configurations = candidate_configurations(state, approval['changeSet'], artifact)
    revisions = {}
    for change in approval["changeSet"]["configurations"]:
        if change['kind'] == 'remove':
            del state['configurations'][change['id']]
            revisions[change['id']] = None
        else:
            state['configurations'][change['id']] = configurations[change['id']]
            revisions[change['id']] = change['value']['revision']
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
