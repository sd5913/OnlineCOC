"""C: reproducible evidence and explicit coverage limits, never a balance proof."""
import hashlib
import math
import random

from onlinecoc.errors import DomainError

from ..errors import AiError, require
from ..pack import apply_configurations, fixture_state
from ..sandbox import run_scenario, author_private_rules
from .base import check_base
from .common import finding, report
from .rules import pointer


def random_trials(scenario, variant):
    policy = scenario["randomPolicy"]
    if policy["mode"] == "enumerate":
        require(policy["sides"] <= 10000, "ENUMERATION_LIMIT")
        return [[v] for v in range(1, policy["sides"] + 1)], "exact-single-die-v1"
    if policy["mode"] == "fixed":
        return [policy["values"]], "fixed-sequence-v1"
    require(policy["samples"] <= 10000, "SAMPLE_LIMIT")
    # Separate streams prevent an extra roll from shifting a paired sequence.
    # Each trial also has its own seed, making call-count differences visible.
    trials = []
    for index in range(policy["samples"]):
        seed = hashlib.sha256(f'{policy["seed"]}:{scenario["scenarioId"]}:{variant}:{index}'.encode()).digest()
        rng = random.Random(int.from_bytes(seed, "big"))
        trials.append([rng.randrange(1, policy["sides"] + 1) for _ in range(64)])
    return trials, "sha256-seeded-mt19937-randrange-python3.14-v1"


def check_steps(scenario, outputs):
    for trial in outputs:
        require(len(trial["steps"]) == len(scenario["steps"]), "SCENARIO_INCOMPLETE")
        for expected, actual in zip(scenario["steps"], trial["steps"]):
            if "expectError" in expected:
                require(not actual["ok"] and actual.get("code") == expected["expectError"], "SCENARIO_ASSERTION_FAILED")
            else:
                if not actual["ok"] and actual.get("code") == "RANDOM_COVERAGE_UNKNOWN":
                    raise AiError("RANDOM_COVERAGE_UNKNOWN")
                require(actual["ok"], "SCENARIO_EXECUTION_FAILED", actual.get("code", ""))
        if scenario["randomPolicy"]["mode"] == "enumerate" and any("expectError" not in s for s in scenario["steps"]):
            require(len(trial["random"]) == 1, "RANDOM_COVERAGE_UNKNOWN")


def metric_value(metric, outputs):
    values = [pointer(trial["steps"][metric["parameters"]["stepIndex"]], metric["parameters"]["pointer"]) for trial in outputs]
    require(bool(values), "METRIC_MISSING")
    if metric["calculatorId"] == "core.success-rate@1":
        require(all(type(v) is bool for v in values), "METRIC_TYPE_INVALID")
        numbers = [int(v) for v in values]
    else:
        require(all(type(v) in (int, float) and math.isfinite(v) for v in values), "METRIC_TYPE_INVALID")
        numbers = values
    value = max(numbers) if metric["calculatorId"] == "core.maximum@1" else math.fsum(numbers) / len(numbers)
    variance = math.fsum((n - value) ** 2 for n in numbers) / max(1, len(numbers) - 1)
    return value, math.sqrt(variance / len(numbers))


