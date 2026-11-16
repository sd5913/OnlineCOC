import os

import pytest

from onlinecoc_p2p.common import Fault, atomic_json, digest
from onlinecoc_p2p.packages import Cache, Package, safe_path


@pytest.mark.parametrize("path", ["../private.json", "/etc/passwd", "ui\\x.html", "C:/secret", "ui/a:stream",
    "ui/CON.txt", "runtime/state.json", ".env", "secrets/a.json", "x.py", "ui/A. ", "ui//a.html"])
def test_unsafe_export_paths(path):
    with pytest.raises(Fault):
        safe_path(path)


async def test_export_sync_resume_corruption_and_cache(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    raw = b"a" * 600000
    (source / "data.txt").write_bytes(raw)
    spec = source / "distribution.json"
    atomic_json(spec, {"packageId": "demo", "version": "1", "entry": None, "files": ["data.txt"]})
    package = Package(Package.export(source, spec, tmp_path / "export"))
    cache = Cache(tmp_path / "cache")
    calls = []
    async def fetch(m, f, i):
        calls.append(i)
        if i == 1 and len(calls) == 2:
            raise OSError("simulated interruption")
        return package.chunk(m, f, i)
    signed = {"manifest": package.manifest, "digest": package.digest}
    with pytest.raises(OSError):
        await cache.sync(signed, fetch, "room")
    assert not (cache.root / "rooms/room.json").exists()
    await cache.sync(signed, fetch, "room")
    assert calls.count(0) == 1
    assert (cache.root / "blobs" / digest(raw)).read_bytes() == raw
    assert (await cache.sync(signed, fetch, "room"))["downloadedBytes"] == 0
    with pytest.raises(Fault, match="FILE_NOT_AUTHORIZED"):
        package.chunk(package.digest, "f" * 64, 0)


def test_export_rejects_case_collision(tmp_path):
    (tmp_path / "one.txt").write_text("one")
    spec = tmp_path / "distribution.json"
    atomic_json(spec, {"packageId": "demo", "version": "1", "entry": None, "files": ["one.txt", "ONE.TXT"]})
    with pytest.raises(Fault, match="PACKAGE_PATH_COLLISION"):
        Package.export(tmp_path, spec, tmp_path / "out")
