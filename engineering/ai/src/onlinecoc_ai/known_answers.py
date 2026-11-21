"""Strict player responses select evidence; model prose never becomes displayed facts.

This module is deliberately independent of the host and its mutable contracts.
The caller must acquire and recheck every evidence item through KnowledgeService.
"""
import base64
import copy
import hashlib
import json
import re

from .errors import AiError, require

SCHEMA = {'type': 'object', 'additionalProperties': False,
    'required': ['kind', 'evidence', 'next'], 'properties': {
        'kind': {'const': 'known'},
        'evidence': {'type': 'array', 'maxItems': 12, 'uniqueItems': True,
            'items': {'type': 'string', 'pattern': '^k[0-9a-f]{64}$'}},
        'next': {'enum': ['none', 'ask_kp', 'ask_kp_change']}}}

INSTRUCTIONS = '''You assist one player using only their verified personal knowledge.
knownIndex supplies an initial empty-query index of your personal authorized records.
Start by reading relevant refs from it; do not claim lack of permission merely because
a keyword search misses an inventory or clue nested in a known record. A fallback=personal-index
result is an explicitly unfiltered personal index, not a match for the original keyword.
Use the supplied knowledge search/read tools to answer the request. A search label is
not a detail: read the selected references before answering. Never call another data
source, infer discoveries, use module lore or invent narrative facts.
query is a literal filter, not semantic search. For broad requests to show existing known
information or inventory, search with query="" and follow nextCursor. If a name filter
has no matches, try an empty query before concluding there is no relevant known record.
Return only a valid JSON object: {"kind":"known","evidence":["issued evidenceId"],"next":"none"}.
Select at most 12 distinct evidenceId values actually issued in a detail read.
The server renders their exact authorized observations; do not return text, titles,
choices, conclusions, suspicions or commands. Select next="ask_kp" to offer the neutral
option to request a KP disclosure; it does not grant access or execute anything.
For combining items, inventing content, changing configurations or requesting an action,
select next="ask_kp_change" to offer a separate business request to the KP. Read relevant
known evidence when useful, but do not reject a creative request merely because players
cannot publish configurations. This option is only an offer; the player must click to submit.
If there is no relevant readable evidence, return an empty evidence list. Empty search
results say nothing about whether an object exists. Old observations are not current
world state. Provider failures must not be bypassed with previous model text.
'''


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def evidence_id(ref):
    return 'k' + hashlib.sha256(_canonical(ref).encode()).hexdigest()


def reference_token(ref):
    """Version the opaque UI encoding separately from the content revision."""
    require(type(ref) is dict and set(ref) == {'schemaVersion','scopeId','id','revision','digest'}
        and ref['schemaVersion'] == 1, 'KNOWLEDGE_DATA_INVALID')
    require(all(type(ref[k]) is str and 1 <= len(ref[k]) <= 200 for k in ('scopeId','id','revision','digest')),
        'KNOWLEDGE_DATA_INVALID')
    value = base64.urlsafe_b64encode(_canonical(ref).encode()).decode().rstrip('=')
    require(len(value) <= 1500, 'KNOWLEDGE_DATA_INVALID')
    return '[[knowledge:' + value + '@1]]'


def decode_reference(key, revision):
    require(revision == '1' and type(key) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,1500}', key), 'REFERENCE_INVALID')
    try:
        ref = json.loads(base64.urlsafe_b64decode(key + '=' * (-len(key) % 4)).decode())
        require(reference_token(ref) == '[[knowledge:' + key + '@1]]', 'REFERENCE_INVALID')
        return ref
    except (ValueError, UnicodeError, TypeError, KeyError) as exc:
        raise AiError('REFERENCE_INVALID') from exc


