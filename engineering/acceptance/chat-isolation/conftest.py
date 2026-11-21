import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent/'work/after/engineering'
sys.path[:0]=[str(ROOT/'backend/src'),str(ROOT/'ai/src'),str(ROOT/'data-management')]
