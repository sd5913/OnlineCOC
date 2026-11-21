"""CPU profile of a real command in a previously stopped disposable fixture."""
import argparse
import cProfile
from pathlib import Path
import pstats
import sys
import uuid

HERE=Path(__file__).resolve().parent
ENGINEERING=HERE.parents[1]
sys.path[:0]=[str(ENGINEERING/'backend/src'),str(ENGINEERING/'data-management')]
from onlinecoc.host import Host
parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
args=parser.parse_args()
rooms=list((HERE/'benchmark-tmp').glob('host-*/room'))
path=max(rooms,key=lambda p:p.stat().st_mtime)
host=Host(path)
try:
    message={'protocolVersion':1,'type':'command','roomId':'demo','requestId':'profile',
        'payload':{'authorityEpoch':host.epoch,'commandId':uuid.uuid4().hex,
                   'op':'chat.message.send','args':{'channelId':'general','text':'profile'}}}
    profile=cProfile.Profile();profile.enable();result=host.command('player1',message);profile.disable()
    assert result['status']=='committed',result
    target=(HERE/args.output).resolve()
    if not target.is_relative_to(HERE):raise ValueError('Output outside performance directory')
    with target.open('w',encoding='utf-8') as stream:
        pstats.Stats(profile,stream=stream).strip_dirs().sort_stats('cumulative').print_stats(35)
    print(target.name)
finally:host.close()
