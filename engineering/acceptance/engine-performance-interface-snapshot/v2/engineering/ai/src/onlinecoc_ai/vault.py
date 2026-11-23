"""Local credential storage. Windows DPAPI protects values for the OS user."""
import base64
import os
from pathlib import Path
import re
import threading
import uuid

from .contracts import canonical, loads
from .errors import require
from .local_lock import file_lock

LOCK = threading.RLock()


def default_path():
    root = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local/share'))
    return root / 'OnlineCOC/AI/credentials.json'


class Vault:
    def __init__(self, path=None, *, protector=None):
        self.path = Path(path) if path else default_path()
        self.protector = protector

    def _protect(self, data, decrypt=False):
        if self.protector:return self.protector(data, decrypt)
        require(os.name == 'nt', 'CREDENTIAL_STORE_WINDOWS_REQUIRED')
        from onlinecoc.host_control import protect
        return protect(data, decrypt)

    def _read(self):
        if not self.path.exists():return {'version': 1, 'keys': {}}
        value = loads(self.path.read_bytes())
        require(set(value) == {'version', 'keys'} and value['version'] == 1 and type(value['keys']) is dict, 'CREDENTIAL_STORE_INVALID')
        return value

    def _name(self, reference):
        require(isinstance(reference, str) and re.fullmatch(r'env:[A-Za-z_][A-Za-z0-9_]{0,235}', reference), 'CREDENTIAL_REFERENCE_INVALID')
        return reference[4:]

    def has(self, reference):
        with LOCK:return self._name(reference) in self._read()['keys']

    def get(self, reference):
        with LOCK:value = self._read()['keys'].get(self._name(reference))
        return self._protect(base64.b64decode(value, validate=True), True).decode('utf-8') if value else None

    def put(self, reference, secret):
        name = self._name(reference)
        require(isinstance(secret, str) and 0 < len(secret) <= 8192 and all(32 < ord(c) < 127 for c in secret), 'CREDENTIAL_INVALID')
        encrypted = base64.b64encode(self._protect(secret.encode())).decode()
        with LOCK, file_lock(self.path):
            value = self._read();value['keys'][name] = encrypted;self._save(value)

    def remove(self, reference):
        with LOCK, file_lock(self.path):
            value = self._read();value['keys'].pop(self._name(reference), None);self._save(value)

    def _save(self, value):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            with temporary.open('xb') as stream:
                stream.write(canonical(value));stream.flush();os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:temporary.unlink(missing_ok=True)
