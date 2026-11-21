import copy
import json
import os
from pathlib import Path
import shutil

import pytest

from onlinecoc_ai.errors import AiError
from onlinecoc_ai.pack import Pack, safe_path, local_schema
from onlinecoc_ai.validation.base import check_base


def test_real_load_and_full_merge(validation_case):
    pack, state, baseline, context, changes = validation_case
    before = copy.deepcopy(state)
    report, artifact = check_base(*validation_case)
    assert report["status"] == "pass"
    assert artifact["sources"] == baseline["sources"]
    assert state == before
    assert state["entities"]["token-one"]["numbers"]["bonus"] == 0


@pytest.mark.parametrize("replaced", [False, True])
def test_configuration_without_optional_behaviors(validation_case, replaced):
    from onlinecoc_ai.validation.common import static_context
    pack, state, baseline, _, changes = validation_case
    if replaced:
        changes["configurations"][0]["value"].pop("behaviors")
    else:
        passive = copy.deepcopy(state["configurations"]["fixture.token"])
        passive["configurationId"] = "fixture.passive"
        passive.pop("behaviors")
        state["configurations"]["fixture.passive"] = passive
    context = static_context(pack, state, baseline)
    result, artifact = check_base(pack, state, baseline, context, changes)
    assert result["status"] == "pass", result
    assert artifact is not None


@pytest.mark.parametrize("mutation,code", [
    (lambda c: c["sources"].clear(), "INCOMPLETE_CANDIDATE"),
    (lambda c: c["data"]["tuning.json"].update(maxTarget=101), "PACK_SCHEMA_INVALID"),
    (lambda c: c["data"].update({"new.json": {}}), "SCHEMA_MISSING"),
    (lambda c: c["configurations"][0].update(expectedRevision="old"), "VERSION_CONFLICT"),
    (lambda c: c["configurations"][0]["value"].update(typeRef="skill"), "TYPE_CHANGE_FORBIDDEN"),
    (lambda c: c["configurations"][0]["value"]["behaviors"].update(use={"ruleId": "missing"}), "REFERENCE_CONFLICT"),
    (lambda c: c["sources"].update({"bad.lua": "return rule('bad', {}, function(r) end, {dependencies={'missing'}})"}), "RULE_CYCLE_OR_MISSING"),
    (lambda c: c["sources"].update({"bad.lua": "return rule('bad', {}, function(r) end, {dependencies={'bad'}})"}), "RULE_CYCLE_OR_MISSING"),
    (lambda c: c["sources"].update({"bad.lua": "return rule('bad', {'thing:unknown'}, function(r) end)"}), "RULE_INVALID"),
    (lambda c: c["sources"].update({"bad.lua": "invalid syntax here"}), "RULE_FAILED"),
])
def test_load_rejects_invalid_candidates(validation_case, mutation, code):
    mutation(validation_case[-1])
    report, artifact = check_base(*validation_case)
    assert report["status"] == "fail" and artifact is None
    assert report["findings"][0]["code"] == code


@pytest.mark.parametrize("path", ["../x", "/x", "C:/x", "x\\y", "a//b", "a/../b", "a./b", "CON.json", "a:b", ".hidden"])
def test_path_rejection(path):
    with pytest.raises(AiError, match="PATH_INVALID"):
        safe_path(path)


def test_junction_or_symlink_escape(tmp_path):
    source = Path(__file__).parent / "fixtures/pack"
    root = tmp_path / "pack"
    shutil.copytree(source, root)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.json").write_text("{}")
    link = root / "escape"
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(outside), str(link))
    else:
        link.symlink_to(outside, target_is_directory=True)
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["ai"] = "escape/secret.json"
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(AiError, match="PATH_ESCAPE"):
        Pack(root)


@pytest.mark.parametrize("content,code", [(b'{"x":1,"x":2}', "INPUT_INVALID"), (b'{"x":NaN}', "INPUT_INVALID"), (b'{', "INPUT_INVALID"), (b'x' * (1024 * 1024 + 1), "LIMIT_EXCEEDED")])
def test_pack_bad_json_and_limits(tmp_path, content, code):
    (tmp_path / "manifest.json").write_bytes(content)
    with pytest.raises(AiError, match=code):
        Pack(tmp_path)


@pytest.mark.parametrize("ref", ["https://example.invalid/schema", "file:///secrets", "../schema.json"])
def test_schema_cannot_resolve_external_resources(ref):
    with pytest.raises(AiError, match="SCHEMA_EXTERNAL_REF"):
        local_schema({"$ref": ref})


def test_pack_snapshot_and_baseline_changes_are_detected(validation_case):
    pack, state, baseline, context, changes = validation_case
    state["entities"]["actor-one"]["numbers"]["target"] = 42
    report, _ = check_base(*validation_case)
    assert report["findings"][0]["code"] == "BASELINE_STALE"
    with pytest.raises(AiError, match="SOURCE_MISSING"):
        pack.text("unlisted.json")
