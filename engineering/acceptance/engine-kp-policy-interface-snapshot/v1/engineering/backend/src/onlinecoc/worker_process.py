"""Bounded subprocess transport shared by staging, gameplay checks and live rules.

The security boundary is the restricted Lua environment, backed by an isolated
interpreter process. This is not a container for arbitrary native executables.
"""
import ctypes
import json
import math
import os
from pathlib import Path
import queue
import site
import subprocess
import sys
import threading
import time

from .errors import DomainError, require

POLICY_VERSION = "lua-process-1"
MAX_BYTES = 8 * 1024 * 1024
MEMORY_BYTES = 512 * 1024 * 1024


def wire(value):
    try:
        raw = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii")
    except (ValueError, TypeError, RecursionError):
        raise DomainError("INPUT_INVALID")
    require(len(raw) <= MAX_BYTES, "LIMIT_EXCEEDED")
    return raw + b"\n"


class WindowsJob:
    """Assign before sending input; close kills all worker descendants."""
    def __init__(self, process):
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_ = [("perProcess", ctypes.c_int64), ("perJob", ctypes.c_int64),
                        ("flags", w.DWORD), ("minWorking", ctypes.c_size_t),
                        ("maxWorking", ctypes.c_size_t), ("active", w.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ("readOps", "writeOps", "otherOps", "readBytes", "writeBytes", "otherBytes")]
        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", IO), ("processMemory", ctypes.c_size_t),
                        ("jobMemory", ctypes.c_size_t), ("peakProcess", ctypes.c_size_t), ("peakJob", ctypes.c_size_t)]
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        self.api.CreateJobObjectW.restype = w.HANDLE
        self.api.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        self.api.SetInformationJobObject.restype = w.BOOL
        self.api.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.api.AssignProcessToJobObject.restype = w.BOOL
        self.api.CloseHandle.argtypes = [w.HANDLE]
        self.api.CloseHandle.restype = w.BOOL
        self.handle = self.api.CreateJobObjectW(None, None)
        try:
            require(bool(self.handle), "SANDBOX_UNAVAILABLE")
            limits = Extended()
            # ACTIVE_PROCESS, PROCESS_MEMORY, JOB_MEMORY, KILL_ON_JOB_CLOSE.
            limits.basic.flags = 0x8 | 0x100 | 0x200 | 0x2000
            limits.basic.active = 1
            limits.processMemory = limits.jobMemory = MEMORY_BYTES
            require(self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)), "SANDBOX_UNAVAILABLE")
            require(self.api.AssignProcessToJobObject(self.handle, w.HANDLE(process._handle)), "SANDBOX_UNAVAILABLE")
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def _reader(stream, messages):
    try:
        while True:
            line = stream.readline(MAX_BYTES + 2)
            if not line:
                messages.put(None)
                return
            if len(line) > MAX_BYTES + 1 or not line.endswith(b"\n"):
                messages.put(DomainError("WORKER_OUTPUT_LIMIT"))
                return
            messages.put(line)
    except (ValueError, OSError):
        messages.put(None)


def execute_request(request, random=None, timeout=10):
    require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 120, "INPUT_INVALID")
    payload = wire(request)
    started = time.perf_counter()
    deadline = time.monotonic() + timeout
    # Do not inherit credentials, PYTHONPATH, proxies, or the host save directory.
    env = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR") if key in os.environ}
    env.update(PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    entry = Path(__file__).with_name("worker_entry.py")
    # Windows venv python.exe is a launcher which creates another process. Run
    # the actual interpreter so the one-process Job limit remains meaningful.
    interpreter = getattr(sys, "_base_executable", None) or sys.executable
    process = subprocess.Popen([interpreter, "-I", "-B", "-u", str(entry), json.dumps(site.getsitepackages())],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               cwd=entry.parent, env=env,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                               start_new_session=os.name != "nt")
    job = None
    messages = queue.Queue(maxsize=4)
    reader = threading.Thread(target=_reader, args=(process.stdout, messages), daemon=True)
    try:
        if os.name == "nt":
            job = WindowsJob(process)
        reader.start()
        # Writing can block for a large input or an unresponsive child; include it
        # in the same wall-clock deadline rather than blocking the host forever.
        def send_input():
            try:
                process.stdin.write(payload)
                process.stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                pass
        writer = threading.Thread(target=send_input, daemon=True)
        writer.start()
        while time.monotonic() < deadline:
            try:
                message = messages.get(timeout=min(.05, max(.001, deadline - time.monotonic())))
            except queue.Empty:
                continue
            require(message is not None, "WORKER_EXITED")
            if isinstance(message, DomainError):
                raise message
            try:
                message = json.loads(message)
            except (ValueError, RecursionError):
                raise DomainError("WORKER_PROTOCOL_INVALID")
            require(type(message) is dict, "WORKER_PROTOCOL_INVALID")
            if "random" in message:
                try:
                    sides = message["random"]
                    require(type(sides) is int and 1 <= sides <= 1000000, "WORKER_PROTOCOL_INVALID")
                    require(random is not None, "RANDOM_UNAVAILABLE")
                    value = random(sides)
                    require(type(value) is int and 1 <= value <= sides, "RANDOM_TRACE_CONFLICT")
                    answer = {"value": value}
                except Exception as exc:
                    answer = {"error": getattr(exc, "code", "RANDOM_FAILED")}
                process.stdin.write(wire(answer))
                process.stdin.flush()
                continue
            require(type(message.get("ok")) is bool, "WORKER_PROTOCOL_INVALID")
            if not message["ok"]:
                raise DomainError(message.get("code", "RULE_FAILED"), message.get("diagnostic", ""))
            message["workerMs"] = (time.perf_counter() - started) * 1000
            return message
        raise DomainError("RULE_TIMEOUT")
    finally:
        if job:
            job.close()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=3)
        for stream in (process.stdin, process.stdout):
            stream.close()
        if reader.is_alive():
            reader.join(.2)

