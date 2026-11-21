"""Keep every trial; count each deterministic case only at its latest result."""
import ast
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE=Path(__file__).parent
ROOT=HERE.parents[2]
ORDER=['first.xml','second.xml','third.xml','freeze.xml','boundaries.xml','boundaries-final.xml','receipt-visibility.xml','receipt-final.xml']
SOURCES=[
 'engineering/ai/src/onlinecoc_ai/'+name+'.py' for name in
 ('messages','api','sessions','coordinator','review_queue','batches','reviews')]
SOURCES += ['engineering/ai/web/components/'+name for name in
 ('chat.js','chat.css','markdown.css','reference-editor.js','reference-details.js','client.js','index.d.ts')]
SOURCES += ['engineering/ai/tests/'+name for name in ('test_message_history.py','test_message_history_ui.py','test_known_runtime.py')]
DOCS=['docs/current/engineering/'+name+'.md' for name in
 ('ai-session-access','ai-player-knowledge','ai-rulings','ai-responses','ai-pack-embedding','ai-debug-review')]


def main():
    latest={};rounds=[]
    names={}
    for file in HERE.glob('test_*.py'):
        for node in ast.parse(file.read_text(encoding='utf-8')).body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                names.setdefault(node.name,[]).append(file.stem)
    for filename in ORDER:
        cases=[]
        for node in ET.parse(HERE/filename).findall('.//testcase'):
            module=node.attrib['classname'].split('.')[-1]
            if not module:
                candidates=names.get(node.attrib['name'].split('[')[0],[])
                if len(candidates)!=1:raise ValueError('Ambiguous empty pytest classname')
                module=candidates[0]
            key=module+'::'+node.attrib['name']
            status='failed' if node.find('failure') is not None or node.find('error') is not None else 'skipped' if node.find('skipped') is not None else 'passed'
            item={'id':key,'status':status,'evidence':filename};cases.append(item);latest[key]=item
        rounds.append({'evidence':filename,'passed':sum(c['status']=='passed' for c in cases),'total':len(cases),
            'failures':[c['id'] for c in cases if c['status']=='failed']})
    live=json.loads((HERE/'live-results.json').read_text(encoding='utf-8'))
    result={'schemaVersion':1,'scope':'ISSUE-018 AI message history and explicit completion',
        'rounds':rounds,'uniqueLatest':{'passed':sum(x['status']=='passed' for x in latest.values()),'total':len(latest),'cases':list(latest.values())},
        'live':{k:live[k] for k in ('model','providerCalls','usageTokens','successes','total','sourceConfigUnchanged','latencyPassed')},
        'latency':{'samples':len(live['latency']),'maxSeconds':max(v['seconds'] for v in live['latency']),'boundary':'public ASGI HTTP during live provider wait'},
        'sourceHashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES+DOCS}}
    (HERE/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    files=['engineering/ai/src/onlinecoc_ai/messages.py','engineering/ai/tests/test_message_history.py','engineering/ai/tests/test_message_history_ui.py']
    files += [str(p.relative_to(ROOT)).replace('\\','/') for p in HERE.iterdir() if p.is_file() and p.name!='manifest.json']
    files.append(str((HERE/'manifest.json').relative_to(ROOT)).replace('\\','/'))
    (HERE/'manifest.json').write_text(json.dumps({'newFiles':sorted(files),'updatedSourceFiles':SOURCES,'updatedDocuments':DOCS},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':result['uniqueLatest']['passed'],'total':len(latest),'newFiles':len(files)},ensure_ascii=False))


if __name__=='__main__':main()
