import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent/'work/engine/engineering'
sys.path[:0]=[str(ROOT/'backend/src'),str(ROOT/'data-management'),str(ROOT/'ai/src')]
from onlinecoc.host import Host
h=Host(sys.argv[1],bootstrap='synthetic-account-password')
h.fault=lambda stage:os._exit(77) if stage==sys.argv[2] else None
h.local_account_change(json.loads(sys.stdin.read()))
h.close()
