"""Audit retained synthetic experiments without model calls or business mutations."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def latest(directory):
    paths = sorted(Path(directory).glob('generations/*.json*'))
    assert paths, directory
    path = paths[-1]
    raw = gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()
    envelope = json.loads(raw)
    return envelope['payload'], {'file': str(path.relative_to(ROOT)),
                                 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    ledger = read(HERE / 'live-ledger.json')
    attempts = ledger['attempts']
    assert len({a['attemptId'] for a in attempts}) == len(attempts)
    assert all(a['status'] == 'completed' and a['chargedTokens'] == a['usage']['total_tokens'] for a in attempts)
    summary_calls = [a for a in attempts if a['input']['messages'][0]['content'].startswith('Return JSON with exactly goals')]
    reports = {}
    tasks = []
    for path in sorted(HERE.glob('*.json')):
        value = read(path)
        if 'rows' not in value or 'group' not in value:
            continue
        reports[path.name] = value
        for row in value['rows']:
            if row.get('task'):
                tasks.append((path.name, value['group'], row))

    original = reports['compression-1795247144510978100.json']
    completed = reports['compression-1795247911156773000.json']
    room, room_proof = latest(Path(original['work']) / 'host/rooms/demo')
    ai, ai_proof = latest(Path(original['work']) / 'host/ai')
    template = room['configurations']['sv.ext.npc.compressed']
    base = room['configurations']['sv.npc']
    assert len(base['defaults']) == 12
    expected = dict(base['defaults'], hp=4, maxHp=4, isNpc=1)
    assert template['defaults'] == expected
    spawned = [x for x in room['entities'].values() if x['configurationId'] == 'sv.ext.npc.compressed']
    assert len(spawned) == 1 and spawned[0]['name'] == '验收小兵'
    assert spawned[0]['numbers']['hp'] == spawned[0]['numbers']['maxHp'] == 4
    completed_row = next(r for r in completed['rows'] if r['phase'] == 'spawn')
    assert completed_row['actualExecution'] and completed_row['idempotent']
    spawn_task = ai['tasks'][completed_row['task']['taskId']]
    assert spawn_task['diagnostics']['compression']
    assert len(ai['proposals']) == 1, 'Duplicate definition proposed'
    assert original['rows'][1]['approval']['status'] == 'committed'
    compression_review = {
        'status': 'passed', 'definitionPublications': 1, 'instances': 1,
        'assistantSuggestedHp': 3, 'userCorrection': '+1', 'actualHp': 4,
        'definitionExact': True, 'instanceIdempotent': True,
        'diagnostics': spawn_task['diagnostics']['compression'],
        'proofs': [room_proof, ai_proof],
        'harnessCorrections': ['definition oracle omitted mandatory isNpc=1',
                               'task terminal status was visible before diagnostics finally persisted'],
    }

    pl = reports['pl-1795248201266683700.json']
    row = pl['rows'][0]
    calls = [a for a in attempts if a['attemptId'] in row['attemptIds']]
    assert len(calls) == 1
    assert all('松鼠桥' not in str(a['input']) and '松鼠桥' not in str(a.get('output')) for a in calls)
    context = json.loads(calls[0]['input']['messages'][1]['content'])
    assert context['sessionAccess'] == {'boundPlayer': 'player1', 'level': 'player'}
    assert context['dataAccess']['mode'] == 'strict-known'
    assert row['task']['status'] == 'needs_input'
    assert not row['task'].get('proposalId') and not row['task'].get('batchId')
    pl_room, pl_room_proof = latest(Path(pl['work']) / 'host/rooms/demo')
    assert pl_room['entities']['actor-one']['name'] == '阿栗'
    pl_review = {'status': 'passed', 'strictKnown': True, 'secretAbsentFromInputAndOutput': True,
                 'noCandidate': True, 'nameUnchanged': True, 'proof': pl_room_proof,
                 'harnessCorrection': 'needs_input is a valid player clarification, not a generation failure'}

    # Manual language assessment: factual counts, source claims, feasible alternatives,
    # and truthful execution status. These are NOT rewritten from harness pass flags.
    language_failures = {
        ('compression-1795247144510978100.json', 'assistant-plan'): 'Claims 13 base default fields; actual sv.npc has 12.',
        ('compression-1795247144510978100.json', 'compressed-npc'): 'Claims 11 base default fields; actual sv.npc has 12. Exact candidate is correct.',
        ('compression-1795247324248927700.json', 'spawn'): 'Compression provenance failure; request did not reach a usable answer.',
        ('compression-1795247490062917900.json', 'spawn'): 'Compression quote/provenance failure; request did not reach a usable answer.',
        ('consultation-1795248177952401900.json', 'independent-source'): 'Did not read explicitly required independent map source, but implies it did; also changed exact description punctuation.',
        ('items-1795248206108486700.json', 'delete'): 'Offers an unsupported high-risk exception to an append-only A/B restriction.',
        ('npc-1795248289799830800.json', 'add'): 'Correct candidate, but offers to remove the mandatory isNpc marker if asked.',
        ('map-1795248371462053900.json', 'add'): 'Invalid test input index=99 is blocked; text still says it has been appended.',
        ('map-1795248575201243400.json', 'delete'): 'Stable-array removal blocked; text still presents it as awaiting KP approval.',
    }
    quality = [{'report': name, 'group': group, 'phase': row['phase'],
                'passed': (name, row['phase']) not in language_failures,
                'failure': language_failures.get((name, row['phase'])),
                'attemptIds': row['attemptIds']}
               for name, group, row in tasks]
    assert len(quality) == 18 and sum(q['passed'] for q in quality) == 9

    supported = [(name, group, row) for name, group, row in tasks
                 if group in ('items', 'npc', 'map', 'consultation')
                 and not (group in ('items', 'map') and row['phase'] == 'delete')
                 and name != 'map-1795248371462053900.json']
    assert len(supported) == 9
    assert sum(row['status'] == 'passed' for _, _, row in supported) == 8
    assert all(row['actualExecution'] and row['idempotent']
               for _, _, row in supported if row['status'] == 'passed')
    negative_keys = [('items-1795248206108486700.json', 'delete'),
                     ('map-1795248371462053900.json', 'add'),
                     ('map-1795248575201243400.json', 'delete'),
                     ('pl-1795248201266683700.json', 'hidden')]
    negatives = []
    for name, phase in negative_keys:
        r = next(r for r in reports[name]['rows'] if r['phase'] == phase)
        # All these failures occurred after the harness asserted unchanged business.
        assert r['reason'] in ('blocked', 'needs_input') and not r.get('actualExecution')
        negatives.append({'report': name, 'phase': phase, 'status': r['task']['status'],
                          'noBusinessMutation': True, 'clearCorrectFeedback': name.startswith('pl-')})

    xml = HERE / 'release-core.xml'
    core = None
    if xml.exists():
        suite = next(ET.parse(xml).getroot().iter('testsuite'))
        core = {k: int(suite.attrib[k]) for k in ('tests', 'failures', 'errors', 'skipped')}
        core['seconds'] = float(suite.attrib['time'])
        core['passed'] = core['tests'] - core['failures'] - core['errors'] - core['skipped']
    result = {
        'scope': 'ISSUE-023 synthetic rooms with actual Stumpsville pack; prior round excluded',
        'api': {'attempts': len(attempts), 'completedResponses': len(attempts),
                'tokens': sum(a['chargedTokens'] for a in attempts), 'unknownUsage': 0,
                'summaryCalls': len(summary_calls),
                'summaryRepairCalls': sum(len(a['input']['messages']) == 3 for a in summary_calls)},
        'supportedCrud': {'distinctOperations': 8, 'eventuallyExecutedExactly': 8,
                          'requestAttempts': 9, 'successfulAttempts': 8,
                          'firstAttemptOperationsPassed': 7,
                          'successfulTasksWithAutomaticTechnicalRepair': 2,
                          'automaticTechnicalRepairs': 3,
                          'excluded': 'compression workflow, physical item/map deletion, invalid map index=99'},
        'negativeBoundaries': {'cases': 4, 'noBusinessMutation': 4, 'clearCorrectFeedback': 1,
                               'casesDetail': negatives},
        'compressionWorkflow': {'businessRequests': 4, 'successfulBusinessRequests': 2,
                                'finalWorkflowPassed': True, 'planRequests': 1, 'review': compression_review},
        'overallRequestQuality': {'requests': 18, 'passed': 9, 'failed': 9,
                                 'definition': 'Usable outcome/refusal plus materially accurate text; all attempts retained, automatic repairs allowed. Exact execution and language quality are separate.',
                                 'rows': quality},
        'fullCore': core,
        'providerDefaults': read(HERE / 'provider-defaults-review.json'),
    }
    offline = {'compression': compression_review, 'playerBoundary': pl_review}
    return result, offline


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    result, offline = main()
    if args.write:
        for name, value in [('results-summary.json', result), ('offline-review.json', offline)]:
            (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('api', 'supportedCrud', 'fullCore')}, ensure_ascii=False))
