import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from onlinecoc_p2p.common import Fault, digest, public_key, token
from onlinecoc_p2p.rooms import PASSWORDS, Rooms, settings


def key():
    return public_key(ec.generate_private_key(ec.SECP256R1()))


def setup_room(tmp_path, **config):
    now = [1000]
    rooms = Rooms(tmp_path / "rooms.json", clock=lambda: now[0])
    lease = rooms.acquire("owner", key(), {"visibility": "public", **config})
    rooms.leases[lease["roomId"]]["connected"] = True
    session = rooms.new_client(key())
    return rooms, lease, rooms.client(session["clientToken"]), now


def test_restart_removes_online_leases(tmp_path):
    rooms, lease, client, now = setup_room(tmp_path)
    assert len(rooms.listing()["items"]) == 1
    restarted = Rooms(tmp_path / "rooms.json", clock=lambda: now[0])
    assert restarted.listing()["items"] == []
    assert len(restarted.rooms) == 1


def test_expiry_old_lease_cannot_take_over(tmp_path):
    rooms, lease, client, now = setup_room(tmp_path)
    with pytest.raises(Fault, match="ROOM_ALREADY_ONLINE"):
        rooms.acquire("owner", rooms.rooms[lease["roomId"]]["hostKey"], {}, lease["roomId"])
    now[0] += 61
    assert not rooms.listing()["items"]
    renewed = rooms.acquire("owner", rooms.rooms[lease["roomId"]]["hostKey"], {}, lease["roomId"])
    assert renewed["connectionEpoch"] == 2
    with pytest.raises(Fault, match="LEASE_INVALID"):
        rooms.heartbeat(lease["roomId"], lease["leaseToken"])


def test_private_rooms_hidden_and_invite_expires(tmp_path):
    secret = token()
    rooms, lease, client, now = setup_room(tmp_path, visibility="private",
        invites={digest(secret.encode()): {"expires": 1020, "remaining": 1}})
    assert not rooms.listing()["items"]
    with pytest.raises(Fault, match="ROOM_UNAVAILABLE"):
        rooms.precheck(lease["roomId"], client, "wrong")
    room, hashed = rooms.precheck(lease["roomId"], client, secret)
    item = rooms.new_intent(lease["roomId"], client, hashed, 1)
    rooms.decide(lease["roomId"], item["intentId"], True, 1)
    with pytest.raises(Fault, match="ROOM_UNAVAILABLE"):
        rooms.precheck(lease["roomId"], client, secret)


def test_capacity_and_ticket_one_use(tmp_path):
    rooms, lease, client, now = setup_room(tmp_path, maxPlayers=1)
    rid = lease["roomId"]
    item = rooms.new_intent(rid, client, "", 1)
    rooms.decide(rid, item["intentId"], True, 1)
    other = rooms.client(rooms.new_client(key())["clientToken"])
    with pytest.raises(Fault, match="ROOM_FULL"):
        rooms.new_intent(rid, other, "", 1)
    with pytest.raises(Fault, match="TICKET_INVALID"):
        rooms.redeem(rid, item["ticket"], other["id"])
    rooms.redeem(rid, item["ticket"], client["id"])
    with pytest.raises(Fault, match="TICKET_INVALID"):
        rooms.redeem(rid, item["ticket"], client["id"])


def test_policy_change_revokes_pending_ticket(tmp_path):
    rooms, lease, client, now = setup_room(tmp_path)
    rid = lease["roomId"]
    item = rooms.new_intent(rid, client, "", 1)
    rooms.decide(rid, item["intentId"], True, 1)
    updated, cancelled = rooms.patch(rid, {"visibility": "private"}, 1)
    assert updated["policyRevision"] == 2 and len(cancelled) == 1
    with pytest.raises(Fault, match="TICKET_INVALID"):
        rooms.redeem(rid, item["ticket"], client["id"])
    with pytest.raises(Fault, match="REVISION_CONFLICT"):
        rooms.patch(rid, {}, 1)


@pytest.mark.parametrize("bad", [
    {"maxPlayers": True}, {"maxPlayers": 100}, {"visibility": "hidden"}, {"passwordVerifier": "plaintext"},
    {"arbitrary": "ignored?"}, {"bannedKeys": ["bad"]}, {"title": "a" * 65},
])
def test_settings_reject_invalid(bad):
    with pytest.raises(Fault):
        settings(bad)


def test_password_parameters_are_bounded():
    hashed = PASSWORDS.hash("sample")
    assert settings({"passwordVerifier": hashed})["passwordVerifier"] == hashed
    with pytest.raises(Fault):
        settings({"passwordVerifier": hashed.replace("m=16384", "m=1048576")})
