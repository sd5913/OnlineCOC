#!/bin/sh
set -eu
test "$(id -u)" = 0
stage=/home/ubuntu/onlinecoc-network-deploy
test -f "$stage/deploy.tar.gz"
# Scoped services on this newly provisioned test VM.
systemctl disable --now coturn.service
id onlinecoc-net >/dev/null 2>&1 || useradd --system --home /var/lib/onlinecoc-network --shell /usr/sbin/nologin onlinecoc-net
install -d -m 0755 /opt/onlinecoc-network
install -d -m 0750 -o root -g onlinecoc-net /etc/onlinecoc-network
install -d -m 0700 -o onlinecoc-net -g onlinecoc-net /var/lib/onlinecoc-network
tar -xzf "$stage/deploy.tar.gz" -C /opt/onlinecoc-network
python3 -m venv /opt/onlinecoc-network/venv
/opt/onlinecoc-network/venv/bin/pip install --disable-pip-version-check -q -r /opt/onlinecoc-network/app/requirements.lock
/opt/onlinecoc-network/venv/bin/pip install --disable-pip-version-check -q --no-deps /opt/onlinecoc-network/app
for file in directory.json server.pem server.key turnserver.conf; do
    install -m 0640 -o root -g onlinecoc-net "/opt/onlinecoc-network/private/$file" "/etc/onlinecoc-network/$file"
done
chmod 0700 /opt/onlinecoc-network/private
install -m 0644 /opt/onlinecoc-network/app/deploy/onlinecoc-directory.service /etc/systemd/system/onlinecoc-directory.service
install -m 0644 /opt/onlinecoc-network/app/deploy/onlinecoc-turn.service /etc/systemd/system/onlinecoc-turn.service
if [ ! -f /var/lib/onlinecoc-network/turn.sqlite ]; then
    sqlite3 /var/lib/onlinecoc-network/turn.sqlite < /usr/share/coturn/schema.sql
    chown onlinecoc-net:onlinecoc-net /var/lib/onlinecoc-network/turn.sqlite
    chmod 0600 /var/lib/onlinecoc-network/turn.sqlite
fi
systemctl daemon-reload
systemctl enable onlinecoc-directory.service onlinecoc-turn.service
systemctl restart onlinecoc-directory.service onlinecoc-turn.service
systemctl is-active onlinecoc-directory.service onlinecoc-turn.service
