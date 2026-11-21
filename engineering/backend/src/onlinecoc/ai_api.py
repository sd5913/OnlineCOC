"""HTTP wiring only. Application policy belongs to the independent AI module."""
import asyncio
from fastapi import Request
from fastapi.responses import JSONResponse


def install(app, runtime, auth):
    from onlinecoc_ai.errors import AiError
    from onlinecoc_ai.contracts import loads
    service = runtime.application
    from onlinecoc_ai.references import References
    references = References(service.host)
    from onlinecoc_ai.data_queries import DataQueryService, TOOLS
    queries = DataQueryService(service.host)

    @app.post('/api/v1/ai/data/{operation}')
    async def data_query(operation: str, request: Request):
        account = auth(request, True)
        from onlinecoc_ai.access import can_use
        role=can_use(service.host,service.repository,account)
        return await asyncio.to_thread(queries.execute, account, operation, loads(await request.body()),player=account if role!='kp' else None)

    @app.get('/api/v1/ai/references')
    def reference_search(request: Request, kind: str = 'config', q: str = ''):
        account=auth(request)
        from onlinecoc_ai.access import can_use
        can_use(service.host,service.repository,account)
        return references.search(account, kind, q)

    @app.post('/api/v1/ai/references/resolve')
    async def reference_resolve(request: Request):
        account = auth(request, True);data = loads(await request.body())
        from onlinecoc_ai.access import can_use
        can_use(service.host,service.repository,account)
        from onlinecoc_ai.errors import require
        require(type(data) is dict and set(data) == {'tokens'}, 'INPUT_INVALID')
        return await asyncio.to_thread(references.resolve, account, data['tokens'])

    @app.exception_handler(AiError)
    async def ai_error(request, exc):
        return JSONResponse({'code': exc.code}, status_code=403 if exc.code == 'PERMISSION_DENIED' else 409)

    @app.post('/api/v1/ai/commands')
    @app.post('/api/v1/ai/drafts')
    async def command(request: Request):
        account = auth(request, True);data = loads(await request.body())
        if request.url.path.endswith('/drafts'):
            from .errors import require
            require(type(data) is dict and data.get('op') in ('ai.draft.create', 'ai.proposal.revise'), 'INPUT_INVALID')
        return await asyncio.to_thread(service.command, account, data)

    @app.get('/api/v1/ai/receipts/{request_id}')
    def receipt(request_id: str, request: Request):return service.receipt(auth(request), request_id)

    @app.get('/api/v1/ai/tasks')
    def tasks(request: Request, before: str | None = None, limit: int = 30):return service.tasks(auth(request), before, limit, delivered=True)

    @app.get('/api/v1/ai/usage')
    def usage(request: Request):
        from onlinecoc_ai.errors import require
        account = auth(request)
        require(len(request.query_params.multi_items()) == len(request.query_params), 'INPUT_INVALID')
        return service.usage(account, dict(request.query_params))

    @app.get('/api/v1/ai/debug')
    def debug(request: Request):
        from onlinecoc_ai.errors import require
        account = auth(request)
        require(len(request.query_params.multi_items()) == len(request.query_params), 'INPUT_INVALID')
        options = dict(request.query_params)
        require(set(options) <= {'sessionId', 'requestId', 'rulingId', 'includeContent'}, 'INPUT_INVALID')
        require(bool(set(options) & {'sessionId', 'requestId', 'rulingId'}), 'INPUT_INVALID')
        content = options.get('includeContent', 'false')
        require(content in ('true', 'false'), 'INPUT_INVALID')
        options['includeContent'] = content == 'true'
        for key in ('sessionId', 'requestId', 'rulingId'):
            if key in options:
                require(1 <= len(options[key]) <= 200, 'INPUT_INVALID')
        # Authorization is evaluated live by Application.debug; no command or
        # receipt is created for this read-only projection.
        return JSONResponse(service.debug(account, options), headers={'Cache-Control': 'no-store'})

    @app.get('/api/v1/ai/proposals/{proposal_id}')
    def proposal(proposal_id: str, request: Request):return service.proposal(auth(request), proposal_id)

    @app.get('/api/v1/ai/access')
    def access(request: Request):return service.sessions.access(auth(request))

    @app.get('/api/v1/ai/rulings')
    def rulings(request: Request):
        import inspect
        listing=service.rulings.list
        # Older separately deployed AI modules do not yet accept delivery proofs.
        return listing(auth(request),delivered=True) if 'delivered' in inspect.signature(listing).parameters else listing(auth(request))

    @app.get('/api/v1/ai/batches')
    def batches(request: Request):return service.batches.list(auth(request))

    @app.get('/api/v1/ai/settings')
    def settings(request: Request):return service.settings(auth(request))

    @app.get('/api/v1/ai/contracts')
    def contracts(request: Request):
        auth(request)
        from onlinecoc_ai.api import OPERATIONS
        from onlinecoc_ai.contracts import SCHEMAS
        return {'version': 1, 'operations': OPERATIONS, '$defs': SCHEMAS['$defs'], 'dataTools': TOOLS}

    @app.get('/api/v1/ai/sessions')
    def sessions(request: Request, archived: bool = False):return service.sessions.list(auth(request), archived)

    @app.get('/api/v1/ai/sessions/{session_id}')
    def session(session_id: str, request: Request):return service.sessions.get(auth(request), session_id, delivered=True)
