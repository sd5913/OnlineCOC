import copy
import os
import subprocess
import time

import pytest
from onlinecoc.errors import DomainError
from onlinecoc.lua_runtime import execute
from onlinecoc.worker_process import execute_request
from onlinecoc_ai.sandbox import execute as ai_execute


def test_ai_and_host_share_execution_policy():
    assert ai_execute is execute


def test_top_level_loop_is_bounded():
    start = time.monotonic()
    with pytest.raises(DomainError, match="RULE_TIMEOUT"):
        execute({"bad.lua": "while true do end"}, {"kind": "inspect"}, timeout=.7)
    assert time.monotonic() - start < 4


@pytest.mark.parametrize("source", [
    "local t={} while true do table.insert(t, string.format('%08000d',1)) end",
    "return rule('huge', {}, function(r) return string.format('%09000000d',1) end)",
])
def test_memory_and_output_limits(source, validation_case):
    state = validation_case[1]
    with pytest.raises(DomainError) as error:
        execute({"bad.lua": source}, {"kind": "run", "rule": "huge", "input": {}, "mode": "action", "state": state, "account": "kp"}, timeout=4)
    assert error.value.code in {"RULE_FAILED", "LIMIT_EXCEEDED", "WORKER_EXITED", "RULE_TIMEOUT", "WORKER_OUTPUT_LIMIT"}


@pytest.mark.parametrize("expression", ["os.getenv('ONLINECOC_DEEPSEEK_API_KEY')", "io.open('save.json','w')", "require('socket')", "python.eval('1')", "debug.getregistry()", "_G.os", "r.read.__globals__", "r.read['__self__']"])
def test_lua_cannot_access_host_bridges(expression, validation_case, tmp_path):
    state = validation_case[1]
    before = copy.deepcopy(state)
    source = "return rule('probe', {}, function(r) return " + expression + " end)"
    with pytest.raises(DomainError):
        execute({"probe.lua": source}, {"kind": "run", "rule": "probe", "input": {}, "mode": "action", "state": state, "account": "kp"})
    assert state == before
    assert not (tmp_path / "save.json").exists()


def test_secrets_are_removed_before_process_creation(monkeypatch):
    monkeypatch.setenv("ONLINECOC_DEEPSEEK_API_KEY", "sentinel-not-a-real-key")
    monkeypatch.setenv("HTTPS_PROXY", "http://secret.invalid")
    original = subprocess.Popen
    observed = []
    def capture(*args, **kwargs):
        observed.append(kwargs["env"])
        return original(*args, **kwargs)
    monkeypatch.setattr(subprocess, "Popen", capture)
    assert execute({"one.lua": "return rule('one',{},function(r) return 1 end)"}, {"kind": "inspect"})["ok"]
    assert observed and all("ONLINECOC_DEEPSEEK_API_KEY" not in env and "HTTPS_PROXY" not in env for env in observed)


def test_worker_failure_is_not_success():
    with pytest.raises(DomainError):
        execute_request({"sources": {}, "job": {}})
