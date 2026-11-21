import sys
import copy
import pytest
from pathlib import Path

ENGINEERING = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ENGINEERING / "ai/src"), str(ENGINEERING / "backend/src"),
               str(ENGINEERING / "data-management")]


@pytest.fixture
def validation_case():
    from onlinecoc_ai.pack import Pack, fixture_state, merge_changes
    from onlinecoc_ai.sandbox import stage
    from onlinecoc_ai.validation.common import static_context
    pack = Pack(Path(__file__).parent / "fixtures/pack")
    artifact = stage(pack.sources, pack.data)
    state = fixture_state(pack.json(pack.scenarios[0]["fixtureRef"]), pack.configurations)
    context = static_context(pack, state, artifact)
    config = copy.deepcopy(pack.configurations["fixture.token"])
    config["revision"] = "2"
    config["defaults"]["bonus"] = 15
    changes = merge_changes(artifact, {"schemaVersion": 1, "configurations": [
        {"kind": "replace", "id": config["configurationId"], "expectedRevision": "1", "value": config}],
        "sources": {}, "data": {}, "suggestions": []})
    return pack, state, artifact, context, changes