def assess(pack, state, baseline, context, changes, artifact=None):
    base, artifact = check_base(pack, state, baseline, context, changes)
    if base["status"] != "pass":
        return report("C", context, changes, "unknown", [finding("BASE_CHECK_REQUIRED")], risk="unknown")
    candidate = apply_configurations(state, changes)
    findings, coverage, comparisons, executions = [], [], [], []
    status, risk = "pass", "low"
    ranks = {"low": 0, "medium": 1, "high": 2}
    metrics = {m["metricId"]: m for m in pack.metrics}
    required = set(pack.contract["requiredMetrics"]) | {m["metricId"] for m in pack.metrics if m["required"]}
    measured = set()
    try:
        require(bool(pack.scenarios) and required <= set(metrics), "REQUIRED_METRIC_MISSING")
        for scenario in pack.scenarios:
            identifier = scenario["scenarioId"]
            try:
                fixture = pack.json(scenario["fixtureRef"])
                outputs, policies = {}, {}
                for variant, configurations, rules in (("baseline", state["configurations"], baseline), ("candidate", candidate["configurations"], artifact)):
                    world = fixture_state(fixture, configurations)
                    trials, algorithm = random_trials(scenario, variant)
                    results = run_scenario(rules, world, scenario, trials, private_rule_ids=author_private_rules(rules,scenario))
                    check_steps(scenario, results)
                    outputs[variant] = results
                    policies[variant] = {"algorithm": algorithm, "seed": scenario["randomPolicy"]["seed"], "trials": len(trials),
                        "randomCalls": sorted({len(t["random"]) for t in results})}
                execution = {"scenarioId": identifier, "population": "new-instances-from-same-fixture",
                    "policies": policies, "trials": outputs}
                executions.append(execution)
                for metric_id in scenario["metricIds"]:
                    require(metric_id in metrics, "METRIC_MISSING")
                    metric = metrics[metric_id]
                    before, before_se = metric_value(metric, outputs["baseline"])
                    after, after_se = metric_value(metric, outputs["candidate"])
                    delta = after - before
                    comparison = {"scenarioId": identifier, "metricId": metric_id, "unit": metric["unit"],
                        "baseline": before, "candidate": after, "absoluteDelta": delta,
                        "relativeDelta": delta / abs(before) if before != 0 else None,
                        "relativeUnavailableReason": "zero-baseline" if before == 0 else None,
                        "exact": scenario["randomPolicy"]["mode"] == "enumerate"}
                    if scenario["randomPolicy"]["mode"] == "sample":
                        comparison["standardErrorOfDifference"] = math.sqrt(before_se ** 2 + after_se ** 2)
                        comparison["sampleOnly"] = True
                    comparisons.append(comparison)
                    measured.add(metric_id)
                    if abs(delta) > metric["threshold"]["absoluteDelta"]:
                        metric_risk = metric["threshold"]["risk"]
                        if ranks[metric_risk] > ranks[risk]:
                            risk = metric_risk
                        findings.append(finding("GAMEPLAY_DELTA", evidence=comparison, severity="warning",
                            suggestion="KP must review the measured change and remaining choices"))
                coverage.append(identifier)
            except (AiError, DomainError, KeyError, IndexError, TypeError) as exc:
                findings.append(finding(getattr(exc, "code", "SCENARIO_MATERIAL_INVALID"), path=identifier))
                status = "unknown"
        missing = sorted(required - measured)
        if missing:
            status = "unknown"
            findings.append(finding("REQUIRED_METRIC_UNMEASURED", evidence={"metrics": missing}))
        # A changed executable rule also needs coverage for existing instances.
        # Without an explicit mapping, fail closed instead of implying that new
        # fixture instances prove compatibility with an arbitrary live room.
        code_changed = changes["sources"] != baseline["sources"] or changes["data"] != baseline["data"]
        from .extensions import assess_extensions
        extension_evidence=assess_extensions(pack,state,baseline,artifact,changes,context['reviewPrincipal'])
        from .live import assess_live
        live_evidence=assess_live(pack,state,baseline,artifact,changes,context['reviewPrincipal']) if code_changed and extension_evidence is None else None
        if live_evidence:
            executions.append({'liveValidation':live_evidence})
            risk='high'
            findings.append(finding('LIVE_GAMEPLAY_REVIEW',severity='warning',suggestion='Review author-declared compatibility coverage and remaining gameplay changes'))
        if extension_evidence and (extension_evidence['changedRules'] or changes['configurations']):
            risk='high'
            findings.append(finding('EXTENSION_GAMEPLAY_REVIEW',severity='warning',suggestion='Review NPC template deltas and explicit rule effects before publication'))
            executions.append({'extensionValidation':extension_evidence})
        if code_changed and state["entities"] and extension_evidence is None and live_evidence is None:
            covered_entities = set()
            for scenario in pack.scenarios:
                ids = {v for step in scenario["steps"] for v in step["input"].values() if isinstance(v, str) and v in state["entities"]}
                if not ids:
                    continue
                try:
                    for variant, rules in (("existing-baseline", baseline), ("existing-candidate", artifact)):
                        trials, _ = random_trials(scenario, variant)
                        results = run_scenario(rules, state, scenario, trials, private_rule_ids=author_private_rules(rules,scenario))
                        check_steps(scenario, results)
                    covered_entities |= ids
                except (AiError, DomainError):
                    pass
            if covered_entities != set(state["entities"]):
                status = "unknown"
                findings.append(finding("EXISTING_INSTANCE_COVERAGE_MISSING", evidence={"ids": sorted(set(state["entities"]) - covered_entities)}))
        return report("C", context, changes, status, findings, coverage,
            {"comparisons": comparisons, "scenarios": executions, "requiredMetrics": sorted(required),
             "measuredMetrics": sorted(measured), "limitations": ["Only declared scenarios and metrics are covered", "Existing instance values are not migrated", "KP judgment is required for subjective gameplay impact"]},
            risk if status == "pass" else "unknown", pack.contract["reviewPolicy"]["items"])
    except (AiError, DomainError) as exc:
        return report("C", context, changes, "unknown", [finding(exc.code)], coverage, risk="unknown", review=pack.contract["reviewPolicy"]["items"])
