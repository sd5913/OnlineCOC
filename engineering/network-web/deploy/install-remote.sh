#!/bin/sh
set -eu
test "$(id -u)" = 0
stage=/home/ubuntu/onlinecoc-web-deploy
root=/opt/onlinecoc-network
test -f "$stage/web.tar.gz"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
release="$root/releases/web-$stamp"
backup="$root/rollback/web-$stamp"
install -d -m 0755 "$release"
install -d -m 0700 "$backup"
tar -xzf "$stage/web.tar.gz" -C "$release"
# Prepare a separate runtime before stopping the live service.
python3 -m venv --system-site-packages "$release/venv"
"$release/venv/bin/pip" install --disable-pip-version-check -q -r "$root/app/requirements.lock"
"$release/venv/bin/pip" install --disable-pip-version-check -q --no-deps "$release/p2p-app" "$release/web-app"
"$release/venv/bin/python" -c 'import onlinecoc_web.portal, onlinecoc_web.host'
cp /etc/systemd/system/onlinecoc-directory.service "$backup/directory.service"
cp /etc/onlinecoc-network/directory.json "$backup/directory.json"
systemctl stop onlinecoc-directory
tar -czf "$backup/state.tar.gz" -C /var/lib/onlinecoc-network .
python3 - "$release" <<'PY'
import json, os, sys
from pathlib import Path
config_path = Path('/etc/onlinecoc-network/directory.json')
config = json.loads(config_path.read_text())
config['webStateFile'] = '/var/lib/onlinecoc-network/web-accounts.json'
config.setdefault('registration', True)
config.setdefault('maxAccounts', 2000)
temporary = config_path.with_suffix('.new')
temporary.write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
os.chmod(temporary, 0o640)
import shutil
shutil.chown(temporary, user='root', group='onlinecoc-net')
os.replace(temporary, config_path)
unit_path = Path('/etc/systemd/system/onlinecoc-directory.service')
unit = unit_path.read_text()
lines = []
for line in unit.splitlines():
    if line.startswith('ExecStart='):
        line = f'ExecStart={sys.argv[1]}/venv/bin/python -m onlinecoc_web serve --config /etc/onlinecoc-network/directory.json --bind 0.0.0.0 --port 443 --cert /etc/onlinecoc-network/server.pem --key /etc/onlinecoc-network/server.key'
    if line.startswith('Description='):
        line = 'Description=OnlineCOC web portal, room directory and signaling'
    lines.append(line)
unit_path.write_text('\n'.join(lines) + '\n')
PY
systemctl daemon-reload
if systemctl start onlinecoc-directory && sleep 2 && systemctl is-active --quiet onlinecoc-directory; then
    printf '%s\n' "$release" > "$root/current-web-release"
    printf 'Web portal active. Rollback: %s\n' "$backup"
else
    cp "$backup/directory.service" /etc/systemd/system/onlinecoc-directory.service
    cp "$backup/directory.json" /etc/onlinecoc-network/directory.json
    systemctl daemon-reload
    systemctl restart onlinecoc-directory
    exit 1
fi
systemctl is-active onlinecoc-directory onlinecoc-turn
