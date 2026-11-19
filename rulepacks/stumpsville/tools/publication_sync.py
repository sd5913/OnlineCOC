"""Three-way package projection of an already committed host artifact."""
import copy


class SyncConflict(ValueError):
    pass


def validate_game(previous, candidate):
    for key, identity in [('items', 'id'), ('locations', 'index')]:
        old, new = previous[key], candidate[key]
        ids = [v[identity] for v in new]
        if len(ids) != len(set(ids)) or ids[:len(old)] != [v[identity] for v in old]:
            raise SyncConflict(key + ' 的既有编号必须保留，只能追加新编号')
    indices = {v['index'] for v in candidate['locations']}
    if indices != set(range(1, len(indices) + 1)):
        raise SyncConflict('地点编号必须连续，现有规则按编号查表')
    for place in candidate['locations']:
        if any(v not in indices or v == place['index'] for v in place['exits']):
            raise SyncConflict('地点出口必须指向存在的其他地点')
        if any(not 1 <= v['item'] <= len(candidate['items']) for v in place['stock']):
            raise SyncConflict('地点库存指向不存在的物品')


def merge_value(old, local, approved, path):
    if approved == old:
        return copy.deepcopy(local)
    if local == old or local == approved:
        return copy.deepcopy(approved)
    raise SyncConflict('发布已提交，包侧待同步：' + path + ' 与本地编辑冲突')


def projection(state, previous, candidate):
    validate_game(previous, candidate)
    places = copy.deepcopy(state['locations'])
    baseline = {str(v['index']): v for v in previous['locations']}
    for place in candidate['locations']:
        key = str(place['index'])
        if key not in baseline:
            if key in places and places[key] != place:
                raise SyncConflict('新地点编号已被包侧使用：' + key)
            places[key] = copy.deepcopy(place)
            continue
        local = places[key]
        for field, value in place.items():
            local[field] = merge_value(baseline[key].get(field), local.get(field), value, key + '/' + field)
    edges = {'-'.join(map(str, sorted((p['index'], end)))) for p in candidate['locations'] for end in p['exits']}
    doors = {edge: state['doors'].get(edge, 'closed') for edge in sorted(edges)}
    encounters = merge_value(previous['encounters'], state['encounters'], candidate['encounters'], 'encounters')
    return {'locations': places, 'doors': doors, 'encounters': encounters}
