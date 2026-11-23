"""B: pack-authored constraints, executed by a versioned engineering registry."""
import copy

from jsonschema import Draft202012Validator
from onlinecoc.errors import DomainError

from ..errors import AiError, require
from ..pack import apply_configurations, fixture_state
from ..sandbox import run_scenario, author_private_rules
from .base import check_base
from .common import finding, report


def pointer(value, path):
    require(isinstance(path, str) and (path == "" or path.startswith("/")), "CHECK_PARAMETERS_INVALID")
    for token in path.split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        try:
            value = value[int(token)] if isinstance(value, list) else value[token]
        except (KeyError, IndexError, TypeError, ValueError):
            raise AiError("CHECK_VALUE_MISSING", path=path)
    return value


def parameter_schema(properties, required):
    return {"type": "object", "additionalProperties": False, "properties": properties, "required": required}


STR = {"type": "string", "minLength": 1}
NUMBER = {"type": "number"}
PARAMETERS = {
    "core.numeric-range@1": parameter_schema({"pointer": STR, "minimum": NUMBER, "maximum": NUMBER}, ["pointer", "minimum", "maximum"]),
    "core.reference-exists@1": parameter_schema({"pointer": STR, "collection": {"enum": ["configurations", "entities", "relations"]}}, ["pointer", "collection"]),
    "core.unique@1": parameter_schema({"pointer": STR}, ["pointer"]),
    "core.scenario-assert@1": parameter_schema({"scenarioId": STR, "stepIndex": {"type": "integer", "minimum": 0, "maximum": 31},
        "pointer": STR, "equals": {}, "expectedError": STR}, ["scenarioId", "stepIndex"]),
}


def selected(state, selector):
    values = state[selector["collection"]]
    keys = selector.get("ids", list(values))
    require(all(k in values for k in keys), "CHECK_TARGET_MISSING")
    return [values[k] for k in keys if "typeRef" not in selector or values[k].get("typeRef") == selector["typeRef"]]


def constraint(check, state, pack=None, artifact=None):
    checker = check["checkerId"]
    require(checker in PARAMETERS, "CHECKER_UNKNOWN")
    params = check["parameters"]
    require(next(Draft202012Validator(PARAMETERS[checker]).iter_errors(params), None) is None, "CHECK_PARAMETERS_INVALID")
    targets = selected(state, check["selector"])
    require(bool(targets), "CHECK_TARGET_MISSING")
    if checker == "core.scenario-assert@1":
        require(("expectedError" in params) != ("pointer" in params and "equals" in params), "CHECK_PARAMETERS_INVALID")
        scenario = next((s for s in pack.scenarios if s["scenarioId"] == params["scenarioId"]), None)
        require(scenario is not None and scenario["randomPolicy"]["mode"] == "fixed", "CHECK_SCENARIO_MISSING")
        world = fixture_state(pack.json(scenario["fixtureRef"]), state["configurations"])
        trials = run_scenario(artifact, world, scenario, [scenario["randomPolicy"]["values"]],private_rule_ids=author_private_rules(artifact,scenario))
        require(params["stepIndex"] < len(trials[0]["steps"]), "CHECK_ASSERTION_FAILED")
        step = trials[0]["steps"][params["stepIndex"]]
        passed = step.get("code") == params["expectedError"] if "expectedError" in params else step["ok"] and pointer(step, params["pointer"]) == params["equals"]
        return bool(passed), {"scenarioId": scenario["scenarioId"], "step": step}
    values = [pointer(t, params["pointer"]) for t in targets]
    if checker == "core.numeric-range@1":
        require(params["minimum"] <= params["maximum"], "CHECK_PARAMETERS_INVALID")
        passed = all(type(v) in (int, float) and params["minimum"] <= v <= params["maximum"] for v in values)
    elif checker == "core.reference-exists@1":
        passed = all(isinstance(v, str) and v in state[params["collection"]] for v in values)
    else:
        from ..contracts import digest
        hashes = [digest(v) for v in values]
        passed = len(hashes) == len(set(hashes))
    return passed, {"matched": len(targets), "values": values}


def changed_paths(old, new, prefix=""):
    if isinstance(old, dict) and isinstance(new, dict):
        out = []
        for key in sorted(set(old) | set(new)):
            path = prefix + "/" + key.replace("~", "~0").replace("/", "~1")
            out.extend(changed_paths(old[key], new[key], path) if key in old and key in new else [path])
        return out
    return [] if old == new else [prefix]


