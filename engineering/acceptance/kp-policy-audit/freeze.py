from pathlib import Path
import hashlib,json,shutil
HERE=Path(__file__).resolve().parent;target=HERE.parent/'engine-kp-policy-interface-snapshot';dest=target/'v1/engineering'
assert not dest.exists()
shutil.copytree(HERE/'work/engineering',dest,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.pytest_cache'))
(target/'.gitignore').write_text('v*/engineering/\n',encoding='utf-8')
files={p.relative_to(dest).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.rglob('*') if p.is_file()}
(target/'v1/source.json').write_text(json.dumps({'engine':'ISSUE-023 v1','aiContracts':'ai-compression-interface-snapshot/contracts-v1','files':files},indent=2),encoding='utf-8')
print(json.dumps({'path':str(dest.parent),'files':len(files)}))
