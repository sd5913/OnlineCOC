import time

import pytest
from onlinecoc_p2p.common import Fault
from onlinecoc_p2p.rooms import Rooms
from onlinecoc_web.host import WebHost
from test_portal import room


async def test_expiry_removes_directory_shortcuts_and_claims(room):
    host, service, owner, player = room
    rid, code = host.room_id, host.room['roomCode']
    await player.call('/v1/web/join', {'roomCode': code})
    await host.close()
    service.store.rooms[rid]['inactiveSince'] = time.time() - 86399
    assert (await player.call('/v1/web/rooms'))['items']
    service.store.rooms[rid]['inactiveSince'] = time.time() - 86401
    assert not (await player.call('/v1/web/rooms'))['items']
    assert rid not in service.store.rooms and rid not in service.portal.data['rooms']
    await owner.call('/v1/web/claim', {'roomCode': code, 'claim': host.claim}, expected=404)
    # Restarting from the same local state explicitly creates a NEW room, never old members.
    replacement = WebHost(host.config)
    try:
        await replacement.start()
        assert replacement.room_id != rid and replacement.room['roomCode'] != code
        assert not service.portal.room(replacement.room_id)['members']
    finally:
        await replacement.close()


async def test_owner_removes_immediately_and_background_cannot_recreate(room):
    host, service, owner, player = room
    rid = host.room_id
    path = '/v1/web/rooms/' + rid + '/manage'
    await player.call('/v1/web/join', {'roomCode': host.room['roomCode']})
    await player.call(path, {'action':'close'}, expected=403)
    result = await owner.call(path, {'action':'close'})
    assert result['removed']
    assert not (await owner.call('/v1/web/rooms'))['items']
    assert not (await player.call('/v1/web/rooms'))['items']
    assert rid not in service.store.rooms and rid not in service.portal.data['rooms']
    with pytest.raises(Fault, match='NOT_FOUND'):
        await host.republish()


async def test_expired_signal_closes_even_after_request_purges_lease(room):
    host, service, owner, player = room
    rid = host.room_id
    socket = service.hosts[rid]
    service.store.leases[rid]['expires'] = time.time() - 1
    service.store.purge()  # Another request may consume the expired-lease list first.
    await service.cleanup_rooms()
    assert socket.closed
    assert rid in service.store.rooms  # The room still has its one-day grace.


async def test_active_empty_room_and_reconnection_reset_timer(room):
    host, service, owner, player = room
    rid = host.room_id
    service.store.rooms[rid]['inactiveSince'] = time.time() - 100000
    assert (await owner.call('/v1/web/rooms'))['items']  # Online with zero players remains active.
    service.store.connected(rid, False)
    service.store.rooms[rid]['inactiveSince'] = time.time() - 100
    service.store.connected(rid, True)
    assert 'inactiveSince' not in service.store.rooms[rid]
    service.store.connected(rid, False)
    assert time.time() - service.store.rooms[rid]['inactiveSince'] < 2
    service.store.connected(rid, True)


async def test_deadline_survives_restart_and_legacy_data_gets_grace(room, tmp_path):
    host, service, owner, player = room
    rid = host.room_id
    await host.close()
    store = service.store
    deadline_start = time.time() - 100
    store.rooms[rid]['inactiveSince'] = deadline_start
    store.save()
    restored = Rooms(store.path)
    assert restored.rooms[rid]['inactiveSince'] == deadline_start
    restored.clock = lambda: deadline_start + 86401
    restored.purge()
    assert rid not in restored.rooms
    # Old installations had neither activity timestamp. Migration must not guess from metadata age.
    from onlinecoc_p2p.common import atomic_json
    legacy = dict(store.rooms[rid])
    legacy.pop('inactiveSince', None); legacy.pop('lastActive', None)
    path = tmp_path / 'legacy.json'
    atomic_json(path, {'rooms': {rid: legacy}})
    migrated = Rooms(path, clock=lambda: 10000)
    assert migrated.rooms[rid]['inactiveSince'] == 10000
    migrated.clock = lambda: 96399
    migrated.purge()
    assert rid in migrated.rooms
    migrated.clock = lambda: 96400
    migrated.purge()
    assert rid not in migrated.rooms
