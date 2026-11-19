"""AI checks use precisely the host worker and never a live Host instance."""
from onlinecoc.lua_runtime import execute
from onlinecoc.registry import stage
from onlinecoc.worker_process import POLICY_VERSION, execute_request


def author_private_rules(artifact, scenario):
    """Only pass author-authored scenario steps here, never model invocations."""
    return tuple(sorted({step['rule'] for step in scenario['steps'] if step['rule'] in artifact['metadata'] and not artifact['metadata'][step['rule']]['public']}))


def run_scenario(artifact, state, scenario, trials, timeout=30, *, private_rule_ids=()):
    return execute_request({"kind": "sequence", "sources": artifact["sources"],
        "data": artifact["data"], "metadata": artifact["metadata"], "state": state,
        "account": scenario["account"], "steps": scenario["steps"],
        "policy": scenario["randomPolicy"], "trials": trials,
        **({'privateRuleIds':list(private_rule_ids)} if private_rule_ids else {})}, timeout=timeout)["trials"]
