"""Acceptance harness for the real backend, isolated from concurrent edits."""
import argparse
import sys
from pathlib import Path

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument("--snapshot",type=Path,required=True)
    parser.add_argument("--data-dir",type=Path,required=True)
    parser.add_argument("--port",type=int,required=True)
    parser.add_argument("--host-control-dir",type=Path)
    args=parser.parse_args()
    sys.path[:0]=[str(args.snapshot/"backend/src"),str(args.snapshot/"data-management")]
    from onlinecoc.host import Host
    from onlinecoc.server import create_app
    from onlinecoc.host_control import HostControl
    import uvicorn
    
    host=Host(args.data_dir,bootstrap="p2p-test-only-password")
    control=HostControl(host,args.port,args.host_control_dir) if args.host_control_dir else None
    try:
        uvicorn.run(create_app(host,args.port,host_control=control),host="127.0.0.1",port=args.port,log_level="warning",ws_max_size=65536)
    finally:
        host.close()
