"""Real loopback HTTP and Edge fetches against Application, with no model API."""
import socket
import threading
import time
from types import SimpleNamespace
import httpx
import uvicorn
from playwright.sync_api import sync_playwright
from onlinecoc.server import create_app
from test_entrypoints import application
from test_coordinator import setup
from test_chat_isolation import generated
from test_context import add_message


def test_real_http_browser_retains_task_and_ruling_originals(application):
    app=application;s,task=generated(app,'/entities/actor-one')
    async def idle():pass
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];origin=f'http://127.0.0.1:{port}'
    server=uvicorn.Server(uvicorn.Config(create_app(app.host,port=port,ai_runtime=SimpleNamespace(application=app,start=idle,close=idle)),log_level='error'))
    worker=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);worker.start()
    try:
        deadline=time.monotonic()+10
        while not server.started and time.monotonic()<deadline:time.sleep(.01)
        assert server.started
        with httpx.Client(base_url=origin,headers={'origin':origin},trust_env=False) as client:
            assert client.get('/api/v1/ai/rulings').status_code==401
            assert not app.repository.state()['settings'].get('rulingDeliveries')
            assert client.post('/api/v1/login',json={'loginName':'kp','password':'test-password'}).status_code==200
            before=client.get('/api/v1/ai/rulings').json()['items'][0]
            assert before['summary']==task['text']
            assert app.repository.state()['settings'].get('rulingDeliveries')
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(channel='msedge',headless=True)
            page=browser.new_page();page.goto(origin+'/ai-ui/chat.html')
            login=page.evaluate("async()=>{let r=await fetch('/api/v1/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({loginName:'kp',password:'test-password'})});return r.status}")
            assert login==200
            before_task=page.evaluate("async(sid)=>(await fetch('/api/v1/ai/sessions/'+sid)).json()",s['sessionId'])['items'][0]
            add_message(app.host,'player1','普通聊天不得影响AI卡片')
            room=app.host.state();del room['entities']['actor-one'];app.host.commit(room)
            values=page.evaluate("async(sid)=>Promise.all(['/api/v1/ai/sessions/'+sid,'/api/v1/ai/rulings'].map(async p=>(await fetch(p)).json()))",s['sessionId'])
            item=values[0]['items'][0];ruling=values[1]['items'][0]
            assert item['text']==before_task['text'] and item['initiator']=='kp' and item['response']==task['text']
            assert item['sourceState']==ruling['sourceState']=='stale' and ruling['summary']==task['text'] and not ruling['canDecide']
            room=app.host.state();room['members']['kp']['authorizationEpoch']+=1;app.host.commit(room)
            # Membership authorization changed: the HTTP identity may remain
            # logged in, but old source authority and delivered bodies are denied.
            denied=page.evaluate("async()=>(await fetch('/api/v1/ai/rulings')).json()")['items'][0]
            assert denied['sourceState']=='denied' and denied['summary']!=task['text'] and not denied['canDecide']
            browser.close()
    finally:server.should_exit=True;worker.join(10);sock.close();assert not worker.is_alive()
