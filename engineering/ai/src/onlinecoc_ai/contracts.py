"""Versioned strict JSON contracts and host-compatible content digests."""

import hashlib
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker

from .errors import AiError, require

ENGINEERING = Path(__file__).resolve().parents[3]
SCHEMA_PATH = ENGINEERING / "contracts" / "ai.json"
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_DEPTH = 64


def _json_value(value, depth=0):
    require(depth <= MAX_DEPTH, "LIMIT_EXCEEDED", "JSON nesting exceeds limit")
    if value is None or type(value) in (bool, str):
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeError as exc:
                raise AiError("INPUT_INVALID", "Invalid Unicode") from exc
        return
    if type(value) in (int, float):
        require(abs(value) <= 2**53 - 1 and math.isfinite(value),
                "INPUT_INVALID", "Numbers must be finite and within the safe range")
        return
    if type(value) is list:
        for item in value:
            _json_value(item, depth + 1)
        return
    require(type(value) is dict, "INPUT_INVALID", "Value is not JSON")
    for key, item in value.items():
        require(type(key) is str, "INPUT_INVALID", "Object keys must be strings")
        _json_value(key, depth + 1)
        _json_value(item, depth + 1)


def canonical(value):
    _json_value(value)
    try:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, RecursionError) as exc:
        raise AiError("INPUT_INVALID", "Invalid JSON value") from exc
    require(len(raw) <= MAX_JSON_BYTES, "LIMIT_EXCEEDED", "JSON exceeds size limit")
    return raw


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def loads(raw):
    if isinstance(raw, str):
        try:
            raw = raw.encode("utf-8")
        except UnicodeError as exc:
            raise AiError("INPUT_INVALID", "Invalid Unicode") from exc
    require(isinstance(raw, bytes), "INPUT_INVALID", "Expected UTF-8 JSON")
    require(len(raw) <= MAX_JSON_BYTES, "LIMIT_EXCEEDED", "JSON exceeds size limit")

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "INPUT_INVALID", "Duplicate JSON key: " + key)
            result[key] = value
        return result

    def constant(value):
        raise AiError("INPUT_INVALID", "Non-finite JSON number: " + value)

    try:
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                            parse_constant=constant)
        canonical(result)
        return result
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise AiError("INPUT_INVALID", "Invalid UTF-8 JSON") from exc


SCHEMAS = loads(SCHEMA_PATH.read_bytes())
Draft202012Validator.check_schema(SCHEMAS)
VALIDATORS = {
    name: Draft202012Validator({"$ref": "#/$defs/" + name,
                               "$defs": SCHEMAS["$defs"]}, format_checker=FormatChecker())
    for name in SCHEMAS["$defs"]
}


def validate(kind, value):
    canonical(value)
    require(kind in VALIDATORS, "SCHEMA_UNSUPPORTED", "Unknown model: " + kind)
    errors = sorted(VALIDATORS[kind].iter_errors(value), key=lambda e: str(list(e.path)))
    if errors:
        error = errors[0]
        pointer = "/" + "/".join(str(p).replace("~", "~0").replace("/", "~1") for p in error.path)
        raise AiError("INPUT_INVALID", error.message, pointer)
    _semantic(kind, value)
    return value


