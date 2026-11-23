"""Recompute acceptance counts, source hashes and measured comparisons."""
import hashlib,json,xml.etree.ElementTree as ET
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def write(name,value):(HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def read(name):return json.loads((HERE/name).read_text(encoding='utf-8'))
rounds=[]
for path in sorted(HERE.glob('*.xml')):
    suites=list(ET.parse(path).getroot().iter('testsuite'))
    counts={key:sum(int(s.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')}
    counts['passed']=counts['tests']-counts['failures']-counts['errors']-counts['skipped']
    rounds.append({'file':path.name,**counts,'passRate':counts['passed']/counts['tests'] if counts['tests'] else None,
        'failuresDetail':[{'name':t.get('classname','')+'::'+t.get('name',''),'message':f.get('message','')}
            for t in ET.parse(path).getroot().iter('testcase') for f in list(t) if f.tag in ('failure','error')]})
frozen=ROOT/'engineering/acceptance/ai-performance-interface-snapshot/v3'
manifest=json.loads((frozen/'source.json').read_text())
mismatches=[name for name,sha in manifest['files'].items() if hashlib.sha256((frozen/name).read_bytes()).hexdigest()!=sha]
current_mismatches=[name for name,sha in manifest['files'].items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha]
verification={'rounds':rounds,'frozenVersion':'v3','sourceManifestSha256':hashlib.sha256((frozen/'source.json').read_bytes()).hexdigest(),
    'frozenFiles':len(manifest['files']),'frozenHashMismatches':mismatches,'currentSourceMismatches':current_mismatches,'realModelCalls':0,
    'largeHistory':[{ 'file':p.name,**{key:read(p.name)[key] for key in ('status','count','stateBytes')},'passedScenarios':sum(c['status']=='passed' for c in read(p.name)['checks'])}
        for p in sorted(HERE.glob('*.json')) if p.name in ('large-history.json','delivery-large-history.json','delivery-cold-v2.json','delivery-cold-v3.json')]}
verification['finalCore']=next((row for row in rounds if row['file']=='release-v3-recovered.xml'),None)
write('verification.json',verification)
baseline=read('baseline-benchmark.json');latest=read('v2-benchmark.json');comparison={'baseline':'baseline-benchmark.json','adapted':'v2-benchmark.json',
    'note':'v2 direct Python benchmark; final v3 delivery write-set comparison separately recorded. Same fixture design; one initial and 30 subsequent calls; not HTTP/UI/model latency.','scales':[]}
for old,new in zip(baseline['scales'],latest['scales']):
    row={'count':new['count'],'baselineStatus':old['status'],'adaptedStatus':new['status'],'stateBytes':new.get('stateBytes')}
    for op in ('list','detail','verify','transaction3Updates'):
        row[op]={'adaptedP50Ms':new[op]['p50Ms'],'adaptedP95Ms':new[op]['p95Ms'],'adaptedFirstMs':new[op]['coldMs']}
        if op in old:row[op].update(baselineP50Ms=old[op]['p50Ms'],baselineP95Ms=old[op]['p95Ms'],p95ReductionPct=round(100*(1-new[op]['p95Ms']/old[op]['p95Ms']),2))
    comparison['scales'].append(row)
if (HERE/'delivery-cold-v3.json').exists():
    before=read('delivery-cold-v2.json');after=read('delivery-cold-v3.json')
    comparison['deliveryCold']={name:{'before':{key:before[name][key] for key in ('coldMs','p50Ms','p95Ms')},
        'after':{key:after[name][key] for key in ('coldMs','p50Ms','p95Ms')},
        'firstCallReductionPct':100*(1-after[name]['coldMs']/before[name]['coldMs'])} for name in ('deliveredList','archivedList')}
write('comparison.json',comparison)
assert not mismatches and not current_mismatches
print(json.dumps({'rounds':len(rounds),'frozenFiles':len(manifest['files']),'hashesMatch':True,'largeHistoryRuns':len(verification['largeHistory'])}))
