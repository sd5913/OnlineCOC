from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection
from aiortc.rtcconfiguration import RTCIceTransportPolicy

from .common import require


def connection(servers, relay_only=False):
    require(not relay_only or any(any(u.startswith(("turn:", "turns:")) for u in
            ([s["urls"]] if isinstance(s["urls"], str) else s["urls"])) for s in servers), "TURN_REQUIRED")
    return RTCPeerConnection(RTCConfiguration(
        iceServers=[RTCIceServer(**s) for s in servers],
        iceTransportPolicy=RTCIceTransportPolicy.RELAY if relay_only else RTCIceTransportPolicy.ALL))


def selected_path(pc):
    # aiortc 1.16 has no public candidate-pair stats; bounded read-only diagnostic.
    if not pc.sctp:
        return {"state": pc.connectionState}
    ice = pc.sctp.transport.transport
    pairs = getattr(getattr(ice, "_connection", None), "_nominated", {})
    return {"state": pc.connectionState, "pairs": [
        {"localType": p.local_candidate.type, "remoteType": p.remote_candidate.type}
        for p in pairs.values()]}
