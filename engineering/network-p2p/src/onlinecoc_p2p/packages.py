from __future__ import annotations

import base64
import json
import re
import shutil
import unicodedata
from pathlib import Path, PurePosixPath

from .common import Fault, MAX_RESPONSE, atomic_json, canonical, digest, read_json, require, sign

BLOCK = 262144
DENIED_PARTS = {"identity", "rooms", "runtime", "backups", "logs", "host", "secrets", "node_modules", "__pycache__"}
DENIED_SUFFIXES = {".exe", ".dll", ".py", ".pyc", ".ps1", ".bat", ".cmd", ".sh", ".so", ".dylib", ".pem", ".key", ".ppk"}
DEVICE = re.compile(r"^(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)", re.I)


def safe_path(value):
    require(isinstance(value, str) and 0 < len(value) <= 240 and value == unicodedata.normalize("NFC", value), "PACKAGE_PATH_INVALID")
    path = PurePosixPath(value)
    require(not path.is_absolute() and "\\" not in value and not re.search(r'[<>:"|?*\x00-\x1f]', value), "PACKAGE_PATH_INVALID")
    parts = value.split("/")
    require(all(p and p not in {".", ".."} and not p.startswith(".") and not p.endswith((" ", "."))
                and p.casefold() not in DENIED_PARTS and not DEVICE.match(p) for p in parts), "PACKAGE_PATH_INVALID")
    require(path.suffix.lower() not in DENIED_SUFFIXES, "PACKAGE_EXECUTABLE_DENIED")
    return path


