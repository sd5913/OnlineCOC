"""Read-only offline validation. No Host, datastore lock, or migration writes."""
import hashlib
import json
from pathlib import Path
from onlinecoc_data import canonical
from .errors import DomainError, require
from .model import validate


def check_file(path, kind="room"):
    try:
        if kind == "backup":
            from .assets import verify_bundle
            verify_bundle(path)
            return
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        if kind == "snapshot":
            require(value.get("format") == 1, "BACKUP_INVALID")
            payload = value["payload"]
            validate(payload)
            require(hashlib.sha256(canonical(payload)).hexdigest() == value["digest"], "BACKUP_INVALID")
        else:
            require(kind == "room", "INPUT_INVALID")
            validate(value)
    except DomainError:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise DomainError("INPUT_INVALID", {"constraint": "readable-json-or-bundle"}) from None
