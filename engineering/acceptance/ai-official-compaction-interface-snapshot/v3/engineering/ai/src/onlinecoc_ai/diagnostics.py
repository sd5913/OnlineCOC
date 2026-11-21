"""Bounded task diagnostics. Never persist exception messages or frame locals."""
import logging
import re
import traceback
import copy
import time
import threading

from .contracts import canonical, digest

LOG = logging.getLogger(__name__)
TOOLS = {'room_read_context', 'pack_read_contract', 'room_search_data',
         'room_read_data', 'room_read_chat', 'room_read_case', 'room_search_knowledge','room_read_knowledge',
         'pack_read_config_data','room_manage_catalog','room_read_management','room_read_sessions','room_read_compressed'}
KEYS = {'refIds','file','path','types', 'query', 'limit', 'cursor', 'refs', 'fields', 'channelId', 'after', 'before','includeHistory','operations','section','offset','sessionId','archived'}
KINDS = {'entity', 'config', 'rule', 'memory', 'channel', 'chat', 'event', 'ruling','room','knowledge'}
STAGES = {'profile_check':'检查服务配置','context_capture':'使用发送时资料快照',
          'context_compress':'压缩上下文并保留可追溯原文',
          'provider_complete':'等待 AI 服务回复','tool_execute':'读取已授权资料',
          'output_validate':'检查回答格式','dependency_check':'核对发送后的资料变化',
          'batch_preflight':'预检整批指令与规则前置条件','technical_repair':'自动修复技术参数（最多两次）',
          'proposal_create':'保存待审核候选','validation_a':'校验 A：格式与引用',
          'validation_b':'校验 B：规则执行','validation_c':'校验 C：游戏场景',
          'result_save':'保存回答','completed':'生成完成，等待后续处理'}


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
        self.preflight_checks = []
        self.context_budget = None
        self.timeline = []
        self.event_lock = threading.RLock()

    def event(self, stage, summary, **fields):
        with self.event_lock:
            self.finish()
            if len(self.timeline)<256:
                self.timeline.append({'seq':len(self.timeline)+1,'at':time.time(),'stage':stage,
                    'status':'running','summary':summary,**fields})

    def finish(self):
        with self.event_lock:
            if self.timeline and self.timeline[-1]['status']=='running':
                last=self.timeline[-1];last.update(status='completed',durationMs=round(max(0,time.time()-last['at'])*1000,2))

    def events(self):
        with self.event_lock:
            result=copy.deepcopy(self.timeline)
            if result and result[-1]['status']=='running':result[-1]['durationMs']=round(max(0,time.time()-result[-1]['at'])*1000,2)
            return result

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

    def preflight(self,value,attempt):
        # Keep structural diagnostics only; never save raw rule text or objects.
        fields=('index','target','op','status','code','ruleId','ruleCode','path')
        if len(self.preflight_checks)<3:self.preflight_checks.append({'attempt':attempt,'status':value['status'],
            'scope':value['scope'],'items':[{k:row[k] for k in fields if k in row} for row in value['items']]})

    def at(self, stage, *, turn=None):
        self.stage = stage
        if turn is not None:self.turn = turn
        if stage in STAGES and stage!='tool_execute':self.event(stage,STAGES[stage])
        if stage=='tool_result_encode':
            self.finish()
            if self.tools and self.tools[-1]['status']=='rejected' and self.timeline:
                self.timeline[-1].update(status='failed',code=self.tools[-1]['code'])

    def tool(self, name, args):
        entry = {'name': name if name in TOOLS else 'unknown', 'status': 'started',
                 'argumentsDigest': digest(args), 'keys': sorted(set(args) & KEYS),
                 'unknownKeys': bool(set(args) - KEYS), 'turn': self.turn}
        if isinstance(args.get('types'), list):entry['types'] = [k for k in args['types'] if isinstance(k, str) and k in KINDS][:8]
        if isinstance(args.get('refs'), list):entry['referenceCount'] = len(args['refs'])
        if isinstance(args.get('query'), str):entry['hasQuery'] = bool(args['query'])
        self.tools.append(entry)
        self.event('tool_execute','读取已授权资料',tool=entry['name'])
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
        with self.event_lock:
            self.finish()
            if self.timeline:self.timeline[-1].update(status='failed',code=item['code'])

    def snapshot(self):
        return {'schemaVersion': 1, 'stage': self.stage, 'turn': self.turn,
                'toolCalls': self.tools[-24:], 'errors': self.errors[:3], 'outputFailures':self.output_failures[-3:],
                'preflightChecks':copy.deepcopy(self.preflight_checks),
                **({'contextPolicy':copy.deepcopy(self.context_policy)} if hasattr(self,'context_policy') else {}),
                **({'contextOverflow':copy.deepcopy(self.context_overflow)} if hasattr(self,'context_overflow') else {}),
                **({'contextBudget':self.context_budget} if self.context_budget else {}), **({'compression':copy.deepcopy(self.compression)} if hasattr(self,'compression') else {})}

    def log(self, task_id):
        # No exc_info: logging a traceback would also print the exception text.
        LOG.error('AI task diagnostic %s', canonical({'taskId': task_id, **self.snapshot()}).decode())