def extension_check(pack, state, baseline, artifact, changes):
    extensions = pack.contract["extensionPoints"]
    from ..change_policy import configuration_allowed
    high = pack.contract.get('highRisk', {})
    reference_path=pack.contract['contextMapping'].get('dataReferences')
    if reference_path:
        declarations=pack.json(reference_path)
        require(isinstance(declarations,list), 'DATA_REFERENCE_POLICY_INVALID')
        for declaration in declarations:
            required={'dataRef','pointer','idKey','referencesKey'}
            require(isinstance(declaration,dict) and required<=set(declaration)<=required|{'contiguousFrom','allowSelf'} and all(isinstance(declaration[k],str) and declaration[k] for k in required), 'DATA_REFERENCE_POLICY_INVALID')
            name=declaration['dataRef'];require(name in changes['data'], 'DATA_REFERENCE_POLICY_INVALID')
            values=pointer(changes['data'][name],declaration['pointer']);key=declaration['idKey'];refs=declaration['referencesKey']
            require(isinstance(values,list) and all(isinstance(v,dict) and key in v and isinstance(v.get(refs),list) for v in values), 'DATA_REFERENCE_POLICY_INVALID')
            from ..contracts import digest
            identifiers=[digest(v[key]) for v in values]
            require(len(set(identifiers))==len(identifiers) and all(digest(ref) in identifiers for v in values for ref in v[refs]), 'DATA_REFERENCE_CONFLICT',path='/data/'+name+declaration['pointer'])
            if 'contiguousFrom' in declaration:
                start=declaration['contiguousFrom'];require(type(start) is int,'DATA_REFERENCE_POLICY_INVALID')
                require([v[key] for v in values]==list(range(start,start+len(values))), 'DATA_REFERENCE_CONFLICT',path='/data/'+name+declaration['pointer'])
            if 'allowSelf' in declaration:
                require(type(declaration['allowSelf']) is bool, 'DATA_REFERENCE_POLICY_INVALID')
                if not declaration['allowSelf']:require(all(v[key] not in v[refs] for v in values), 'DATA_REFERENCE_CONFLICT',path='/data/'+name+declaration['pointer'])
    stable_path=pack.contract['contextMapping'].get('stableArrays')
    if stable_path:
        declarations=pack.json(stable_path)
        require(isinstance(declarations,list), 'STABLE_ARRAY_POLICY_INVALID')
        for declaration in declarations:
            require(isinstance(declaration,dict) and set(declaration)=={'dataRef','pointer','idKey','appendOnly'} and declaration['appendOnly'] is True, 'STABLE_ARRAY_POLICY_INVALID')
            require(all(isinstance(declaration[k],str) and declaration[k] for k in ('dataRef','pointer','idKey')), 'STABLE_ARRAY_POLICY_INVALID')
            name=declaration['dataRef'];key=declaration['idKey']
            require(name in baseline['data'] and name in changes['data'], 'STABLE_ARRAY_POLICY_INVALID')
            old=pointer(baseline['data'][name],declaration['pointer']);new=pointer(changes['data'][name],declaration['pointer'])
            require(isinstance(old,list) and isinstance(new,list) and all(isinstance(v,dict) and key in v for v in old+new), 'STABLE_ARRAY_POLICY_INVALID')
            from ..contracts import digest
            old_ids=[digest(v[key]) for v in old];new_ids=[digest(v[key]) for v in new]
            require(len(new_ids)>=len(old_ids) and new_ids[:len(old_ids)]==old_ids and len(set(new_ids))==len(new_ids), 'STABLE_ARRAY_ID_CONFLICT', path='/data/'+name+declaration['pointer'])
    for change in changes["configurations"]:
        identifier, value = change["id"], change["value"]
        if change['kind'] == 'remove':
            old=state['configurations'].get(identifier,{})
            extension_allowed=any(old.get('typeRef') in e['typeRefs'] and (identifier in e['allowExistingIds'] or identifier.startswith(e['namespace'])) for e in extensions)
            require(high.get('allowRemove') and (configuration_allowed(pack.contract, identifier) or extension_allowed), 'EXTENSION_FORBIDDEN', path='/configurations/'+identifier)
            continue
        if configuration_allowed(pack.contract, identifier):continue
        matches = [e for e in extensions if value["typeRef"] in e["typeRefs"] and
                   ((identifier in e["allowExistingIds"] or e.get("allowNamespaceReplace",False) and identifier.startswith(e["namespace"])) if change["kind"] == "replace" else identifier.startswith(e["namespace"]))]
        require(matches, "EXTENSION_FORBIDDEN", path="/configurations/" + identifier)
        if change["kind"] == "replace":
            paths = set(changed_paths(state["configurations"][identifier], value)) - {"/revision"}
            require(any(all(any(p == allowed or p.startswith(allowed + "/") for allowed in e["allowedPaths"]) for p in paths) for e in matches), "EXTENSION_FORBIDDEN")
    require(set(baseline["metadata"]) <= set(artifact["metadata"]), "RULE_REMOVAL_FORBIDDEN")
    changed_code = any(baseline["sources"].get(n) != v for n, v in changes["sources"].items())
    changed_meta = {}
    if changed_code:
        owning_sources = [name for name, text in changes["sources"].items() if baseline["sources"].get(name) != text and name not in high.get('ruleFiles', [])]
        from ..sandbox import execute
        if owning_sources:changed_meta = execute({name: changes["sources"][name] for name in owning_sources}, {"kind": "inspect"})["metadata"]
    for key, meta in artifact["metadata"].items():
        old = baseline["metadata"].get(key)
        # Existing unrelated source files may remain verbatim. A changed source
        # requires its rule to be in an explicitly authorized namespace.
        if changed_code:
            if key in changed_meta:
                require(any(key.startswith(prefix) for e in extensions for prefix in e["rulePrefixes"]), "EXTENSION_FORBIDDEN")
                require(meta["mode"] != "flow", "FLOW_GENERATION_FORBIDDEN")
        if old:
            require(all(meta[k] == old[k] for k in ("inputs", "mode", "public", "kp")), "RULE_INTERFACE_CHANGE")


