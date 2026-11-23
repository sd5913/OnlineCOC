import hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
name=sys.argv[1];target=OUT/'work'/name/'engineering'
assert not target.exists()
ignore=shutil.ignore_patterns('__pycache__','*.pyc','.pytest_cache','.test-output','*-tmp')
shutil.copytree(ROOT/'engineering/acceptance/engine-performance-interface-snapshot/v2/engineering',target,ignore=ignore)
for part in ('backend','data-management'):
    shutil.copytree(ROOT/'engineering'/part,target/part,dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__','*.pyc','.pytest_cache','.test-output','*-tmp','engineering','work','tmp'))
shutil.copytree(ROOT/'engineering/acceptance/ai-performance-interface-snapshot/v3/engineering/ai',target/'ai',dirs_exist_ok=True,ignore=ignore)
for name in ('messages','models','operations','knowledge','host-control','notifications','atomic-batches','ai-operations'):
    shutil.copy2(ROOT/'engineering/contracts'/(name+'.json'),target/'contracts'/(name+'.json'))
shutil.copy2(ROOT/'engineering/acceptance/ai-performance-interface-snapshot/v3/engineering/contracts/ai.json',target/'contracts/ai.json')
files={'engineering/'+p.relative_to(target).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in target.rglob('*') if p.is_file()}
(target.parents[2]/(target.parent.name+'-source.json')).write_text(json.dumps({'files':files,'aiDependency':'ai-performance-interface-snapshot/v3'},indent=2),encoding='utf-8')
print(target)
