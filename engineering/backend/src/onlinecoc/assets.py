import hashlib,json,os,shutil,uuid,re,copy,time
from pathlib import Path
from onlinecoc_data import FileDataStore,canonical
from .errors import require

class Assets:
    def __init__(self,host):
        self.host=host;self.path=host.path/'rooms/demo/assets';self.path.mkdir(exist_ok=True)
    def upload(self,account,name,data,visibility='public'):
        require(len(data)<=10*1024*1024,'LIMIT_EXCEEDED');require(visibility in ('public','kp'))
        with self.host.lock:
            self.host.kp(account);digest=hashlib.sha256(data).hexdigest();target=self.path/digest
            if not target.exists():
                temp=self.path/(uuid.uuid4().hex+'.tmp')
                try:
                    with open(temp,'xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
                    os.replace(temp,target)
                finally:
                    if temp.exists():temp.unlink()
            s=self.host.state();id=uuid.uuid4().hex
            s['assets'][id]={'assetId':id,'name':str(name)[:200],'digest':digest,'size':len(data),'visibility':visibility,'ready':True}
            self.host.commit(s);return id
    def read(self,account,id):
        from .model import member
        with self.host.lock:
            s=self.host.state();m=member(s,account);asset=s['assets'].get(id)
            require(asset and (asset['visibility']=='public' or m['role']=='kp'),'NOT_VISIBLE')
            require(m['role']=='kp' or not self.host.knowledge.managed(s,'asset',id,asset),'NOT_VISIBLE')
            require(m['role']=='kp' or not any(id in e['components'].get('core.assets',[]) and self.host.knowledge.managed(s,'entity',key,e) for key,e in s['entities'].items()),'NOT_VISIBLE')
            raw=(self.path/asset['digest']).read_bytes();require(hashlib.sha256(raw).hexdigest()==asset['digest'],'ASSET_CORRUPT')
            return raw,asset
    def backup(self,account,target,include_identity=False,*,ai_snapshot=None):
        with self.host.lock:
            self.host.kp(account);target=Path(target);require(not target.exists(),'TARGET_EXISTS');target.mkdir(parents=True)
            self.host.store.export_snapshot(target/'room.json')
            assets=self.host.state()['assets'];(target/'assets').mkdir()
            for a in assets.values():
                raw=(self.path/a['digest']).read_bytes();require(hashlib.sha256(raw).hexdigest()==a['digest'],'ASSET_CORRUPT')
                durable_write(target/'assets'/a['digest'],raw)
            manifest={'format':1,'roomDigest':hashlib.sha256((target/'room.json').read_bytes()).hexdigest(),'assets':assets}
            identity=self.host.identity.store.snapshot()[1]
            manifest['identityBindings']={k:binding(identity['accounts'][k]) for k in self.host.state()['members']}
            if include_identity:
                identity=copy.deepcopy(identity);identity['sessions']={}
                durable_write(target/'identity.json',canonical(identity));manifest['identityDigest']=hashlib.sha256(canonical(identity)).hexdigest()
            if ai_snapshot is not None:
                require(ai_snapshot.get('schemaVersion')==1 and ai_snapshot.get('scopeId')==self.host.state()['aiControl']['scopeId'],'SCOPE_MISMATCH')
                durable_write(target/'ai.json',canonical(ai_snapshot));manifest['aiDigest']=hashlib.sha256(canonical(ai_snapshot)).hexdigest()
            durable_write(target/'manifest.json',canonical(manifest));return str(target)
    def collect_orphans(self,account,older_than=86400):
        with self.host.lock:
            self.host.kp(account);used={a['digest'] for a in self.host.state()['assets'].values()};removed=[]
            for p in self.path.iterdir():
                if p.is_file() and p.name not in used and time.time()-p.stat().st_mtime>older_than:
                    p.unlink();removed.append(p.name)
            return removed
    @staticmethod
    def restore(bundle,directory,identity_mapping):
        bundle=Path(bundle);directory=Path(directory);require(not directory.exists(),'TARGET_EXISTS')
        manifest,payload=verify_bundle(bundle)
        require(identity_mapping=={k:k for k in payload['members']},'IDENTITY_MAPPING_REQUIRED')
        from .room_lifecycle import fork_scope
        restored=fork_scope(payload)
        with FileDataStore(directory) as store:store.commit(0,restored)
        shutil.copytree(bundle/'assets',directory/'assets')

def durable_write(path,data):
    with open(path,'xb') as f:f.write(data);f.flush();os.fsync(f.fileno())

def binding(account):
    return hashlib.sha256(canonical({k:account[k] for k in ('accountId','passwordHash')})).hexdigest()

def verify_bundle(bundle):
    from .model import validate
    bundle=Path(bundle);manifest=json.loads((bundle/'manifest.json').read_bytes());require(manifest['format']==1,'BACKUP_INVALID')
    raw=(bundle/'room.json').read_bytes();require(hashlib.sha256(raw).hexdigest()==manifest['roomDigest'],'BACKUP_INVALID')
    env=json.loads(raw);payload=env['payload'];validate(payload)
    from .ai_contracts import approval_digest
    require(all(a['approvalDigest']==approval_digest(a) for a in payload['aiControl']['approvals'].values()),'BACKUP_INVALID')
    require(env['format']==1 and hashlib.sha256(canonical(payload)).hexdigest()==env['digest'],'BACKUP_INVALID')
    require(payload['assets']==manifest['assets'],'BACKUP_INVALID')
    for a in manifest['assets'].values():
        require(re.fullmatch('[a-f0-9]{64}',a['digest']),'BACKUP_INVALID')
        require(hashlib.sha256((bundle/'assets'/a['digest']).read_bytes()).hexdigest()==a['digest'],'ASSET_CORRUPT')
    if 'aiDigest' in manifest:
        ai_raw=(bundle/'ai.json').read_bytes();require(hashlib.sha256(ai_raw).hexdigest()==manifest['aiDigest'],'BACKUP_INVALID')
        ai=json.loads(ai_raw);require(ai.get('schemaVersion')==1 and ai.get('scopeId')==payload.get('aiControl',{}).get('scopeId'),'SCOPE_MISMATCH')
        # Optional history is retained as an inert, verified attachment. It is
        # not automatically rebound to a new room scope or treated as authority.
        require(all(p['scopeId']==ai['scopeId'] and p['requestId'] in ai.get('requests',{}) and p['contextRef'] in ai.get('contexts',{}) and
                    set(p['reportRefs'])<=set(ai.get('reports',{})) for r in ai.get('proposals',{}).values() for p in r['revisions'].values()),'BACKUP_INVALID')
    return manifest,payload

def restore_host(bundle,target,identity_directory=None):
    # Fully verify before creating a new host; never overwrite a live or existing directory.
    bundle=Path(bundle);target=Path(target);require(not target.exists(),'TARGET_EXISTS')
    manifest,payload=verify_bundle(bundle)
    if identity_directory:
        with FileDataStore(identity_directory) as identity_store:identity=identity_store.snapshot()[1]
    else:
        raw=(bundle/'identity.json').read_bytes();require(hashlib.sha256(raw).hexdigest()==manifest.get('identityDigest'),'IDENTITY_MAPPING_REQUIRED');identity=json.loads(raw)
    require(all(k in identity['accounts'] and binding(identity['accounts'][k])==v for k,v in manifest['identityBindings'].items()),'IDENTITY_MAPPING_REQUIRED')
    identity=copy.deepcopy(identity);identity['sessions']={}
    staging=target.with_name(target.name+'.restoring-'+uuid.uuid4().hex);staging.mkdir(parents=True)
    with FileDataStore(staging/'identity') as store:store.commit(0,identity)
    Assets.restore(bundle,staging/'rooms/demo',{k:k for k in payload['members']})
    if 'aiDigest' in manifest:
        durable_write(staging/'ai-history-before-restore.json',(bundle/'ai.json').read_bytes())
    # Windows scanners may briefly retain a handle after the last durable write.
    # Retry only sharing/access errors, never replace an existing target.
    for attempt in range(6):
        require(not target.exists(),'TARGET_EXISTS')
        try:
            os.rename(staging,target)
            break
        except PermissionError as exc:
            if os.name!='nt' or getattr(exc,'winerror',None) not in (5,32) or attempt==5:raise
            time.sleep(.05*(attempt+1))
    return str(target)
