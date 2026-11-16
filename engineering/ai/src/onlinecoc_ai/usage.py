"""Authorized, read-only usage summaries derived from the durable call ledger.

Confirmed tokens and conservative reservations are deliberately separate. The
room ledger is not an account-wide provider bill and contains no price estimate.
"""
from datetime import date, datetime, timedelta, timezone

from onlinecoc.model import member
from .errors import require

QUERY_FIELDS = {'from', 'to', 'scope', 'profileId', 'sessionId', 'before', 'limit'}


def metrics():
    return {key: 0 for key in ('calls', 'settledCalls', 'pendingCalls', 'uncertainCalls',
        'confirmedTokens', 'promptTokens', 'completionTokens', 'missingBreakdownCalls',
        'pendingReservedTokens', 'uncertainReservedTokens', 'accountedTokens')}


def add(target, values):
    for key, value in values.items():target[key] += value


def summarize(app, account, options=None):
    options = {} if options is None else options
    require(type(options) is dict and set(options) <= QUERY_FIELDS and
        all(type(v) is str for v in options.values()), 'INPUT_INVALID')
    today = datetime.now(timezone.utc).date()
    try:
        start = date.fromisoformat(options.get('from', (today - timedelta(days=6)).isoformat()))
        end = date.fromisoformat(options.get('to', today.isoformat()))
        limit = int(options.get('limit', '50'))
    except (ValueError, TypeError):
        require(False, 'INPUT_INVALID')
    require(0 <= (end - start).days < 366 and 1 <= limit <= 100, 'INPUT_INVALID')
    scope = options.get('scope', 'mine')
    require(scope in ('mine', 'room'), 'INPUT_INVALID')
    for key in ('profileId', 'sessionId', 'before'):
        require(key not in options or 1 <= len(options[key]) <= 200, 'INPUT_INVALID')
    if hasattr(app.runtime, 'refresh_profiles'):app.runtime.refresh_profiles()
    with app.host.lock:
        room = app.host.state();principal = member(room, account)
        require(scope != 'room' or principal['role'] == 'kp', 'PERMISSION_DENIED')
        state = app.repository.state()
        sessions = state['settings'].get('sessions', {})
        selected = sessions.get(options.get('sessionId'))
        if 'sessionId' in options:require(selected and selected['owner'] == account, 'NOT_VISIBLE')
        # A dispatched task has its own request ID. Preserve the original owner
        # and session through dispatch rather than attributing all usage to KP.
        originals = {tid: rid for rid, tid in state['settings'].get('dispatch', {}).items()}
        own_sessions = {rid: sid for sid, s in sessions.items() if s['owner'] == account for rid in s['requestIds']}
        calls = {}
        for tid, task in state['tasks'].items():
            rid = originals.get(tid, task['requestId']);request = state['requests'].get(rid)
            for call in task.get('calls', []):calls[call['callId']] = (task, request, rid, call)
        totals = metrics();days = {};profiles = {};items = []
        for key, budget in state['budgets'].items():
            profile_id, day = key.rsplit(':', 1)
            if not start.isoformat() <= day <= end.isoformat():continue
            if options.get('profileId', profile_id) != profile_id:continue
            for cid, entry in budget['calls'].items():
                task, request, rid, detail = calls.get(cid, (None, None, None, {}))
                if scope == 'mine' and (not request or request['initiator'] != account):continue
                sid = own_sessions.get(rid)
                if selected and rid not in selected['requestIds']:continue
                model = task['profile']['model'] if task else None
                value = metrics();value['calls'] = 1;value['accountedTokens'] = entry['charged']
                outcome = 'uncertain'
                if entry['status'] == 'settled':
                    outcome = 'confirmed';value['settledCalls'] = 1;value['confirmedTokens'] = entry['charged']
                    usage = detail.get('usage')
                    if usage:
                        value['promptTokens'] = usage['prompt_tokens'];value['completionTokens'] = usage['completion_tokens']
                    else:value['missingBreakdownCalls'] = 1
                elif entry.get('outcome') == 'pending' and task and task['status'] in ('generating', 'validating'):
                    outcome = 'pending';value['pendingCalls'] = 1;value['pendingReservedTokens'] = entry['charged']
                else:
                    value['uncertainCalls'] = 1;value['uncertainReservedTokens'] = entry['charged']
                add(totals, value);add(days.setdefault(day, metrics()), value)
                add(profiles.setdefault((profile_id, model), metrics()), value)
                items.append({'callId': cid, 'date': day, 'profileId': profile_id, 'model': model,
                    'requestId': rid, 'sessionId': sid, 'status': outcome, 'taskStatus': task['status'] if task else None,
                    'createdAt': entry.get('createdAt'), **value})
        items.sort(key=lambda item: (item['date'], item['createdAt'] or 0, item['callId']), reverse=True)
        if 'before' in options:
            index = next((i for i, item in enumerate(items) if item['callId'] == options['before']), None)
            require(index is not None, 'CURSOR_INVALID');items = items[index + 1:]
        # Budget status always describes today's whole room; never expose it in
        # a player's own summary or mix it with a historical filtered total.
        ceilings = []
        if scope == 'room':
            for profile in app.coordinator.profiles.values():
                if options.get('profileId', profile['profileId']) != profile['profileId']:continue
                ceiling = profile['limits'].get('dailyTokenBudget')
                charged = state['budgets'].get(profile['profileId'] + ':' + today.isoformat(), {}).get('charged', 0)
                ceilings.append({'profileId': profile['profileId'], 'date': today.isoformat(), 'dailyTokenBudget': ceiling,
                    'enabled': ceiling is not None, 'accountedTokens': charged,
                    'remainingTokens': None if ceiling is None else max(0, ceiling - charged)})
        return {'schemaVersion': 1, 'scopeId': state['scopeId'], 'scope': scope, 'timezone': 'UTC',
            'from': start.isoformat(), 'to': end.isoformat(), 'totals': totals,
            'byDay': [{'date': day, **value} for day, value in sorted(days.items(), reverse=True)],
            'byProfile': [{'profileId': key[0], 'model': key[1], **value} for key, value in sorted(profiles.items(), key=lambda row: (row[0][0], row[0][1] or ''))],
            'budgetsToday': ceilings, 'items': items[:limit],
            'nextBefore': items[limit - 1]['callId'] if len(items) > limit else None}
