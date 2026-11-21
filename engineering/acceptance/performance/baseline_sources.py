"""Reconstruct the measured baseline in an ignored mirror; verify every old hash.

This never rewrites current source and never reads a production room. It allows
additional dataset sizes after implementation while preserving baseline identity.
"""
import hashlib
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent;ENGINEERING=HERE.parents[1]
TARGET=HERE/'baseline-source-tmp'
expected=json.loads((HERE/'baseline.json').read_text(encoding='utf-8'))['sha256']
for relative in ('backend/src','data-management','contracts','rulepacks','client-sdk'):
    shutil.copytree(ENGINEERING/relative,TARGET/relative,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
(TARGET/'test-console').mkdir(exist_ok=True)

path=TARGET/'backend/src/onlinecoc/contracts.py';source=path.read_text(encoding='utf-8')
for line in ('import copy\n','import threading\n','from collections import OrderedDict\n','from onlinecoc_data import canonical\n'):
    source=source.replace(line,'')
start=source.index('_MODEL_VALIDATORS=');end=source.index('def validate_operation',start)
source=source[:start]+'''def validate_model(kind,value):
    error = next(Draft202012Validator(MODELS[kind]).iter_errors(value), None)
    if error is not None:
        path = list(error.absolute_path)
        if error.validator == 'required' and isinstance(error.instance, dict):
            path.append(next(k for k in error.validator_value if k not in error.instance))
        pointer = '/' + '/'.join(str(k).replace('~','~0').replace('/','~1') for k in path)
        raise DomainError('INPUT_INVALID', {'model': kind, 'path': pointer[:512], 'constraint': error.validator})
'''+source[end:]
path.write_text(source,encoding='utf-8')

path=TARGET/'backend/src/onlinecoc/host.py';source=path.read_text(encoding='utf-8')
source=source.replace('def catalog(self,account,*,state=None):','def catalog(self,account):')
source=source.replace("s=self.state() if state is None else state;m=member(s,account);a=s['artifacts'][s['activeRuleset']]", "s=self.state();m=member(s,account);a=s['artifacts'][s['activeRuleset']]")
source=source.replace('self.catalog(account,state=s)','self.catalog(account)')
start=source.index("                check('command',message);payload=");end=source.index('            if needs_prepare:prepared=resolver',start)
source=source[:start]+'''                check('command',message);pre=self.state();member(pre,account)
                payload=message['payload'];prior=pre['commands'].get(account+':'+payload['commandId'])
                needs_prepare=not prior and payload['op']=='ai.proposal.approve'
                if needs_prepare:
                    require(member(pre,account)['role']=='kp','PERMISSION_DENIED')
                    validate_operation(payload['op'],payload['args'])
                    resolver=self.ai_prepared_resolver
                    require(resolver is not None,'AI_SERVICE_UNAVAILABLE')
'''+source[end:]
source=source.replace("                        rec['status']='committed';rec['receipt']=", "                        validate(s);rec['status']='committed';rec['receipt']=")
source=source.replace("for f in list(s['flows']):self.advance(f)","for f in list(self.state()['flows']):self.advance(f)")
path.write_text(source,encoding='utf-8')

path=TARGET/'data-management/onlinecoc_data/store.py';source=path.read_text(encoding='utf-8')
start=source.index('    def _disk_bytes(self):');end=source.index('    def compress_history(',start)
source=source[:start]+'''    def _disk_bytes(self):
        return (sum(path.stat().st_size for _, paths in self._generation_files() for path in paths.values())
                + sum(path.stat().st_size for path in self.staging.glob('*.tmp')))

'''+source[end:]
start=source.index('            env = {"format":self.FORMAT');end=source.index('            used = self._disk_bytes()',start)
source=source[:start]+'''            env = {"format":self.FORMAT,"generation":self.generation+1,"parent":self.head,
                   "digest":digest(data),"length":len(data),"payload":value}
            raw = canonical(env)
'''+source[end:]
path.write_text(source,encoding='utf-8')

path=TARGET/'backend/src/onlinecoc/server.py';source=path.read_text(encoding='utf-8')
source=source.replace('await ws.accept();last=None;last_generation=None;can_skip=False\n        loop=asyncio.get_running_loop()', 'await ws.accept();last=None')
start=source.index('                def capture():');end=source.index('                    if len(raw)>',start)
source=source[:start]+'''                def capture():
                    with host.lock:
                        host.auth(ws.cookies.get('onlinecoc',''));return host.project(account)
                projection=await asyncio.to_thread(capture)
                raw=canonical(projection);fingerprint=hashlib.sha256(raw).hexdigest()
                if fingerprint!=last:
'''+source[end:]
start=source.index('                    def finish():');end=source.index('                    if not valid:',start)
source=source[:start]+'''                    with host.lock:
                        host.auth(ws.cookies.get('onlinecoc',''))
                        current=hashlib.sha256(canonical(host.project(account))).hexdigest()
                        valid=current==fingerprint
                        outgoing=asyncio.create_task(ws.send_json({'type':'snapshot.end','id':snapshot} if valid else {'type':'reset'}))
                    await asyncio.wait_for(outgoing,2)
'''+source[end:]
start=source.index('                if projection is not None:');end=source.index('                try:\n                    message=',start)
source=source[:start]+source[end:];path.write_text(source,encoding='utf-8')

for name,sha in expected.items():
    path=TARGET/Path(name).relative_to('engineering')
    text=path.read_text(encoding='utf-8');matched=False
    for raw in (text.encode('utf-8'),text.replace('\n','\r\n').encode('utf-8')):
        if hashlib.sha256(raw).hexdigest()==sha:path.write_bytes(raw);matched=True;break
    if not matched:raise RuntimeError('Baseline SHA mismatch: '+name)
print('Verified original baseline SHA-256 for all '+str(len(expected))+' measured source files')
