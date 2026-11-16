"""Single writer, atomic file storage. Sessions and reusable room membership are distinct."""
from __future__ import annotations

import copy
import time
from pathlib import Path

from onlinecoc_p2p.common import atomic_json, read_json, require
from onlinecoc_p2p.ownership import SessionLock


class PortalStore:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = SessionLock(self.path.with_suffix(".lock"))
        self.lock.acquire()
        try:
            self.data = read_json(self.path) if self.path.exists() else {
                "version": 1, "accounts": {}, "sessions": {}, "rooms": {}}
            require(self.data["version"] == 1, "STORE_VERSION_INVALID")
            for key in ("accounts", "sessions", "rooms"):
                require(isinstance(self.data[key], dict), "STORE_INVALID")
        except Exception:
            self.lock.close()
            raise

    def save(self):
        # Keep the previous committed generation. Corruption requires explicit restore;
        # silently rolling back a blacklist or credential change is unsafe.
        if self.path.exists():
            atomic_json(self.path.with_suffix(".backup.json"), read_json(self.path))
        atomic_json(self.path, self.data)

    def room(self, rid):
        value = self.data["rooms"].get(rid)
        require(value and not value["closed"], "ROOM_UNAVAILABLE", 404)
        return value

    def member(self, rid, aid):
        room = self.room(rid)
        require(aid not in room["banned"] and aid in room["members"], "MEMBERSHIP_REQUIRED", 403)
        return room

    def owner(self, rid, aid):
        room = self.member(rid, aid)
        require(room["owner"] == aid, "OWNER_REQUIRED", 403)
        return room

    def session(self, key):
        item = self.data["sessions"].get(key)
        require(item and item["expires"] > time.time(), "LOGIN_REQUIRED", 401)
        return item

    def public_account(self, aid):
        return {"accountId": aid, "name": self.data["accounts"][aid]["name"]}

    def close(self):
        self.lock.close()
