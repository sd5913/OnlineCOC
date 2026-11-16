"""Prepare private deployment artifacts locally; never print secrets."""
import datetime as dt
import ipaddress
import json
import secrets
import tarfile
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

from onlinecoc_p2p.common import atomic_json, digest

root=Path(__file__).resolve().parents[1]
local=root/"local"
server=json.loads((local/"server.json").read_text())
out=local/"deploy"
out.mkdir(exist_ok=True)
secrets_path=local/"deployment-secrets.json"
if not secrets_path.exists():
    atomic_json(secrets_path, {"publisherToken":secrets.token_urlsafe(32),"turnSecret":secrets.token_urlsafe(48)})
credentials=json.loads(secrets_path.read_text())
now=dt.datetime.now(dt.timezone.utc)
def needs_key_ids(path):
    if not path.exists():
        return True
    cert=x509.load_pem_x509_certificate(path.read_bytes())
    try:
        cert.extensions.get_extension_for_class(x509.SubjectKeyIdentifier)
        cert.extensions.get_extension_for_class(x509.AuthorityKeyIdentifier)
        return False
    except x509.ExtensionNotFound:
        return True
if needs_key_ids(local/"test-ca.pem"):
    ca_key=serialization.load_pem_private_key((local/"test-ca.key").read_bytes(),None) if (local/"test-ca.key").exists() else ec.generate_private_key(ec.SECP256R1())
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,"OnlineCOC closed-test CA")])
    ca=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now-dt.timedelta(minutes=5))
        .not_valid_after(now+dt.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),critical=False)
        .add_extension(x509.KeyUsage(False,False,False,False,False,True,True,False,False),critical=True)
        .sign(ca_key,hashes.SHA256()))
    (local/"test-ca.key").write_bytes(ca_key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    (local/"test-ca.pem").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
if needs_key_ids(out/"server.pem"):
    ca=x509.load_pem_x509_certificate((local/"test-ca.pem").read_bytes())
    ca_key=serialization.load_pem_private_key((local/"test-ca.key").read_bytes(),None)
    key=ec.generate_private_key(ec.SECP256R1())
    cert=(x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,"OnlineCOC test directory")]))
        .issuer_name(ca.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now-dt.timedelta(minutes=5)).not_valid_after(now+dt.timedelta(days=90))
        .add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),critical=False)
        .add_extension(x509.KeyUsage(True,False,False,False,False,False,False,False,False),critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(server["host"]))]),critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),critical=False)
        .sign(ca_key,hashes.SHA256()))
    (out/"server.key").write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    (out/"server.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM)+(local/"test-ca.pem").read_bytes())
atomic_json(out/"directory.json",{"stateFile":"/var/lib/onlinecoc-network/rooms.json",
    "publishers":{"owner":digest(credentials["publisherToken"].encode())},
    "turn":{"urls":[f'stun:{server["host"]}:3478',f'turn:{server["host"]}:3478?transport=udp',f'turn:{server["host"]}:3478?transport=tcp'],
            "secret":credentials["turnSecret"]}})
# No turns URL is advertised until clients trust a certificate for the TURN endpoint.
turn=f'''listening-port=3478
tls-listening-port=5349
listening-ip={server["privateIp"]}
relay-ip={server["privateIp"]}
external-ip={server["host"]}/{server["privateIp"]}
min-port=49160
max-port=49259
fingerprint
use-auth-secret
static-auth-secret={credentials["turnSecret"]}
realm=onlinecoc-test
userdb=/var/lib/onlinecoc-network/turn.sqlite
cert=/etc/onlinecoc-network/server.pem
pkey=/etc/onlinecoc-network/server.key
no-tlsv1
no-tlsv1_1
no-dtls
no-cli
no-multicast-peers
no-tcp-relay
stale-nonce=600
user-quota=4
total-quota=64
max-bps=65536
bps-capacity=1048576
relay-threads=2
log-file=stdout
simple-log
no-stdout-log
denied-peer-ip=0.0.0.0-0.255.255.255
denied-peer-ip=10.0.0.0-10.255.255.255
denied-peer-ip=100.64.0.0-100.127.255.255
denied-peer-ip=127.0.0.0-127.255.255.255
denied-peer-ip=169.254.0.0-169.254.255.255
denied-peer-ip=172.16.0.0-172.31.255.255
denied-peer-ip=192.168.0.0-192.168.255.255
denied-peer-ip=224.0.0.0-255.255.255.255
'''
(out/"turnserver.conf").write_text(turn,encoding="utf-8")
config={"directory":"https://"+server["host"],"caFile":str(local/"test-ca.pem"),
        "publisherToken":credentials["publisherToken"],"statePath":str(local/"host-session"),
        "upstream":"http://127.0.0.1:8765"}
if not (local/"client-config.json").exists():
    atomic_json(local/"client-config.json",config)
with tarfile.open(local/"deploy.tar.gz","w:gz") as archive:
    for relative in ("src","pyproject.toml","requirements.txt","requirements.lock","deploy"):
        for path in (root/relative).rglob("*") if (root/relative).is_dir() else [root/relative]:
            if path.is_file() and "__pycache__" not in path.parts:
                archive.add(path,arcname="app/"+str(path.relative_to(root)).replace("\\","/"))
    for path in out.iterdir():
        if path.is_file():
            archive.add(path,arcname="private/"+path.name)
print(json.dumps({"artifact":"local/deploy.tar.gz","tls":"private CA pinned by native client; no global trust installation","certificateExpires":str(now+dt.timedelta(days=90))}))
