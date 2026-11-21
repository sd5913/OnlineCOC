from pathlib import Path
import shutil,hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];dest=HERE/'work/engineering'
for source in ('engine-chat-interface-snapshot','ai-chat-interface-snapshot'):
 shutil.copytree(HERE.parent/source/'v2/engineering',dest,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
hashes={}
for folder in ('backend/src','backend/tests','data-management'):
 for p in (ROOT/'engineering'/folder).rglob('*'):
  if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc':continue
  target=dest/p.relative_to(ROOT/'engineering');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
  hashes[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
for name in ('models.json','operations.json'):
 p=ROOT/'engineering/contracts'/name;shutil.copyfile(p,dest/'contracts'/name)
 hashes[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
frozen=HERE.parent/'ai-compression-interface-snapshot/contracts-v1'
for name in ('ai.json','ai-operations.json'):
 p=frozen/name;shutil.copyfile(p,dest/'contracts'/name)
 hashes[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
shutil.copyfile(frozen/'consultation.py',dest/'ai/src/onlinecoc_ai/consultation.py')
(HERE/'source.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
shutil.copyfile(HERE/'test_kp_policy.py',dest/'backend/tests/test_kp_policy.py')
print(json.dumps({'files':len(hashes),'root':str(dest)}))
