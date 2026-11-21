import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent/'work/engine/engineering'
sys.path[:0]=[str(ROOT/'backend/src'),str(ROOT/'data-management'),str(ROOT/'ai/src')]
