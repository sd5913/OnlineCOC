"""Versioned, one-use room setup handoff. Never includes publisher or game credentials."""
from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

from onlinecoc_p2p.common import canonical, read_json, require

PREFIX = "OCOC-ROOM1."


def platform_origin(url):
    require(isinstance(url, str), "SETUP_INVALID")
    parsed = urlsplit(url)
    require(parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username
            and not parsed.password and parsed.path in {"", "/"} and not parsed.query and not parsed.fragment,
            "SETUP_INVALID")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def make_room_setup(directory, room_code, claim):
    data = {"version": 1, "origin": platform_origin(directory), "roomCode": room_code, "claim": claim}
    value = PREFIX + base64.urlsafe_b64encode(canonical(data)).decode().rstrip("=")
    parse_room_setup(value, data["origin"])
    return value


def parse_room_setup(value, origin):
    require(isinstance(value, str) and len(value) <= 2048, "SETUP_INVALID")
    value = value.strip()
    require(value.startswith(PREFIX), "SETUP_INVALID")
    encoded = value[len(PREFIX):]
    require(re.fullmatch(r"[A-Za-z0-9_-]+", encoded), "SETUP_INVALID")
    try:
        data = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    except (ValueError, UnicodeError):
        require(False, "SETUP_INVALID")
    require(isinstance(data, dict) and set(data) == {"version", "origin", "roomCode", "claim"}, "SETUP_INVALID")
    require(type(data["version"]) is int and data["version"] == 1, "SETUP_VERSION_UNSUPPORTED")
    require(data["origin"] == platform_origin(origin), "SETUP_PLATFORM_MISMATCH")
    require(isinstance(data["roomCode"], str) and re.fullmatch(r"[A-Z0-9]{8}", data["roomCode"]), "SETUP_INVALID")
    require(isinstance(data["claim"], str) and re.fullmatch(r"[A-Za-z0-9_-]{16,256}", data["claim"]), "SETUP_INVALID")
    return data


def export_room_setup(state_path):
    """Public pack integration helper; return the string to a host-only copy button."""
    entry = read_json(Path(state_path) / "web-entry.json")
    require(entry.get("claim"), "ROOM_ALREADY_CLAIMED", 409)
    require(entry.get("claimExpiresAt", 0) > time.time(), "CLAIM_EXPIRED", 409)
    return make_room_setup(entry["url"], entry["roomCode"], entry["claim"])
