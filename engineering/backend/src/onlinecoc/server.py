import asyncio, hashlib, json, time, logging, mimetypes
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI,Request,WebSocket,WebSocketDisconnect
from fastapi.responses import JSONResponse,FileResponse,Response
from fastapi.staticfiles import StaticFiles
from onlinecoc_data import StoreError,canonical
from .errors import DomainError,require
from .contracts import check
from .assets import Assets
from .version import ENGINE_VERSION, ROOM_SCHEMA_VERSION

ROOT=Path(__file__).resolve().parents[3]

def runtime_info():
    import os,ctypes
    result={'pid':os.getpid()}
    if os.name=='nt':
        class Counters(ctypes.Structure):
            _fields_=[('cb',ctypes.c_ulong),('pageFaults',ctypes.c_ulong)]+[(k,ctypes.c_size_t) for k in ('peakWorkingSet','workingSet','peakPaged','paged','peakNonpaged','nonpaged','pagefile','peakPagefile')]
        counters=Counters();counters.cb=ctypes.sizeof(counters)
        get_process=ctypes.windll.kernel32.GetCurrentProcess;get_process.restype=ctypes.c_void_p
        get_memory=ctypes.windll.psapi.GetProcessMemoryInfo;get_memory.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong];get_memory.restype=ctypes.c_int
        if get_memory(get_process(),ctypes.byref(counters),counters.cb):
            result.update(workingSetBytes=counters.workingSet,peakWorkingSetBytes=counters.peakWorkingSet)
    return result