def register(pool, items):
    """Only detailed, already-authorized items can be issued to this model turn."""
    issued = []
    for item in items:
        require(type(item) is dict and 'data' in item and item.get('mode') in ('observed_snapshot','live_scope')
            and type(item.get('label')) is str and type(item.get('facetId')) is str, 'KNOWLEDGE_DATA_INVALID')
        reference_token(item.get('ref'))
        require(len(_canonical(item).encode()) <= 64 * 1024, 'KNOWLEDGE_DATA_INVALID')
        key = evidence_id(item['ref'])
        require(key not in pool or pool[key] == item, 'KNOWLEDGE_DATA_INVALID')
        require(key in pool or len(pool) < 128, 'QUERY_LIMIT')
        pool[key] = copy.deepcopy(item)
        issued.append({**copy.deepcopy(item), 'evidenceId': key})
    return issued


def parse(content, pool):
    from jsonschema import Draft202012Validator
    require(type(content) is str and len(content) <= 8000, 'MODEL_JSON_INVALID')
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, 'MODEL_FIELDS_INVALID')
            result[key] = value
        return result
    fenced = re.fullmatch(r'\s*```(?:json)?\s*\n([\s\S]*?)\n```\s*', content)
    try:
        value = json.loads(fenced[1] if fenced else content, object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(AiError('MODEL_JSON_INVALID')))
    except (ValueError, RecursionError):
        raise AiError('MODEL_JSON_INVALID') from None
    require(Draft202012Validator(SCHEMA).is_valid(value), 'MODEL_KNOWN_ANSWER_INVALID')
    require(all(key in pool for key in value['evidence']), 'REFERENCE_UNVERIFIED')
    return value


def _literal(value):
    """Evidence is data, never nested reference markup, HTML or instructions."""
    text = value if type(value) is str else _canonical(value)
    return re.sub(r'([\\`*_{}\[\]()<>#!|])', r'\\\1', text).replace('\r', '')


# Presentation only: these fields have already passed knowledge authorization.
# Technical identifiers remain in the immutable evidence, not in player prose.
FIELD_LABELS = {
    'name':'名称','label':'名称','text':'内容','description':'说明','features':'环境特征',
    'clues':'已知线索','actions':'已记录行动','choices':'行动选项','hint':'提示','process':'处理说明',
    'exits':'出口编号','doors':'观察时的门状态','numbers':'数值','metadata':'补充资料',
    'tags':'标签','hp':'生命','maxHp':'生命上限','str':'力量','dex':'敏捷','wil':'意志','armor':'护甲',
    'location':'位置编号','round':'回合','phase':'阶段','autoResolve':'自动裁决','pips':'钱币',
    'testimony':'证词','note':'备注','reason':'原因','status':'状态','uses':'剩余用量',
    'slot':'携带槽位','itemIndex':'物品编号','kind':'类别','slots':'占用槽位','damage':'伤害','light':'照明','useDie':'用量骰','maxUses':'用量上限','ticks':'刻度','inventory':'携带物品','title':'标题','value':'数值','count':'数量','known':'已获知'}
TECHNICAL_FIELDS = frozenset({'id','entityId','instanceId','configurationId','typeRef','revision',
    'digest','scopeId','navigation','rules','components','sourceGuard','ref','provenance','owner','visibility','lifecycle','index'})


def format_data(data, limit=4000):
    """Deterministic player prose, without querying, inferring or executing data."""
    lines=[];nodes=0;omitted=False
    def walk(value, depth=0, label=None):
        nonlocal nodes,omitted
        nodes+=1
        if nodes>180 or depth>10:omitted=True;return
        prefix='  '*depth+'- '
        if isinstance(value,(dict,list)):
            entries=[(k,v) for k,v in value.items() if k not in TECHNICAL_FIELDS] if isinstance(value,dict) else list(enumerate(value))
            if label:lines.append(prefix+'**'+_literal(label)+'**'+('：无可展示条目' if not entries else ''));depth+=1
            if not entries and not label:lines.append(prefix+'无可展示条目')
            for key,item in entries:
                title=(FIELD_LABELS.get(key,key if re.search(r'[\u4e00-\u9fff]',str(key)) else '编号 '+str(key) if str(key).isdigit() else '其他已知资料') if isinstance(value,dict) else '条目 '+str(key+1))
                walk(item,depth,title)
        else:
            text='未记录' if value is None else '是' if value is True else '否' if value is False else str(value)
            lines.append(prefix+('**'+_literal(label)+'**：' if label else '')+_literal(text).replace('\n',' '))
    walk(data)
    selected=[];size=0
    for line in lines:
        if size+len(line)+1>max(0,limit-60):omitted=True;break
        selected.append(line);size+=len(line)+1
    if omitted:selected.append('部分内容未展开，请打开引用详情查看。')
    return '\n'.join(selected) or '暂无可展示的已知内容。'


