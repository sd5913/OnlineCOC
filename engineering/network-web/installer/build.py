"""Build a single offline Windows EXE from the validated locked dependency environment."""
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile

MODULE = Path(__file__).resolve().parents[1]
BUILD = MODULE / 'build/installer'
DIST = MODULE / 'dist'
BUILD.mkdir(parents=True, exist_ok=True)
DIST.mkdir(exist_ok=True)
assert sys.platform == 'win32' and sys.version_info[:2] == (3, 14)
url = 'https://www.python.org/ftp/python/3.14.2/python-3.14.2-embed-amd64.zip'
archive = BUILD / 'python-3.14.2-embed-amd64.zip'
with urllib.request.urlopen(url + '.spdx.json', timeout=60) as response:
    sbom = json.load(response)
package = next(p for p in sbom['packages'] if p.get('packageFileName') == archive.name)
expected = next(c['checksumValue'] for c in package['checksums'] if c['algorithm'] == 'SHA256')
if not archive.exists():
    with urllib.request.urlopen(url, timeout=120) as response:
        archive.write_bytes(response.read())
assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected, 'Python download checksum mismatch'
payload = BUILD / 'runtime.zip'
versions = {}
with zipfile.ZipFile(payload, 'w', zipfile.ZIP_DEFLATED) as output:
    with zipfile.ZipFile(archive) as source:
        for item in source.infolist():
            if not item.is_dir() and item.filename != "python314._pth":
                output.writestr('Scripts/' + item.filename, source.read(item))
    for line in (MODULE.parent / 'network-p2p/requirements.lock').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        name, version = line.split('==')
        dist = metadata.distribution(name)
        assert dist.version == version, (name, dist.version, version)
        versions[name] = version
        for relative in dist.files:
            if '..' in relative.parts or '__pycache__' in relative.parts or relative.suffix == '.pyc':
                continue
            source = Path(dist.locate_file(relative))
            assert source.is_file(), source
            output.write(source, 'Lib/site-packages/' + relative.as_posix())
    output.writestr('dependency-versions.json', json.dumps(versions, indent=2))
    output.writestr('Scripts/python314._pth', 'python314.zip\n.\n../Lib/site-packages\n../../../network-p2p/src\n../../../network-web/src\nimport site\n')
digest = hashlib.sha256(payload.read_bytes()).hexdigest()
(BUILD / 'PayloadHash.cs').write_text('internal static class PayloadHash { internal const string Value = "' + digest + '"; }')
compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
exe = DIST / 'OnlineCOC-Network-Setup.exe'
subprocess.run([str(compiler), '/nologo', '/target:winexe', '/platform:x64', '/optimize+',
    '/reference:System.dll', '/reference:System.Core.dll', '/reference:System.Windows.Forms.dll',
    '/reference:System.Drawing.dll', '/reference:System.IO.Compression.dll', '/reference:System.IO.Compression.FileSystem.dll',
    '/resource:' + str(payload) + ',runtime.zip', '/out:' + str(exe),
    str(MODULE / 'installer/Setup.cs'), str(BUILD / 'PayloadHash.cs')], check=True)
result = {'installerVersion': '1.0.0', 'platform': 'Windows x64', 'python': '3.14.2',
    'pythonSource': url, 'pythonSHA256': expected, 'payloadSHA256': digest,
    'exeSHA256': hashlib.sha256(exe.read_bytes()).hexdigest(), 'exeBytes': exe.stat().st_size,
    'dependencies': versions}
(DIST / 'release.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'exe': str(exe), 'bytes': exe.stat().st_size, 'sha256': result['exeSHA256']}))
