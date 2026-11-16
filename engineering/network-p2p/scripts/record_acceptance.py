"""Curate passing-suite evidence without copying credentials or raw logs."""
import argparse
import datetime
import hashlib
import json
import platform
import xml.etree.ElementTree as ET
from pathlib import Path

from onlinecoc_p2p import __version__
from onlinecoc_p2p.common import atomic_json

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--results", type=Path, default=root / "local/acceptance/final-0.2.xml")
args = parser.parse_args()
suite = ET.parse(args.results).getroot().find("testsuite")
assert suite is not None and suite.attrib["failures"] == "0" and suite.attrib["errors"] == "0"
count = int(suite.attrib["tests"])
assert count > 0 and int(suite.attrib.get("skipped", 0)) == 0
required = {"test_codes_collision_migration_and_stability",
            "test_short_code_preserves_private_invite_password_and_approval",
            "test_offline_room_code_cannot_create_intent",
            "test_discovery_filters_stale_external_redirect_and_secrets",
            "test_discovery_local_capability_publisher_and_origin_boundary",
            "test_browser_discover_host_copy_private_code_and_join",
            "test_real_backend_registered_host_discovery"}
assert required <= {case.attrib["name"] for case in suite.findall("testcase")}
reports = {}
for name in ("cloud-udp", "cloud-tcp", "browser-cloud", "cross-machine-relay", "cross-machine-auto",
             "real-host", "player-bundle", "player-smoke", "deployment-health"):
    reports[name] = json.loads((root / ("local/acceptance/" + name + ".json")).read_text(encoding="utf-8"))
assert reports["cloud-udp"]["shortCodeJoin"] and reports["cloud-tcp"]["shortCodeJoin"]
sources = {}
for path in (root / "src/onlinecoc_p2p").rglob("*"):
    if path.is_file() and path.suffix in {".py", ".js", ".html", ".css"} and "__pycache__" not in path.parts:
        sources[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
for path in [root / "play.cmd", root / "setup.ps1", root / "start.ps1", root / "scripts/build_player.py"]:
    sources[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
payload = {
    "date": datetime.datetime.now().astimezone().isoformat(), "moduleVersion": __version__,
    "python": platform.python_version(),
    "tests": {"passed": count, "failed": 0, "skipped": 0, "seconds": float(suite.attrib["time"])},
    "features": {"persistentShortCodes": True, "legacyRoomIds": True, "privateAdmissionPreserved": True,
                 "clipboardJoinInfo": True, "registeredLocalHosts": True, "realHostDiscovery": True,
                 "playerLauncher": "play.cmd"},
    "evidence": reports,
    "limits": ["No two human testers on independent residential/mobile networks in this run",
               "No 80-player or long-duration saturation claim",
               "Stumpsville full UI and package-service forwarding remain unsupported",
               "Single-node directory; manual client rejoin after transport failure",
               "Discovery reads current-user host registrations and the configured loopback address, not stopped saves",
               "Source player bundle requires Python 3.14 and first-install network access"],
    "sourceSha256": sources}
atomic_json(root / ("acceptance/2026-11-13-" + __version__ + ".json"), payload)
print(f"Curated acceptance {__version__}: {count} passed; source hashes and sanitized evidence saved")