def create_app(host,port=8765,host_control=None,*,ai_runtime=None):
    origins={f'http://127.0.0.1:{port}',f'http://localhost:{port}'}
    allowed_hosts={f'127.0.0.1:{port}',f'localhost:{port}'}
    assets=Assets(host);inflight=0
    # Windows registry MIME associations must not control browser module delivery.
    mimetypes.add_type('text/javascript','.js');mimetypes.add_type('text/css','.css');mimetypes.add_type('text/html','.html')
    @asynccontextmanager
    async def lifespan(app):
        async def ticker():
            while True:
                try:await asyncio.to_thread(host.tick)
                except Exception:logging.exception('Room scheduler failed; inspect storage and pending flows')
                await asyncio.sleep(.2)
        if host_control:
            try: host_control.publish()
            except OSError:
                # Sandboxed/service accounts may have no usable DPAPI profile.
                host_control.close()
                logging.warning('Local host account control unavailable; room service continues')
        task=asyncio.create_task(ticker())
        if ai_runtime:await ai_runtime.start()
        try:
            yield
        finally:
            if ai_runtime:await ai_runtime.close()
            if host_control: host_control.close()
            task.cancel()
        try:await task
        except asyncio.CancelledError:pass
    app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.state.host=host
    @app.exception_handler(DomainError)
    async def domain_error(request,e):
        status=401 if e.code.startswith('AUTH') else 404 if e.code=='NOT_VISIBLE' else 403 if e.code=='PERMISSION_DENIED' else 409
        return JSONResponse({'code':e.code},status_code=status)
    @app.exception_handler(json.JSONDecodeError)
    async def invalid_json(request,e):return JSONResponse({'code':'INPUT_INVALID'},status_code=400)
    @app.exception_handler(StoreError)
    async def store_error(request,e):return JSONResponse({'code':'STORAGE_UNAVAILABLE'},status_code=503)
    @app.middleware('http')
    async def boundary(request,call_next):
        if request.headers.get('host') not in allowed_hosts:return JSONResponse({'code':'HOST_REJECTED'},status_code=403)
        if request.method in ('POST','PUT','DELETE') and not request.url.path.startswith('/api/v1/host-control/') and request.headers.get('origin') not in origins:return JSONResponse({'code':'ORIGIN_REJECTED'},status_code=403)
        if request.url.path.startswith('/api/'):
            limit=10*1024*1024 if request.url.path=='/api/v1/assets' else 8*1024*1024 if request.url.path=='/api/v1/ai/drafts' else 64*1024
            # Bound streamed bodies, including requests without Content-Length.
            raw=bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw)>limit:return JSONResponse({'code':'LIMIT_EXCEEDED'},status_code=413)
            request._body=bytes(raw)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        # Only the three room AI entry pages support same-origin framing.
        frame_policy = "'self'" if ai_runtime and request.url.path in ('/ai-ui/page.html', '/ai-ui/conversation.html', '/ai-ui/collapsible.html', '/ai-ui/sessions.html') else "'none'"
        response.headers['Content-Security-Policy']="default-src 'self'; connect-src 'self' ws://127.0.0.1:* ws://localhost:*; style-src 'self'; script-src 'self'; frame-ancestors " + frame_policy
        return response
    def auth(request,write=False):
        token=request.cookies.get('onlinecoc','');session=host.auth(token)
        if write:require(request.headers.get('x-csrf-token')==session['csrf'],'PERMISSION_DENIED')
        return session['accountId']
    async def read_object(request):
        data=await request.json();require(isinstance(data,dict));return data
    def local_authority(request):
        require(host_control is not None, 'PERMISSION_DENIED')
        host_control.authorize(request)

    @app.get('/api/v1/host-control/accounts')
    def host_accounts(request:Request):
        local_authority(request)
        return host_control.accounts()

    @app.post('/api/v1/host-control/accounts')
    async def host_change(request:Request):
        local_authority(request)
        data=await read_object(request)
        def run():
            with host.lock:
                local_authority(request)
                result=host.local_account_change(data)
                if result['status']=='rejected':
                    return JSONResponse(result,status_code=404 if result.get('code')=='NOT_VISIBLE' else 409)
                return result
        return await asyncio.to_thread(run)

    @app.get('/api/v1/host-control/receipts/{request_id}')
    def host_receipt(request_id:str,request:Request):
        local_authority(request)
        with host.lock:
            result=host.local_account_receipt(request_id)
            if result['status']=='pending':return JSONResponse(result,status_code=503)
            if result['status']=='rejected':return JSONResponse(result,status_code=404 if result.get('code')=='NOT_VISIBLE' else 409)
            return result

    @app.get('/api/v1/capabilities')
    def capabilities():return {'engineVersion':ENGINE_VERSION,'roomSchemaVersion':ROOM_SCHEMA_VERSION,'protocolVersion':1,'transports':['http','websocket'],'resumeWindow':0,'storage':'files','maxCommandBytes':65536,'ai':{'version':1,'available':ai_runtime is not None,'enabled':bool(ai_runtime and host.state()['aiControl']['settings']['enabled']),'maxCommandBytes':65536,'maxDraftBytes':8*1024*1024,'maxPage':100},'chat':{'version':1,'maxTextLength':4000,'maxHistoryPage':100,'maxChannels':128,'maxMessages':10000,'privateAssetAttachments':False}}
    @app.post('/api/v1/login')
    async def login(request:Request):
        data=await read_object(request);check('login',data)
        def enter():
            with host.lock:return host.identity.login(data['loginName'],data['password'])
        token,csrf=await asyncio.to_thread(enter);response=JSONResponse({'csrf':csrf})
        response.set_cookie('onlinecoc',token,httponly=True,samesite='strict',max_age=86400)
        return response
    @app.get('/api/v1/me')
    def me(request:Request):
        session=host.auth(request.cookies.get('onlinecoc',''));return {'accountId':session['accountId'],'csrf':session['csrf']}
    @app.post('/api/v1/logout')
    def logout(request:Request):
        auth(request,True)
        with host.lock:host.identity.logout(request.cookies.get('onlinecoc',''))
        response=JSONResponse({'ok':True});response.delete_cookie('onlinecoc');return response
    @app.get('/api/v1/view')
    def view(request:Request):return host.project(auth(request))
    @app.get('/api/v1/notifications')
    def notifications(request:Request):
        require(set(request.query_params)<= {'after','limit'}, 'INPUT_INVALID')
        try:
            after=int(request.query_params.get('after','0'));limit=int(request.query_params.get('limit','50'))
        except ValueError:raise DomainError('INPUT_INVALID')
        return host.notifications(auth(request),after,limit)
    @app.get('/api/v1/knowledge/capabilities')
    def knowledge_capabilities(request:Request):
        with host.lock:return host.knowledge.capabilities(auth(request))
    @app.post('/api/v1/knowledge/{operation:path}')
    async def knowledge_query(operation:str,request:Request):
        methods={'preview':host.knowledge.preview,'search':host.knowledge.search,'read':host.knowledge.read,'grants/query':host.knowledge.grants}
        require(operation in methods,'NOT_VISIBLE')
        data=await read_object(request)
        def dispatch():
            with host.lock:return methods[operation](auth(request,True),data)
        return await asyncio.to_thread(dispatch)
    @app.post('/api/v1/query')
    async def query(request:Request):
        data=await read_object(request);require(set(data)<={'collection','equals'} and 'collection' in data)
        def dispatch():
            with host.lock:return host.query(auth(request,True),data['collection'],data.get('equals'))
        return {'items':await asyncio.to_thread(dispatch)}
    @app.get('/api/v1/chat/members')
    def chat_members(request:Request):
        with host.lock:return {'items':host.chat_members(auth(request))}
    @app.get('/api/v1/chat/channels')
    def chat_channels(request:Request):
        with host.lock:return host.chat_channels(auth(request))
    @app.post('/api/v1/chat/history')
    async def chat_history(request:Request):
        data=await read_object(request);check('chat.history',data)
        def dispatch():
            with host.lock:return host.chat_history(auth(request,True),data['channelId'],data.get('before'),data.get('limit',50))
        return await asyncio.to_thread(dispatch)
    @app.get('/api/v1/contracts')
    def contracts():
        from .contracts import MODELS,OPERATIONS
        return {'protocolVersion':1,'models':MODELS,'operations':OPERATIONS,'knowledge':json.loads((ROOT/'contracts/knowledge.json').read_text(encoding='utf-8')),'ai':json.loads((ROOT/'contracts/ai.json').read_text(encoding='utf-8')),'aiOperations':json.loads((ROOT/'contracts/ai-operations.json').read_text(encoding='utf-8'))}
    @app.get('/api/v1/catalog')
    def catalog(request:Request):return host.catalog(auth(request))
    @app.post('/api/v1/commands')
    async def command(request:Request):
        nonlocal inflight
        require(inflight<128,'LIMIT_EXCEEDED')
        data=await request.json()
        def dispatch():
            return host.dispatch(request.cookies.get('onlinecoc',''),request.headers.get('x-csrf-token'),data)
        inflight+=1
        try:return await asyncio.to_thread(dispatch)
        finally:inflight-=1
    @app.get('/api/v1/receipts/{command_id}')
    def receipt(command_id:str,request:Request):
        with host.lock:return host.receipt(auth(request),command_id)
    @app.post('/api/v1/calculate')
    async def calculate(request:Request):
        data=await read_object(request);require(set(data)=={'rule','input'})
        def dispatch():
            with host.lock:return host.calculate(auth(request,True),data['rule'],data['input'])
        return {'result':await asyncio.to_thread(dispatch)}
    @app.post('/api/v1/preview')
    async def preview(request:Request):
        from .lua_runtime import execute
        account=auth(request,True);data=await request.json()
        def run():
            with host.lock:
                account=auth(request,True);host.kp(account);s=host.state();artifact=s['artifacts'].get(data.get('revision',s['activeRuleset']));require(artifact,'NOT_VISIBLE')
                from jsonschema import Draft202012Validator
                metadata=artifact['metadata'].get(data.get('rule'));require(metadata and metadata['mode']!='flow')
                require(Draft202012Validator(metadata['schema']).is_valid(data.get('input')))
                return execute(artifact['sources'],{'kind':'run','rule':data['rule'],'input':data['input'],'mode':'action','state':host.snapshot_for_execution(s),'account':account,'data':artifact['data']},lambda sides:min(50,sides))
        result=await asyncio.to_thread(run);return {'result':result['result'],'effects':result['effects']}
    @app.post('/api/v1/assets')
    async def upload(request:Request):
        account=auth(request,True);raw=await request.body()
        def dispatch():
            with host.lock:return assets.upload(auth(request,True),request.headers.get('x-asset-name','asset'),raw,request.headers.get('x-asset-visibility','public'))
        return {'assetId':await asyncio.to_thread(dispatch)}
    @app.get('/api/v1/assets/{id}')
    def download(id:str,request:Request):
        raw,a=assets.read(auth(request),id)
        return Response(raw,media_type='application/octet-stream',headers={'Content-Disposition':'attachment'})
    @app.get('/api/v1/admin')
    def admin(request:Request):
        account=auth(request);host.kp(account)
        with host.lock:
            s=host.state();return {'store':host.store.inspect(),'members':s['members'],'assets':s['assets'],'audit':s['audit'][-100:],'flows':s['flows'],'artifacts':list(s['artifacts']),'runtime':runtime_info(),'metrics':host.metrics,'configurations':s['configurations']}
    @app.get('/api/v1/admin/artifacts/{revision}')
    def artifact(revision:str,request:Request):
        with host.lock:
            host.kp(auth(request));s=host.state();a=s['artifacts'].get(revision);require(a,'NOT_VISIBLE')
            old=s['artifacts'][s['activeRuleset']]
            changes={k:('added' if k not in old['sources'] else 'removed' if k not in a['sources'] else 'changed') for k in set(a['sources'])|set(old['sources']) if a['sources'].get(k)!=old['sources'].get(k)}
            return {'artifact':a,'comparedTo':s['activeRuleset'],'sourceChanges':changes,'dataChanged':old['data']!=a['data']}
    @app.post('/api/v1/backup')
    async def backup(request:Request):
        from .model import uid
        account=auth(request,True);target=host.path/'backups'/uid()
        def dispatch():
            with host.lock:return assets.backup(auth(request,True),target)
        await asyncio.to_thread(dispatch);return {'backupId':target.name}
    @app.websocket('/api/v1/connect')
    async def connect(ws:WebSocket):
        if ws.headers.get('host') not in allowed_hosts or ws.headers.get('origin') not in origins:
            await ws.close(code=1008);return
        try:session=host.auth(ws.cookies.get('onlinecoc',''));account=session['accountId']
        except DomainError:await ws.close(code=1008);return
        await ws.accept();last=None;last_generation=None;can_skip=False
        loop=asyncio.get_running_loop()
        try:
            # Each full projection is captured under the room lock and applied as one snapshot.
            # Superseded states are coalesced; no cross-connection delta replay is advertised.
            while True:
                def capture():
                    with host.lock:
                        host.auth(ws.cookies.get('onlinecoc',''))
                        if can_skip and host.store.generation==last_generation:return None,host.store.generation
                        return host.project(account),host.store.generation
                projection,generation=await asyncio.to_thread(capture)
                raw=canonical(projection) if projection is not None else None
                fingerprint=hashlib.sha256(raw).hexdigest() if raw is not None else last
                if projection is not None and fingerprint!=last:
                    if len(raw)>2*1024*1024:await ws.close(code=1009);return
                    snapshot=hashlib.sha256(raw).hexdigest()[:24]
                    # Chunk as JSON text, then atomically parse/apply after end.
                    text=raw.decode('utf-8');chunks=[text[i:i+24000] for i in range(0,len(text),24000)]
                    await asyncio.wait_for(ws.send_json({'type':'snapshot.begin','id':snapshot,'parts':len(chunks)}),2)
                    for i,part in enumerate(chunks):await asyncio.wait_for(ws.send_json({'type':'snapshot.part','id':snapshot,'index':i,'data':part}),2)
                    host.hit('before_snapshot_end')
                    # The authorization check and outbound scheduling are one
                    # lock-protected boundary; network I/O runs after release.
                    def finish():
                        with host.lock:
                            host.auth(ws.cookies.get('onlinecoc',''))
                            # A room-owned projection cannot change at the same
                            # committed generation. External knowledge still rechecks.
                            if 'knowledge' not in projection and host.store.generation==generation:
                                valid=True
                            else:
                                current=hashlib.sha256(canonical(host.project(account))).hexdigest()
                                valid=current==fingerprint
                            outgoing=asyncio.run_coroutine_threadsafe(ws.send_json({'type':'snapshot.end','id':snapshot} if valid else {'type':'reset'}),loop)
                            return valid,outgoing
                    valid,outgoing=await asyncio.to_thread(finish)
                    await asyncio.wait_for(asyncio.wrap_future(outgoing),2)
                    if not valid:last=None;continue
                    last=fingerprint
                if projection is not None:
                    last_generation=generation
                    # External providers may change without a room commit.
                    can_skip='knowledge' not in projection
                try:
                    message=await asyncio.wait_for(ws.receive_text(),timeout=.25)
                    if len(message)>65536:await ws.close(code=1009);return
                    if message=='ping':await ws.send_json({'type':'pong'})
                except asyncio.TimeoutError:pass
        except DomainError:
            try:await ws.send_json({'type':'reset'});await ws.close(code=1008)
            except Exception:pass
        except (WebSocketDisconnect,RuntimeError,asyncio.TimeoutError):
            try:await ws.close(code=1013)
            except Exception:pass
    if ai_runtime:
        from .ai_api import install
        install(app,ai_runtime,auth)
        app.mount('/ai-ui',StaticFiles(directory=ROOT/'ai/web/components'),name='ai-components')
    app.mount('/sdk',StaticFiles(directory=ROOT/'client-sdk'),name='sdk')
    app.mount('/',StaticFiles(directory=ROOT/'test-console',html=True),name='console')
    return app
