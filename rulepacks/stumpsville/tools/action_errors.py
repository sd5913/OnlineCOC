"""Explain verified pack preconditions without exposing host traces or hidden data."""
from copy import deepcopy
from client import HostError

MESSAGES = {
 'NOT_READY': ('角色尚未准备。', 'PL：进入准备页并点击准备；KP：在角色完成准备后再批准。'),
 'NOT_APPROVED': ('角色尚未通过审核或尚未分配。', 'PL：提交角色草稿；KP：到裁决队列审核角色。'),
 'NOT_STARTED': ('场次尚未开场。', 'KP：在控制台点击开场；PL：等待开场后重新提交。'),
 'CANNOT_REST': ('角色力量已降至 0，普通休息不能使其恢复。', 'PL：请求 KP 裁决角色后续状态；KP：核对死亡与恢复规则，不要重复执行休息。'),
 'INCAPACITATED': ('角色处于失能状态。', 'PL：请求照料或休息；KP：按规则处理恢复，并确认角色恢复行动能力。'),
 'ZERO_ATTRIBUTE': ('角色的{field}为 {value}，不能继续行动。', 'PL：申请 KP 处理角色恢复；KP：核对受伤及恢复规则，处理相应属性与失能状态。'),
 'ROOM_PAUSED': ('房间已暂停或归档。', 'KP：在控制台恢复房间；PL：等待恢复后再提交。'),
 'EMPTY_SLOT': ('槽位 {slot} 没有可操作的物品。', 'PL：刷新背包并选择实际放有物品的槽位；KP：核对申请中的物品是否已移走。'),
 'SLOT_OCCUPIED': ('槽位 {slot} 已被另一件物品占用。', 'PL：先移动占用物品或选择空位；KP：整理目标角色背包后重新批准。'),
 'TARGET_SLOT': ('目标槽位无效或与原槽位相同。', '选择 1—20 中的其他有效槽位后重新提交。'),
 'TWO_SLOTS': ('两格物品不能从槽位 {slot} 开始放置。', '使用 1、3、5、6、8、9 作为起始格，并空出相邻格；或放入 11—20 的超载区。'),
 'FOUR_SLOTS': ('四格物品不能从槽位 {slot} 开始放置。', '使用 5 或 6 作为起始格，并空出对应 2×2 区域；或使用超载区。'),
 'ARMOR_SLOTS': ('轻甲在装备区必须从槽位 2 开始，占用槽位 2 和 3。', '空出副手及身体对应格，或改放背包的合法两格位置。'),
 'ITEM_EXHAUSTED': ('槽位 {slot} 的物品用量已耗尽。', 'PL：更换仍有用量的物品；KP：只有规则允许补充后，才调整物品用量。'),
 'MANUAL_ITEM': ('该物品、状态或法术不能按普通消耗品自动使用。', 'PL：提交自由行动申请说明用途；KP：按状态或法术规则裁决。'),
 'NOT_LIGHT': ('槽位 {slot} 的物品不是可点燃的光源。', '选择火把等光源；若用量为 0，先更换光源。'),
 'NOT_LIT': ('槽位 {slot} 的光源当前没有点燃。', '刷新背包，选择当前点燃的光源再执行熄灭。'),
 'SCENE_LOCATION': ('角色已不在该预设行动所属地点。', 'PL：刷新场景并选择当前位置的行动；KP：退回过期申请或让角色回到原地点。'),
 'DOOR_CLOSED': ('当前通路尚未开启。', 'PL：尝试场景中的开门行动或申请裁决；KP：核对门状态与通行条件，开放后再移动。'),
 'LOCATION_UNAVAILABLE': ('目标地点当前不可通行。', 'PL：请求 KP 说明可走的路线；KP：核对目标地点发布状态与通路，不要重复提交同一失败命令。'),
 'NOT_ADJACENT': ('目标地点与角色当前位置不相邻。', '先移动到相邻地点；特殊移动请申请 KP 裁决。'),
 'INVALID_INPUT': ('行动参数与当前规则不符。', '刷新页面重新选择；若仍失败，将行动编号交给 KP 核对当前规则。'),
 'RULE_FAILED': ('宿主拒绝了本次规则执行，未返回可识别的具体条件。', 'KP：按行动编号核对角色状态、参数及当前规则；修正后重新提交。请勿把此结果当作成功结算。'),
 'VERSION_CONFLICT': ('相关对象或规则已被其他操作修改。', '刷新并核对最新状态后重新提交；KP：检查是否有其他裁决同时修改了目标。'),
 'NOT_VISIBLE': ('所需对象已不可见或当前账号无权操作。', 'PL：请求 KP 核对授权；KP：检查角色归属、资料授权和对象是否仍有效。'),
 'PERMISSION_DENIED': ('当前账号没有执行此操作的权限。', 'PL：将请求提交 KP；KP：使用管理视窗并核对当前账号身份。'),
 'UNKNOWN': ('宿主未能完成该操作。', '保留行动编号并交给 KP 核查回执与运行日志；原因尚未确认。'),
}


def failure(code, **params):
    reason, next_step = MESSAGES.get(code, MESSAGES['UNKNOWN'])
    return {'code': code, 'reason': reason.format(**params), 'nextStep': next_step, 'params': params}


