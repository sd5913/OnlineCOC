import time
import uuid
from pathlib import Path

from ..contracts import baseline_digest, candidate_digest, digest, validate
from ..errors import require


def validator_digest():
    from onlinecoc.ai_contracts import validator_digest as host_digest
    return host_digest()


def world_digest(state):
    from onlinecoc.ai_contracts import world_digest as host_digest
    return host_digest(state)


def binding(pack, state, baseline, context):
    validate("ContextSnapshot", context)
    require(context["contractDigest"] == pack.digest and context["validatorSetDigest"] == validator_digest(), "VALIDATOR_STALE")
    require(context["baseRuleset"] == baseline["revision"] and context["configDigest"] == digest(state["configurations"]) and context["worldDigest"] == world_digest(state), "BASELINE_STALE")


def finding(code, message="", path="", source="", evidence=None, severity="error", suggestion=""):
    if isinstance(message, dict):
        path = path or message.get("path", "")
        message = str(message.get("model", "")) + ": " + str(message.get("constraint", code))
    return {"code": code, "severity": severity, "path": path, "sourceRef": source,
            "message": message or code, "evidence": evidence, "suggestion": suggestion}


def report(level, context, changes, status="pass", findings=None, coverage=None, evidence=None, risk="low", review=None):
    value = {"schemaVersion": 1, "reportId": uuid.uuid4().hex, "level": level, "status": status,
        "candidateDigest": candidate_digest(context, changes), "baselineDigest": baseline_digest(context),
        "contextDigest": digest(context), "contractDigest": context["contractDigest"],
        "validatorSetDigest": context["validatorSetDigest"], "coverage": coverage or [],
        "findings": findings or [], "evidence": evidence or {}, "risk": risk,
        "reviewItems": review or [], "createdAt": time.time()}
    return validate("ValidationReport", value)


def static_context(pack, state, artifact, principal="kp", scope="offline-check"):
    return validate("ContextSnapshot", {"schemaVersion": 1, "scopeId": scope, "initiator": principal,
        "reviewPrincipal": principal, "authorityEpoch": "offline", "authorizationEpoch": state["members"][principal]["authorizationEpoch"],
        "baseRuleset": artifact["revision"], "configDigest": digest(state["configurations"]),
        "contractDigest": pack.digest, "validatorSetDigest": validator_digest(), "worldDigest": world_digest(state),
        "sourceRefs": [], "memoryRefs": [], "includedSources": [], "omittedSources": [], "facts": {}, "createdAt": time.time()})