def compact_data(data, label='已知资料'):
    """One captured name and purpose; the immutable reference opens full detail."""
    if isinstance(data,dict):
        label=next((data[k] for k in ('name','label','title') if type(data.get(k)) is str and data[k].strip()),label)
        detail=next((data[k] for k in ('text','description','hint','note') if type(data.get(k)) is str and data[k].strip()),'')
    else:detail=data if type(data) is str else ''
    title=_literal(' '.join(label.split())[:80]);detail=_literal(' '.join(detail.split())[:180])
    return '**'+title+'**'+('：'+detail if detail else '')+'\n\n点击引用查看完整资料。'


def format_legacy(text):
    """Reformat only our old escaped-JSON evidence blocks, after source recheck.

    No current-room lookups and no persistent migration of historical answers.
    """
    if not isinstance(text,str):return text
    pattern=r'((?:观察记录|持续告知资料) · \[\[knowledge:[A-Za-z0-9_.-]+@1\]\])\n\n(.*?)(?=\n\n(?:观察记录|持续告知资料) · |\Z)'
    def replace(match):
        raw=re.sub(r'\\([\\`*_{}\[\]()<>#!|])',r'\1',match[2])
        try:value=json.loads(raw)
        except (ValueError,RecursionError):
            # This is only called for authorized strict-known responses. Recognize
            # the old server formatter, never rewrite arbitrary conversation prose.
            if not match[2].startswith('- '):return match[0]
            value={}
            for field,label in (('name','名称'),('text','内容'),('description','说明')):
                found=re.search(r'^- \*\*'+label+r'\*\*：([^\n]+)',match[2],re.M)
                if found:value[field]=re.sub(r'\\([\\`*_{}\[\]()<>#!|])',r'\1',found[1])
        if not isinstance(value,(dict,list)):return match[0]
        return match[1]+'\n\n'+compact_data(value)
    return re.sub(pattern,replace,text,flags=re.S)

def render(output, pool):
    # Fixed order avoids a model-provided priority/suspicion ranking.
    selected = sorted((pool[key] for key in output['evidence']), key=lambda v: (v.get('observedAt') or 0, v['ref']['id'], v['facetId']))
    parts = []
    for item in selected:
        heading = '观察记录' if item['mode'] == 'observed_snapshot' else '持续告知资料'
        data = item['data']
        text = compact_data(data,item['label'])
        parts.append(heading + ' · ' + reference_token(item['ref']) + '\n\n' + text)
    text = '\n\n'.join(parts) or '暂未获得与问题匹配的本人已知资料。可换个关键词查询，或向 KP 申请资料。'
    require(len(text) <= 8000, 'MODEL_KNOWN_ANSWER_LIMIT')
    choices = None
    if output['next'] == 'ask_kp':
        choices = {'prompt': '需要向 KP 请求说明吗？', 'options': [
            {'id':'ask_kp','label':'向 KP 申请披露','text':'请 KP 说明本次问题中允许我获知的信息。'},
            {'id':'known_only','label':'仅整理已知资料','text':'只整理当前已经核验的本人已知资料。'}]}
    if output['next']=='ask_kp_change':
        choices={'prompt':'需要由 KP 评估并准备方案吗？','options':[
            {'id':'ask_kp_change','label':'提交创作／配置申请','text':'请 KP 评估这次创作或组合需求。'},
            {'id':'known_only','label':'继续查看已知资料','text':'继续整理本人已经获知的相关资料。'}]}
        if not selected:text='可以将这次创作或组合需求提交给 KP。接收申请后由 KP 准备方案，修改仍需另行审核。'
    return {'kind': 'plan', 'text': text, **({'choices': choices} if choices else {})}
