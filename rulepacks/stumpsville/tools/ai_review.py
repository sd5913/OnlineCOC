"""Resolve package review locators without granting or executing a game action."""
import copy
import hashlib
import json


def source(state, view, args):
    if view.get('role') != 'kp':
        raise ValueError('需要主持权限')
    if not isinstance(args, dict) or not {'kind', 'id'} <= set(args) <= {'kind', 'id', 'account'}:
        raise ValueError('裁决来源格式不正确')
    kind, key = args['kind'], args['id']
    if not isinstance(kind, str) or kind not in {'draft', 'request', 'wait', 'flow', 'event'} or not isinstance(key, str) or not 0 < len(key) <= 200:
        raise ValueError('裁决来源无效')
    if kind != 'event' and 'account' in args:
        raise ValueError('裁决来源不接受指定账号')
    record = None
    if kind == 'draft':
        record = state.get('drafts', {}).get(key)
    elif kind == 'request':
        record = state.get('requests', {}).get(key)
    elif kind == 'wait':
        record = view.get('waits', {}).get(key)
        if record and record.get('role') != 'kp':
            raise ValueError('不是主持待处理事项')
    elif kind == 'flow':
        record = view.get('flows', {}).get(key)
    elif kind == 'event':
        owner = args.get('account')
        if not isinstance(owner, str) or owner not in state.get('events', {}):
            raise ValueError('记录所属账号无效')
        record = next((e for e in state.get('events', {}).get(owner, []) if e.get('id') == key), None)
    if not isinstance(record, dict):
        raise ValueError('原裁决不存在或已移除，请刷新')
    record = copy.deepcopy(record)
    related = state.get('requests', {}).get(record.get('requestId'), {}) if kind == 'event' else {}
    title = {'draft': '角色审核', 'request': '玩家行动申请', 'wait': '宿主流程等待',
             'flow': '宿主流程异常', 'event': '裁决与行动记录'}[kind]
    details = record.get('text') or record.get('reason') or record.get('error') or record.get('name') or record.get('title')
    if not details:
        options = record.get('options') or {}
        details = options.get('question') or options.get('prompt') or record.get('status') or title
    summary = str(details)[:8000]
    requested_by = related.get('account') or record.get('account') or record.get('owner')
    # A flow without a recorded applicant remains unattributed; never label it KP's own request.
    if not isinstance(requested_by, str) or not 0 < len(requested_by) <= 200:
        requested_by = None
    context = {'record': record, 'status': record.get('status'), 'sourceLocator': copy.deepcopy(args)}
    if related:
        context['request'] = copy.deepcopy(related)
    encoded = json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    revision = hashlib.sha256(encoded.encode()).hexdigest()
    if len(encoded.encode()) > 30 * 1024:
        context = {'status': record.get('status'), 'sourceLocator': copy.deepcopy(args),
                   'contentOmitted': True, 'reason': 'SOURCE_TOO_LARGE'}
    result = {'kind': 'package', 'sourceId': 'stumpsville', 'category': kind, 'id': key,
              'revision': revision, 'title': title, 'summary': summary, 'context': context}
    if requested_by:
        result['requestedBy'] = requested_by
    # The module bounds the whole source, including the duplicated summary.
    # ASCII JSON is an upper bound for the UTF-8 canonical form, including CJK.
    if len(json.dumps(result, ensure_ascii=True).encode()) > 31 * 1024:
        result['context'] = {'status': record.get('status'), 'sourceLocator': copy.deepcopy(args),
                             'contentOmitted': True, 'reason': 'SOURCE_TOO_LARGE'}
        if len(result['summary']) > 3000:
            result['summary'] = result['summary'][:3000]
            result['context']['summaryTruncated'] = True
    return result


def submit(job, view, review_source):
    """Persist the AI envelope before sending; retry only after querying its receipt."""
    entry = job.record.get('aiReview')
    fresh = entry is None
    if fresh:
        request_id = 'sv-review-' + hashlib.sha256(job.record['requestKey'].encode()).hexdigest()[:48]
        entry = {'envelope': {'requestId': request_id, 'authorityEpoch': view['authorityEpoch'],
                             'op': 'ai.review.create', 'args': {'source': review_source}}}
        job.record['aiReview'] = entry
        job.store.save()
    if 'result' not in entry:
        envelope = entry['envelope']
        receipt = {'status': 'unknown'} if fresh else job.client.request('/ai/receipts/' + envelope['requestId'])
        if receipt['status'] == 'unknown':
            envelope['authorityEpoch'] = view['authorityEpoch']
            job.store.save()
            receipt = job.client.request('/ai/commands', envelope)
        if receipt['status'] != 'committed':
            from client import HostError
            raise HostError(receipt)
        entry['result'] = copy.deepcopy(receipt['result'])
        job.store.save()
    return {'message': '已转 AI 准备方案，原裁决仍需处理', **copy.deepcopy(entry['result'])}
