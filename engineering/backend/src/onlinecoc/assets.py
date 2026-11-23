import hashlib,json,os,shutil,uuid,re,copy,time
from pathlib import Path
from onlinecoc_data import FileDataStore,canonical
from .errors import require

class Assets:
    def __init__(self,host):
        self.host=host;self.path=host.path/'rooms/demo/assets';self.path.mkdir(exist_ok=True)
        with host.lock:
            if not hasattr(host,'_asset_backup_pins'):host._asset_backup_pins={}
            self._backup_pins=host._asset_backup_pins
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
        return self.write_backup(self.prepare_backup(account,include_identity,ai_snapshot=ai_snapshot),target)

    def prepare_backup(self,account,include_identity=False,*,ai_snapshot=None):
        """Capture one consistent generation and pin immutable asset blobs."""
        started=time.perf_counter()
        with self.host.lock:
            self.host.kp(account)
            generation,state=self.host.store.snapshot()
            identity=self.host.identity.store.snapshot()[1]
            bindings={k:binding(identity['accounts'][k]) for k in state['members']}
            if include_identity:identity['sessions']={}
            if ai_snapshot is not None:
                require(ai_snapshot.get('schemaVersion')==1 and ai_snapshot.get('scopeId')==state['aiControl']['scopeId'],'SCOPE_MISMATCH')
                ai_snapshot=copy.deepcopy(ai_snapshot)
            pins={a['digest'] for a in state['assets'].values()}
            for key in pins:self._backup_pins[key]=self._backup_pins.get(key,0)+1
            return dict(generation=generation,state=state,bindings=bindings,identity=identity if include_identity else None,
                        ai=ai_snapshot,pins=pins,captureMs=(time.perf_counter()-started)*1000)

    def write_backup(self,snapshot,target):
        """Write/fsync outside the room lock; publish the manifest only on success."""
        started=time.perf_counter();written=0;complete=False
        try:
            target=Path(target);require(not target.exists(),'TARGET_EXISTS');target.mkdir(parents=True)
            state=snapshot['state'];assets=state['assets'];data=canonical(state)
            raw=canonical({'format':1,'sourceGeneration':snapshot['generation'],'payload':state,'digest':hashlib.sha256(data).hexdigest()})
            durable_write(target/'room.json',raw);written+=len(raw)
            manifest={'format':1,'roomDigest':hashlib.sha256(raw).hexdigest(),'assets':assets,'identityBindings':snapshot['bindings']}
            (target/'assets').mkdir()
            for key in snapshot['pins']:
                raw=(self.path/key).read_bytes();require(hashlib.sha256(raw).hexdigest()==key,'ASSET_CORRUPT')
                durable_write(target/'assets'/key,raw);written+=len(raw)
            for field,manifest_key in (('identity','identityDigest'),('ai','aiDigest')):
                if snapshot[field] is not None:
                    raw=canonical(snapshot[field]);durable_write(target/(field+'.json'),raw)
                    manifest[manifest_key]=hashlib.sha256(raw).hexdigest();written+=len(raw)
            durable_write(target/'manifest.json',canonical(manifest));complete=True;return str(target)
        finally:
            with self.host.lock:
                for key in snapshot['pins']:
                    self._backup_pins[key]-=1
                    if not self._backup_pins[key]:del self._backup_pins[key]
                metrics=self.host.metrics.setdefault('backups',[])
                metrics.append({'captureMs':snapshot['captureMs'],'writeMs':(time.perf_counter()-started)*1000,'bytes':written,
                                'complete':complete})
                del metrics[:-100]
    def collect_orphans(self,account,older_than=86400):
        with self.host.lock:
            self.host.kp(account);used={a['digest'] for a in self.host.state()['assets'].values()}|self._backup_pins.keys();removed=[]
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
