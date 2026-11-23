"""A: engineering-owned parsing, complete merge, real stage and model checks."""
from onlinecoc.errors import DomainError
from onlinecoc.model import validate as validate_state, validate_execution_state, EXECUTION_KEYS

from ..contracts import validate
from ..errors import AiError, require
from ..pack import apply_configurations
from ..sandbox import stage
from .common import binding, finding, report


def check_base(pack, state, baseline, context, changes):
    artifact = None
    try:
        validate("ChangeSet", changes)
        validate("Artifact", baseline)
        binding(pack, state, baseline, context)
        if "activeRuleset" in state:
            require(state["activeRuleset"] == baseline["revision"], "BASELINE_STALE")
        require(set(baseline["sources"]) <= set(changes["sources"]) and set(baseline["data"]) <= set(changes["data"]), "INCOMPLETE_CANDIDATE")
        artifact = stage(changes["sources"], changes["data"])
        for name, validator in pack.schemas.items():
            require(name in changes["data"], "SCHEMA_TARGET_MISSING")
            inherited = pack.inherited_only.get(name)
            if inherited is not None and inherited.is_valid(changes['data'][name]):
                require(changes['data'][name] == baseline['data'].get(name),
                        'PACK_PROJECTION_EDIT_FORBIDDEN',
                        'This runtime projection is inheritance-only; submit the complete author document to change it.', '/data/' + name)
            error = next(validator.iter_errors(changes["data"][name]), None)
            require(error is None, "PACK_SCHEMA_INVALID", str(error)[:500] if error else "", "/data/" + name)
        for name in changes["data"]:
            if name not in baseline["data"] or changes["data"][name] != baseline["data"][name]:
                require(name in pack.schemas, "SCHEMA_MISSING", "Changed data needs a pack-author Schema")
        candidate = apply_configurations(state, changes)
        for config in candidate["configurations"].values():
            validate("Configuration", config)
            for ref in config.get("behaviors", {}).values():
                require(ref["ruleId"] in artifact["metadata"], "REFERENCE_CONFLICT")
        if set(candidate) <= set(EXECUTION_KEYS) | {"flows", "waits"}:
            validate_execution_state(candidate)
        else:
            validate_state(candidate)
        require(candidate["entities"] == state["entities"] and candidate["relations"] == state["relations"], "INSTANCE_MIGRATION_FORBIDDEN")
        return report("A", context, changes, coverage=["json", "full-artifact", "host-stage", "pack-schemas", "host-model", "references"],
                      evidence={"artifactRevision": artifact["revision"], "configurationCount": len(candidate["configurations"])}), artifact
    except (AiError, DomainError) as exc:
        code = exc.code
        status = "error" if code in ("WORKER_EXITED", "SANDBOX_UNAVAILABLE", "WORKER_FAILED") else "fail"
        return report("A", context, changes, status, [finding(code, getattr(exc, "detail", ""), getattr(exc, "path", ""))], risk="unknown"), None
