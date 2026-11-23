"""Bounded, immutable snapshot of administrator-selected pack material."""
import copy
from pathlib import Path, PurePosixPath
import re

from jsonschema import Draft202012Validator

from .contracts import canonical, digest, loads, validate
from .errors import AiError, require

MAX_PACK_BYTES = 8 * 1024 * 1024
MAX_FILE_BYTES = 1024 * 1024


def safe_path(name):
    require(isinstance(name, str) and 0 < len(name) <= 240 and
            all(re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*", part) and
                part.rstrip(". ") == part and part.split(".")[0].upper() not in
                {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(10)], *[f"LPT{i}" for i in range(10)]}
                for part in name.split("/")), "PATH_INVALID", "Invalid pack path", str(name))
    return PurePosixPath(name)


def local_schema(schema):
    """No remote/file resolution or external Schema resources."""
    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("$ref", "$dynamicRef"):
                    require(isinstance(item, str) and item.startswith("#"), "SCHEMA_EXTERNAL_REF")
                if key == "$id":
                    require(False, "SCHEMA_EXTERNAL_REF")
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(schema)
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise AiError("SCHEMA_INVALID", str(exc)[:300]) from exc
    return Draft202012Validator(schema)


class Pack:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        require(self.root.is_dir(), "PATH_INVALID")
        self.files = {}
        self._size = 0
        # Existing flat host packs can keep AI metadata in a subdirectory so
        # their normal root-level Lua/JSON loader remains unchanged.
        manifest_path = 'manifest.json' if (self.root / 'manifest.json').exists() else 'ai/manifest.json'
        self.manifest = self.json(manifest_path)
        required = {"id", "version", "protocolVersion", "configurations", "rules", "data", "ai"}
        require(required <= set(self.manifest) <= required | {'layout'} and
                self.manifest.get('layout', 'directories') in ('directories', 'flat'), "PACK_MANIFEST_INVALID")
        require(self.manifest["protocolVersion"] == 1, "SCHEMA_UNSUPPORTED")
        self.contract = validate("PackContract", self.json(self.manifest["ai"]))
        require(self.contract["packId"] == self.manifest["id"] and self.contract["packVersion"] == self.manifest["version"], "PACK_MANIFEST_INVALID")
        require(self.contract["hostProtocolRange"]["min"] <= 1 <= self.contract["hostProtocolRange"]["max"], "SCHEMA_UNSUPPORTED")
        configs = self.json(self.manifest["configurations"])
        require(isinstance(configs, list) and len(configs) <= 1024, "PACK_MANIFEST_INVALID")
        self.configurations = {c["configurationId"]: validate("Configuration", c) for c in configs}
        require(len(configs) == len(self.configurations), "DUPLICATE_CONFIGURATION")
        flat = self.manifest.get('layout') == 'flat'
        self.sources = self._mapped("rules", "" if flat else "rules/", ".lua", False)
        # Host's normal Path.read_text loader uses universal newlines. Keep the
        # executable artifact identical while raw file bytes still bind the pack.
        self.sources = {name: text.replace('\r\n', '\n').replace('\r', '\n') for name, text in self.sources.items()}
        self.data = self._mapped("data", "" if flat else "config/", ".json", True)
        self.checks = self.json(self.contract["checks"])
        self.metrics = self.json(self.contract["metrics"])
        require(isinstance(self.checks, list) and len(self.checks) <= 256 and isinstance(self.metrics, list) and len(self.metrics) <= 256, "LIMIT_EXCEEDED")
        for name, values in (("CheckSpec", self.checks), ("Metric", self.metrics)):
            for value in values:
                validate(name, value)
        require(len({c["checkId"] for c in self.checks}) == len(self.checks), "PACK_CHECK_INVALID")
        require(len({m["metricId"] for m in self.metrics}) == len(self.metrics), "PACK_CHECK_INVALID")
        self.scenarios = [validate("Scenario", self.json(p)) for p in self.contract["scenarios"]]
        require(len({s["scenarioId"] for s in self.scenarios}) == len(self.scenarios), "PACK_CHECK_INVALID")
        for source in self.contract["sources"]:
            self.text(source["path"])
        self.text(self.contract["reviewChecklist"])
        self.schemas = {}
        self.inherited_only = {}
        for target, schema in self.contract["schemas"].items():
            safe_path(target)
            require(target.startswith("config/") and target[7:] in self.data, "SCHEMA_TARGET_INVALID")
            document = self.json(schema)
            self.schemas[target[7:]] = local_schema(document)
            if 'x-ai-inherited-only' in document:
                self.inherited_only[target[7:]] = local_schema(document['x-ai-inherited-only'])
        for check in self.checks:
            require(check["sourceRef"].split("#")[0] in {s["id"] for s in self.contract["sources"]}, "SOURCE_MISSING")
            for case in check["caseRefs"]:
                self.json(case)
        for scenario in self.scenarios:
            self.json(scenario["fixtureRef"])
        self.extension_validation = None
        if self.contract['contextMapping'].get('extensionValidation'):
            self.extension_validation=validate('ExtensionValidation',self.json(self.contract['contextMapping']['extensionValidation']))
            local_schema(self.json(self.extension_validation['defaultsSchema']))
            self.json(self.extension_validation['fixtureRef'])
        self.digest = digest(self.files)
        self._sealed = True

    def _mapped(self, field, prefix, suffix, json):
        names = self.manifest[field]
        require(isinstance(names, list) and len(names) <= 64, "LIMIT_EXCEEDED")
        require(len(names) == len({str(n).casefold() for n in names}), "PATH_COLLISION")
        require(all(isinstance(n, str) and "/" not in n and n.endswith(suffix) for n in names), "PATH_INVALID")
        return {n: self.json(prefix + n) if json else self.text(prefix + n) for n in names}

    def text(self, name):
        path = safe_path(name)
        if name in self.files:
            return self.files[name]
        require(not getattr(self, "_sealed", False), "SOURCE_MISSING", "File is outside the pack snapshot", name)
        require(name.casefold() not in {n.casefold() for n in self.files}, "PATH_COLLISION")
        current = self.root
        try:
            for part in path.parts:
                current /= part
                require(not current.is_symlink() and not current.is_junction(), "PATH_ESCAPE")
            resolved = current.resolve(strict=True)
            require(resolved.is_relative_to(self.root) and resolved.is_file(), "PATH_ESCAPE")
            require(resolved.stat().st_size <= MAX_FILE_BYTES, "LIMIT_EXCEEDED")
            with resolved.open("rb") as stream:
                raw = stream.read(MAX_FILE_BYTES + 1)
            require(len(raw) <= MAX_FILE_BYTES, "LIMIT_EXCEEDED")
            self._size += len(raw)
            require(self._size <= MAX_PACK_BYTES and len(self.files) < 512, "LIMIT_EXCEEDED")
            value = raw.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise AiError("PACK_FILE_INVALID", "Missing or invalid UTF-8 pack file", name) from exc
        self.files[name] = value
        return value

    def json(self, name):
        return loads(self.text(name))


