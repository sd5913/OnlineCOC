"""Read-only discovery of this user's registered, running loopback hosts."""
from __future__ import annotations

import asyncio
import ctypes
import itertools
import json
import os
import re
from pathlib import Path

import aiohttp

from .common import Fault, loopback_url


def process_matches(pid, registered_at):
    if type(pid) is not int or not 0 < pid < 2**32:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except (OSError, OverflowError):
            return False
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x00100000 | 0x1000, False, pid)  # SYNCHRONIZE | QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        if kernel.WaitForSingleObject(handle, 0) != 0x102:
            return False
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            return False
        created = ((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime) / 10_000_000 - 11644473600
        return created <= registered_at + 1  # Ignore stale records after PID reuse.
    finally:
        kernel.CloseHandle(handle)


def records(directory):
    result = {}
    if directory is None or not directory.is_dir() or directory.is_symlink() or directory.is_junction():
        return result
    for file in itertools.islice(directory.glob("*.json"), 64):
        try:
            if file.is_symlink() or file.is_junction() or file.stat().st_size > 32768:
                continue
            item = json.loads(file.read_text(encoding="utf-8-sig"))
            iid = item.get("instanceId")
            if (item.get("version") != 1 or not isinstance(iid, str)
                    or not re.fullmatch(r"[0-9a-f]{32}", iid) or file.stem != iid
                    or not process_matches(item.get("pid"), file.stat().st_mtime)):
                continue
            url = loopback_url(item["url"])
            location = item.get("dataDirectory", "")
            if not isinstance(location, str) or len(location) > 2048:
                continue
            # Never decrypt or return protectedKey or other host-control credentials.
            result[url] = {"url": url, "instanceId": iid, "source": "registered", "dataDirectory": location,
                           "label": location.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1] or "本机房间"}
        except (OSError, ValueError, KeyError, TypeError, AttributeError, Fault):
            continue
    return result


async def discover(config):
    configured_path = config.get("hostDiscoveryPath")
    directory = (Path(configured_path) if configured_path else
                 Path(os.environ["LOCALAPPDATA"]) / "OnlineCOC/HostControl" if os.environ.get("LOCALAPPDATA") else None)
    candidates = await asyncio.to_thread(records, directory)
    try:
        url = loopback_url(config.get("upstream", "http://127.0.0.1:8765"))
        candidates.setdefault(url, {"url": url, "source": "configured", "label": "已配置的宿主", "dataDirectory": ""})
    except (Fault, ValueError):
        pass
    slots = asyncio.Semaphore(8)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=1.2), trust_env=False,
                                     cookie_jar=aiohttp.DummyCookieJar()) as client:
        async def probe(item):
            async with slots:
                try:
                    async with client.get(item["url"] + "/api/v1/capabilities", allow_redirects=False) as response:
                        if response.status != 200:
                            return None
                        body = bytearray()
                        async for chunk in response.content.iter_chunked(8192):
                            body.extend(chunk)
                            if len(body) > 65536:
                                return None
                        value = json.loads(body)
                        if isinstance(value, dict) and value.get("protocolVersion") == 1:
                            return item
                except (aiohttp.ClientError, TimeoutError, ValueError):
                    pass
            return None
        items = await asyncio.gather(*(probe(item) for item in candidates.values()))
    return sorted((item for item in items if item), key=lambda item: (item["label"], item["url"]))
