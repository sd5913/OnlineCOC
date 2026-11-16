import asyncio
import json

import aiohttp
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from onlinecoc_p2p.common import Fault, public_key
from onlinecoc_web.host import WebHost
from onlinecoc_web.store import PortalStore
from onlinecoc_web.resources import Resources


class User:
    def __init__(self, url, ca_file=None):
        self.url, self.csrf, self.account = url, "", None
        import ssl
        self.http = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True),
            connector=aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=ca_file)) if ca_file else None)

    async def call(self, path, data=None, token=None, expected=200):
        headers = {"X-CSRF-Token": self.csrf}
        if token:
            headers["Authorization"] = "Bearer " + token
        async with self.http.request("GET" if data is None else "POST", self.url + path, json=data, headers=headers) as response:
            result = await response.json()
            assert response.status == expected, result
            return result

    async def register(self, name):
        result = await self.call("/v1/web/auth/register", {"name": name, "password": "test-password-long"})
        self.csrf, self.account = result["csrf"], result["accountId"]
        return result


@pytest.fixture
async def room(portal, upstream, resources, tmp_path):
    service, url, publisher = portal
    host = WebHost({"directory": url, "publisherToken": publisher, "statePath": str(tmp_path / "host"),
        "upstream": upstream[1], "webPackagePath": str(resources), "settings": {"title": "网页测试"}})
    await host.start()
    owner, player = User(url), User(url)
    await owner.register("owner")
    await player.register("player")
    await owner.call("/v1/web/claim", {"roomCode": host.room["roomCode"], "claim": host.claim})
    try:
        yield host, service, owner, player
    finally:
        await owner.http.close()
        await player.http.close()
        await host.close()


async def test_code_only_join_shortcuts_no_game_connection(room):
    host, service, owner, player = room
    listing = await player.call("/v1/rooms")
    assert host.room_id not in [r["roomId"] for r in listing["items"]]
    assert (await player.call("/v1/web/rooms"))["items"] == []
    await player.call("/v1/web/rooms/" + host.room_id + "/presence", {}, expected=403)
    result = await player.call("/v1/web/join", {"roomCode": host.room["roomCode"].lower()})
    assert result["status"] == "member"
    assert len((await player.call("/v1/web/rooms"))["items"]) == 1
    info = await player.call("/v1/web/rooms/" + host.room_id + "/presence", {})
    assert info["metadata"]["package"]["id"] == "onlinecoc-core-table"
    assert not service.store.intents and not host.peers
    outsider = await player.call("/v1/client-sessions", {"publicKey": public_key(ec.generate_private_key(ec.SECP256R1()))})
    await player.call("/v1/join-intents", {"roomId": host.room_id}, outsider["clientToken"], 404)


async def test_approval_ban_unban_and_permanent_close(room):
    host, service, owner, player = room
    host.config["webPolicy"] = {"approvalRequired": True}
    await host.configure()
    result = await player.call("/v1/web/join", {"roomCode": host.room["roomCode"]})
    assert result["status"] == "pending"
    assert (await player.call("/v1/web/rooms/" + host.room_id + "/presence", {})) == {"status": "pending"}
    manage = "/v1/web/rooms/" + host.room_id + "/manage"
    await player.call(manage, {"action": "approve", "accountId": player.account}, expected=403)
    await owner.call(manage, {"action": "approve", "accountId": player.account})
    await owner.call(manage, {"action": "ban", "accountId": player.account})
    await player.call("/v1/web/join", {"roomCode": host.room["roomCode"]}, expected=404)
    await player.call("/v1/web/rooms/" + host.room_id + "/presence", {}, expected=403)
    await owner.call(manage, {"action": "unban", "accountId": player.account})
    await player.call("/v1/web/rooms/" + host.room_id + "/presence", {}, expected=403)
    await owner.call(manage, {"action": "close"})
    await owner.call("/v1/web/rooms/" + host.room_id + "/presence", {}, expected=404)
    with pytest.raises(Fault, match="ROOM_CLOSED"):
        await host.configure()


