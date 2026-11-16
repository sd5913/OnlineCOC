from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid

from .common import Fault, MAX_RESPONSE, canonical, require

FRAME_BYTES = 8192


class Frames:
    """Bounded fragmentation; a peer never controls unbounded allocation."""
    def __init__(self, maximum=MAX_RESPONSE):
        self.maximum, self.pending = maximum, {}

    def feed(self, raw):
        require(isinstance(raw, str) and len(raw.encode()) <= 16384, "FRAME_INVALID")
        frame = json.loads(raw)
        require(isinstance(frame, dict) and set(frame) == {"frame", "index", "count", "data"}, "FRAME_INVALID")
        fid, index, count = frame["frame"], frame["index"], frame["count"]
        require(isinstance(fid, str) and len(fid) == 32 and all(c in "0123456789abcdef" for c in fid), "FRAME_INVALID")
        require(type(index) is int and type(count) is int and 0 <= index < count <= (self.maximum // FRAME_BYTES + 1),
                "FRAME_INVALID")
        require(isinstance(frame["data"], str) and len(frame["data"]) <= 11000, "FRAME_INVALID")
        try:
            chunk = base64.b64decode(frame["data"], validate=True)
        except ValueError:
            raise Fault("FRAME_INVALID") from None
        require(len(chunk) <= FRAME_BYTES, "FRAME_INVALID")
        now = time.monotonic()
        self.pending = {k: v for k, v in self.pending.items() if now - v["time"] < 15}
        require(fid in self.pending or len(self.pending) < 8, "FRAME_CAPACITY")
        state = self.pending.setdefault(fid, {"count": count, "parts": {}, "size": 0, "time": now})
        require(state["count"] == count and index not in state["parts"], "FRAME_INVALID")
        state["size"] += len(chunk)
        require(state["size"] <= self.maximum, "LIMIT_EXCEEDED")
        state["parts"][index] = chunk
        if len(state["parts"]) == count:
            del self.pending[fid]
            data = b"".join(state["parts"][i] for i in range(count))
            value = json.loads(data)
            require(isinstance(value, dict), "MESSAGE_INVALID")
            return value
        return None


class Sender:
    def __init__(self, channel):
        self.channel, self.lock = channel, asyncio.Lock()

    async def send(self, value):
        raw = canonical(value)
        require(len(raw) <= MAX_RESPONSE, "LIMIT_EXCEEDED", 413)
        fid, count = uuid.uuid4().hex, max(1, (len(raw) + FRAME_BYTES - 1) // FRAME_BYTES)
        async with self.lock:
            for index in range(count):
                deadline = time.monotonic() + 10
                while self.channel.bufferedAmount > 262144:
                    if self.channel.readyState != "open" or time.monotonic() >= deadline:
                        raise Fault("BACKPRESSURE_TIMEOUT", 504)
                    await asyncio.sleep(.01)
                require(self.channel.readyState == "open", "DISCONNECTED", 409)
                self.channel.send(json.dumps({"frame": fid, "index": index, "count": count,
                    "data": base64.b64encode(raw[index * FRAME_BYTES:(index + 1) * FRAME_BYTES]).decode()},
                    separators=(",", ":")))
