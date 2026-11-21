import sys
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parent/'work/engine/engineering'
sys.path[:0]=[str(ROOT/'backend/src'),str(ROOT/'data-management'),str(ROOT/'ai/src')]
from onlinecoc.host import Host
from onlinecoc.host_control import HostControl
from onlinecoc.server import create_app
import uvicorn

host=Host(sys.argv[1],bootstrap='synthetic-account-password')
control=HostControl(host,int(sys.argv[2]),sys.argv[3])
if len(sys.argv)>4:
    host.fault=lambda stage:os._exit(77) if stage==sys.argv[4] else None
try:uvicorn.run(create_app(host,int(sys.argv[2]),control),host='127.0.0.1',port=int(sys.argv[2]),log_level='error')
finally:host.close()
