"""Server-calculated publication risk, bound to the complete candidate digest."""
import copy


def configuration_allowed(contract, identifier):
    policy = contract.get('highRisk', {})
    return identifier in policy.get('configurationIds', []) or any(identifier.startswith(p) for p in policy.get('configurationPrefixes', []))


def describe(contract, state, baseline, changes, *, include_diff=True):
    tags, diff = set(), []
    for change in changes['configurations']:
        old = state['configurations'].get(change['id'])
        new = change['value']
        if change['kind'] == 'remove':tags.add('configuration-remove')
        if (new or old or {}).get('typeRef') in ('item', 'weapon', 'bag'):tags.add('item-configuration')
        if configuration_allowed(contract, change['id']):tags.add('pack-critical-configuration')
        if include_diff:diff.append({'target':'configuration', 'id':change['id'], 'kind':change['kind'], 'before':copy.deepcopy(old), 'after':copy.deepcopy(new)})
    for field, tag in (('sources', 'core-rules'), ('data', 'map-or-game-data')):
        for name in sorted(set(baseline[field]) | set(changes[field])):
            old, new = baseline[field].get(name), changes[field].get(name)
            if old != new:
                tags.add(tag)
                if include_diff:diff.append({'target':field, 'id':name, 'kind':'replace' if name in baseline[field] else 'add', 'before':copy.deepcopy(old), 'after':copy.deepcopy(new)})
    return {'highRisk':bool(tags), 'riskTags':sorted(tags), 'diff':diff}