async def test_sessions_csrf_recovery_and_other_device(portal):
    service, url, _ = portal
    a, b = User(url), User(url)
    try:
        registered = await a.register("recoverme")
        assert "recovery" in registered
        b.csrf = a.csrf
        await b.call("/v1/web/rooms", expected=401)
        a.csrf = "wrong"
        await a.call("/v1/web/auth/logout", {}, expected=403)
        result = await b.call("/v1/web/auth/recover", {"name": "recoverme", "password": "new-password-long", "recovery": registered["recovery"]})
        b.csrf = result["csrf"]
        assert result["accountId"] == a.account
        await a.call("/v1/web/me", expected=401)
        await a.call("/v1/web/auth/recover", {"name": "recoverme", "password": "another-password-long", "recovery": registered["recovery"]}, expected=401)
    finally:
        await a.http.close()
        await b.http.close()


async def test_duplicate_seat_and_revoke_ticket(room):
    host, service, owner, player = room
    await player.call("/v1/web/join", {"roomCode": host.room["roomCode"]})
    async def session():
        return await player.call("/v1/web/game/session", {"publicKey": public_key(ec.generate_private_key(ec.SECP256R1()))})
    first, second = await session(), await session()
    request = {"roomId": host.room_id, "resourceVersion": host.resources.version}
    result = await player.call("/v1/web/game/join", request, first["clientToken"])
    await player.call("/v1/web/game/join", request, second["clientToken"], 409)
    for _ in range(100):
        if service.store.intents[result["intentId"]]["status"] == "approved":
            break
        await asyncio.sleep(.02)
    item = service.store.intents[result["intentId"]]
    ticket = item["ticket"]
    await owner.call("/v1/web/rooms/" + host.room_id + "/manage", {"action": "ban", "accountId": player.account})
    assert result["intentId"] not in service.store.intents
    await owner.call("/v1/join-tickets/redeem", {"roomId": host.room_id, "ticket": ticket, "clientId": item["clientId"]}, host.lease_token, 403)


def test_persistent_store_lock_backup_and_no_silent_rollback(tmp_path):
    path = tmp_path / "state.json"
    store = PortalStore(path)
    store.data["accounts"]["a"] = {"name": "persist"}
    store.save()
    with pytest.raises(Fault, match="SESSION_ALREADY_OWNED"):
        PortalStore(path)
    store.data["rooms"]["r"] = {"banned": ["a"], "members": {}, "closed": False}
    store.save()
    store.close()
    restored = PortalStore(path)
    assert restored.data["rooms"]["r"]["banned"] == ["a"]
    assert path.with_suffix(".backup.json").exists()
    restored.close()
    path.write_text("broken")
    with pytest.raises(ValueError):
        PortalStore(path)


def test_resource_projection_and_unlisted_hash_denied(resources):
    from cryptography.hazmat.primitives.asymmetric import ec
    bundle = Resources(resources)
    identity = ec.generate_private_key(ec.SECP256R1())
    manifest = bundle.manifest("startup", [], identity)
    assert "revealed-note" not in json.dumps(manifest)
    with pytest.raises(Fault, match="RESOURCE_FORBIDDEN"):
        bundle.manifest("revealed-note", [], identity)
    hidden = bundle.groups["revealed-note"]["package"]
    package = bundle.allowed("startup", [])
    with pytest.raises(Fault):
        package.chunk(package.digest, hidden.manifest["files"][0]["digest"], 0)
    assert bundle.manifest("revealed-note", ["revealed-note"], identity)["manifest"]["group"] == "revealed-note"


async def test_cross_device_membership_and_offline_shortcut(room):
    host, service, owner, player = room
    await player.call("/v1/web/join", {"roomCode": host.room["roomCode"]})
    device = User(player.url)
    try:
        login = await device.call("/v1/web/auth/login", {"name": "player", "password": "test-password-long"})
        device.csrf = login["csrf"]
        assert (await device.call("/v1/web/rooms"))["items"][0]["roomId"] == host.room_id
        await host.close()
        info = await device.call("/v1/web/rooms/" + host.room_id + "/presence", {})
        assert not info["online"] and info["metadata"]["package"]["id"] == "onlinecoc-core-table"
        assert len((await device.call("/v1/web/rooms"))["items"]) == 1
    finally:
        await device.http.close()


