"""Current-room initialization and restore forking; no format migration."""
import copy
import uuid

def initial_control():
    return {"schemaVersion": 1, "scopeId": uuid.uuid4().hex, "packBinding": None,
            "proposalHeads": {}, "approvals": {}, "publications": {},
            "settings": {"enabled": False, "profileId": None,
                "auto": {"enabled": False, "principal": None, "channelIds": [], "prefix": "!ai "},
                "externalSources": {"public": False, "kp": False, "private": False}}}


def fork_scope(state):
    from .model import validate
    validate(state)
    result = copy.deepcopy(state)
    result["aiControl"]["scopeId"] = uuid.uuid4().hex
    result['knowledge']['scopeId'] = uuid.uuid4().hex
    result["aiControl"]["settings"]["auto"].update(enabled=False, principal=None)
    for approval in result["aiControl"]["approvals"].values():
        if approval["status"] == "approved":
            approval["status"] = "revoked"
    return result