def blocked(code, **params):
    item = failure(code, **params)
    raise HostError({'code': 'ACTION_BLOCKED', 'status': 'rejected', 'failure': item})


def layout(numbers, items):
    occupied = set()
    for slot in range(1, 21):
        index = numbers.get('item'+str(slot), 0)
        if not index:
            continue
        item = items[index-1] if type(index) is int and 1 <= index <= len(items) else None
        if not item:
            blocked('INVALID_INPUT')
        cells = [slot]
        if slot <= 10 and item['slots'] == 2:
            if item.get('shape') == 'offhand-body' and slot <= 4:
                if slot != 2: blocked('ARMOR_SLOTS')
                cells = [2, 3]
            else:
                if slot not in {1, 3, 5, 6, 8, 9}: blocked('TWO_SLOTS', slot=slot)
                cells = [slot, slot+1]
        elif slot <= 10 and item['slots'] == 4:
            if slot not in {5, 6}: blocked('FOUR_SLOTS', slot=slot)
            cells = [slot, slot+1, slot+3, slot+4]
        for cell in cells:
            if cell in occupied: blocked('SLOT_OCCUPIED', slot=cell)
            occupied.add(cell)


def check(rule, args, view, game, session=None):
    """Called before new host envelopes, never instead of receipt recovery."""
    actor = view['entities'].get(args.get('actor'))
    if not actor: return  # The host handles missing / inaccessible objects.
    n = deepcopy(actor['numbers'])
    if rule == 'sv.adjudicate': rule = 'sv.'+args.get('kind', '')
    if rule == 'sv.rest' and n.get('str', 0) <= 0: blocked('CANNOT_REST')
    if rule in {'sv.check', 'sv.scene.resolve', 'sv.travel.auto', 'sv.ready'}:
        if n.get('approved') != 1: blocked('NOT_APPROVED')
    if rule in {'sv.check', 'sv.scene.resolve', 'sv.travel.auto'}:
        if n.get('ready') != 1: blocked('NOT_READY')
        if n.get('incapacitated'): blocked('INCAPACITATED')
        for key, name in [('str','力量'),('dex','敏捷'),('wil','意志')]:
            if n.get(key, 0) <= 0: blocked('ZERO_ATTRIBUTE', field=name, value=n.get(key, 0))
        if session and session['numbers'].get('phase') != 1: blocked('NOT_STARTED')
    if rule in {'sv.inventory', 'sv.remove', 'sv.transfer', 'sv.grant'}:
        slot = args.get('slot')
        if type(slot) is not int or slot not in range(1, 21): blocked('TARGET_SLOT')
        item = next((item for index,item in enumerate(game['items'],1) if index == n.get('item'+str(slot))), None)
        if rule != 'sv.grant' and not item: blocked('EMPTY_SLOT', slot=slot)
        if rule == 'sv.inventory':
            operation = args.get('operation')
            if operation == 'move':
                dest = args.get('value')
                if type(dest) is not int or dest not in range(1, 21) or dest == slot: blocked('TARGET_SLOT')
                if n.get('item'+str(dest)): blocked('SLOT_OCCUPIED', slot=dest)
                n['item'+str(dest)], n['item'+str(slot)] = n['item'+str(slot)], 0
            elif operation == 'use':
                if item['uses'] <= 0 or item['kind'] in {'condition','spell'}: blocked('MANUAL_ITEM')
                if n.get('uses'+str(slot), 0) <= 0: blocked('ITEM_EXHAUSTED', slot=slot)
            elif operation == 'light':
                if not item.get('light'): blocked('NOT_LIGHT', slot=slot)
                if n.get('uses'+str(slot), 0) <= 0: blocked('ITEM_EXHAUSTED', slot=slot)
            elif operation == 'extinguish':
                if n.get('litSlot') != slot: blocked('NOT_LIT', slot=slot)
            else: blocked('INVALID_INPUT')
        elif rule == 'sv.grant':
            if n.get('item'+str(slot)): blocked('SLOT_OCCUPIED', slot=slot)
            n['item'+str(slot)] = args.get('item')
        elif rule == 'sv.transfer':
            target = view['entities'].get(args.get('target'))
            if not target: return
            dest = args.get('destination')
            if type(dest) is not int or dest not in range(1, 21): blocked('TARGET_SLOT')
            other = deepcopy(target['numbers'])
            if other.get('item'+str(dest)): blocked('SLOT_OCCUPIED', slot=dest)
            other['item'+str(dest)] = n['item'+str(slot)]
            layout(other, game['items'])
            n['item'+str(slot)] = 0
        else: n['item'+str(slot)] = 0
        layout(n, game['items'])
    elif rule in {'sv.check','sv.scene.resolve'}:
        layout(n, game['items'])
    if rule == 'sv.travel.auto':
        destination = view['entities'].get(args.get('destination'))
        # Strict PL projections intentionally omit destination entities. Do not
        # consult hidden package state to explain why an unseen door is closed.
        if destination:
            if destination['visibility'] != 'public': blocked('LOCATION_UNAVAILABLE')
            start, end = n['location'], destination['numbers']['index']
            place = next((p for p in game['locations'] if p['index']==start), {})
            if end not in place.get('exits', []): blocked('NOT_ADJACENT')
            if session and session['numbers'].get('door'+str(min(start,end))+'_'+str(max(start,end))) != 1:
                blocked('DOOR_CLOSED')
