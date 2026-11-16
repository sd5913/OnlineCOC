from __future__ import annotations

import os
from pathlib import Path

from .common import Fault


class SessionLock:
    """OS-released process lock: crashes cannot leave a live ownership claim."""
    def __init__(self, path: Path):
        self.path, self.file = path, None

    def acquire(self):
        if self.file is not None:
            raise Fault("ALREADY_RUNNING", 409)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+b")
        try:
            stream.seek(0)
            if not stream.read(1):
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            stream.close()
            raise Fault("SESSION_ALREADY_OWNED", 409) from None
        self.file = stream

    def close(self):
        if self.file is not None:
            if os.name == "nt":
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            self.file.close()
            self.file = None
