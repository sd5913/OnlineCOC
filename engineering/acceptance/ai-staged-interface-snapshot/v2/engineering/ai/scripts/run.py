"""Repository entry point; no editable install or environment mutation needed."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "ai/src"), str(ROOT / "backend/src"), str(ROOT / "data-management")]
from onlinecoc_ai.cli import main

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
