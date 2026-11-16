from __future__ import annotations

import argparse
import asyncio
import json
import ssl
import webbrowser
from pathlib import Path

from aiohttp import web

from .common import atomic_json, read_json, require
from .directory import Directory
from .host import Host
from .local_app import start_local
from .packages import Package


async def client(config, port, open_browser):
    shell, runner, url = await start_local(config, port)
    try:
        # This URL contains a local-only capability. Never include it in public logs.
        if open_browser:
            webbrowser.open(url)
        else:
            atomic_json(Path(config["statePath"]) / "local-entry.json", {"url": url})
        print(json.dumps({"localOrigin": shell.origin, "status": "ready"}, ensure_ascii=False), flush=True)
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


async def host(config):
    adapter = Host(config)
    try:
        print(json.dumps(await adapter.start(), ensure_ascii=False), flush=True)
        await asyncio.Event().wait()
    finally:
        await adapter.close()


def main():
    parser = argparse.ArgumentParser(description="OnlineCOC 公网房间与 P2P 联机")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("directory", "host", "client"):
        command = sub.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
        if name == "directory":
            command.add_argument("--bind", default="127.0.0.1")
            command.add_argument("--port", type=int, default=8443)
            command.add_argument("--cert", type=Path)
            command.add_argument("--key", type=Path)
        if name == "client":
            command.add_argument("--port", type=int, default=0)
            command.add_argument("--no-browser", action="store_true")
    export = sub.add_parser("export")
    export.add_argument("--source", type=Path, required=True)
    export.add_argument("--descriptor", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "export":
            print(Package.export(args.source, args.descriptor, args.output))
            return
        config = read_json(args.config)
        for key in ("caFile", "statePath", "packagePath", "stateFile", "hostDiscoveryPath"):
            if config.get(key) and not Path(config[key]).is_absolute():
                config[key] = str((args.config.resolve().parent / config[key]).resolve())
        if args.command == "directory":
            context = None
            require(args.bind in {"127.0.0.1", "::1"} or (args.cert and args.key), "TLS_REQUIRED")
            if args.cert and args.key:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.minimum_version = ssl.TLSVersion.TLSv1_2
                context.load_cert_chain(args.cert, args.key)
            service = Directory(config, Path(config["stateFile"]))
            web.run_app(service.app(), host=args.bind, port=args.port, ssl_context=context, access_log=None)
        elif args.command == "host":
            asyncio.run(host(config))
        else:
            asyncio.run(client(config, args.port, not args.no_browser))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
