from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import ssl
import time
from collections import OrderedDict, deque
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

PROTOCOL = 1
MAX_REQUEST = 65536
MAX_RESPONSE = 2 * 1024 * 1024


class Fault(Exception):
    def __init__(self, code: str, status: int = 400):
        self.code, self.status = code, status
        super().__init__(code)


def require(condition, code="INPUT_INVALID", status=400):
    if not condition:
        raise Fault(code, status)


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def token() -> str:
    return secrets.token_urlsafe(32)


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def unb64(value: str) -> bytes:
    require(isinstance(value, str) and len(value) <= 8192)
    try:
        return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, TypeError):
        raise Fault("INPUT_INVALID") from None


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
    try:
        with open(temporary, "xb") as output:
            if os.name != "nt":
                os.chmod(temporary, 0o600)
            output.write(canonical(value))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def public_key(key) -> dict:
    point = key.public_key().public_numbers()
    return {"kty": "EC", "crv": "P-256", "x": b64(point.x.to_bytes(32, "big")), "y": b64(point.y.to_bytes(32, "big"))}


def parse_public(value: dict):
    require(isinstance(value, dict) and set(value) <= {"kty", "crv", "x", "y", "ext", "key_ops"})
    require(value.get("kty") == "EC" and value.get("crv") == "P-256")
    try:
        x, y = unb64(value["x"]), unb64(value["y"])
        require(len(x) == len(y) == 32)
        return ec.EllipticCurvePublicNumbers(int.from_bytes(x, "big"), int.from_bytes(y, "big"), ec.SECP256R1()).public_key()
    except (ValueError, KeyError):
        raise Fault("PUBLIC_KEY_INVALID") from None


def key_id(value: dict) -> str:
    key = parse_public(value).public_numbers()
    return digest(key.x.to_bytes(32, "big") + key.y.to_bytes(32, "big"))


def sign(key, message: str) -> str:
    der = key.sign(message.encode(), ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der)
    return b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def verify(key: dict, message: str, signature: str):
    from cryptography.exceptions import InvalidSignature
    raw = unb64(signature)
    require(len(raw) == 64, "PROOF_INVALID", 403)
    der = utils.encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    try:
        parse_public(key).verify(der, message.encode(), ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        raise Fault("PROOF_INVALID", 403) from None


def load_identity(path: Path):
    if path.exists():
        return serialization.load_pem_private_key(path.read_bytes(), password=None)
    path.parent.mkdir(parents=True, exist_ok=True)
    key = ec.generate_private_key(ec.SECP256R1())
    with open(path, "xb") as output:
        if os.name != "nt":
            os.chmod(path, 0o600)
        output.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return key


def loopback_url(value: str) -> str:
    require(isinstance(value, str), "UPSTREAM_INVALID")
    u = urlsplit(value)
    require(u.scheme == "http" and u.hostname in {"127.0.0.1", "localhost", "::1"}
            and not u.username and not u.password and u.path in {"", "/"}
            and not u.query and not u.fragment, "UPSTREAM_INVALID")
    try:
        require(1 <= (u.port or 80) <= 65535, "UPSTREAM_INVALID")
    except ValueError:
        raise Fault("UPSTREAM_INVALID") from None
    return value.rstrip("/")


def directory_tls(url: str, ca_file: str | None):
    parsed = urlsplit(url)
    require(not parsed.username and not parsed.password and parsed.path in {"", "/"}
            and not parsed.query and not parsed.fragment, "DIRECTORY_URL_INVALID")
    if parsed.scheme == "http":
        require(parsed.hostname in {"localhost", "127.0.0.1", "::1"}, "TLS_REQUIRED")
        return None
    require(parsed.scheme == "https", "TLS_REQUIRED")
    return ssl.create_default_context(cafile=ca_file)


def sdp_fingerprint(sdp: str) -> str:
    require(isinstance(sdp, str) and len(sdp.encode()) < MAX_REQUEST, "SDP_INVALID")
    require("m=application " in sdp and "m=audio " not in sdp and "m=video " not in sdp, "DATA_ONLY")
    values = re.findall(r"^a=fingerprint:sha-256 ([0-9A-Fa-f:]+)\r?$", sdp, flags=re.MULTILINE)
    require(values and len(set(v.upper() for v in values)) == 1, "DTLS_FINGERPRINT_INVALID")
    fingerprint = values[0].upper()
    require(bool(re.fullmatch(r"(?:[0-9A-F]{2}:){31}[0-9A-F]{2}", fingerprint)), "DTLS_FINGERPRINT_INVALID")
    return fingerprint


class RateLimit:
    """Bounded in-memory limiter; caller uses trusted socket remote address."""
    def __init__(self, maximum=30, window=60, keys=4096, clock=time.monotonic):
        self.maximum, self.window, self.keys, self.clock = maximum, window, keys, clock
        self.entries = OrderedDict()

    def check(self, name):
        now = self.clock()
        queue = self.entries.setdefault(name, deque())
        while queue and queue[0] <= now - self.window:
            queue.popleft()
        require(len(queue) < self.maximum, "RATE_LIMITED", 429)
        queue.append(now)
        self.entries.move_to_end(name)
        while len(self.entries) > self.keys:
            self.entries.popitem(last=False)
