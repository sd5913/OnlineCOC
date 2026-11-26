"""Copy only audited engine inputs into a disposable, short-path project."""
import hashlib, json, os, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent
TARGET = Path(os.environ['TEMP']) / 'oc-install-c4b4-1126'
assert not TARGET.exists(), 'Use a new registered temporary directory for another run.'
TARGET.mkdir()
ignore = shutil.ignore_patterns('__pycache__', '*.pyc', '.pytest_cache', '*.egg-info')
for part in ('backend/src','data-management','contracts','rulepacks','client-sdk','test-console'):
    shutil.copytree(ROOT/'engineering'/part, TARGET/'engineering'/part, ignore=ignore)
for name in ('安装依赖.exe','启动OnlineCOC.exe','launcher-config.json','engineering/requirements-runtime.lock',
             'engineering/desktop/DesktopTools.cs','engineering/desktop/desktop_host.py',
             'engineering/desktop/verify_environment.py','engineering/desktop/tests/test_desktop.py'):
    dest = TARGET/name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT/name,dest)
files = {p.relative_to(TARGET).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in TARGET.rglob('*') if p.is_file()}
build = json.loads((ROOT/'engineering/desktop/build-info.json').read_text(encoding='utf-8-sig'))
assert files['engineering/desktop/DesktopTools.cs'] == build['sourceSha256']
for item in build['artifacts']: assert files[item['file']] == item['sha256']
for part in ('wheels','launcher-bootstrap'):
    shutil.copytree(ROOT/'engineering/.test-output'/part, TARGET/'engineering/.test-output'/part)
(OUT/'source.json').write_text(json.dumps({'root':str(TARGET),'files':files,'buildInfoMatched':True},indent=2,ensure_ascii=False),encoding='utf-8')
print(TARGET)
