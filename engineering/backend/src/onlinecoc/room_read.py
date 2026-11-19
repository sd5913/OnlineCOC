"""Explicit KP-only access to persisted Room JSON, never local files or identity."""
from onlinecoc_data import canonical
from .errors import require
from .model import member

ROOM_FIELDS = ('schemaVersion','roomId','name','runId','status','activeRuleset','collectionRevision',
               'entities','relations','members','progress','configurations','commands','flows','waits',
               'artifacts','assets','audit','outbox','chat','aiControl','knowledge')


def authorize(host, state, account, initiator=None):
    require(member(state, account)['role'] == 'kp', 'PERMISSION_DENIED')
    require(member(state, initiator or account)['role'] == 'kp', 'PERMISSION_DENIED')
    check = getattr(host, 'ai_room_read_authorizer', None)
    require(callable(check) and check(account) is True, 'PERMISSION_DENIED')


def fragments(state):
    """Split large records by JSON path and long text by character offset."""
    def walk(value, path):
        record = {'path':path, 'value':value}
        if len(canonical(record)) <= 4096:
            yield record
        elif isinstance(value, dict):
            for key in sorted(value):yield from walk(value[key], path + [key])
        elif isinstance(value, list):
            for index, child in enumerate(value):yield from walk(child, path + [index])
        elif isinstance(value, str):
            start = 0
            while start < len(value):
                end = min(start + 512, len(value))
                chunk = {'path':path, 'value':value[start:end], 'textOffset':start, 'textLength':len(value)}
                while len(canonical(chunk)) > 4096 and end > start + 1:
                    end = start + max(1,(end-start)//2);chunk['value'] = value[start:end]
                require(len(canonical(chunk)) <= 4096, 'QUERY_RESULT_LIMIT')
                yield chunk;start = end
        else:
            require(False, 'QUERY_RESULT_LIMIT')
    for field in ROOM_FIELDS:
        if field not in state:continue
        value = state[field]
        if isinstance(value, dict) and value:
            for key in sorted(value):yield from walk(value[key], [field,key])
        elif isinstance(value, list) and value:
            for index, child in enumerate(value):yield from walk(child, [field,index])
        else:
            yield from walk(value, [field])
