"""Own room process trees; Windows handles also clean up after a GUI crash."""
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys


class WindowsJob:
    def __init__(self, process):
        from ctypes import wintypes as w

        class Basic(ctypes.Structure):
            _fields_ = [('processTime', ctypes.c_int64), ('jobTime', ctypes.c_int64),
                        ('flags', w.DWORD), ('minimumWorking', ctypes.c_size_t),
                        ('maximumWorking', ctypes.c_size_t), ('active', w.DWORD),
                        ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ('readOps', 'writeOps', 'otherOps', 'readBytes', 'writeBytes', 'otherBytes')]

        class Extended(ctypes.Structure):
            _fields_ = [('basic', Basic), ('io', IO), ('processMemory', ctypes.c_size_t),
                        ('jobMemory', ctypes.c_size_t), ('peakProcess', ctypes.c_size_t), ('peakJob', ctypes.c_size_t)]

        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        for name, args, result in (
            ('CreateJobObjectW', [ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
            ('SetInformationJobObject', [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
            ('AssignProcessToJobObject', [w.HANDLE, w.HANDLE], w.BOOL),
            ('CloseHandle', [w.HANDLE], w.BOOL),
        ):
            method = getattr(self.api, name)
            method.argtypes, method.restype = args, result
        self.handle = self.api.CreateJobObjectW(None, None)
        try:
            if not self.handle:
                raise ctypes.WinError(ctypes.get_last_error())
            limits = Extended()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not self.api.AssignProcessToJobObject(self.handle, w.HANDLE(process._handle)):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


class OwnedProcess:
    """A gated base interpreter joins its Job before spawning any venv launcher."""
    def __init__(self, args, *, input_data=None, **options):
        self.job = None
        self.args = [str(arg) for arg in args]
        interpreter = Path(getattr(sys, '_base_executable', sys.executable))
        if interpreter.name.lower() == 'pythonw.exe':
            interpreter = interpreter.with_name('python.exe')
        self.process = subprocess.Popen([str(interpreter), '-I', '-B', str(Path(__file__).resolve()), '--child'],
            stdin=subprocess.PIPE, start_new_session=os.name != 'nt', **options)
        try:
            if os.name == 'nt':
                self.job = WindowsJob(self.process)
            if input_data is not None and not isinstance(input_data, str):
                raise TypeError('Owned process input must be text')
            payload = json.dumps({'command': self.args, 'input': input_data}, ensure_ascii=True) + '\n'
            self.process.stdin.write(payload if self.process.text_mode else payload.encode('ascii'))
            self.process.stdin.close()
            self.process.stdin = None
        except BaseException:
            self.terminate()
            self.process.wait(timeout=10)
            raise

    def __getattr__(self, name):
        return getattr(self.process, name)

    def terminate(self):
        if self.job:
            self.job.close()
        elif os.name != 'nt':
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        elif self.process.poll() is None:
            self.process.terminate()

    kill = terminate


def stop_process(process):
    if process is not None:
        # Close the Job even if the first process has exited with descendants alive.
        process.terminate()
        process.wait(timeout=10)


def run_owned(args, *, check=False, timeout=None, capture_output=False, input=None, **options):
    if capture_output:
        options.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process = OwnedProcess(args, input_data=input, **options)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        if check and process.returncode:
            raise subprocess.CalledProcessError(process.returncode, args, output=stdout, stderr=stderr)
        return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
    finally:
        stop_process(process)


if __name__ == '__main__':
    payload = json.loads(sys.stdin.buffer.readline())
    command, content = payload['command'], payload['input']
    child = subprocess.Popen(command, stdin=subprocess.PIPE if content is not None else subprocess.DEVNULL,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    child.communicate(content.encode('utf-8') if content is not None else None)
    raise SystemExit(child.returncode)
