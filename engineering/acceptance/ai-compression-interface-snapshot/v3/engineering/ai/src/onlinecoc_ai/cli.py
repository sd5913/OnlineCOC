"""Offline tools: every invocation uses the same validation service as AI/UI."""
import argparse
import json
from pathlib import Path
import sys
import asyncio

from .contracts import loads, validate
from .errors import AiError
from .pack import Pack, fixture_state, merge_changes
from .sandbox import stage
from .validation.base import check_base
from .validation.common import static_context
from .validation.gameplay import assess
from .validation.rules import check_rules


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0].startswith("profile-"):
        return profile_main(argv)
    parser = argparse.ArgumentParser(description="OnlineCOC AI offline tools")
    parser.add_argument("command", choices=["check-base", "check-rules", "assess"])
    parser.add_argument("--pack", required=True)
    parser.add_argument("--changes", required=True, help="ChangeSet JSON; sources/data are merged into the full candidate")
    parser.add_argument("--state", help="Optional exported execution snapshot; never modified")
    args = parser.parse_args(argv)
    try:
        pack = Pack(args.pack)
        baseline = stage(pack.sources, pack.data)
        state = loads(Path(args.state).read_bytes()) if args.state else fixture_state(pack.json(pack.scenarios[0]["fixtureRef"]), pack.configurations)
        if "activeRuleset" in state:
            baseline = validate("Artifact", state["artifacts"][state["activeRuleset"]])
        changes = merge_changes(baseline, loads(Path(args.changes).read_bytes()))
        context = static_context(pack, state, baseline)
        if args.command == "check-base":
            result, _ = check_base(pack, state, baseline, context, changes)
        else:
            result = (check_rules if args.command == "check-rules" else assess)(pack, state, baseline, context, changes)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0 if result["status"] == "pass" else 1
    except Exception as exc:
        print(json.dumps({"status": "error", "code": getattr(exc, "code", "INPUT_INVALID")}, ensure_ascii=False))
        return 2


def profile_main(argv):
    from .profiles import DEFAULT_PATH, initialize, load_profiles, save_profile
    from .providers import create_provider
    parser = argparse.ArgumentParser(description="Local AI provider administration")
    parser.add_argument("command", choices=["profile-init", "profile-list", "profile-put", "profile-probe"])
    parser.add_argument("--config", default=str(DEFAULT_PATH))
    parser.add_argument("--input", help="Complete Profile JSON, with credentialRef only")
    parser.add_argument("--profile")
    args = parser.parse_args(argv)
    try:
        if args.command == "profile-init":
            result = {"path": initialize(args.config)}
        elif args.command == "profile-list":
            result = {"profiles": list(load_profiles(args.config).values())}
        elif args.command == "profile-put":
            if not args.input:
                parser.error("--input is required")
            result = save_profile(loads(Path(args.input).read_bytes()), args.config)
        else:
            profiles = load_profiles(args.config)
            if args.profile not in profiles:
                parser.error("--profile must name an existing profile")
            async def probe():
                provider = create_provider(profiles[args.profile])
                try:
                    return await provider.probe()
                finally:
                    await provider.close()
            result = asyncio.run(probe())
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "code": getattr(exc, "code", "INPUT_INVALID")}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