async def test_room_cannot_be_enumerated_by_changing_legacy_settings(room):
    host, service, owner, player = room
    with pytest.raises(Fault, match="WEB_ROOM_PRIVATE"):
        await host.patch({**host.settings, "visibility": "public"}, host.room["revision"])
    await host.close()
    from onlinecoc_p2p.control import Control
    control = Control(player.url)
    try:
        with pytest.raises(Fault, match="WEB_ROOM_PRIVATE"):
            await control.request("POST", "/v1/rooms", host.config["publisherToken"], {
                "hostKey": public_key(host.identity), "roomId": host.room_id, "settings": {**host.settings, "visibility": "public"}})
    finally:
        await control.close()


async def test_wrong_origin_and_page_security_headers(portal):
    _, url, _ = portal
    async with aiohttp.ClientSession() as client:
        async with client.post(url + "/v1/web/auth/login", json={}, headers={"Origin": "https://untrusted.invalid"}) as response:
            assert response.status == 403
        async with client.get(url + "/") as response:
            assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
            assert response.headers["X-Frame-Options"] == "DENY"
        async with client.get(url + "/sandbox.html") as response:
            policy = response.headers["Content-Security-Policy"]
            assert "sandbox allow-scripts" in policy and "connect-src 'none'" in policy
            assert "allow-same-origin" not in policy


async def test_expired_approval_requests_do_not_fill_room_forever(room):
    host, service, owner, player = room
    host.config["webPolicy"] = {"approvalRequired": True}
    await host.configure()
    record = service.portal.data["rooms"][host.room_id]
    record["pending"] = {"expired-" + str(i): 1 for i in range(100)}
    result = await player.call("/v1/web/join", {"roomCode": host.room["roomCode"]})
    assert result["status"] == "pending"
    assert list(record["pending"]) == [player.account]


async def test_server_restart_preserves_account_membership_and_bans(tmp_path, resources, upstream):
    from conftest import serve
    from onlinecoc_web.portal import WebDirectory
    from onlinecoc_p2p.common import digest, token
    secret = token()
    config = {"publishers": {"owner": digest(secret.encode())}, "webStateFile": str(tmp_path / "web.json")}
    path = tmp_path / "rooms.json"
    service = WebDirectory(config, path)
    runner, url = await serve(service.app())
    host_config = {"directory": url, "publisherToken": secret, "statePath": str(tmp_path / "host"),
        "upstream": upstream[1], "webPackagePath": str(resources)}
    host = WebHost(host_config)
    owner, player = User(url), User(url)
    try:
        await host.start()
        await owner.register("owner")
        await player.register("player")
        await owner.call("/v1/web/claim", {"roomCode": host.room["roomCode"], "claim": host.claim})
        await player.call("/v1/web/join", {"roomCode": host.room["roomCode"]})
        rid, code = host.room_id, host.room["roomCode"]
        await host.close()
        await runner.cleanup()
        service = WebDirectory(config, path)
        runner, new_url = await serve(service.app())
        owner.url = player.url = new_url
        host = WebHost({**host_config, "directory": new_url})
        await host.start()
        assert host.room_id == rid and host.room["roomCode"] == code
        assert (await player.call("/v1/web/me"))["accountId"] == player.account
        assert (await player.call("/v1/web/rooms/" + rid + "/presence", {}))["online"]
        await owner.call("/v1/web/rooms/" + rid + "/manage", {"action": "ban", "accountId": player.account})
        await host.close()
        await runner.cleanup()
        service = WebDirectory(config, path)
        runner, new_url = await serve(service.app())
        owner.url = player.url = new_url
        await player.call("/v1/web/rooms/" + rid + "/presence", {}, expected=403)
        assert player.account in service.portal.data["rooms"][rid]["banned"]
    finally:
        await host.close()
        await runner.cleanup()
        await owner.http.close()
        await player.http.close()
