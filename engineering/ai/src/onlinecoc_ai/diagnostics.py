"""Bounded task diagnostics. Never persist exception messages or frame locals."""
import logging
import re
import traceback

from .contracts import canonical, digest

LOG = logging.getLogger(__name__)
TOOLS = {'room_read_context', 'pack_read_contract', 'room_search_data',
         'room_read_data', 'room_read_chat', 'room_read_case', 'room_search_knowledge','room_read_knowledge',
         'pack_read_config_data','room_manage_catalog','room_read_management','room_read_sessions'}
KEYS = {'file','path','types', 'query', 'limit', 'cursor', 'refs', 'fields', 'channelId', 'after', 'before','includeHistory','operations','section','offset','sessionId','archived'}
KINDS = {'entity', 'config', 'rule', 'memory', 'channel', 'chat', 'event', 'ruling','room','knowledge'}


def error_code(exc):
    from .errors import AiError
    from onlinecoc.errors import DomainError
    if isinstance(exc, TimeoutError):return 'TASK_TIMEOUT'
    if isinstance(exc, (AiError, DomainError)) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}', exc.code):return exc.code
    return 'AI_TASK_FAILED'


class TaskTrace:
    def __init__(self):
        self.stage = 'task_start'
        self.turn = 0
        self.tools = []
        self.errors = []
        self.output_failures = []
        self.context_budget = None

    def context_usage(self, messages, tools, limit):
        self.context_budget={'bytes':len(canonical({'messages':messages,'tools':tools})),
            'limitBytes':limit,'toolSchemaBytes':len(canonical(tools)),
            'toolMessageBytes':sum(len(canonical(m)) for m in messages if m.get('role')=='tool')}

    def output_failure(self, exc, attempt):
        # Paths may contain generated object IDs; retain only structural segments.
        known={'kind','text','actions','changeSet','configurations','sources','data','suggestions','value','defaults','behaviors','revision','expectedRevision','args','op','target','choices','options','label','id'}
        parts=re.split(r'[/.\[\]]+',getattr(exc,'path',''))
        path='/'.join(p if p in known or p.isdigit() else '*' for p in parts if p)[:160]
        self.output_failures.append({'attempt':attempt,'code':error_code(exc),'path':'/'+path})

    def at(self, stage, *, turn=None):
        self.stage = stage
        if turn is not None:self.turn = turn

    def tool(self, name, args):
        entry = {'name': name if name in TOOLS else 'unknown', 'status': 'started',
                 'argumentsDigest': digest(args), 'keys': sorted(set(args) & KEYS),
                 'unknownKeys': bool(set(args) - KEYS), 'turn': self.turn}
        if isinstance(args.get('types'), list):entry['types'] = [k for k in args['types'] if isinstance(k, str) and k in KINDS][:8]
        if isinstance(args.get('refs'), list):entry['referenceCount'] = len(args['refs'])
        if isinstance(args.get('query'), str):entry['hasQuery'] = bool(args['query'])
        self.tools.append(entry)
        return entry

    def error(self, exc, *, stage=None):
        frames = []
        for frame, line in traceback.walk_tb(exc.__traceback__):
            module = frame.f_globals.get('__name__', '')
            if module == 'onlinecoc_data' or module.startswith(('onlinecoc_ai.', 'onlinecoc.')):
                frames.append({'module': module, 'function': frame.f_code.co_name, 'line': line})
        kind = type(exc).__name__
        item = {'stage': stage or self.stage, 'code': error_code(exc),
                'exceptionType': kind if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', kind) else 'Exception',
                'frames': frames[-8:]}
        # Keep only a bounded integer; never persist remote messages, headers,
        # URLs, request IDs or exception text (which can echo user data).
        status = getattr(exc, 'http_status', None)
        if type(status) is int and 100 <= status <= 599:
            item['httpStatus'] = status
        if len(self.errors) < 3:self.errors.append(item)

    def snapshot(self):
        return {'schemaVersion': 1, 'stage': self.stage, 'turn': self.turn,
                'toolCalls': self.tools[-24:], 'errors': self.errors[:3], 'outputFailures':self.output_failures[-3:],
                **({'contextBudget':self.context_budget} if self.context_budget else {})}

    def log(self, task_id):
        # No exc_info: logging a traceback would also print the exception text.
        LOG.error('AI task diagnostic %s', canonical({'taskId': task_id, **self.snapshot()}).decode())
