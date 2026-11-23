from __future__ import annotations

import copy
import re
import secrets
import time
from pathlib import Path

from argon2 import PasswordHasher, extract_parameters
from argon2.exceptions import InvalidHashError

from .common import Fault, atomic_json, digest, key_id, read_json, require, token

PASSWORDS = PasswordHasher(time_cost=2, memory_cost=16384, parallelism=1)
CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def new_room_code():
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))


def normalize_room_code(value):
    require(isinstance(value, str) and len(value) <= 32, "ROOM_UNAVAILABLE", 404)
    code = re.sub(r"[\s-]", "", value).upper()
    require(len(code) == 8 and all(c in CODE_ALPHABET for c in code), "ROOM_UNAVAILABLE", 404)
    return code


def settings(value):
    require(isinstance(value, dict))
    allowed = {"title", "summary", "visibility", "passwordVerifier", "approvalRequired", "maxPlayers",
               "gameSystem", "language", "joinable", "invites", "bannedKeys", "packageSummary"}
    require(not (set(value) - allowed), "SETTINGS_INVALID")
    data = {"title": "OnlineCOC 房间", "summary": "", "visibility": "private", "passwordVerifier": "",
            "approvalRequired": True, "maxPlayers": 8, "gameSystem": "通用跑团", "language": "zh-CN",
            "joinable": True, "invites": {}, "bannedKeys": [], "packageSummary": {}}
    data.update(copy.deepcopy(value))
    for name, limit in (("title", 64), ("summary", 512), ("gameSystem", 64), ("language", 32)):
        require(isinstance(data[name], str) and len(data[name]) <= limit, "SETTINGS_INVALID")
    require(bool(data["title"].strip()) and data["visibility"] in {"public", "private", "code"}, "SETTINGS_INVALID")
    require(type(data["maxPlayers"]) is int and 1 <= data["maxPlayers"] <= 32, "SETTINGS_INVALID")
    require(type(data["approvalRequired"]) is bool and type(data["joinable"]) is bool, "SETTINGS_INVALID")
    require(isinstance(data["invites"], dict) and len(data["invites"]) <= 128, "SETTINGS_INVALID")
    for invite_hash, spec in data["invites"].items():
        require(bool(re.fullmatch(r"[0-9a-f]{64}", invite_hash)) and isinstance(spec, dict), "INVITE_INVALID")
        require(set(spec) == {"expires", "remaining"} and type(spec["remaining"]) is int
                and 1 <= spec["remaining"] <= 1000 and isinstance(spec["expires"], (int, float)), "INVITE_INVALID")
    require(isinstance(data["bannedKeys"], list) and len(data["bannedKeys"]) <= 1000, "SETTINGS_INVALID")
    require(all(isinstance(k, str) and re.fullmatch(r"[0-9a-f]{64}", k) for k in data["bannedKeys"]), "SETTINGS_INVALID")
    require(isinstance(data["packageSummary"], dict) and set(data["packageSummary"]) <= {"id", "version", "bytes", "digest"},
            "SETTINGS_INVALID")
    verifier = data["passwordVerifier"]
    require(isinstance(verifier, str) and len(verifier) <= 256, "PASSWORD_INVALID")
    if verifier:
        try:
            p = extract_parameters(verifier)
            require(p.type.name == "ID" and p.memory_cost == 16384 and p.time_cost == 2
                    and p.parallelism == 1 and p.hash_len == 32 and p.salt_len == 16, "PASSWORD_INVALID")
        except (InvalidHashError, ValueError):
            raise Fault("PASSWORD_INVALID") from None
    return data


