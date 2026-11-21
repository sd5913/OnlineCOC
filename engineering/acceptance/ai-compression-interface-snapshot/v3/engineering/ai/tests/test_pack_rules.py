import copy
import pytest

from onlinecoc_ai.errors import AiError
from onlinecoc_ai.validation.rules import check_rules, constraint
from onlinecoc_ai.validation.common import world_digest


def test_valid_constraints_and_old_instances_preserved(validation_case):
    report = check_rules(*validation_case)
    assert report["status"] == "pass"
    assert set(report["coverage"]) == {"bonus-range", "charges-range"}
    assert report["evidence"]["existingInstances"] == {"ids": ["token-one"], "valuesPreserved": True}


def test_out_of_range_is_traced_to_rule_clause(validation_case):
    validation_case[-1]["configurations"][0]["value"]["defaults"]["bonus"] = 16
    report = check_rules(*validation_case)
    assert report["status"] == "fail"
    assert report["findings"][0]["sourceRef"] == "rules#bonus"


def test_cost_change_outside_extension_is_rejected(validation_case):
    validation_case[-1]["configurations"][0]["value"]["defaults"]["charges"] = 100
    assert check_rules(*validation_case)["findings"][0]["code"] == "EXTENSION_FORBIDDEN"


@pytest.mark.parametrize("mutation", [lambda p: p.checks.pop(), lambda p: p.checks[0].update(checkerId="unknown@1"),
    lambda p: p.checks[0].update(caseRefs=[]), lambda p: p.checks[0]["parameters"].update(override=True),
    lambda p: p.checks[0]["selector"].update(ids=["missing"])])
def test_missing_or_unknown_required_evidence_never_passes(validation_case, mutation):
    mutation(validation_case[0])
    assert check_rules(*validation_case)["status"] != "pass"


def test_old_flow_is_not_assumed_to_use_old_configs(validation_case):
    state, context = validation_case[1], validation_case[3]
    state["flows"] = {"flow": {"id": "flow", "account": "player1", "rule": "fixture.check", "input": {},
        "ruleset": validation_case[2]["revision"], "cursor": "next", "status": "waiting", "results": {}}}
    context["worldDigest"] = world_digest(state)
    report = check_rules(*validation_case)
    assert report["status"] == "unknown"
    assert any(f["code"] == "FLOW_DEPENDENCY_UNMEASURED" for f in report["findings"])


def test_versioned_reference_and_unique_checkers(validation_case):
    state = validation_case[1]
    check = {"checkerId": "core.reference-exists@1", "selector": {"collection": "entities"},
        "parameters": {"pointer": "/configurationId", "collection": "configurations"}}
    assert constraint(check, state)[0]
    broken = copy.deepcopy(state)
    broken["entities"]["token-one"]["configurationId"] = "missing"
    assert not constraint(check, broken)[0]
    check.update(checkerId="core.unique@1", parameters={"pointer": "/owner"})
    assert not constraint(check, state)[0]
    check["parameters"]["pointer"] = "/instanceId"
    assert constraint(check, state)[0]


def test_missing_numeric_field_is_not_zero(validation_case):
    state = copy.deepcopy(validation_case[1])
    del state["configurations"]["fixture.token"]["defaults"]["bonus"]
    with pytest.raises(AiError, match="CHECK_VALUE_MISSING"):
        constraint(validation_case[0].checks[0], state)


def test_scenario_checker_covers_permission_and_cost(validation_case):
    pack, state, artifact, _, _ = validation_case
    check = {"checkerId": "core.scenario-assert@1", "selector": {"collection": "configurations", "ids": ["fixture.token"]},
             "parameters": {"scenarioId": "wrong-owner", "stepIndex": 0, "expectedError": "PERMISSION_DENIED"}}
    assert constraint(check, state, pack, artifact)[0]
    check["parameters"]["expectedError"] = "INPUT_INVALID"
    assert not constraint(check, state, pack, artifact)[0]
    check["parameters"] = {"scenarioId": "resource-exhaustion", "stepIndex": 0, "pointer": "/result/cost", "equals": 1}
    assert constraint(check, state, pack, artifact)[0]
    check["parameters"]["equals"] = 0
    assert not constraint(check, state, pack, artifact)[0]
