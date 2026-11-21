"""Recompute paired statistics from immutable reports and the sealed ledger."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORTS = {
    'baseline': 'baseline-1795256781623400600.json',
    'adapted-v1': 'adapted-1795256916717539800.json',
    'adapted-v2': 'adapted-1795257596167240900.json',
}


def load(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def metrics(calls):
    return {
        'calls': len(calls),
        'promptTokens': sum(c.get('usage', {}).get('prompt_tokens', 0) for c in calls),
        'completionTokens': sum(c.get('usage', {}).get('completion_tokens', 0) for c in calls),
        'chargedTokens': sum(c['chargedTokens'] for c in calls),
        'providerSeconds': round(sum(c['seconds'] for c in calls), 3),
        'unknownUsageCalls': sum('usage' not in c for c in calls),
    }


def main():
    ledger = load('live-ledger.json')
    assert ledger['status'] == 'sealed'
    attempts = {a['attemptId']: a for a in ledger['attempts']}
    results = {}; fixture_digests = set(); pack_digests = set(); used = []
    for name, filename in REPORTS.items():
        report = load(filename); phases = []; calls = []
        fixture_digests.add(report['syntheticHistory']['fixtureDigest'])
        pack_digests.add(hashlib.sha256(json.dumps(report['packHashes'], sort_keys=True).encode()).hexdigest())
        for row in report['rows']:
            ids = row['attemptIds']; selected = [attempts[i] for i in ids]
            calls.extend(selected); used.extend(ids)
            phase = {k: row[k] for k in ('phase', 'status', 'seconds', 'attemptIds')}
            phase['usage'] = metrics(selected)
            phase['compression'] = row['task']['diagnostics'].get('compression', [])
            if 'ruling' in row:
                phase['candidateConfigurations'] = [
                    {'kind': c['kind'], 'id': c['id'],
                     'hp': c.get('value', {}).get('defaults', {}).get('hp'),
                     'maxHp': c.get('value', {}).get('defaults', {}).get('maxHp')}
                    for c in row['ruling']['changeSet'].get('configurations', [])]
            if row['status'] != 'passed':
                phase['failure'] = {k: row.get(k) for k in ('code', 'reason')}
                phase['failure']['publishedInSyntheticRoomBeforeOracle'] = 'approval' in row
            phases.append(phase)
        summary = [c for c in calls if c['input']['messages'][0]['content'].startswith('Return JSON with exactly goals,')]
        business = [c for c in calls if c not in summary]
        passed = sum(p['status'] == 'passed' for p in phases)
        results[name] = {'report': filename, 'sourceTree': report['tree'],
                         'passed': passed, 'attempted': len(phases), 'planned': 3,
                         'successRate': passed / len(phases),
                         'phaseEndToEndSeconds': round(sum(p['seconds'] for p in phases), 3),
                         'allCalls': metrics(calls), 'summaryCalls': metrics(summary),
                         'businessCalls': metrics(business), 'phases': phases}
    assert len(fixture_digests) == 1 and len(pack_digests) == 1
    assert len(used) == len(set(used)) and set(used) == set(attempts)
    baseline = results['baseline']; adapted = results['adapted-v2']
    output = {
        'schemaVersion': 1, 'sealed': True,
        'fixtureDigest': next(iter(fixture_digests)),
        'packManifestDigest': next(iter(pack_digests)),
        'conditions': {'declaredWindowTokens': 131072, 'assistantPlanIsSeededFixture': True,
                       'seedExternalCalls': 0, 'syntheticRoomsOnly': True,
                       'sameThreeScenarios': ['accepted', 'replace', 'cancel'],
                       'repetitionsPerVersion': 1, 'productionProfileUnchanged': True},
        'versions': results, 'experimentTotal': metrics(list(attempts.values())),
        'retainedOutcomeTotals': {'passed': sum(v['passed'] for v in results.values()),
                                  'attempted': sum(v['attempted'] for v in results.values())},
        'comparison': {
            'totalTokensReductionFraction': 1 - adapted['allCalls']['chargedTokens'] / baseline['allCalls']['chargedTokens'],
            'summaryTokensReductionFraction': 1 - adapted['summaryCalls']['chargedTokens'] / baseline['summaryCalls']['chargedTokens'],
            'providerSecondsReductionFraction': 1 - adapted['allCalls']['providerSeconds'] / baseline['allCalls']['providerSeconds'],
            'phaseEndToEndSecondsReductionFraction': 1 - adapted['phaseEndToEndSeconds'] / baseline['phaseEndToEndSeconds'],
        },
        'limitations': [
            'One synthetic paired sequence per version, not a statistical reliability estimate.',
            'Paired adapted-v2 run required one summary repair; the failed first adapted implementation remains in the totals.',
            'No real upstream context overflow occurred; overflow recovery and tool pruning were deterministic tests.',
            'The first adapted report mislabels afterExtractionBytes as afterPruneBytes; do not infer pruning savings from it.',
            'Success is checked after explicit synthetic approval: the failed HP5 candidate was published only inside its isolated test room.',
            'Rolling checkpoints cover one generation task; later tasks reuse identical authorized summary groups, not an unlimited session checkpoint.',
        ],
        'evidenceHashes': {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                           for name in ['live-ledger.json', 'budget.json', 'live_pair.py', *REPORTS.values()]},
    }
    (HERE / 'comparison.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: output[k] for k in ('experimentTotal', 'retainedOutcomeTotals', 'comparison')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
