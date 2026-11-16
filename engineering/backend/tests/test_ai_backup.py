import json
import pytest

from onlinecoc.host import Host
from onlinecoc.assets import Assets,restore_host
from onlinecoc.errors import DomainError
from onlinecoc_data import FileDataStore
from ai_helpers import ai_message,approve_case


def test_current_room_restarts_without_upgrade(tmp_path):
    path=tmp_path/'host';host=Host(path,bootstrap='test-password')
    from onlinecoc.version import ROOM_SCHEMA_VERSION
    assert host.state()['schemaVersion']==ROOM_SCHEMA_VERSION
    scope=host.state()['aiControl']['scopeId'];generation=host.store.generation;host.close()
    host=Host(path)
    try:
        assert host.store.generation==generation and host.state()['aiControl']['scopeId']==scope
        assert not (path/'migrations').exists()
    finally:host.close()


def test_unknown_room_version_is_not_overwritten(tmp_path):
    path=tmp_path/'host';host=Host(path,bootstrap='test-password');state=host.state();host.close();state['schemaVersion']=99
    with FileDataStore(path/'rooms/demo') as store:store.commit(store.generation,state);generation=store.generation
    with pytest.raises(DomainError,match='SCHEMA_UNSUPPORTED'):Host(path)
    with FileDataStore(path/'rooms/demo') as store:assert store.generation==generation


def test_restore_forks_scope_revokes_approval_and_retains_optional_history(ai_case,tmp_path):
    host,service,_,_=ai_case;identifier=approve_case(ai_case);scope=host.state()['aiControl']['scopeId']
    snapshot=service.repository.state()
    Assets(host).backup('kp',tmp_path/'backup',True,ai_snapshot=snapshot)
    restore_host(tmp_path/'backup',tmp_path/'restored')
    restored=Host(tmp_path/'restored')
    try:
        assert restored.state()['aiControl']['scopeId']!=scope
        assert restored.state()['aiControl']['approvals'][identifier]['status']=='revoked'
        result=restored.command('kp',ai_message(restored,'publication.apply',{'approvalId':identifier},'old-approval'))
        assert result['code']=='APPROVAL_REVOKED'
        assert json.loads((restored.path/'ai-history-before-restore.json').read_text(encoding='utf-8'))==snapshot
    finally:restored.close()


def test_published_game_restores_without_ai_store(ai_case,tmp_path):
    host,service,_,_=ai_case;identifier=approve_case(ai_case)
    host.command('kp',ai_message(host,'publication.apply',{'approvalId':identifier},'load'));service.close()
    Assets(host).backup('kp',tmp_path/'backup',True)
    restore_host(tmp_path/'backup',tmp_path/'restored');restored=Host(tmp_path/'restored')
    try:
        assert restored.state()['configurations']['fixture.token']['defaults']['bonus']==15
        assert len(restored.state()['aiControl']['publications'])==1
        assert not (restored.path/'ai').exists()
    finally:restored.close()


def test_restore_retries_transient_windows_directory_handle(ai_case, tmp_path, monkeypatch):
    import os
    if os.name != 'nt':pytest.skip('Windows sharing violation')
    import onlinecoc.assets as assets
    host, _, _, _ = ai_case
    Assets(host).backup('kp', tmp_path/'backup', True)
    rename = assets.os.rename;attempts = []
    def transient(source, target):
        attempts.append(str(source))
        if len(attempts) == 1:raise PermissionError(13, 'sharing violation', str(source), 32)
        return rename(source, target)
    monkeypatch.setattr(assets.os, 'rename', transient)
    restore_host(tmp_path/'backup', tmp_path/'restored')
    assert len(attempts) == 2
    recovered = Host(tmp_path/'restored')
    recovered.close()


@pytest.mark.parametrize('damage',['artifact','ai-reference'])
def test_backup_missing_references_fails_before_creating_target(ai_case,tmp_path,damage):
    import hashlib
    from onlinecoc_data import canonical
    host,service,_,_=ai_case;identifier=approve_case(ai_case)
    bundle=tmp_path/'backup';Assets(host).backup('kp',bundle,True,ai_snapshot=service.repository.state())
    manifest=json.loads((bundle/'manifest.json').read_text(encoding='utf-8'))
    if damage=='artifact':
        env=json.loads((bundle/'room.json').read_text(encoding='utf-8'))
        del env['payload']['artifacts'][env['payload']['aiControl']['approvals'][identifier]['artifactRevision']]
        env['digest']=hashlib.sha256(canonical(env['payload'])).hexdigest()
        raw=canonical(env);(bundle/'room.json').write_bytes(raw);manifest['roomDigest']=hashlib.sha256(raw).hexdigest()
    else:
        value=json.loads((bundle/'ai.json').read_text(encoding='utf-8'))
        next(iter(value['proposals'].values()))['revisions']['1']['contextRef']='f'*64
        raw=canonical(value);(bundle/'ai.json').write_bytes(raw);manifest['aiDigest']=hashlib.sha256(raw).hexdigest()
    (bundle/'manifest.json').write_bytes(canonical(manifest))
    with pytest.raises(DomainError):restore_host(bundle,tmp_path/'invalid')
    assert not (tmp_path/'invalid').exists()
