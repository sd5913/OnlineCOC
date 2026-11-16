"""Immutable group exports; unauthorized group names and hashes never leave the host."""
from pathlib import Path
import re

from onlinecoc_p2p.common import atomic_json, canonical, digest, read_json, require, sign
from onlinecoc_p2p.packages import Package
from .bridge import validate_bridge


class Resources:
    def __init__(self, path):
        self.path = Path(path)
        self.descriptor = read_json(self.path / "web.json")
        self.version = digest(canonical(self.descriptor))
        self.groups = {g["id"]: {**g, "package": Package(self.path / g["digest"])} for g in self.descriptor["groups"]}

    @classmethod
    def export(cls, source, descriptor, output):
        data = read_json(Path(descriptor))
        expected = {"webVersion", "package", "rules", "groups", "routes", "modules"}
        if data.get('webVersion') == 2:
            expected.add('bridge'); validate_bridge(data.get('bridge'))
        require(set(data) == expected, "WEB_DESCRIPTOR_INVALID")
        require(data["webVersion"] in {1, 2} and data["modules"].get("required") == ["network-web"], "WEB_VERSION_UNSUPPORTED")
        require(isinstance(data["groups"], list) and 1 <= len(data["groups"]) <= 32)
        require(isinstance(data["rules"], str) and len(data["rules"]) <= 8000)
        require(set(data["package"]) == {"id", "name", "version", "source", "description"})
        require(all(isinstance(v, str) and len(v) <= 1024 for v in data["package"].values()))
        require(isinstance(data["routes"], list) and len(data["routes"]) <= 64)
        for route in data["routes"]:
            require(set(route) <= {"method", "path", "requires"} and route["method"] in {"GET", "POST"})
            require(isinstance(route["path"], str) and re.fullmatch(r"[a-z/]{1,80}", route["path"]))
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        groups, seen = [], set()
        for group in data["groups"]:
            require(set(group) == {"id", "access", "entry", "files"})
            gid = group["id"]
            require(isinstance(gid, str) and re.fullmatch(r"[a-z0-9-]{1,40}", gid) and gid not in seen)
            require(group["access"] in {"members", "grant"})
            seen.add(gid)
            if gid == "startup":
                require(group["access"] == "members" and group["entry"], "STARTUP_INVALID")
            temporary = output / ("descriptor-" + gid + ".json")
            atomic_json(temporary, {"packageId": data["package"]["id"], "version": data["package"]["version"],
                "entry": group["entry"], "files": group["files"]})
            try:
                exported = Package.export(Path(source), temporary, output)
            finally:
                temporary.unlink(missing_ok=True)
            groups.append({"id": gid, "access": group["access"], "digest": exported.name})
        require("startup" in seen, "STARTUP_REQUIRED")
        require(all(set(r.get("requires", [])) <= seen for r in data["routes"]), "ROUTE_GROUP_INVALID")
        value = {**data, "groups": groups}
        destination = output / ("web-" + digest(canonical(value)))
        destination.mkdir(exist_ok=True)
        # Exports are immutable. Copy only explicit player blobs, never the source tree.
        import shutil
        for group in groups:
            target = destination / group["digest"]
            if not target.exists():
                shutil.copytree(output / group["digest"], target)
        atomic_json(destination / "web.json", value)
        return destination

    def allowed(self, gid, grants):
        group = self.groups.get(gid)
        require(group and (group["access"] == "members" or gid in grants), "RESOURCE_FORBIDDEN", 403)
        return group["package"]

    def manifest(self, gid, grants, identity):
        package = self.allowed(gid, grants)
        manifest = {**package.manifest, "protocolVersion": 2, "resourceVersion": self.version, "group": gid,
            **({'bridge': self.descriptor['bridge']} if 'bridge' in self.descriptor else {}),
            "availableGroups": [k for k, v in self.groups.items() if v["access"] == "members" or k in grants]}
        checksum = digest(canonical(manifest))
        return {"manifest": manifest, "digest": checksum, "signature": sign(identity, checksum)}

    def metadata(self, title):
        return {"title": title, "description": self.descriptor["package"]["description"],
            "package": self.descriptor["package"], "rules": self.descriptor["rules"], "resourceVersion": self.version,
            "startupBytes": sum(f["size"] for f in self.groups["startup"]["package"].manifest["files"]),
            "totalBytes": sum(f["size"] for v in self.groups.values() for f in v["package"].manifest["files"])}
