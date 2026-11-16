"""Build a source-only bundle; local configurations, credentials and game assets are excluded."""
import hashlib
import json
import tarfile
from pathlib import Path

module = Path(__file__).resolve().parents[1]
destination = module / "local/web.tar.gz"
destination.parent.mkdir(parents=True, exist_ok=True)
with tarfile.open(destination, "w:gz") as archive:
    for name, root in (("web-app", module), ("p2p-app", module.parent / "network-p2p")):
        archive.add(root / "pyproject.toml", arcname=name + "/pyproject.toml")
        for path in sorted((root / "src").rglob("*")):
            if path.is_file() and path.suffix in {".py", ".html", ".js", ".css"} and "__pycache__" not in path.parts:
                archive.add(path, arcname=name + "/" + path.relative_to(root).as_posix())
    archive.add(module / "deploy/install-remote.sh", arcname="install-remote.sh")
print(json.dumps({"bundle": str(destination), "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(), "bytes": destination.stat().st_size}))
