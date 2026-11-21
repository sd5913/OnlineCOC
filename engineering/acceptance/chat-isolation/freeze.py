"""Freeze the tested engine without reading concurrently edited AI sources."""
from pathlib import Path
import hashlib,json,shutil,sys
HERE=Path(__file__).resolve().parent
target=HERE.parent/'engine-chat-interface-snapshot'
version=sys.argv[1] if len(sys.argv)>1 else 'v1'
dest=target/version/'engineering'
assert not dest.exists(), 'Never overwrite a delivered interface'
shutil.copytree(HERE/'work'/'after'/'engineering',dest,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.pytest_cache'))
if version=='v1':(target/'.gitignore').write_text('v*/engineering/\n',encoding='utf-8')
hashes={p.relative_to(dest).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.rglob('*') if p.is_file()}
(target/version/'source.json').write_text(json.dumps({'engine':'ISSUE-022 '+version,'files':hashes},indent=2),encoding='utf-8')
print(json.dumps({'path':str(dest.parent),'files':len(hashes)}))
