"""Run on the CVM with its release venv. Print only non-secret deployment evidence."""
import hashlib
import json
import subprocess
from pathlib import Path

import onlinecoc_p2p
import onlinecoc_web
from cryptography import x509

config = json.loads(Path("/etc/onlinecoc-network/directory.json").read_text())
state = json.loads(Path(config["webStateFile"]).read_text())
cert = x509.load_pem_x509_certificate(Path("/etc/onlinecoc-network/server.pem").read_bytes())
sources = {}
for name, module in (("network-web", onlinecoc_web), ("network-p2p", onlinecoc_p2p)):
    root = Path(module.__file__).parent
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix in {".py", ".js", ".html", ".css"} and "__pycache__" not in path.parts:
            sources[name + "/src/" + root.name + "/" + path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
print(json.dumps({"release": Path("/opt/onlinecoc-network/current-web-release").read_text().strip(),
    "webVersion": onlinecoc_web.__version__, "p2pVersion": onlinecoc_p2p.__version__,
    "services": {name: subprocess.check_output(["systemctl", "is-active", name], text=True).strip()
                 for name in ("onlinecoc-directory", "onlinecoc-turn")},
    "roomStateFile": config["stateFile"], "accountStateFile": config["webStateFile"],
    "accountCount": len(state["accounts"]), "webRoomCount": len(state["rooms"]),
    "certificateNotAfterUTC": cert.not_valid_after_utc.isoformat(), "sources": sources}, ensure_ascii=False))
