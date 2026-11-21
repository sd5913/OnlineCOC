"""Reproducible summary; never rewrites first-run evidence or previous-round files."""
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def read(name):return json.loads((HERE/name).read_text(encoding='utf-8'))
def write(name,value):(HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
ledger=read('live-ledger.json');budget=read('budget.json');original=read('natural-1795193315656682400.json')
replay=read('replay-1795194105655650000.json');focused=read('evidence-repair-1795194368156215900.json')
known=sum(a['chargedTokens'] for a in ledger['attempts'] if a['status']=='completed')
unknown=sum(a.get('chargedTokens',a['reservedTokens']) for a in ledger['attempts'] if a['status']!='completed')
assert len(ledger['attempts'])<=budget['externalAttemptLimit'] and known+unknown<=budget['totalTokenLimit']
tests={}
for file in HERE.glob('*.xml'):
    node=ET.parse(file).getroot();suites=[node] if node.tag=='testsuite' else list(node.iter('testsuite'))
    tests[file.name]={k:sum(int(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
    tests[file.name]['seconds']=round(sum(float(s.get('time',0)) for s in suites),3)
complete='core-v3-final.xml' in tests and tests['core-v3-final.xml']['failures']==tests['core-v3-final.xml']['errors']==0
cases=original['cases'];terminal=[c for c in cases if c.get('firstOutput')]
assert len(cases)==16 and len(terminal)==15 and len(replay['cases'])==9
assert all(c['status']=='passed' and c['actualExecution'] and c['fullEffectOracle'] for c in replay['cases'])
results={'status':'complete' if complete else 'waiting-core-regression','uniqueNaturalCases':16,'terminalAnswers':15,
    'firstRun':{'format':{'passed':15,'denominator':15},'semanticOriginalOracle':{'passed':13,'denominator':15},
        'semanticAfterIndependentOracleCorrection':{'passed':14,'denominator':15,'note':'Short-rest attribute is unused by the short branch; source and actual effects independently verified. Original result retained.'},
        'completedWholeCases':{'passed':sum(c['status']=='passed' for c in cases),'denominator':16},
        'actualMutation':{'passed':2,'denominator':9},'correctRefusals':{'passed':2,'denominator':2}},
    'replay':{'externalCalls':0,'actualMutation':{'passed':9,'denominator':9},'configurationCases':6,'runtimeCases':3,'preservesOriginalOutputs':True},
    'focusedFeedback':{'externalCalls':3,'factualRetrieval':'passed','exactAnswerOnlyInstruction':'failed-extra-source-prose',
        'fullProductionPrompt':False,'note':'Production Coordinator guard verified with controlled provider; real API probe uses reduced prompt and actual authorized read tools. Not counted as full-prompt E2E success.'},
    'uncovered':[{'caseId':'genuine-ambiguity','reason':'One external tool-call response; next request stopped by conservative full-request budget reservation before HTTP. No final answer, not counted as a successful clarification.'}],
    'budget':{'externalAttempts':len(ledger['attempts']),'knownTokens':known,'unknownReservedTokens':unknown,'accountedTokens':known+unknown,
        'tokenLimit':budget['totalTokenLimit'],'attemptLimit':budget['externalAttemptLimit'],'totalExternalSeconds':round(sum(a['seconds'] for a in ledger['attempts']),3)},'regressions':tests}
write('results.json',results)
ledger['status']='sealed';ledger['sealReason']='No additional external requests in this round; remaining work is offline verification.';write('live-ledger.json',ledger)
failures=[
 {'id':'fixture-knowledge','first':'Synthetic personal descriptor used fixture.* prefix; sv.character invisible.','resolution':'Explicit synthetic identity-only descriptor; not production knowledge-provider verification.','status':'fixed'},
 {'id':'fixture-dice','first':'d100 probe used default d20, RANDOM_COVERAGE_UNKNOWN.','resolution':'randomSides plus retained underlying execution error; actual supplemental coverage regression passed.','status':'fixed'},
 {'id':'engine-approval-schema','first':'Six configuration approvals rejected INPUT_INVALID; models.json duplicate Approval lacked new proof fields.','resolution':'Engine v3; six saved outputs published and effects verified. Original failures retained.','status':'fixed'},
 {'id':'short-rest-oracle','first':'Oracle rejected attribute=hp although the short branch ignores it.','resolution':'Original output unchanged; exact business effect verified in zero-API replay.','status':'oracle-corrected'},
 {'id':'unqueried-negative-answer','first':'KP room query returned a false absence without tools (attempt14).','resolution':'MODEL_EVIDENCE_REQUIRED, bounded repair, actual read probe. Full production prompt not re-run; extra source prose remains.','status':'partially-verified'},
 {'id':'closed-repository-callback','first':'Closing AI left a callback to closed storage; first lifecycle run also found the existing access callback still closed.','resolution':'C resolver and access callbacks reopen current persisted evidence; changed basis and locked store remain failures; 38 tests passed.','status':'fixed'},
 {'id':'negative-guard-overmatch','first':'Initial regex matched an explicit query-incomplete statement across punctuation.','resolution':'Clause-bounded expression plus regression. This is not a general hallucination detector.','status':'fixed'},
 {'id':'focused-driver-path','first':'Local test driver guessed a nonexistent .local.json profile filename; no HTTP.','resolution':'Uses existing ai-providers.json read-only.','status':'fixed'},
 {'id':'clarification-budget','first':'Case16 obtained one tool response then conservative reservation blocked next HTTP.','resolution':'Retained incomplete evidence; no hidden retry or budget increase.','status':'uncovered'},
 {'id':'strict-answer-format','first':'Focused repaired answer correctly retrieved secret but appended source prose.','resolution':'Recorded as factual retrieval pass and exact brevity instruction failure; no extra API retry.','status':'known-limitation'}]
write('failure-register.json',{'failures':failures})
freeze=json.loads((ROOT/'engineering/acceptance/ai-c-review-interface-snapshot/source-v2.json').read_text())
mismatches=[name for name,sha in freeze['files'].items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha]
docs=['ai-rulings.md','ai-session-access.md','ai-responses.md','ai-pack-embedding.md','ai-debug-review.md',
    'ai-runtime.md','ai-manager.md','ai-data-query.md','ai-player-knowledge.md',
    'developer-reference/stumpsville-interface.md','developer-reference/stumpsville-data-management.md']
broken=[]
for name in docs:
    p=ROOT/'docs/current/engineering'/name
    for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
        if '://' in target or target.startswith('#'):continue
        relative=target.split('#',1)[0]
        if relative and not (p.parent/relative).resolve().exists():broken.append({'file':name,'target':target})
write('document-check.json',{'frozenSourceMismatches':mismatches,'brokenRelativeFileLinks':broken,'documents':docs})
assert not mismatches and not broken
new=['engineering/ai/src/onlinecoc_ai/c_review.py','engineering/ai/src/onlinecoc_ai/room_defaults.py',
    'engineering/ai/tests/test_c_review_defaults.py','engineering/ai/tests/test_c_review_ui.py',
    'engineering/acceptance/ai-c-review-interface-snapshot/.gitignore','engineering/acceptance/ai-c-review-interface-snapshot/source.json',
    'engineering/acceptance/ai-c-review-interface-snapshot/source-v2.json','engineering/acceptance/ai-c-review-interface-snapshot/v1/',
    'engineering/acceptance/ai-c-review-interface-snapshot/v2/','engineering/acceptance/ai-defaults-c-review/work/']
new += [p.relative_to(ROOT).as_posix() for p in HERE.iterdir() if p.is_file() and p.name!='new-files.json']
new.append((HERE/'new-files.json').relative_to(ROOT).as_posix());write('new-files.json',{'files':sorted(set(new))})
print(json.dumps({'status':results['status'],'budget':results['budget'],'regressions':tests,'newFiles':len(new)},ensure_ascii=False))
