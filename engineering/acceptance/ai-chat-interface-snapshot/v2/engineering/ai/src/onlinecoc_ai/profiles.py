"""Local administrator configuration. Secrets are resolved only when calling."""
import copy
import os
from pathlib import Path
import uuid
import threading

from .contracts import canonical, loads, validate
from .errors import AiError, require
from .local_lock import file_lock

AI_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = AI_ROOT / "config/ai-providers.json"
PROFILE_LOCK = threading.RLock()


def load_profiles(path=DEFAULT_PATH):
    value = loads(Path(path).read_bytes())
    require(type(value) is dict and set(value) == {"schemaVersion", "profiles"} and value["schemaVersion"] == 1, "INPUT_INVALID")
    require(type(value["profiles"]) is list and len(value["profiles"]) <= 32, "LIMIT_EXCEEDED")
    profiles = {}
    for profile in value["profiles"]:
        validate("Profile", profile)
        require(profile["profileId"] not in profiles, "PROFILE_ID_CONFLICT")
        profiles[profile["profileId"]] = profile
    return profiles


def initialize(path=DEFAULT_PATH):
    path = Path(path)
    require(not path.exists(), "TARGET_EXISTS")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write((AI_ROOT / "examples/ai-providers.json").read_bytes())
        stream.flush()
        os.fsync(stream.fileno())
    return str(path)


def save_profile(profile, path=DEFAULT_PATH, *, expected_revision=None):
    with PROFILE_LOCK, file_lock(path):
        return _save_profile(profile, path, expected_revision=expected_revision)


def _save_profile(profile, path=DEFAULT_PATH, *, expected_revision=None):
    """The caller supplies a complete Profile; revision is server-assigned."""
    validate("Profile", profile)
    path = Path(path)
    profiles = load_profiles(path)
    if expected_revision is not None:
        require(profiles.get(profile['profileId'], {}).get('revision', 0) == expected_revision, 'PROFILE_VERSION_CONFLICT')
    value = copy.deepcopy(profile)
    value["revision"] = profiles.get(value["profileId"], {}).get("revision", 0) + 1
    profiles[value["profileId"]] = value
    require(len(profiles) <= 32, "LIMIT_EXCEEDED")
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(canonical({"schemaVersion": 1, "profiles": list(profiles.values())}) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return value


def delete_profile(identifier, revision, path=DEFAULT_PATH):
    with PROFILE_LOCK, file_lock(path):
        profiles = load_profiles(path)
        require(identifier in profiles, 'PROFILE_NOT_FOUND')
        require(profiles[identifier]['revision'] == revision, 'PROFILE_VERSION_CONFLICT')
        require(not profiles[identifier]['enabled'], 'PROFILE_MUST_BE_DISABLED')
        del profiles[identifier]
        target = Path(path);temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            with temporary.open('xb') as stream:
                stream.write(canonical({'schemaVersion': 1, 'profiles': list(profiles.values())}) + b'\n')
                stream.flush();os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:temporary.unlink(missing_ok=True)
        return {'deleted': identifier}


def credential(profile, *, vault=None):
    """Only read the one explicitly configured process/user variable."""
    from .vault import Vault
    vault = vault or Vault()
    # An explicit key saved in the manager takes precedence over legacy env.
    value = vault.get(profile['credentialRef'])
    if value:return value
    name = profile["credentialRef"][4:]
    value = os.environ.get(name)
    if not value and os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                value, kind = winreg.QueryValueEx(key, name)
                if kind != winreg.REG_SZ:
                    value = None
        except OSError:
            value = None
    require(isinstance(value, str) and 0 < len(value) <= 8192 and all(32 < ord(c) < 127 for c in value), "CREDENTIAL_MISSING")
    return value
