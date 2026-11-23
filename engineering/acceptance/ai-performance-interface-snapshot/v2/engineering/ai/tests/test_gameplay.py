import copy
import pytest

from onlinecoc_ai.validation.gameplay import assess, random_trials, metric_value
from onlinecoc_ai.validation.common import world_digest


def test_exact_d100_probability_and_cost_no_live_effects(validation_case):
    before = copy.deepcopy(validation_case[1])
    result = assess(*validation_case)
    assert result["status"] == "pass" and result["risk"] == "high"
    success, cost = result["evidence"]["comparisons"]
    assert success["baseline"] == .6 and success["candidate"] == .75
    assert success["absoluteDelta"] == pytest.approx(.15)
    assert success["relativeDelta"] == pytest.approx(.25)
    assert cost["baseline"] == cost["candidate"] == 1
    assert len(result["evidence"]["scenarios"][0]["trials"]["candidate"]) == 100
    assert validation_case[1] == before


def test_wrong_owner_and_repeated_use_are_exercised(validation_case):
    pack = validation_case[0]
    # The author-supplied pack includes these scenarios; do not only exercise
    # privileged positive fixtures assembled by the engine developer.
    assert {s["scenarioId"] for s in pack.scenarios} >= {"wrong-owner", "resource-exhaustion"}
    result = assess(*validation_case)
    assert result["status"] == "pass"
    assert "wrong-owner" in result["coverage"] and "resource-exhaustion" in result["coverage"]


def test_missing_cost_guard_fails_resource_exhaustion(validation_case):
    changes = validation_case[-1]
    changes["sources"]["check.lua"] = changes["sources"]["check.lua"].replace("r.set(item, 'charges', charges - 1)", "-- no resource debit")
    if changes["sources"] == validation_case[2]["sources"]:
        changes["sources"]["check.lua"] = changes["sources"]["check.lua"].replace("r.set(item, \"charges\", charges - 1)", "-- no resource debit")
    assert changes["sources"] != validation_case[2]["sources"]
    result = assess(*validation_case)
    assert result["status"] == "unknown"
    assert any(f["code"] == "SCENARIO_ASSERTION_FAILED" for f in result["findings"])


def test_positive_fixture_cannot_replace_negative_assertion(validation_case):
    pack = validation_case[0]
    negative = copy.deepcopy(pack.scenarios[0])
    negative.update(scenarioId="unexpected-permission", account="player1", metricIds=[])
    negative["steps"][0]["expectError"] = "PERMISSION_DENIED"
    negative["randomPolicy"].update(mode="fixed", values=[50])
    pack.scenarios.append(negative)
    result = assess(*validation_case)
    assert result["status"] == "unknown"


def test_missing_required_metric_blocks(validation_case):
    validation_case[0].scenarios[0]["metricIds"] = []
    result = assess(*validation_case)
    assert result["status"] == "unknown"
    assert any(f["code"] == "REQUIRED_METRIC_UNMEASURED" for f in result["findings"])


def test_extra_random_call_is_not_paired_with_old_trace(validation_case):
    changes = validation_case[-1]
    changes["sources"]["check.lua"] = changes["sources"]["check.lua"].replace("local rolled=r.roll(100)", "local extra=r.roll(100); local rolled=r.roll(100)")
    # Whitespace-independent fixture mutation.
    if "local extra" not in changes["sources"]["check.lua"]:
        changes["sources"]["check.lua"] = changes["sources"]["check.lua"].replace("r.roll(100)", "r.roll(100) + 0 * r.roll(100)")
    result = assess(*validation_case)
    assert result["status"] == "unknown"
    assert any(f["code"] in ("RANDOM_COVERAGE_UNKNOWN", "SCENARIO_INCOMPLETE") for f in result["findings"])


def test_sampling_uses_replayable_independent_streams(validation_case):
    scenario = copy.deepcopy(validation_case[0].scenarios[0])
    scenario["randomPolicy"].update(mode="sample", samples=20)
    first, version = random_trials(scenario, "baseline")
    assert first == random_trials(scenario, "baseline")[0]
    assert first != random_trials(scenario, "candidate")[0]
    assert "mt19937" in version


def test_zero_baseline_is_not_divided(validation_case):
    pack, state, baseline, context, changes = validation_case
    # Fixture initializes target from config; this is a new-instance comparison.
    state["configurations"]["fixture.actor"]["defaults"]["target"] = 0
    from onlinecoc_ai.contracts import digest
    context["configDigest"] = digest(state["configurations"])
    result = assess(*validation_case)
    assert result["status"] == "pass"
    metric = result["evidence"]["comparisons"][0]
    assert metric["baseline"] == 0 and metric["candidate"] == .15
    assert metric["relativeDelta"] is None and metric["relativeUnavailableReason"] == "zero-baseline"
