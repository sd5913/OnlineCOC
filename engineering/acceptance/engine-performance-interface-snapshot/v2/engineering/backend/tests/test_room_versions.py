import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import pytest
from onlinecoc.host import Host
from onlinecoc.model import validate, execution_snapshot, validate_execution_state
from onlinecoc.version import ENGINE_VERSION, ROOM_SCHEMA_VERSION
from onlinecoc.assets import Assets, verify_bundle, restore_host
from onlinecoc.errors import DomainError
from onlinecoc.room_validation import check_file
from onlinecoc_data import FileDataStore, canonical
from test_host import host


CASES = ["v1", "v2", "future", "no-chat", "no-control", "no-commands", "reference", "bad-version"]

def damage(state, case):
    state=copy.deepcopy(state)
    if case in ("v1", "v2", "future"):
        state['schemaVersion']={'v1':1,'v2':2,'future':99}[case]
        if case=='v1':state.pop('aiControl')
    elif case=='bad-version':state['schemaVersion']='private body must not appear in errors'
    elif case=='reference':state['entities']['actor-player1']['owner']='missing'
    else:state.pop({'no-chat':'chat','no-control':'aiControl','no-commands':'commands'}[case])
    return state


def expected(case):
    return 'SCHEMA_UNSUPPORTED' if case in ('v1','v2','future','bad-version') else 'REFERENCE_CONFLICT' if case=='reference' else 'INPUT_INVALID'


def files(directory):
    return {str(p.relative_to(directory)):p.read_bytes() for p in directory.rglob('*') if p.is_file() and p.name!='writer.lock'}


@pytest.mark.parametrize('case',CASES)
def test_open_rejects_before_room_mutation(host,case):
    path=host.path;state=damage(host.state(),case);host.close()
    with FileDataStore(path/'rooms/demo') as store:store.commit(store.generation,state)
    before=files(path/'rooms/demo')
    with pytest.raises(DomainError) as error:Host(path)
    assert error.value.code==expected(case)
    assert files(path/'rooms/demo')==before
    assert not (path/'migrations').exists()
    if expected(case)=='SCHEMA_UNSUPPORTED':
        assert error.value.detail['supportedVersions']==[ROOM_SCHEMA_VERSION]
        assert 'private body' not in str(error.value.detail)
    elif case=='no-chat':assert error.value.detail['path']=='/chat'


@pytest.mark.parametrize('case',CASES)
def test_backup_rejects_before_any_restore_target(host,tmp_path,case):
    bundle=tmp_path/'bundle';Assets(host).backup('kp',bundle,True)
    env=json.loads((bundle/'room.json').read_bytes());env['payload']=damage(env['payload'],case)
    env['digest']=hashlib.sha256(canonical(env['payload'])).hexdigest()
    raw=canonical(env);(bundle/'room.json').write_bytes(raw)
    manifest=json.loads((bundle/'manifest.json').read_bytes());manifest['roomDigest']=hashlib.sha256(raw).hexdigest()
    (bundle/'manifest.json').write_bytes(canonical(manifest));before=files(bundle)
    for check in [lambda:verify_bundle(bundle),lambda:restore_host(bundle,tmp_path/'restored'),
                  lambda:Assets.restore(bundle,tmp_path/'room',{k:k for k in env['payload']['members']}),
                  lambda:check_file(bundle,'backup'),lambda:check_file(bundle/'room.json','snapshot')]:
        with pytest.raises(DomainError) as error:check()
        assert error.value.code==expected(case)
    assert files(bundle)==before and not (tmp_path/'restored').exists() and not (tmp_path/'room').exists()
    assert not list(tmp_path.glob('*.restoring-*'))


def test_execution_projection_cannot_be_used_as_room(host):
    projection=execution_snapshot(host.state());validate_execution_state(projection)
    with pytest.raises(DomainError,match='INPUT_INVALID'):validate(projection)
    before=host.store.generation
    with pytest.raises(DomainError,match='INPUT_INVALID'):host.commit(projection)
    assert host.store.generation==before


def test_external_conversion_is_explicit_and_works(host,tmp_path):
    # Simulate an external owner's conversion of a valid v2 room, in isolation.
    state=host.state();state['schemaVersion']=2
    with pytest.raises(DomainError,match='SCHEMA_UNSUPPORTED'):validate(state)
    state['schemaVersion']=ROOM_SCHEMA_VERSION;validate(state)
    target=tmp_path/'external';target.mkdir()
    with FileDataStore(target/'rooms/demo') as store:store.commit(0,state)
    # Real restart needs the separately managed matching identity.
    import shutil
    host.close();shutil.copytree(host.path/'identity',target/'identity')
    restored=Host(target)
    try:assert restored.state()==state
    finally:restored.close()
    state.pop('chat')
    with pytest.raises(DomainError,match='INPUT_INVALID'):validate(state)


@pytest.mark.parametrize('kind',['room','snapshot','backup'])
def test_validation_cli_is_read_only(host,tmp_path,kind):
    bundle=tmp_path/'bundle';Assets(host).backup('kp',bundle,True)
    plain=tmp_path/'room.json';plain.write_bytes(canonical(host.state()))
    path={'room':plain,'snapshot':bundle/'room.json','backup':bundle}[kind]
    before=files(tmp_path)
    script=Path(__file__).resolve().parents[1]/'scripts/run.py'
    result=subprocess.run([sys.executable,str(script),'validate-room','--input',str(path),'--format',kind],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)=={'valid':True,'engineVersion':ENGINE_VERSION,'roomSchemaVersion':ROOM_SCHEMA_VERSION}
    assert files(tmp_path)==before
    if kind=='room':
        state=host.state();state.pop('chat');plain.write_bytes(canonical(state))
        result=subprocess.run([sys.executable,str(script),'validate-room','--input',str(path)],capture_output=True,text=True)
        assert result.returncode==2
        failure=json.loads(result.stdout)
        assert failure['code']=='INPUT_INVALID' and failure['detail']['path']=='/chat'


def test_release_schema_and_fixture_agree():
    import tomllib
    from onlinecoc.contracts import MODELS
    root=Path(__file__).resolve().parents[2]
    assert tomllib.loads((root/'backend/pyproject.toml').read_text())['project']['version']==ENGINE_VERSION
    assert MODELS['Room']['properties']['schemaVersion']['const']==ROOM_SCHEMA_VERSION
    assert 'RoomV1' not in MODELS
    check_file(root/'contracts/fixtures/room-initial.json')


def test_restore_lifecycle_disables_auto_without_mutating_input(host):
    from onlinecoc.room_lifecycle import fork_scope
    state=host.state()
    state['aiControl']['settings']['auto'].update(enabled=True,principal='kp',channelIds=['general'])
    validate(state);before=copy.deepcopy(state)
    result=fork_scope(state);validate(result)
    assert state==before
    assert result['aiControl']['scopeId']!=state['aiControl']['scopeId']
    assert result['aiControl']['settings']['auto']['enabled'] is False
    assert result['aiControl']['settings']['auto']['principal'] is None
    assert result['schemaVersion']==ROOM_SCHEMA_VERSION
