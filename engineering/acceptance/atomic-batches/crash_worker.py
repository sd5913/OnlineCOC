"""Hard-exit fault probe, invoked only with an isolated acceptance save."""
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'backend/src'),str(ROOT/'data-management')]
from onlinecoc.host import Host

host=Host(sys.argv[1])
point=sys.argv[3]
def fault(stage):
    if stage==point:os._exit(70)
host.fault=fault
host.execute_batch('kp',json.loads(Path(sys.argv[2]).read_text(encoding='utf-8')),command_id='batch')
host.close()
