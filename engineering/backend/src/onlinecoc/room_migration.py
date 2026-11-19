"""Explicit offline v3 -> v4 copy conversion; never edits the source."""
import copy
import hashlib
import json
import shutil
from pathlib import Path
from onlinecoc_data import canonical
from .errors import require
from .model import validate
from .knowledge.models import initial
from .assets import durable_write, verify_bundle

def convert_state(source):
    require(isinstance(source,dict) and type(source.get('schemaVersion')) is int and source['schemaVersion']==3,'SCHEMA_UNSUPPORTED')
    require('knowledge' not in source,'INPUT_INVALID')
    value=copy.deepcopy(source);value['schemaVersion']=4;value['knowledge']=initial()
    for rec in value['commands'].values():
        if isinstance(rec.get('snapshot'),dict) and rec['snapshot'].get('schemaVersion')==3:
            rec['snapshot']['schemaVersion']=4
    validate(value)
    return value

def convert_file(source, target, kind='room'):
    source=Path(source).resolve();target=Path(target).resolve()
    require(source!=target and not target.exists() and source not in target.parents,'TARGET_EXISTS')
    require(kind in ('room','snapshot','backup'),'INPUT_INVALID')
    raw_path=source/'room.json' if kind=='backup' else source
    raw=raw_path.read_bytes();before=hashlib.sha256(raw).hexdigest();value=json.loads(raw.decode('utf-8-sig'))
    if kind in ('snapshot','backup'):
        require(value.get('format')==1 and value.get('digest')==hashlib.sha256(canonical(value['payload'])).hexdigest(),'BACKUP_INVALID')
        result=copy.deepcopy(value);result['payload']=convert_state(value['payload']);result['digest']=hashlib.sha256(canonical(result['payload'])).hexdigest()
    else:result=convert_state(value)
    data=canonical(result)
    if kind=='backup':
        manifest=json.loads((source/'manifest.json').read_bytes())
        require(manifest['format']==1 and manifest['roomDigest']==before and manifest['assets']==value['payload']['assets'],'BACKUP_INVALID')
        for asset in manifest['assets'].values():
            key=asset['digest']; require(len(key)==64 and all(c in '0123456789abcdef' for c in key),'BACKUP_INVALID')
            require(hashlib.sha256((source/'assets'/key).read_bytes()).hexdigest()==key,'ASSET_CORRUPT')
        for file,key in [('identity.json','identityDigest'),('ai.json','aiDigest')]:
            if key in manifest:require(hashlib.sha256((source/file).read_bytes()).hexdigest()==manifest[key],'BACKUP_INVALID')
        target.mkdir(parents=True)
        shutil.copytree(source/'assets',target/'assets')
        for file,key in [('identity.json','identityDigest'),('ai.json','aiDigest')]:
            if key in manifest:durable_write(target/file,(source/file).read_bytes())
        manifest['roomDigest']=hashlib.sha256(data).hexdigest()
        durable_write(target/'room.json',data);durable_write(target/'manifest.json',canonical(manifest))
        verify_bundle(target)
    else:
        target.parent.mkdir(parents=True,exist_ok=True);durable_write(target,data)
    require(raw_path.read_bytes()==raw,'SOURCE_CHANGED')
    return dict(sourceVersion=3,targetVersion=4,sourceDigest=before,targetDigest=hashlib.sha256(data).hexdigest(),output=str(target),historicalKnowledgeImported=False)
