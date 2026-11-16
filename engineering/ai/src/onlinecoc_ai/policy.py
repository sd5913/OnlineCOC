"""Model-facing capabilities; never expose host management operations."""

MODEL_TOOLS = frozenset({
    "room.read_context", "pack.read_contract", "pack.read_rule", "memory.search",
    "proposal.submit_draft", "proposal.request_clarification",
    "validate_base", "validate_pack_rules", "evaluate_gameplay", "sandbox.preview",
})

FORBIDDEN_MODEL_OPERATIONS = frozenset({
    "ai.proposal.approve", "ai.proposal.revoke", "publication.apply", "rule.stage",
    "rule.activate", "configuration.put", "entity.create", "entity.update",
})

ERROR_CODES = frozenset({
    "INPUT_INVALID", "SCHEMA_UNSUPPORTED", "DIGEST_MISMATCH", "SCOPE_MISMATCH",
    "NOT_VISIBLE", "PERMISSION_DENIED", "STALE_BASELINE", "SOURCE_CHANGED",
    "CHECKS_INCOMPLETE", "APPROVAL_EXPIRED", "APPROVAL_CONSUMED",
    "BUDGET_EXCEEDED", "PROVIDER_UNAVAILABLE", "PROVIDER_AUTH_FAILED",
    "PROVIDER_RATE_LIMITED", "PROVIDER_RESPONSE_INVALID", "STORAGE_UNAVAILABLE",
    "LIMIT_EXCEEDED", "CANCELLED", "COMMAND_ID_CONFLICT", "VERSION_CONFLICT",
    "UNSUPPORTED_CAPABILITY", "SANDBOX_UNAVAILABLE", "RULE_TIMEOUT",
})