def check_rules(pack, state, baseline, context, changes, artifact=None, *, _base_result=None):
    base, checked_artifact = _base_result if _base_result is not None else check_base(pack, state, baseline, context, changes)
    if base["status"] != "pass":
        return report("B", context, changes, "unknown", [finding("BASE_CHECK_REQUIRED")], risk="unknown")
    artifact = checked_artifact
    findings, coverage, evidence = [], [], {}
    status = "pass"
    try:
        extension_check(pack, state, baseline, artifact, changes)
        candidate = apply_configurations(state, changes)
        from .extensions import configuration_checks
        configuration_checks(pack,candidate,baseline,artifact,changes)
        required = set(pack.contract["requiredChecks"])
        present = {c["checkId"] for c in pack.checks}
        require(required <= present, "REQUIRED_CHECK_MISSING")
        for check in pack.checks:
            try:
                require(check["caseRefs"], "CHECK_FIXTURES_MISSING")
                expected = set()
                for ref in check["caseRefs"]:
                    case = pack.json(ref)
                    require(case.get("checkId") == check["checkId"], "CHECK_FIXTURE_INVALID")
                    if check["checkerId"] == "core.numeric-range@1":
                        test_state = copy.deepcopy(candidate)
                        config = test_state["configurations"][case["configurationId"]]
                        tokens = case["pointer"].split("/")[1:]
                        for token in tokens[:-1]:
                            config = config[token]
                        config[tokens[-1]] = case["value"]
                        passed, _ = constraint(check, test_state, pack, artifact)
                        require(("pass" if passed else "fail") == case["expected"], "CHECK_FIXTURE_INVALID")
                    else:
                        require("state" in case, "CHECK_FIXTURE_INVALID")
                        passed, _ = constraint(check, case["state"], pack, artifact)
                        require(("pass" if passed else "fail") == case["expected"], "CHECK_FIXTURE_INVALID")
                    expected.add(case["expected"])
                require(expected == {"pass", "fail"}, "CHECK_FIXTURES_MISSING")
                passed, result = constraint(check, candidate, pack, artifact)
                evidence[check["checkId"]] = result
                coverage.append(check["checkId"])
                if not passed:
                    findings.append(finding("PACK_RULE_VIOLATION", source=check["sourceRef"], evidence=result))
                    status = "fail"
            except (AiError, DomainError, KeyError, TypeError) as exc:
                findings.append(finding(getattr(exc, "code", "CHECK_MATERIAL_INVALID"), source=check["sourceRef"]))
                if check["required"] or check["checkId"] in required:
                    status = "unknown" if status != "fail" else status
        affected = {c["id"] for c in changes["configurations"]}
        instances = [e["instanceId"] for e in state["entities"].values() if e["configurationId"] in affected]
        evidence["existingInstances"] = {"ids": instances, "valuesPreserved": True}
        for instance in state["entities"].values():
            if instance["configurationId"] in affected:
                require(set(candidate["configurations"][instance["configurationId"]]["defaults"]) <= set(instance["numbers"]), "INSTANCE_FIELDS_MISSING")
        active_flows = [f.get("id", key) for key, f in state.get("flows", {}).items() if f["status"] not in ("completed", "cancelled")]
        if active_flows and affected:
            findings.append(finding("FLOW_DEPENDENCY_UNMEASURED", evidence={"flows": active_flows}, suggestion="Complete or cancel these flows before revalidating"))
            status = "unknown" if status != "fail" else status
        return report("B", context, changes, status, findings, coverage, evidence, "unknown" if status == "unknown" else "low")
    except (AiError, DomainError) as exc:
        return report("B", context, changes, "fail", [finding(exc.code, getattr(exc, "detail", ""), getattr(exc, "path", ""))], coverage, evidence, "unknown")