class Package:
    """Explicit player export only. Snapshots are immutable; no recursive source sharing."""
    def __init__(self, path: Path | None = None):
        self.path = path
        self.manifest = read_json(path / "manifest.json") if path else {
            "protocolVersion": 1, "packageId": "onlinecoc-console", "version": "1", "entry": None, "files": []}
        self.digest = digest(canonical(self.manifest))
        self.files = {f["digest"]: f for f in self.manifest["files"]}
        require(len(self.files) <= 10000 and len(canonical(self.manifest)) < MAX_RESPONSE - 8192, "PACKAGE_LIMIT")

    def signed_manifest(self, identity):
        return {"manifest": self.manifest, "digest": self.digest, "signature": sign(identity, self.digest)}

    def chunk(self, expected, file_digest, block_index):
        require(expected == self.digest, "CONTENT_CHANGED", 409)
        require(isinstance(file_digest, str) and file_digest in self.files, "FILE_NOT_AUTHORIZED", 403)
        file = self.files[file_digest]
        require(type(block_index) is int and 0 <= block_index < len(file["blocks"]), "BLOCK_INVALID")
        with open(self.path / "blobs" / file_digest, "rb") as source:
            source.seek(block_index * BLOCK)
            data = source.read(BLOCK)
        require(digest(data) == file["blocks"][block_index], "EXPORT_CORRUPTED", 500)
        return {"digest": file_digest, "index": block_index, "data": base64.b64encode(data).decode(),
                "blockDigest": file["blocks"][block_index]}

    @staticmethod
    def export(source: Path, descriptor: Path, output: Path):
        spec = read_json(descriptor)
        require(isinstance(spec, dict) and set(spec) == {"packageId", "version", "entry", "files"}, "DISTRIBUTION_INVALID")
        require(isinstance(spec["packageId"], str) and re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", spec["packageId"]), "DISTRIBUTION_INVALID")
        require(isinstance(spec["version"], str) and 0 < len(spec["version"]) <= 64, "DISTRIBUTION_INVALID")
        require(isinstance(spec["files"], list) and len(spec["files"]) <= 10000, "PACKAGE_LIMIT")
        source, files, seen, total = source.resolve(), [], set(), 0
        contents = {}
        for name in spec["files"]:
            relative = safe_path(name)
            folded = name.casefold()
            require(folded not in seen, "PACKAGE_PATH_COLLISION")
            seen.add(folded)
            candidate = source.joinpath(*relative.parts)
            for parent in (candidate, *candidate.parents):
                if parent == source:
                    break
                require(not parent.is_symlink() and not parent.is_junction(), "PACKAGE_LINK_DENIED")
            require(candidate.is_file() and candidate.resolve().is_relative_to(source), "PACKAGE_PATH_INVALID")
            st = candidate.stat()
            require(st.st_nlink == 1, "PACKAGE_LINK_DENIED")
            require(st.st_size <= 64 * 1024 * 1024, "PACKAGE_LIMIT")
            raw = candidate.read_bytes()
            total += len(raw)
            require(total <= 512 * 1024 * 1024, "PACKAGE_LIMIT")
            sha = digest(raw)
            blocks = [digest(raw[i:i + BLOCK]) for i in range(0, len(raw), BLOCK)]
            files.append({"path": name, "digest": sha, "size": len(raw), "blocks": blocks})
            contents[sha] = raw
        require(spec["entry"] is None or (isinstance(spec["entry"], str) and spec["entry"].casefold() in seen
                                         and spec["entry"].lower().endswith(".html")), "PACKAGE_ENTRY_INVALID")
        manifest = {"protocolVersion": 1, "packageId": spec["packageId"], "version": spec["version"],
                    "entry": spec["entry"], "files": sorted(files, key=lambda f: f["path"])}
        require(len(canonical(manifest)) < MAX_RESPONSE - 8192, "PACKAGE_LIMIT")
        final = output.resolve() / digest(canonical(manifest))
        require(not final.exists(), "EXPORT_ALREADY_EXISTS", 409)
        final.mkdir(parents=True)
        (final / "blobs").mkdir()
        for sha, raw in contents.items():
            (final / "blobs" / sha).write_bytes(raw)
        atomic_json(final / "manifest.json", manifest)
        return final


class Cache:
    def __init__(self, root: Path):
        self.root = root
        for part in ("blobs", "staging", "manifests", "rooms"):
            (root / part).mkdir(parents=True, exist_ok=True)

    async def sync(self, signed, fetch, room_id):
        manifest = signed["manifest"]
        expected = digest(canonical(manifest))
        require(expected == signed["digest"], "MANIFEST_CORRUPTED")
        require(isinstance(room_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", room_id), "ROOM_INVALID")
        total = sum(file["size"] for file in manifest["files"])
        require(total <= 512 * 1024 * 1024 and shutil.disk_usage(self.root).free > total * 2 + 1024 * 1024, "CACHE_SPACE")
        downloaded = 0
        for file in manifest["files"]:
            safe_path(file["path"])
            require(re.fullmatch(r"[0-9a-f]{64}", file["digest"]) and type(file["size"]) is int and
                    0 <= file["size"] <= 64 * 1024 * 1024, "MANIFEST_INVALID")
            require(len(file["blocks"]) == (file["size"] + BLOCK - 1) // BLOCK, "MANIFEST_INVALID")
            target = self.root / "blobs" / file["digest"]
            if target.exists() and digest(target.read_bytes()) == file["digest"]:
                continue
            stage = self.root / "staging" / file["digest"]
            stage.mkdir(exist_ok=True)
            for index, sha in enumerate(file["blocks"]):
                part = stage / str(index)
                if not part.exists() or digest(part.read_bytes()) != sha:
                    block = await fetch(expected, file["digest"], index)
                    raw = base64.b64decode(block["data"], validate=True)
                    require(len(raw) <= BLOCK and digest(raw) == sha, "CHUNK_CORRUPTED")
                    part.write_bytes(raw)
                    downloaded += len(raw)
            temporary = target.with_suffix(".part")
            with open(temporary, "wb") as stream:
                for index in range(len(file["blocks"])):
                    stream.write((stage / str(index)).read_bytes())
            require(temporary.stat().st_size == file["size"] and digest(temporary.read_bytes()) == file["digest"], "FILE_CORRUPTED")
            temporary.replace(target)
        atomic_json(self.root / "manifests" / (expected + ".json"), signed)
        atomic_json(self.root / "rooms" / (room_id + ".json"), {"digest": expected})
        return {"digest": expected, "downloadedBytes": downloaded}
