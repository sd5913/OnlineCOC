from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from pathlib import Path

from aiohttp import WSMsgType
from aiortc import RTCSessionDescription
from cryptography.hazmat.primitives.asymmetric import ec

from .common import Fault, canonical, digest, load_identity, public_key, require, sdp_fingerprint, sign, verify
from .control import Control
from .packages import Cache
from .rtc import connection, selected_path
from .wire import Frames, Sender


class Player:
    def __init__(self, directory, ca_file=None, identity_path=None, relay_only=False):
        self.control = Control(directory, ca_file)
        self.identity = load_identity(Path(identity_path)) if identity_path else ec.generate_private_key(ec.SECP256R1())
        self.relay_only = relay_only
        self.session, self.intent, self.pc, self.socket = None, None, None, None
        self.events, self.states = asyncio.Queue(maxsize=128), asyncio.Queue(maxsize=256)
        self.pending, self.senders, self.tasks = {}, {}, set()
        self.challenge = None
        self.closed = False
        self.pump_task = None

    async def start(self):
        self.session = await self.control.request("POST", "/v1/client-sessions", data={"publicKey": public_key(self.identity)})
        self.socket = await self.control.socket(self.session["clientToken"], "client")
        self.pump_task = asyncio.create_task(self.pump())

    async def pump(self):
        try:
            async for message in self.socket:
                if message.type == WSMsgType.TEXT:
                    data = message.json()
                    if data["type"] != "heartbeat":
                        await self.events.put(data)
        finally:
            if not self.closed:
                await self.events.put({"type": "error", "code": "SIGNAL_DISCONNECTED"})

    async def wait_event(self, expected, timeout=60):
        deadline = time.monotonic() + timeout
        while True:
            data = await asyncio.wait_for(self.events.get(), max(.01, deadline - time.monotonic()))
            if data["type"] in {"error", "cancelled"}:
                raise Fault(data.get("code", "JOIN_CANCELLED"), 409)
            if data["type"] == expected:
                return data

    async def join(self, room_id=None, password="", invitation="", *, room_code=None):
        require(bool(room_id) != bool(room_code), "INPUT_INVALID")
        if not self.session:
            await self.start()
        self.challenge = asyncio.get_running_loop().create_future()
        await self.control.request("POST", "/v1/join-intents", self.session["clientToken"],
            {**({"roomCode": room_code} if room_code else {"roomId": room_id}),
             "password": password, "invitation": invitation})
        self.intent = (await self.wait_event("decision"))["intent"]
        require(self.intent["status"] == "approved", "JOIN_REJECTED", 403)
        ice = await self.control.request("POST", "/v1/turn-credentials", self.session["clientToken"],
                                         {"intentId": self.intent["intentId"], "role": "client"})
        self.pc = connection(ice["iceServers"], self.relay_only)
        for name in ("control", "state", "package"):
            channel = self.pc.createDataChannel(name, ordered=True)
            parser = Frames()
            self.senders[name] = Sender(channel)
            @channel.on("message")
            def receive(raw, parser=parser):
                try:
                    value = parser.feed(raw)
                    if value:
                        self.receive(value)
                except (Fault, ValueError):
                    task = asyncio.create_task(self.close())
                    self.tasks.add(task)
                    task.add_done_callback(self.tasks.discard)
        await self.pc.setLocalDescription(await self.pc.createOffer())
        description = {"type": "offer", "sdp": self.pc.localDescription.sdp}
        offer_fp = sdp_fingerprint(description["sdp"])
        await self.socket.send_json({"type": "signal", "intentId": self.intent["intentId"], "description": description})
        answer = await self.wait_event("signal", 40)
        require(answer["intentId"] == self.intent["intentId"], "SIGNAL_MISMATCH")
        answer_fp = sdp_fingerprint(answer["description"]["sdp"])
        verify(self.intent["hostKey"], f"{self.intent['intentId']}|{offer_fp}|{answer_fp}|{self.intent['connectionEpoch']}",
               answer["signature"])
        await self.pc.setRemoteDescription(RTCSessionDescription(**answer["description"]))
        challenge = await asyncio.wait_for(self.challenge, 30)
        return await self.rpc("admit", {"ticket": self.intent["ticket"], "signature": sign(self.identity, challenge)})

    def receive(self, value):
        if value.get("event") == "challenge":
            if not self.challenge.done():
                self.challenge.set_result(value["challenge"])
        elif value.get("event") == "state":
            if self.states.full():
                self.states.get_nowait()
            self.states.put_nowait(value["message"])
        elif value.get("id") in self.pending:
            future = self.pending.pop(value["id"])
            if not future.done():
                if value.get("ok"):
                    future.set_result(value["result"])
                else:
                    future.set_exception(Fault(value["error"]["code"], value["error"].get("status", 400)))

    async def rpc(self, method, params=None, channel="control", timeout=30):
        require(self.pc and not self.closed and channel in self.senders, "DISCONNECTED", 409)
        require(len(self.pending) < 32, "CLIENT_BUSY", 429)
        rid = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self.pending[rid] = future
        try:
            await self.senders[channel].send({"id": rid, "method": method, "params": params or {}})
            return await asyncio.wait_for(future, timeout)
        finally:
            self.pending.pop(rid, None)

    async def request(self, path, method="GET", body=None, csrf=None):
        options = {"method": method}
        if body is not None:
            options["body"] = body
        if csrf is not None:
            options["csrf"] = csrf
        return await self.rpc("request", {"path": path, "options": options})

    async def prepare(self, cache_path):
        signed = await self.rpc("package.manifest")
        require(digest(canonical(signed["manifest"])) == signed["digest"], "MANIFEST_CORRUPTED")
        verify(self.intent["hostKey"], signed["digest"], signed["signature"])
        async def fetch(manifest, file, index):
            return await self.rpc("package.chunk", {"manifestDigest": manifest, "fileDigest": file, "index": index},
                                  channel="package")
        result = await Cache(Path(cache_path)).sync(signed, fetch, self.intent["roomId"])
        await self.rpc("ready", {"manifestDigest": signed["digest"]})
        return result

    def network(self):
        return selected_path(self.pc)

    async def close(self):
        if self.closed:
            return
        self.closed = True
        for future in self.pending.values():
            if not future.done():
                future.set_exception(Fault("DISCONNECTED", 409))
        self.pending.clear()
        if self.pc:
            await self.pc.close()
        if self.socket:
            await self.socket.close()
        if self.pump_task and self.pump_task is not asyncio.current_task():
            self.pump_task.cancel()
            await asyncio.gather(self.pump_task, return_exceptions=True)
        await self.control.close()
