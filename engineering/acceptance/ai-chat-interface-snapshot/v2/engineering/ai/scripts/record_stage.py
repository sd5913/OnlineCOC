"""Record a completed pytest invocation without manufacturing acceptance results."""
import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone, timedelta
from pathlib import Path
from xml.etree import ElementTree


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage")
    parser.add_argument("--junit", required=True)
    parser.add_argument("--group", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    junit = (root / args.junit).resolve()
    tests = list(ElementTree.parse(junit).iter("testcase"))
    failed = sum(x.find("failure") is not None or x.find("error") is not None for x in tests)
    skipped = sum(x.find("skipped") is not None for x in tests)
    sources = sorted((root / "engineering/ai/src").rglob("*.py")) + sorted((root / "engineering/backend/src").rglob("*.py")) + sorted((root / "engineering/contracts").glob("*.json"))
    sources += sorted(p for p in (root / "engineering/ai/tests/fixtures").rglob("*") if p.is_file())
    sources += sorted(p for folder in ('engineering/rulepacks/demo', 'engineering/test-console', 'engineering/client-sdk')
                      for p in (root / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    sources += sorted((root / 'engineering/ai/tests').glob('*.py'))
    sources += sorted((root / 'engineering/ai/scripts').glob('*.py'))
    sources += sorted(p for p in (root / 'engineering/ai/web').rglob('*') if p.is_file())
    hashes = {str(p.relative_to(root)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    result = {"stage": args.stage, "group": args.group,
              "completedAt": datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).isoformat(),
              "python": platform.python_version(), "platform": platform.platform(),
              "tests": len(tests), "failed": failed, "skipped": skipped,
              "passed": len(tests) - failed - skipped,
              "status": "passed" if tests and not failed and not skipped else "incomplete",
              "junit": str(junit.relative_to(root)).replace("\\", "/"), "sourceDigests": hashes}
    output = root / "engineering/acceptance/ai-runtime" / (args.stage.lower() + ".json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("stage", "status", "passed", "failed", "skipped")}))
    return int(result["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