class Rooms:
    """Single-event-loop state machine. Persistence excludes leases, online flags and tickets."""
    def __init__(self, path: Path | None = None, clock=time.time, lease_seconds=60, retention_seconds=86400):
        self.path, self.clock, self.lease_seconds = path, clock, lease_seconds
        require(type(retention_seconds) is int and 1 <= retention_seconds <= 2592000, "RETENTION_INVALID")
        self.retention_seconds = retention_seconds
        self.rooms = read_json(path).get("rooms", {}) if path and path.exists() else {}
        self.leases, self.clients, self.intents, self.tickets = {}, {}, {}, {}
        self.codes = {}
        for rid, room in self.rooms.items():
            room["settings"] = settings(room["settings"])
            if room.get("roomCode"):
                code = normalize_room_code(room["roomCode"])
                require(code not in self.codes, "ROOM_CODE_CONFLICT", 500)
                room["roomCode"] = code
                self.codes[code] = rid
        migrated = False
        for rid, room in self.rooms.items():
            if "inactiveSince" not in room:
                # Old data gets a full grace period; new data resumes its last checkpoint.
                room["inactiveSince"] = room.get("lastActive", self.clock())
                migrated = True
            if not room.get("roomCode"):
                room["roomCode"] = self.assign_code(rid)
                migrated = True
        if migrated:
            self.save()

    def assign_code(self, rid):
        for _ in range(64):
            code = new_room_code()
            if code not in self.codes:
                self.codes[code] = rid
                return code
        raise Fault("ROOM_CODE_CAPACITY", 503)

    def resolve_code(self, value):
        self.purge()
        rid = self.codes.get(normalize_room_code(value))
        require(rid, "ROOM_UNAVAILABLE", 404)
        return rid

    def save(self):
        if self.path:
            atomic_json(self.path, {"version": 2, "rooms": self.rooms})

    def purge(self):
        now = self.clock()
        dead_leases = [rid for rid, item in self.leases.items() if item["expires"] <= now]
        for rid in dead_leases:
            self.rooms[rid].setdefault("inactiveSince", self.leases[rid]["expires"])
            del self.leases[rid]
        changed = bool(dead_leases)
        for rid, room in list(self.rooms.items()):
            if self.leases.get(rid, {}).get("connected"):
                continue
            if now - room.get("inactiveSince", now) >= self.retention_seconds:
                self.remove(rid)
                changed = True
        for iid, item in list(self.intents.items()):
            if item["roomId"] not in self.leases or item["expires"] <= now:
                self.drop_intent(iid)
        for cid, client in list(self.clients.items()):
            if client["expires"] <= now:
                del self.clients[cid]
        if changed:
            self.save()
        return dead_leases

    def connected(self, rid, value):
        if rid not in self.leases or rid not in self.rooms:
            return
        self.leases[rid]["connected"] = value
        room = self.rooms[rid]
        if value:
            room.pop("inactiveSince", None)
            room["lastActive"] = self.clock()
        else:
            room.setdefault("inactiveSince", self.clock())
        self.save()

    def remove(self, rid):
        self.leases.pop(rid, None)
        items = [self.drop_intent(iid) for iid, item in list(self.intents.items()) if item["roomId"] == rid]
        room = self.rooms.pop(rid, None)
        if room:
            self.codes.pop(room["roomCode"], None)
            self.save()
        return items

    def new_client(self, public_key):
        self.purge()
        require(len(self.clients) < 4096, "CAPACITY", 503)
        kid = key_id(public_key)
        cid, credential = token(), token()
        self.clients[cid] = {"id": cid, "token": credential, "publicKey": public_key, "keyId": kid,
                             "expires": self.clock() + 86400}
        return {"clientId": cid, "clientToken": credential, "expires": self.clock() + 86400}

    def client(self, credential):
        self.purge()
        for client in self.clients.values():
            if credential and __import__("secrets").compare_digest(client["token"], credential):
                client["expires"] = self.clock() + 86400
                return client
        raise Fault("CLIENT_AUTH_REQUIRED", 401)

    def acquire(self, owner, public_key, value, room_id=None):
        self.purge()
        key_id(public_key)
        config = settings(value)
        require(len(self.rooms) < 1000 or room_id in self.rooms, "CAPACITY", 503)
        if room_id:
            require(room_id in self.rooms and self.rooms[room_id]["owner"] == owner, "NOT_FOUND", 404)
            require(room_id not in self.leases, "ROOM_ALREADY_ONLINE", 409)
            room = self.rooms[room_id]
            require(key_id(room["hostKey"]) == key_id(public_key), "HOST_IDENTITY_CHANGED", 409)
            room.update(epoch=room["epoch"] + 1, revision=room["revision"] + 1,
                        policyRevision=room["policyRevision"] + 1, settings=config)
        else:
            room_id = token()
            room = {"roomId": room_id, "roomCode": self.assign_code(room_id), "owner": owner, "hostKey": public_key, "epoch": 1,
                    "revision": 1, "policyRevision": 1, "settings": config}
            self.rooms[room_id] = room
        lease = {"leaseId": token(), "leaseToken": token(), "expires": self.clock() + self.lease_seconds,
                 "connected": False}
        self.leases[room_id] = lease
        room.update(lastActive=self.clock(), inactiveSince=self.clock())
        self.save()
        return self.host_view(room_id)

    def host_view(self, rid):
        room, lease = self.rooms[rid], self.leases[rid]
        return {**self.public(rid), "leaseId": lease["leaseId"], "leaseToken": lease["leaseToken"],
                "settings": copy.deepcopy(room["settings"]), "hostKey": room["hostKey"]}

    def lease(self, rid, credential):
        self.purge()
        lease = self.leases.get(rid)
        require(lease and credential and __import__("secrets").compare_digest(lease["leaseToken"], credential),
                "LEASE_INVALID", 401)
        return lease

    def heartbeat(self, rid, credential):
        lease = self.lease(rid, credential)
        lease["expires"] = self.clock() + self.lease_seconds
        room = self.rooms[rid]
        if lease["connected"] and self.clock() - room.get("lastActive", 0) >= 60:
            room["lastActive"] = self.clock()
            self.save()
        return {"expires": lease["expires"], "connectionEpoch": self.rooms[rid]["epoch"]}

    def count(self, rid):
        return sum(i["roomId"] == rid and i["status"] in {"approved", "syncing", "ready"} for i in self.intents.values())

    def public(self, rid):
        room, config = self.rooms[rid], self.rooms[rid]["settings"]
        return {"roomId": rid, "roomCode": room["roomCode"], **{k: config[k] for k in ("title", "summary", "visibility", "approvalRequired",
                 "maxPlayers", "gameSystem", "language", "joinable", "packageSummary")},
                "passwordRequired": bool(config["passwordVerifier"]), "playerCount": self.count(rid),
                "connectionEpoch": room["epoch"], "revision": room["revision"],
                "policyRevision": room["policyRevision"], "protocolVersion": 1}

    def listing(self, cursor="", limit=50):
        self.purge()
        require(isinstance(cursor, str) and len(cursor) <= 128)
        visible = sorted(rid for rid, lease in self.leases.items() if lease["connected"]
                         and self.rooms[rid]["settings"]["visibility"] == "public")
        visible = [rid for rid in visible if rid > cursor]
        selected = visible[:limit]
        return {"items": [self.public(rid) for rid in selected], "nextCursor": selected[-1] if len(visible) > limit else None}

    def precheck(self, rid, client, invitation, *, web_member=False):
        self.purge()
        room, lease = self.rooms.get(rid), self.leases.get(rid)
        require(room and lease and lease["connected"], "ROOM_UNAVAILABLE", 404)
        config = room["settings"]
        require(config["visibility"] != "code" or web_member, "ROOM_UNAVAILABLE", 404)
        invitation = invitation or ""
        require(isinstance(invitation, str) and len(invitation) <= 256, "ROOM_UNAVAILABLE", 404)
        invitation_hash = digest(invitation.encode())
        if config["visibility"] == "private":
            spec = config["invites"].get(invitation_hash)
            require(spec and spec["expires"] > self.clock() and spec["remaining"] > 0, "ROOM_UNAVAILABLE", 404)
        require(config["joinable"] and client["keyId"] not in config["bannedKeys"], "ROOM_UNAVAILABLE", 404)
        return room, invitation_hash

    def new_intent(self, rid, client, invitation_hash, expected_policy):
        room, config = self.rooms[rid], self.rooms[rid]["settings"]
        require(room["policyRevision"] == expected_policy and rid in self.leases, "POLICY_CHANGED", 409)
        require(self.count(rid) < config["maxPlayers"], "ROOM_FULL", 409)
        require(len(self.intents) < 4096, "CAPACITY", 503)
        pending = [i for i in self.intents.values() if i["clientId"] == client["id"]]
        for item in pending:
            if item["roomId"] == rid:
                self.drop_intent(item["intentId"])
        require(sum(i["roomId"] == rid and i["status"] == "pending" for i in self.intents.values()) < 64, "ROOM_BUSY", 429)
        iid = token()
        item = {"intentId": iid, "roomId": rid, "clientId": client["id"], "clientKey": client["publicKey"],
                "clientKeyId": client["keyId"], "policyRevision": expected_policy, "connectionEpoch": room["epoch"],
                "leaseId": self.leases[rid]["leaseId"], "status": "pending", "expires": self.clock() + 60,
                "invitationHash": invitation_hash}
        self.intents[iid] = item
        return item

    def decide(self, rid, iid, approve, policy):
        self.purge()
        item = self.intents.get(iid)
        require(item and item["roomId"] == rid and item["status"] == "pending", "INTENT_EXPIRED", 409)
        room = self.rooms[rid]
        require(policy == room["policyRevision"] == item["policyRevision"], "POLICY_CHANGED", 409)
        if not approve:
            item.update(status="rejected", expires=self.clock() + 30)
            return item
        require(self.count(rid) < room["settings"]["maxPlayers"], "ROOM_FULL", 409)
        if room["settings"]["visibility"] == "private":
            spec = room["settings"]["invites"].get(item["invitationHash"])
            require(spec and spec["remaining"] > 0 and spec["expires"] > self.clock(), "ROOM_UNAVAILABLE", 404)
            spec["remaining"] -= 1
            if not spec["remaining"]:
                del room["settings"]["invites"][item["invitationHash"]]
            self.save()
        ticket = token()
        item.update(status="approved", ticket=ticket, ticketExpires=self.clock() + 60, expires=self.clock() + 600)
        self.tickets[digest(ticket.encode())] = iid
        return item

    def for_client(self, item):
        result = {k: item[k] for k in ("intentId", "roomId", "status", "expires", "policyRevision", "connectionEpoch", "leaseId")}
        if item["status"] == "approved":
            result.update(ticket=item["ticket"], ticketExpires=item["ticketExpires"], hostKey=self.rooms[item["roomId"]]["hostKey"])
        return result

    def redeem(self, rid, ticket, client_id):
        self.purge()
        iid = self.tickets.get(digest(ticket.encode())) if isinstance(ticket, str) else None
        item = self.intents.get(iid)
        require(item and item["roomId"] == rid and item["clientId"] == client_id
                and item["status"] == "approved" and item["ticketExpires"] > self.clock()
                and item["policyRevision"] == self.rooms[rid]["policyRevision"], "TICKET_INVALID", 403)
        self.tickets.pop(digest(ticket.encode()), None)
        item.update(status="syncing", expires=self.clock() + 600)
        return {"ok": True, "intentId": iid}

    def ready(self, rid, iid):
        item = self.intents.get(iid)
        require(item and item["roomId"] == rid and item["status"] in {"syncing", "ready"}, "INTENT_INVALID", 409)
        item.update(status="ready", expires=self.clock() + 86400)

    def drop_intent(self, iid):
        item = self.intents.pop(iid, None)
        if item and item.get("ticket"):
            self.tickets.pop(digest(item["ticket"].encode()), None)
        return item

    def patch(self, rid, value, revision):
        room = self.rooms[rid]
        require(room["revision"] == revision, "REVISION_CONFLICT", 409)
        new = settings(value)
        room.update(settings=new, revision=revision + 1, policyRevision=room["policyRevision"] + 1)
        cancelled = []
        for iid, item in list(self.intents.items()):
            if item["roomId"] == rid and item["status"] in {"pending", "approved"}:
                cancelled.append(self.drop_intent(iid))
        self.save()
        return self.host_view(rid), cancelled

    def close(self, rid):
        self.leases.pop(rid, None)
        if rid in self.rooms:
            self.rooms[rid].setdefault("inactiveSince", self.clock())
            self.save()
        items = [self.drop_intent(iid) for iid, item in list(self.intents.items()) if item["roomId"] == rid]
        return items
