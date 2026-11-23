"""T01: public contract boundaries, approved-content binding and pack materials."""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from onlinecoc_ai.contracts import (SCHEMAS, baseline_digest, candidate_digest,
                                   canonical, digest, loads, validate)
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.policy import FORBIDDEN_MODEL_OPERATIONS, MODEL_TOOLS
from onlinecoc_data import canonical as host_canonical

FIXTURES = Path(__file__).parent / "fixtures"
VALID = loads((FIXTURES / "contracts-valid.json").read_bytes())
INVALID = loads((FIXTURES / "contracts-invalid.json").read_bytes())


@pytest.mark.parametrize("kind", VALID)
def test_valid_model(kind):
    assert validate(kind, copy.deepcopy(VALID[kind])) == VALID[kind]


@pytest.mark.parametrize("kind", VALID)
def test_unknown_authority_fields_rejected(kind):
    value = copy.deepcopy(VALID[kind])
    value["trustedByModel"] = True
    with pytest.raises(AiError, match="INPUT_INVALID"):
        validate(kind, value)


@pytest.mark.parametrize("case", INVALID)
def test_negative_fixtures(case):
    value = copy.deepcopy(VALID[case["model"]])
    value[case["field"]] = case["value"]
    with pytest.raises(AiError):
        validate(case["model"], value)


def test_every_schema_is_valid():
    Draft202012Validator.check_schema(SCHEMAS)
    for definition in SCHEMAS["$defs"].values():
        Draft202012Validator.check_schema(definition)


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"nested":{"x":1,"x":2}}',
                                  b'{"x":NaN}', b'{"x":Infinity}', b'"\\ud800"', b'\xff'])
def test_ambiguous_or_invalid_json_rejected(raw):
    with pytest.raises(AiError, match="INPUT_INVALID"):
        loads(raw)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 2**53, 2**4096, {1: "key"}, object()])
def test_non_json_or_unsafe_numbers_rejected(value):
    with pytest.raises(AiError, match="INPUT_INVALID"):
        canonical(value)


def test_cycles_and_depth_are_bounded():
    cyclic = []
    cyclic.append(cyclic)
    with pytest.raises(AiError, match="LIMIT_EXCEEDED"):
        canonical(cyclic)


def test_golden_digests_and_host_interop():
    for vector in loads((FIXTURES / "digest-vectors.json").read_bytes()):
        assert digest(vector["value"]) == vector["digest"]
        assert canonical(vector["value"]) == host_canonical(vector["value"])
        if "canonical" in vector:
            assert canonical(vector["value"]).decode() == vector["canonical"]
    assert digest({"b": 2, "a": 1}) == digest({"a": 1, "b": 2})
    assert digest({"a": 1}) != digest({"a": 2})


@pytest.mark.parametrize("field", ["scopeId", "baseRuleset", "configDigest", "contractDigest", "validatorSetDigest", "worldDigest"])
def test_baseline_binds_every_precondition(field):
    value = copy.deepcopy(VALID["ContextSnapshot"])
    before = baseline_digest(value)
    value[field] = "different"
    assert before != baseline_digest(value)


def test_candidate_binds_complete_artifact_and_configuration():
    ctx, changes = VALID["ContextSnapshot"], VALID["ChangeSet"]
    before = candidate_digest(ctx, changes)
    for target in ("source", "data", "configuration"):
        candidate = copy.deepcopy(changes)
        if target == "source":
            candidate["sources"]["check.lua"] += "\n-- changed"
        elif target == "data":
            candidate["data"]["tuning.json"]["maxTarget"] = 99
        else:
            candidate["configurations"][0]["value"]["defaults"]["bonus"] = 14
        assert candidate_digest(ctx, candidate) != before


@pytest.mark.parametrize("model", ["PreparedBundle", "Approval"])
def test_mismatched_report_or_candidate_cannot_be_reused(model):
    for change in ("report", "candidate", "source", "scope"):
        value = copy.deepcopy(VALID[model])
        if change == "report":
            value["reports"][1]["contextDigest"] = "0" * 64
        elif change == "candidate":
            value["changeSet"]["configurations"][0]["value"]["defaults"]["bonus"] = 14
        elif change == "source":
            value["context"]["createdAt"] = 9
        else:
            value["scopeId"] = "other-room"
        with pytest.raises(AiError):
            validate(model, value)


def test_change_identity_and_expected_revision():
    for field, replacement in (("id", "another-id"), ("expectedRevision", None)):
        value = copy.deepcopy(VALID["ChangeSet"])
        value["configurations"][0][field] = replacement
        with pytest.raises(AiError):
            validate("ChangeSet", value)


def test_model_tools_do_not_include_approval_or_mutation():
    assert MODEL_TOOLS.isdisjoint(FORBIDDEN_MODEL_OPERATIONS)
    assert {"validate_base", "validate_pack_rules", "evaluate_gameplay"} <= MODEL_TOOLS


def test_pack_materials_are_present_and_typed():
    pack = FIXTURES / "pack"
    contract = loads((pack / "ai/contract.json").read_bytes())
    validate("PackContract", contract)
    files = [contract["checks"], contract["metrics"], contract["reviewChecklist"],
             *contract["scenarios"], *contract["schemas"].values(),
             *(s["path"] for s in contract["sources"])]
    for file in files:
        assert (pack / file).is_file(), file
    checks = loads((pack / contract["checks"]).read_bytes())
    for check in checks:
        validate("CheckSpec", check)
        for file in check["caseRefs"]:
            assert (pack / file).is_file()
    assert set(contract["requiredChecks"]) <= {c["checkId"] for c in checks}
    metrics = loads((pack / contract["metrics"]).read_bytes())
    for metric in metrics:
        validate("Metric", metric)
    assert set(contract["requiredMetrics"]) <= {m["metricId"] for m in metrics}
    for file in contract["scenarios"]:
        scenario = loads((pack / file).read_bytes())
        validate("Scenario", scenario)
        assert (pack / scenario["fixtureRef"]).exists()
        assert set(scenario["metricIds"]) <= {m["metricId"] for m in metrics}
    for data, schema in contract["schemas"].items():
        Draft202012Validator(loads((pack / schema).read_bytes())).validate(loads((pack / data).read_bytes()))


def test_provider_template_is_disabled_and_contains_only_secret_reference():
    template = loads((Path(__file__).parents[1] / "examples/ai-providers.json").read_bytes())
    profile = template["profiles"][0]
    validate("Profile", profile)
    assert profile["enabled"] is False
    assert profile["credentialRef"] == "env:ONLINECOC_DEEPSEEK_API_KEY"
    assert "apiKey" not in json.dumps(template)
