"""AI checks use precisely the host worker and never a live Host instance."""
from onlinecoc.lua_runtime import execute
from onlinecoc.registry import stage
from onlinecoc.worker_process import POLICY_VERSION, execute_request


def run_scenario(artifact, state, scenario, trials, timeout=30):
    return execute_request({"kind": "sequence", "sources": artifact["sources"],
        "data": artifact["data"], "metadata": artifact["metadata"], "state": state,
        "account": scenario["account"], "steps": scenario["steps"],
        "policy": scenario["randomPolicy"], "trials": trials}, timeout=timeout)["trials"]
