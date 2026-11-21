"""Launch the standalone AI manager from the repository checkout."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'ai/src'), str(ROOT / 'backend/src'), str(ROOT / 'data-management')]
from onlinecoc_ai.manager import main

if __name__ == '__main__':main()
