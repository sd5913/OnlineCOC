"""Prepare a local optional adapter without changing the game host or other modules."""
import argparse
import asyncio
from pathlib import Path

from onlinecoc_p2p.common import atomic_json, read_json, require
from onlinecoc_p2p.discovery import discover
from onlinecoc_web.resources import Resources


async def main():
    module = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", help="Explicit loopback game host URL; otherwise detect one registered local host")
    parser.add_argument("--source", type=Path, default=module / "examples/core-table")
    parser.add_argument("--title", default="我的网页跑团房间")
    parser.add_argument("--approval", action="store_true")
    parser.add_argument("--output", type=Path, default=module / "local/host.json")
    args = parser.parse_args()
    config = read_json(module.parent / "network-p2p/local/client-config.json")
    upstream = args.upstream
    if not upstream:
        found = await discover(config)
        require(len(found) == 1, "请选择一个本机宿主，用 --upstream http://127.0.0.1:端口 指定")
        upstream = found[0]["url"]
    exported = Resources.export(args.source, args.source / "web.json", module / "local/exports")
    require(not args.output.exists(), "配置已存在；请使用其他 --output，或编辑原配置，避免覆盖房间身份")
    atomic_json(args.output, {"directory": config["directory"], "caFile": config.get("caFile"),
        "publisherToken": config["publisherToken"], "statePath": str(module / "local/room"),
        "upstream": upstream, "webPackagePath": str(exported), "settings": {"title": args.title, "maxPlayers": 8},
        "webPolicy": {"approvalRequired": args.approval}, "fileBytesPerSecond": 131072})
    print("本机配置已生成：" + str(args.output))


if __name__ == "__main__":
    asyncio.run(main())