def _semantic(kind, value):
    if kind == "Profile":
        url = urlsplit(value["baseUrl"])
        require(url.scheme in ("http", "https") and url.hostname and
                not url.username and not url.password and not url.query and not url.fragment,
                "INPUT_INVALID", "Endpoint must be an HTTP(S) origin/path without credentials")
        require(url.scheme == "https" or value["allowPrivateEndpoint"], "INPUT_INVALID", "HTTP needs explicit local endpoint allowance")
        require(value["request"]["totalTimeoutMs"] >= value["request"]["connectTimeoutMs"], "INPUT_INVALID", "Total timeout is shorter than connect timeout")
    elif kind == "PackContract":
        require(value["hostProtocolRange"]["min"] <= value["hostProtocolRange"]["max"])
        for field in ("requiredChecks", "requiredMetrics", "scenarios"):
            require(len(value[field]) == len(set(value[field])), "INPUT_INVALID", "Duplicate " + field)
        require(len({s["id"] for s in value["sources"]}) == len(value["sources"]))
    elif kind == "ConfigurationChange":
        require(value["id"] == value["value"]["configurationId"], "INPUT_INVALID", "Configuration IDs disagree")
        require((value["kind"] == "add") == (value["expectedRevision"] is None), "INPUT_INVALID", "Invalid change precondition")
    elif kind == "ChangeSet":
        ids = [v["id"] for v in value["configurations"]]
        require(len(ids) == len(set(ids)), "INPUT_INVALID", "Duplicate configuration change")
        for item in value["configurations"]:
            _semantic("ConfigurationChange", item)
        for group, suffix in (("sources", ".lua"), ("data", ".json")):
            names = list(value[group])
            require(len(names) == len({n.casefold() for n in names}), "INPUT_INVALID", "Case-insensitive file collision")
            require(all(re.fullmatch(r"[A-Za-z0-9_.-]+", n) and n.endswith(suffix) and not n.startswith(".") for n in names),
                    "INPUT_INVALID", "Artifact filenames must be basenames (no directories), using ASCII letters/digits/underscore/dot/hyphen and the .lua or .json suffix", "/"+group)
    elif kind == "Scenario":
        require(0 < len(value["steps"]) <= value["maxSteps"])
        policy = value["randomPolicy"]
        if policy["mode"] == "fixed":
            require(bool(policy.get("values")) and all(x <= policy["sides"] for x in policy["values"]))
    elif kind == "Artifact":
        require(digest({k: v for k, v in value.items() if k != "revision"}) == value["revision"],
                "DIGEST_MISMATCH", "Artifact digest does not match content")
    elif kind == "Proposal":
        _semantic("ChangeSet", value["changeSet"])
        if value["status"] in ("review_ready", "approved", "published"):
            require(len(set(value["reportRefs"])) == 3, "CHECKS_INCOMPLETE")
    elif kind in ("PreparedBundle", "Approval"):
        _semantic("ChangeSet", value["changeSet"])
        require(value["scopeId"] == value["context"]["scopeId"], "SCOPE_MISMATCH")
        require(value["baselineDigest"] == baseline_digest(value["context"]), "DIGEST_MISMATCH")
        require(value["candidateDigest"] == candidate_digest(value["context"], value["changeSet"]), "DIGEST_MISMATCH")
        require(sorted(r["level"] for r in value["reports"]) == ["A", "B", "C"], "CHECKS_INCOMPLETE")
        for report in value["reports"]:
            require(report["candidateDigest"] == value["candidateDigest"] and
                    report["baselineDigest"] == value["baselineDigest"] and
                    report["contextDigest"] == digest(value["context"]) and
                    report["contractDigest"] == value["context"]["contractDigest"] and
                    report["validatorSetDigest"] == value["context"]["validatorSetDigest"], "DIGEST_MISMATCH")
        if kind == "PreparedBundle":
            _semantic("Artifact", value["artifact"])
            require(value["artifact"]["sources"] == value["changeSet"]["sources"] and value["artifact"]["data"] == value["changeSet"]["data"], "DIGEST_MISMATCH")
        else:
            require(value["approvalDigest"] == digest({k: v for k, v in value.items() if k not in ("status", "approvalDigest")}), "DIGEST_MISMATCH")
            require(value["contextDigest"] == digest(value["context"]) and
                    value["contractDigest"] == value["context"]["contractDigest"] and
                    value["validatorSetDigest"] == value["context"]["validatorSetDigest"], "DIGEST_MISMATCH")
            require(value["expiresAt"] > value["createdAt"], "INPUT_INVALID", "Approval expiry must follow creation")


def baseline_digest(context):
    return digest({k: context[k] for k in ("scopeId", "baseRuleset", "configDigest",
                                         "contractDigest", "validatorSetDigest", "worldDigest")})


def candidate_digest(context, changes):
    return digest({"scopeId": context["scopeId"], "baseRuleset": context["baseRuleset"],
                   "contractDigest": context["contractDigest"], "changeSet": changes})
