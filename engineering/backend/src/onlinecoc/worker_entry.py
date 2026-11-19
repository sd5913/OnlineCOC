"""Trusted -I subprocess entry; sources arrive only after parent resource limits."""
import copy
import json
import os
from pathlib import Path
import sys

ENGINEERING = Path(__file__).resolve().parents[3]
if len(sys.argv) == 2:
    sys.path[:0] = json.loads(sys.argv[1])
sys.path[:0] = [str(ENGINEERING / "backend/src"), str(ENGINEERING / "data-management")]
if os.name != "nt":
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

from onlinecoc.errors import DomainError, require
from onlinecoc.lua_runtime import worker
from onlinecoc.worker_process import MAX_BYTES, wire


def read():
    raw = sys.stdin.buffer.readline(MAX_BYTES + 2)
    require(len(raw) <= MAX_BYTES + 1 and raw.endswith(b"\n"), "LIMIT_EXCEEDED")
    return json.loads(raw)


def send(message):
    sys.stdout.buffer.write(wire(message))
    sys.stdout.buffer.flush()


class Pipe:
    def __init__(self, random=None):
        self.output = None
        self.random = random
        self.answer = None

    def send(self, message):
        if "random" in message:
            if self.random:
                try:
                    self.answer = {"value": self.random(message["random"])}
                except DomainError as exc:
                    self.answer = {"error": exc.code}
            else:
                send(message)
        else:
            self.output = message

    def recv(self):
        return self.answer if self.random else read()

    def close(self):
        pass


def sequence(request):
    """Finite deterministic trials. Every trial begins from the same snapshot."""
    from jsonschema import Draft202012Validator
    from onlinecoc.model import member
    policy = request["policy"]
    trials = request["trials"]
    # Only the trusted author-side scenario runner supplies this whitelist.
    # It applies to isolated sequences, never to live Host action permissions.
    private_ids = request.get("privateRuleIds", [])
    require(type(private_ids) is list and all(type(key) is str and key in request["metadata"] for key in private_ids), "INPUT_INVALID")
    require(len(set(private_ids)) == len(private_ids), "INPUT_INVALID")
    private_ids = set(private_ids)
    require(0 < len(trials) <= 10000 and 0 < len(request["steps"]) <= 32, "LIMIT_EXCEEDED")
    results = []
    for values in trials:
        state = copy.deepcopy(request["state"])
        ordinal = 0
        trace = []
        def roll(sides):
            nonlocal ordinal
            require(sides == policy["sides"] and ordinal < len(values), "RANDOM_COVERAGE_UNKNOWN")
            value = values[ordinal]
            ordinal += 1
            require(type(value) is int and 1 <= value <= sides, "RANDOM_TRACE_CONFLICT")
            trace.append({"sides": sides, "value": value})
            return value
        outputs = []
        for step in request["steps"]:
            try:
                m = member(state, request["account"])
                meta = request["metadata"].get(step["rule"])
                allowed_private = m["role"] == "kp" and step["rule"] in private_ids
                require(meta and (meta["public"] or allowed_private) and (not meta["kp"] or m["role"] == "kp"), "PERMISSION_DENIED")
                require(meta["mode"] != "flow", "SCENARIO_UNSUPPORTED")
                try:
                    Draft202012Validator(meta["schema"]).validate(step["input"])
                except Exception:
                    raise DomainError("INPUT_INVALID")
                pipe = Pipe(roll)
                worker(pipe, request["sources"], {"kind": "run", "rule": step["rule"],
                    "input": step["input"], "mode": meta["mode"], "state": state,
                    "account": request["account"], "data": request["data"]})
                output = pipe.output
            except DomainError as exc:
                output = {"ok": False, "code": exc.code}
            if output["ok"]:
                state["entities"] = output["entities"]
                state["relations"] = output["relations"]
                outputs.append({"ok": True, "result": output["result"], "effects": output["effects"]})
            else:
                outputs.append({"ok": False, "code": output["code"]})
                if output["code"] != step.get("expectError"):
                    break
        results.append({"steps": outputs, "random": trace})
    return {"ok": True, "trials": results}


if __name__ == "__main__":
    try:
        request = read()
        if request.get("kind") == "sequence":
            result = sequence(request)
        else:
            pipe = Pipe()
            worker(pipe, request["sources"], request["job"])
            result = pipe.output
        send(result)
    except BaseException as exc:
        send({"ok": False, "code": getattr(exc, "code", "WORKER_FAILED")})
