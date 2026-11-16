"""Host-owned AI trust checks, with no provider/repository/framework dependency."""
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from onlinecoc_data import canonical
from .errors import DomainError, require

ROOT = Path(__file__).resolve().parents[3]
AI = json.loads((ROOT / "contracts/ai.json").read_text(encoding="utf-8"))
VALIDATORS = {name: Draft202012Validator({"$ref": "#/$defs/" + name, "$defs": AI["$defs"]}, format_checker=FormatChecker()) for name in AI["$defs"]}


def validate_ai(kind, value):
    try:
        canonical(value)
        VALIDATORS[kind].validate(value)
    except Exception as exc:
        raise DomainError("AI_INPUT_INVALID") from exc


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def world_digest(state):
    return digest({k: state.get(k, {}) for k in ("schemaVersion", "roomId", "entities", "relations", "members", "progress", "flows", "waits", "collectionRevision")})


def baseline_digest(context):
    return digest({k: context[k] for k in ("scopeId", "baseRuleset", "configDigest", "contractDigest", "validatorSetDigest", "worldDigest")})


def candidate_digest(context, changes):
    return digest({"scopeId": context["scopeId"], "baseRuleset": context["baseRuleset"], "contractDigest": context["contractDigest"], "changeSet": changes})


def approval_digest(approval):
    return digest({k: v for k, v in approval.items() if k not in ("status", "approvalDigest")})


def validator_digest():
    directory = ROOT / "ai/src/onlinecoc_ai/validation"
    files = {p.name: p.read_text(encoding="utf-8") for p in sorted(directory.glob("*.py"))}
    for name in ("pack.py", "sandbox.py", "contracts.py"):
        files[name] = (directory.parent / name).read_text(encoding="utf-8")
    for name in ("lua_runtime.py", "worker_process.py", "worker_entry.py", "registry.py", "execution.py", "model.py", "contracts.py", "version.py", "room_lifecycle.py", "ai_contracts.py", "ai_sources.py", "data_queries.py", "data_adapter.py"):
        files["host/" + name] = Path(__file__).with_name(name).read_text(encoding="utf-8")
    for name in ("models.json", "ai.json", "operations.json", "ai-operations.json"):
        files["contracts/" + name] = (ROOT / "contracts" / name).read_text(encoding="utf-8")
    return digest(files)


def validate_artifact(artifact):
    validate_ai("Artifact", artifact)
    require(digest({k: v for k, v in artifact.items() if k != "revision"}) == artifact["revision"], "DIGEST_MISMATCH")


def validate_bundle(bundle):
    validate_ai("PreparedBundle", bundle)
    context, changes = bundle["context"], bundle["changeSet"]
    require(bundle["scopeId"] == context["scopeId"] and bundle["baselineDigest"] == baseline_digest(context), "DIGEST_MISMATCH")
    require(bundle["candidateDigest"] == candidate_digest(context, changes), "DIGEST_MISMATCH")
    require(len({c["id"] for c in changes["configurations"]}) == len(changes["configurations"]), "AI_INPUT_INVALID")
    for change in changes["configurations"]:
        require(change["id"] == change["value"]["configurationId"] and ((change["kind"] == "add") == (change["expectedRevision"] is None)), "AI_INPUT_INVALID")
    artifact = bundle["artifact"]
    validate_artifact(artifact)
    require(artifact["sources"] == changes["sources"] and artifact["data"] == changes["data"], "DIGEST_MISMATCH")
    require(sorted(r["level"] for r in bundle["reports"]) == ["A", "B", "C"], "CHECKS_INCOMPLETE")
    for report in bundle["reports"]:
        require(report["status"] == "pass", "CHECKS_INCOMPLETE")
        require(report["candidateDigest"] == bundle["candidateDigest"] and report["baselineDigest"] == bundle["baselineDigest"] and
                report["contextDigest"] == digest(context) and report["contractDigest"] == context["contractDigest"] and
                report["validatorSetDigest"] == context["validatorSetDigest"], "DIGEST_MISMATCH")
