from pathlib import Path
import hashlib,json,shutil,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
label=sys.argv[1];dest=HERE/'work'/label/'engineering'
base=ROOT/'engineering/acceptance/engine-accounts-interface-snapshot/v3/engineering'
shutil.copytree(base,dest,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.test-output'))
ai=ROOT/'engineering/acceptance/ai-c-review-interface-snapshot/v2/engineering'
shutil.copytree(ai,dest,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
hashes={}
for folder in ('backend/src','backend/scripts','backend/tests','contracts','data-management','client-sdk','test-console','rulepacks'):
 for p in (ROOT/'engineering'/folder).rglob('*'):
  if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc':continue
  target=dest/p.relative_to(ROOT/'engineering');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
  hashes[str(p.relative_to(ROOT)).replace('\\','/')]=hashlib.sha256(p.read_bytes()).hexdigest()
(HERE/(label+'-source.json')).write_text(json.dumps(hashes,indent=2),encoding='utf-8')
print(json.dumps({'label':label,'files':len(hashes)}))
