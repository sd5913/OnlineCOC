"""Balanced history units and conservative text-only tool pruning.

Algorithm reference: deepseek-ai/deepseek-harness @ 2e39e70496aa02986ca6a820c5d497e816b69d7e.
Our structured evidence and pending edit handles remain exact.
"""
import copy
from .contracts import canonical,loads
from .errors import AiError,require

PINNED_TOOLS={'pack_read_contract','pack_read_config_data','room_manage_catalog','room_read_compressed'}
PINNED_KEYS={'editRef','changeSet','dataEdits','preflight','errors','error','schema','parameters',
             'riskDecisions','consultationReview','cReview','approvalDigest'}
TEXT_KEYS={'text','content','description','notes','body','preview'}
PRUNE_MARKER='[context-pruned; exact originals via room_read_compressed: '


def history_units(rows):
    units=[]
    for row in rows:
        if row.get('role')=='user' or not units:units.append([])
        units[-1].append(row)
    return units


def tool_units(rows):
    units=[];n=0
    while n<len(rows):
        row=rows[n];calls=row.get('tool_calls',[])
        require(row.get('role')!='tool','COMPRESSION_PAIRING_INVALID')
        if not calls:
            units.append([row]);n+=1;continue
        pending={c['id'] for c in calls}
        require(len(pending)==len(calls),'COMPRESSION_PAIRING_INVALID')
        unit=[row];n+=1
        while n<len(rows) and rows[n].get('role')=='tool':
            result=rows[n]
            require(result.get('tool_call_id') in pending,'COMPRESSION_PAIRING_INVALID')
            pending.remove(result['tool_call_id']);unit.append(result);n+=1
        # An incomplete exchange must stay intact, never be summarized away.
        units.append(unit)
    return units


def pinned(unit):
    calls=unit[0].get('tool_calls',[])
    if not calls:return True  # Technical correction / closing-turn messages.
    if len(unit)-1!=len(calls):return True
    if any(c['function']['name'] in PINNED_TOOLS for c in calls):return True
    def protected(value):
        if isinstance(value,dict):return bool(set(value)&PINNED_KEYS) or any(protected(v) for v in value.values())
        if isinstance(value,list):return any(protected(v) for v in value)
        return False
    for row in unit[1:]:
        try:
            if protected(loads(row.get('content',''))):return True
        except AiError:pass
    return False


def split_tail(units,limit):
    """Keep a contiguous suffix of complete units, including at least the last."""
    size=0;cut=len(units)
    for n in range(len(units)-1,-1,-1):
        amount=len(canonical(units[n]))
        if cut<len(units) and size+amount>limit:break
        size+=amount;cut=n
    return units[:cut],units[cut:],size


def prune_result(row,archive):
    """Only long textual leaves; identifiers, numbers, JSON shape stay intact."""
    content=row.get('content')
    if not isinstance(content,str) or len(content)<=8192 or PRUNE_MARKER in content:return row
    def trim(text):
        if len(text)<=8192 or PRUNE_MARKER in text:return text
        refs=archive(text,'tool')
        marker='\n'+PRUNE_MARKER+','.join(refs)+']\n'
        value=text[:4096]+marker+text[-1024:]
        return value if len(value)<min(len(text),8192) else text
    def walk(value,key=None):
        if isinstance(value,str):return trim(value) if key in TEXT_KEYS else value
        if isinstance(value,dict):return {k:walk(v,k) for k,v in value.items()}
        if isinstance(value,list):return [walk(v,key) for v in value]
        return value
    try:
        value=loads(content)
        shortened=trim(value) if isinstance(value,str) else walk(value)
        output=canonical(shortened).decode()
    except AiError:output=trim(content)
    if len(output.encode())>=len(content.encode()):return row
    result=copy.deepcopy(row);result['content']=output;return result
