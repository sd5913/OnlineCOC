"""Bounded cross-process locks for administrator-owned local files."""
from contextlib import contextmanager
import os
from pathlib import Path
import time

from .errors import AiError


@contextmanager
def file_lock(path, timeout=3):
    target = Path(str(path) + '.lock')
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('a+b') as stream:
        if target.stat().st_size == 0:stream.write(b'\0');stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:raise AiError('LOCAL_CONFIGURATION_BUSY') from None
                time.sleep(.025)
        try:yield
        finally:
            stream.seek(0)
            if os.name == 'nt':msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
