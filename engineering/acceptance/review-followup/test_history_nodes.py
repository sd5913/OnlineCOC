"""Isolated text-node history checks against real immutable host artifacts."""
import copy
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'ai/tests'),str(ROOT/'ai/src'),str(ROOT/'backend/src'),str(ROOT/'data-management')]
from test_entrypoints import application
from test_coordinator import setup
from test_data_edits import install_game
from onlinecoc_ai.contracts import digest
from onlinecoc_ai.history import assess
from onlinecoc_ai.sandbox import stage


@pytest.mark.parametrize('field',['truth','description'])
@pytest.mark.parametrize('change,readable',[('text',True),('delete-field',False),('delete-object',False),('replace-object',False),('revoke',False)])
def test_text_node_history_has_current_authority_but_not_old_value_equality(application,field,change,readable):
    app=application;install_game(app);room=app.host.state();active=room['artifacts'][room['activeRuleset']]
    data=copy.deepcopy(active['data']);data['game.json']['locations']={'a':{'id':'a','truth':'原来的机关连接','description':'原来的场景描述'}}
    artifact=stage(active['sources'],data);room['artifacts'][artifact['revision']]=artifact;room['activeRuleset']=artifact['revision'];app.host.commit(room)
    context=app.proposals.snapshot('kp')[0]
    context['facts']['configDataReads']=[{'file':'game.json','path':['locations','a',field],'targetDigest':digest(data['game.json']['locations']['a'][field])}]
    room=app.host.state();data=copy.deepcopy(data)
    if change=='text':data['game.json']['locations']['a'][field]='更新后的文本'
    elif change=='delete-field':del data['game.json']['locations']['a'][field]
    elif change=='delete-object':del data['game.json']['locations']['a']
    elif change=='replace-object':data['game.json']['locations']['a']['id']='other-object'
    else:room['members']['kp']['authorizationEpoch']+=1
    updated=stage(active['sources'],data);room['artifacts'][updated['revision']]=updated;room['activeRuleset']=updated['revision'];app.host.commit(room)
    if readable:assert assess(app.host,app.repository,room,context) in ('SOURCE_STALE','BASELINE_STALE')
    else:
        with pytest.raises(Exception) as exc:assess(app.host,app.repository,room,context)
        assert getattr(exc.value,'code',None) in (('PERMISSION_DENIED',) if change=='revoke' else ('SOURCE_STALE',))
