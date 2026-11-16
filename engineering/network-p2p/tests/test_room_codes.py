import asyncio
import json
import time

import pytest

from onlinecoc_p2p.client import Player
from onlinecoc_p2p.common import Fault, digest
from onlinecoc_p2p.rooms import PASSWORDS, Rooms
from test_rooms import key
from test_admission import until


def test_codes_collision_migration_and_stability(tmp_path, monkeypatch):
    path = tmp_path / "rooms.json"
    codes = iter(["ABCDEFGH", "ABCDEFGH", "JKLMNPQR", "STUVWXYZ", "ABCDEFGH", "23456789"])
    monkeypatch.setattr("onlinecoc_p2p.rooms.new_room_code", lambda: next(codes))
    rooms = Rooms(path)
    a = rooms.acquire("owner", key(), {"visibility": "public"})
    b = rooms.acquire("owner", key(), {"visibility": "private"})
    assert a["roomCode"] == "ABCDEFGH" and b["roomCode"] == "JKLMNPQR"
    assert rooms.resolve_code(" abcd-efgh ") == a["roomId"]
    original = json.loads(path.read_text())
    del original["rooms"][b["roomId"]]["roomCode"]  # A pre-0.2 persisted room.
    original["version"] = 1
    path.write_text(json.dumps(original))
    restarted = Rooms(path)
    assert restarted.listing()["items"] == []
    assert restarted.rooms[a["roomId"]]["roomCode"] == a["roomCode"]
    assert restarted.rooms[b["roomId"]]["roomCode"] == "STUVWXYZ"
    assert json.loads(path.read_text())["version"] == 2
    renewed = restarted.acquire("owner", a["hostKey"], a["settings"], a["roomId"])
    assert renewed["roomCode"] == a["roomCode"] and renewed["connectionEpoch"] == 2
    restarted.close(a["roomId"])
    c = restarted.acquire("owner", key(), {})
    assert c["roomCode"] == "23456789"
    assert restarted.resolve_code(a["roomCode"]) == a["roomId"]


async def test_short_code_preserves_private_invite_password_and_approval(hosted, tmp_path):
    host, service, url, _ = hosted
    secret = "private-code-invitation"
    settings = dict(host.settings, visibility="private", approvalRequired=True,
                    passwordVerifier=PASSWORDS.hash("room-password"),
                    invites={digest(secret.encode()): {"expires": time.time() + 120, "remaining": 2}})
    await host.patch(settings, host.room["revision"])
    code = host.room["roomCode"]
    player = Player(url)
    try:
        assert service.store.listing()["items"] == []
        for candidate, password, invitation in [
            (code, "room-password", ""), (code, "wrong", secret),
            ("2222-2222", "room-password", secret), ("invalid", "", "")]:
            with pytest.raises(Fault, match="ROOM_UNAVAILABLE"):
                await player.join(room_code=candidate, password=password, invitation=invitation)
            assert not host.pending
        task = asyncio.create_task(player.join(room_code=code[:4].lower() + "-" + code[4:].lower(),
                                              password="room-password", invitation=secret))
        await until(lambda: bool(host.pending))
        assert not task.done()
        await host.decide(next(iter(host.pending)), True)
        await task
        assert player.intent["roomId"] == host.room_id
        await player.request("login", "POST", {"loginName": "alice", "password": "test-only"})
        await player.prepare(tmp_path / "cache")
        assert (await player.request("me"))["accountId"] == "alice"
        with pytest.raises(Fault, match="INPUT_INVALID"):
            await player.control.request("POST", "/v1/join-intents", player.session["clientToken"],
                                         {"roomId": host.room_id, "roomCode": code})
    finally:
        await player.close()


async def test_offline_room_code_cannot_create_intent(hosted):
    host, service, url, _ = hosted
    code = host.room["roomCode"]
    await host.close()
    player = Player(url)
    try:
        with pytest.raises(Fault, match="ROOM_UNAVAILABLE"):
            await player.join(room_code=code)
        assert not service.store.intents
    finally:
        await player.close()

