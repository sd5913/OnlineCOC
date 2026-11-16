"""Public P2P Python client; invoked by verify_integrations with private input file."""
import asyncio
import json
from pathlib import Path
import sys
import uuid
from onlinecoc_p2p.client import Player
from onlinecoc_p2p.common import Fault


async def main(config):
    players=[Player(config['directory']) for _ in range(2)]
    try:
        for index,player in enumerate(players,1):
            await player.join(config['roomId'])
            await player.request('login','POST',{'loginName':'player'+str(index),'password':config['password']})
            await player.prepare(Path(config['output'])/str(index))
        a,b=players;view=await a.request('view')
        assert view['accountId']=='player1' and (await b.request('view'))['accountId']=='player2'
        for path in ('package/state','package/action','ai/tasks','host-control/accounts'):
            try:await a.request(path)
            except Fault as e:assert e.code=='ROUTE_NOT_EXPOSED'
            else:raise AssertionError('unexpected exposed route '+path)
        command={'protocolVersion':1,'type':'command','requestId':str(uuid.uuid4()),'roomId':view['roomId'],'payload':{
            'commandId':str(uuid.uuid4()),'runId':view['runId'],'authorityEpoch':view['authorityEpoch'],
            'catalogRevision':view['catalog']['revision'],'rulesetRevision':view['catalog']['rulesetRevision'],'expectedViews':{},
            'op':'chat.message.send','args':{'channelId':'general','text':'P2P isolated acceptance'}}}
        sent=await a.request('commands','POST',command);assert sent['status']=='committed',sent
        messages=await b.request('chat/history','POST',{'channelId':'general','limit':10})
        assert any(x['text']=='P2P isolated acceptance' for x in messages['items'])
        await a.rpc('subscribe');assert (await asyncio.wait_for(a.states.get(),10))['type']=='snapshot.begin'
        print('P2P real peer checks passed')
    finally:
        for player in players:await player.close()


if __name__=='__main__':asyncio.run(main(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))))
