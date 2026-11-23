"""Real host HTTP -> frozen AI v1 page/detail, including encoded IDs and revocation."""
from types import SimpleNamespace
from fastapi.testclient import TestClient
from onlinecoc.server import create_app
from test_entrypoints import application
from test_coordinator import setup
from test_access_batches import batch


def test_real_ai_page_detail_delivery_and_current_permission(application):
    app=application;b=batch(app);rid='batch:'+b['batchId']
    class Runtime:
        application=app
        async def start(self):pass
        async def close(self):pass
    http=create_app(app.host,8765,ai_runtime=Runtime())
    with TestClient(http,base_url='http://127.0.0.1:8765',backend_options={}) as client:
        client.headers['origin']='http://127.0.0.1:8765'
        assert client.post('/api/v1/login',json={'loginName':'kp','password':'test-password'}).status_code==200
        page=client.get('/api/v1/ai/rulings?compact=true&queue=active&limit=1').json()
        assert page['activeCount']==1 and page['items'][0]['rulingId']==rid
        detail=client.get('/api/v1/ai/rulings/'+rid.replace(':','%3A')).json()
        assert detail['rulingId']==rid and detail['canDecide'] and detail['actions']
        assert client.get('/api/v1/ai/rulings').json()['items'][0]['rulingId']==rid
        state=app.host.state();state['members']['kp']['authorizationEpoch']+=1;app.host.commit(state)
        stale=client.get('/api/v1/ai/rulings/'+rid.replace(':','%3A')).json()
        assert stale['sourceState']=='denied' and not stale['canDecide']