def merge_changes(baseline, delta):
    """Construct the full candidate; never silently drop unchanged code/data."""
    validate("ChangeSet", delta)
    result = copy.deepcopy(delta)
    for field in ("sources", "data"):
        result[field] = {**copy.deepcopy(baseline[field]), **result[field]}
    validate("ChangeSet", result)
    return result


def apply_configurations(state, changes):
    result = copy.deepcopy(state)
    for change in changes["configurations"]:
        old = result["configurations"].get(change["id"])
        if change["kind"] == "add":
            require(old is None, "VERSION_CONFLICT")
        else:
            require(old and old["revision"] == change["expectedRevision"], "VERSION_CONFLICT")
            if change['kind'] == 'remove':
                require(not any(e['configurationId'] == change['id'] for e in result['entities'].values()), 'REFERENCE_CONFLICT')
                del result['configurations'][change['id']]
                continue
            require(old["typeRef"] == change["value"]["typeRef"], "TYPE_CHANGE_FORBIDDEN")
            require(old["revision"] != change["value"]["revision"], "VERSION_CONFLICT")
        result["configurations"][change["id"]] = copy.deepcopy(change["value"])
    return result


def fixture_state(fixture, configurations):
    from onlinecoc.model import entity, validate_execution_state as validate_state
    from onlinecoc.version import ROOM_SCHEMA_VERSION
    require(set(fixture) <= {"accounts", "instances", "relations"} and {"accounts", "instances"} <= set(fixture), "FIXTURE_INVALID")
    state = {"schemaVersion": ROOM_SCHEMA_VERSION, "roomId": "demo", "members": {}, "entities": {},
             "relations": copy.deepcopy(fixture.get("relations", {})), "configurations": copy.deepcopy(configurations),
             "progress": {}, "collectionRevision": 1}
    for account in fixture["accounts"]:
        key = account["accountId"]
        require(key not in state["members"], "FIXTURE_INVALID")
        state["members"][key] = {"memberId": "member-" + key, "accountId": key, "role": account["role"], "active": True, "authorizationEpoch": 1, "metadata": {}}
    for spec in fixture["instances"]:
        config = configurations.get(spec["configurationId"])
        require(config is not None, "REFERENCE_CONFLICT")
        instance = entity(spec["instanceId"], config["typeRef"], spec["name"], spec["owner"], **{**config["defaults"], **spec.get("numbers", {})})
        instance.update(configurationId=config["configurationId"], configurationRevision=config["revision"], visibility=spec["visibility"])
        if config["typeRef"] == "bag":
            instance["components"] = {"core.container": {"allowed": ["item", "weapon"]}}
        require(instance["instanceId"] not in state["entities"], "FIXTURE_INVALID")
        state["entities"][instance["instanceId"]] = instance
    validate_state(state)
    return state
