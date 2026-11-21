import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"backend/src"),str(ROOT/"data-management"),str(ROOT/"ai/src")]

import copy
import pytest


@pytest.fixture
def ai_case(tmp_path):
    from onlinecoc.host import Host
    from onlinecoc_ai.pack import Pack,fixture_state
    from onlinecoc_ai.sandbox import stage
    from onlinecoc_ai.proposals import Proposals
    h=Host(tmp_path/'host',bootstrap='test-password')
    pack=Pack(ROOT/'ai/tests/fixtures/pack')
    artifact=stage(pack.sources,pack.data)
    state=h.state();world=fixture_state(pack.json(pack.scenarios[0]['fixtureRef']),pack.configurations)
    for key in ('entities','relations','members','configurations','progress','collectionRevision'):state[key]=world[key]
    state['artifacts'][artifact['revision']]=artifact;state['activeRuleset']=artifact['revision'];h.commit(state)
    service=Proposals(h,pack)
    config=copy.deepcopy(pack.configurations['fixture.token']);config['revision']='2';config['defaults']['bonus']=15
    delta={'schemaVersion':1,'configurations':[{'kind':'replace','id':config['configurationId'],'expectedRevision':'1','value':config}],
           'sources':{},'data':{},'suggestions':[]}
    proposal=service.create('kp','制作有限次使用并提高检定成功率的道具',delta)
    result=service.validate('kp',proposal['proposalId'],1)
    assert result['proposal']['status']=='review_ready',result
    yield h,service,result['proposal'],delta
    service.close();h.close()
