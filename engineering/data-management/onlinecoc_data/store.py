"""Framework-free, single-writer JSON snapshot store. No business algorithms."""
import copy
import gzip
import re
import hashlib
import json
import os
import threading
import uuid
from pathlib import Path

class StoreError(Exception):
    pass

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def digest(data):
    return hashlib.sha256(data).hexdigest()

class FileDataStore:
    FORMAT = 1
    def __init__(self, directory, *, max_bytes=512*1024*1024, fault=None,
                 auto_compress=False, retain_generations=2):
        if type(auto_compress) is not bool or type(retain_generations) is not int or retain_generations < 1:
            raise StoreError("INVALID_RETENTION")
        self.path = Path(directory)
        self.path.mkdir(parents=True, exist_ok=True)
        self.generations = self.path / "generations"
        self.generations.mkdir(exist_ok=True)
        self.staging = self.path / "staging"
        self.staging.mkdir(exist_ok=True)
        self.max_bytes, self.fault = max_bytes, fault
        self.auto_compress, self.retain_generations = auto_compress, retain_generations
        self.mutex = threading.RLock()
        self.lock = open(self.path / "writer.lock", "a+b")
        self.lock.seek(0)
        if (self.path / "writer.lock").stat().st_size == 0:
            self.lock.write(b"0"); self.lock.flush()
        self.lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            self.lock.close()
            raise StoreError("STORE_LOCKED") from e
        self.generation, self.head, self.value = 0, None, None
        self.closed = False
        try:
            self.generation, self.head, self.value = self._load_chain()
        except Exception as e:
            self.close()
            raise StoreError("STORE_CORRUPT_OR_UNSUPPORTED") from e

    def _generation_files(self):
        files = {}
        for path in self.generations.iterdir():
            if not (path.name.endswith('.json') or path.name.endswith('.json.gz')): continue
            if not re.fullmatch(r'[0-9]{12,}\.json(?:\.gz)?', path.name) or path.is_symlink():
                raise StoreError('STORE_CORRUPT')
            number = int(path.name.removesuffix('.gz').removesuffix('.json'))
            compressed = path.name.endswith('.gz')
            if number < 1 or path.name != f'{number:012d}.json'+('.gz' if compressed else ''):
                raise StoreError('STORE_CORRUPT')
            files.setdefault(number, {})['compressed' if compressed else 'raw'] = path
        return sorted(files.items())

    def _read_generation(self, path):
        opener = gzip.open if path.name.endswith('.gz') else open
        with opener(path, 'rb') as stream: raw = stream.read(self.max_bytes + 1)
        if len(raw) > self.max_bytes: raise StoreError('STORE_CORRUPT')
        return raw

    def _load_chain(self):
        generation, head, value = 0, None, None
        for number, paths in self._generation_files():
            # Both representations can exist after publication loses its reply.
            # Verify exact original bytes, then count the generation only once.
            versions = [self._read_generation(path) for path in paths.values()]
            raw = versions[0]
            if any(other != raw for other in versions[1:]): raise StoreError('STORE_CORRUPT')
            env = json.loads(raw)
            data = canonical(env.get('payload'))
            if (type(env.get('format')) is not int or env['format'] != self.FORMAT
                or type(env.get('generation')) is not int or env['generation'] != generation+1
                or number != generation+1 or env.get('parent') != head
                or env.get('digest') != digest(data)
                or type(env.get('length')) is not int or env['length'] != len(data)):
                raise StoreError('STORE_CORRUPT')
            generation, head, value = number, digest(raw), env['payload']
        return generation, head, value

    @staticmethod
    def _sync_directory(directory):
        if os.name != 'nt':
            fd = os.open(directory, os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)

    def _disk_bytes(self):
        return (sum(path.stat().st_size for _, paths in self._generation_files() for path in paths.values())
                + sum(path.stat().st_size for path in self.staging.glob('*.tmp')))

    def compress_history(self, expected_generation=None):
        """Reversibly archive old snapshots; preserve every generation and byte.

        The full hash chain is checked first. Publish and verify a lossless gzip
        copy before unlinking its redundant raw file. Keep recent files raw.
        """
        with self.mutex:
            if self.closed: raise StoreError('STORE_CLOSED')
            if expected_generation is not None and expected_generation != self.generation:
                raise StoreError('VERSION_CONFLICT')
            generation, head, _ = self._load_chain()
            if generation != self.generation or head != self.head: raise StoreError('STORE_CHANGED')
            before = self._disk_bytes(); archived = 0
            for number, paths in self._generation_files():
                if number > self.generation-self.retain_generations or 'raw' not in paths: continue
                path = paths['raw']; raw = self._read_generation(path)
                target = path.with_name(path.name+'.gz')
                if 'compressed' not in paths:
                    packed = gzip.compress(raw, compresslevel=6, mtime=0)
                    if len(packed) >= len(raw): continue
                    if self._disk_bytes()+len(packed) > self.max_bytes: raise StoreError('STORE_FULL')
                    tmp = self.staging / (uuid.uuid4().hex+'.tmp')
                    try:
                        self._fault('compression_before_write')
                        with open(tmp, 'xb') as stream:
                            stream.write(packed[:len(packed)//2]); self._fault('compression_half_write')
                            stream.write(packed[len(packed)//2:]); stream.flush()
                            self._fault('compression_before_sync'); os.fsync(stream.fileno())
                        if gzip.decompress(tmp.read_bytes()) != raw: raise StoreError('ARCHIVE_VERIFY_FAILED')
                        self._fault('compression_before_publish')
                        os.replace(tmp, target); self._sync_directory(self.generations)
                        self._fault('compression_after_publish')
                    finally:
                        if tmp.exists(): tmp.unlink()
                if self._read_generation(target) != raw: raise StoreError('ARCHIVE_VERIFY_FAILED')
                self._fault('compression_before_unlink')
                path.unlink(); archived += 1
                self._sync_directory(self.generations); self._fault('compression_after_unlink')
            after = self._disk_bytes()
            return {'generation':self.generation,'archivedGenerations':archived,
                    'freedBytes':before-after,'bytes':after,'historyPreserved':True}

    def _fault(self, stage):
        if self.fault: self.fault(stage)

    def snapshot(self):
        with self.mutex:
            if self.closed: raise StoreError("STORE_CLOSED")
            return self.generation, copy.deepcopy(self.value)

    def commit(self, expected_generation, value):
        with self.mutex:
            if self.closed: raise StoreError("STORE_CLOSED")
            if expected_generation != self.generation: raise StoreError("VERSION_CONFLICT")
            data = canonical(value)
            env = {"format":self.FORMAT,"generation":self.generation+1,"parent":self.head,
                   "digest":digest(data),"length":len(data),"payload":value}
            raw = canonical(env)
            used = self._disk_bytes()
            if used + len(raw)*2 > self.max_bytes and self.auto_compress:
                self.compress_history(expected_generation)
                used = self._disk_bytes()
            if used + len(raw)*2 > self.max_bytes: raise StoreError("STORE_FULL")
            tmp = self.staging / (uuid.uuid4().hex + ".tmp")
            self._fault("before_write")
            try:
                with open(tmp,"xb") as f:
                    f.write(raw[:len(raw)//2]); self._fault("half_write")
                    f.write(raw[len(raw)//2:]); f.flush(); self._fault("before_sync")
                    os.fsync(f.fileno()); self._fault("before_publish")
                target = self.generations / f"{self.generation+1:012d}.json"
                if target.exists(): raise StoreError("GENERATION_EXISTS")
                os.replace(tmp,target)
                # Publication is visible. Preserve in-memory consistency even if the caller loses its reply.
                self.generation += 1
                self.head, self.value = digest(raw), copy.deepcopy(value)
                if os.name != "nt":
                    fd=os.open(self.generations,os.O_RDONLY)
                    try: os.fsync(fd)
                    finally: os.close(fd)
                self._fault("after_publish")
                return self.generation
            finally:
                if tmp.exists(): tmp.unlink()

    def query(self, collection, **equals):
        _, state=self.snapshot()
        values=(state or {}).get(collection,{})
        if not isinstance(values,dict): raise StoreError("INVALID_COLLECTION")
        return [copy.deepcopy(v) for v in values.values() if all(v.get(k)==x for k,x in equals.items())]

    def get_receipt(self, account, command):
        return (self.snapshot()[1] or {}).get("commands",{}).get(account+":"+command)

    def export_snapshot(self, target):
        with self.mutex:
            generation,payload=self.snapshot()
            env={"format":1,"sourceGeneration":generation,"payload":payload,"digest":digest(canonical(payload))}
            path=Path(target)
            with open(path,"xb") as f:
                f.write(canonical(env)); f.flush(); os.fsync(f.fileno())

    @classmethod
    def restore(cls, bundle, directory):
        env=json.loads(Path(bundle).read_bytes())
        if env.get("format")!=1 or env.get("digest")!=digest(canonical(env.get("payload"))):
            raise StoreError("BACKUP_INVALID")
        path=Path(directory)
        if path.exists(): raise StoreError("RESTORE_TARGET_EXISTS")
        with cls(path) as store: store.commit(0,env["payload"])

    def inspect(self):
        with self.mutex:
            return {"format":1,"generation":self.generation,"bytes":self._disk_bytes()}

    def close(self):
        if getattr(self,"closed",False): return
        self.closed=True
        if not self.lock.closed:
            self.lock.seek(0)
            if os.name=="nt":
                import msvcrt
                msvcrt.locking(self.lock.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(self.lock.fileno(),fcntl.LOCK_UN)
            self.lock.close()
    def __enter__(self): return self
    def __exit__(self,*args): self.close()

class MemoryDataStore:
    """Contract test implementation; deliberately not a durable production store."""
    def __init__(self,directory=None): self.generation,self.value=0,None
    def snapshot(self): return self.generation,copy.deepcopy(self.value)
    def commit(self,expected_generation,value):
        if expected_generation!=self.generation: raise StoreError("VERSION_CONFLICT")
        canonical(value)
        self.generation+=1; self.value=copy.deepcopy(value); return self.generation

    query = FileDataStore.query
    get_receipt = FileDataStore.get_receipt
    def close(self): pass
