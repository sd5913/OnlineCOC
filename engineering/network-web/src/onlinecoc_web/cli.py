import argparse
import asyncio
import json
import ssl
from pathlib import Path

from aiohttp import web
from onlinecoc_p2p.common import read_json, require
from .host import WebHost
from .portal import WebDirectory
from .resources import Resources
from .creation import export_room_setup


async def host(config, stop_file=None):
    adapter = WebHost(config)
    try:
        entry = await adapter.start()
        print(json.dumps({k: v for k, v in entry.items() if k not in {"claim", "creationString"}}, ensure_ascii=False), flush=True)
        print("房主认领信息已写入 statePath/web-entry.json；请勿分享 claim。", flush=True)
        if stop_file:
            while not stop_file.exists(): await asyncio.sleep(.25)
        else:
            await asyncio.Event().wait()
    finally:
        await adapter.close()


def main():
    parser = argparse.ArgumentParser(description="OnlineCOC 浏览器房间与按需游戏页")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("serve", "host"):
        p = sub.add_parser(name)
        p.add_argument("--config", type=Path, required=True)
        if name == 'host': p.add_argument('--stop-file', type=Path)
        if name == "serve":
            p.add_argument("--bind", default="127.0.0.1")
            p.add_argument("--port", type=int, default=8443)
            p.add_argument("--cert", type=Path)
            p.add_argument("--key", type=Path)
    p = sub.add_parser("export")
    for name in ("source", "descriptor", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    p = sub.add_parser("room-setup", help="导出本机房主专用开房串；勿写入公共日志")
    p.add_argument("--state-path", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "room-setup":
        print(export_room_setup(args.state_path))
        return
    if args.command == "export":
        print(Resources.export(args.source, args.descriptor, args.output))
        return
    config = read_json(args.config)
    for key in ("stateFile", "webStateFile", "statePath", "caFile", "webPackagePath"):
        if config.get(key) and not Path(config[key]).is_absolute():
            config[key] = str((args.config.resolve().parent / config[key]).resolve())
    try:
        if args.command == "host":
            asyncio.run(host(config, args.stop_file))
        else:
            require(args.bind in {"127.0.0.1", "::1"} or args.cert and args.key, "TLS_REQUIRED")
            tls = None
            if args.cert and args.key:
                tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                tls.minimum_version = ssl.TLSVersion.TLSv1_2
                tls.load_cert_chain(args.cert, args.key)
            service = WebDirectory(config, Path(config["stateFile"]))
            web.run_app(service.app(), host=args.bind, port=args.port, ssl_context=tls, access_log=None)
    except KeyboardInterrupt:
        pass
