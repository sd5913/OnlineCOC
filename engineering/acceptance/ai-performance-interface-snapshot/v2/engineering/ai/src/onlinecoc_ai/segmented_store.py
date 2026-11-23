"""Versioned AI storage manifests; immutable JSON objects precede atomic heads.

Wire/model documents keep their 8 MiB limit. Only the internal aggregate can
grow to 128 MiB. No originals or old generations are garbage-collected.
"""
import copy
import hashlib
import json
import os
import re
import uuid
from onlinecoc_data import FileDataStore
from onlinecoc_data.store import StoreError
from .contracts import _json_value, canonical, MAX_JSON_BYTES
from .errors import require

CHUNK_BYTES=256*1024
STATE_BYTES=128*1024*1024


def _json_bytes(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def state_bytes(value):
    _json_value(value)
    raw=_json_bytes(value)
    require(len(raw)<=STATE_BYTES,'LIMIT_EXCEEDED','AI aggregate state exceeds 128 MiB')
    return raw


class SegmentedStore(FileDataStore):
    def __init__(self,directory,**kwargs):
        self._decoded=None;self._decoded_generation=-1
        super().__init__(directory,**kwargs)
        self.objects=self.path/'objects-v2'
        try:
            if self.objects.is_symlink():raise StoreError('STORE_CORRUPT')
            self.objects.mkdir(exist_ok=True)
            self.snapshot()  # Validate current references before exposing a store.
        except BaseException:
            self.close();raise

    def _disk_bytes(self):
        total=super()._disk_bytes();folder=self.path/'objects-v2'
        if folder.exists():
            if folder.is_symlink():raise StoreError('STORE_CORRUPT')
            with os.scandir(folder) as entries:
                for entry in entries:
                    if entry.is_symlink() or not re.fullmatch(r'[a-f0-9]{64}\.json',entry.name):raise StoreError('STORE_CORRUPT')
                    total+=entry.stat().st_size
        return total

    def _object(self,raw):
        # commit validated the aggregate once; these are canonical byte slices
        # of that JSON, not untrusted caller-supplied serialized documents.
        require(len(raw)<=MAX_JSON_BYTES,'LIMIT_EXCEEDED')
        key=hashlib.sha256(raw).hexdigest();path=self.objects/(key+'.json')
        if path.exists():
            if path.is_symlink() or path.read_bytes()!=raw:raise StoreError('STORE_CORRUPT')
            return {'ref':key}
        if self._disk_bytes()+len(raw)*2>self.max_bytes:raise StoreError('STORE_FULL')
        tmp=self.staging/(uuid.uuid4().hex+'.tmp')
        try:
            self._fault('segment_before_write')
            with open(tmp,'xb') as stream:
                stream.write(raw);stream.flush();self._fault('segment_before_sync');os.fsync(stream.fileno())
            self._fault('segment_before_publish');os.replace(tmp,path);self._sync_directory(self.objects)
            self._fault('segment_after_publish')
        finally:
            if tmp.exists():tmp.unlink()
        return {'ref':key}

    def _encode(self,value,raw=None,partition=0):
        raw=_json_bytes(value) if raw is None else raw
        if len(raw)<=CHUNK_BYTES:return self._object(raw)
        if isinstance(value,dict):
            # Stable key partitions keep one resized/inserted history record
            # from shifting every following chunk boundary.
            if len(value)>128 and partition<64:
                buckets={}
                for key,item in value.items():
                    bucket=hashlib.sha256(key.encode('utf-8')).hexdigest()[partition]
                    buckets.setdefault(bucket,{})[key]=item
                return {'dict':[self._encode(buckets[key],partition=partition+1) for key in sorted(buckets)],'children':{}}
            chunks=[];children={};pending=[];used=2
            for key,item in sorted(value.items()):
                item_raw=_json_bytes(item);entry=_json_bytes(key)+b':'+item_raw
                if len(entry)+2>CHUNK_BYTES:
                    children[key]=self._encode(item,item_raw);continue
                if pending and used+len(entry)+1>CHUNK_BYTES:
                    chunks.append(self._object(b'{'+b','.join(pending)+b'}'));pending=[];used=2
                pending.append(entry);used+=len(entry)+1
            if pending:chunks.append(self._object(b'{'+b','.join(pending)+b'}'))
            return {'dict':chunks,'children':children}
        if isinstance(value,list):
            parts=[];pending=[];used=2
            for item in value:
                item_raw=_json_bytes(item);size=len(item_raw)+1
                if pending and used+size>CHUNK_BYTES:
                    parts.append({'chunk':self._object(b'['+b','.join(pending)+b']')});pending=[];used=2
                if size+1>CHUNK_BYTES:parts.append({'single':self._encode(item,item_raw)})
                else:pending.append(item_raw);used+=size
            if pending:parts.append({'chunk':self._object(b'['+b','.join(pending)+b']')})
            return {'list':parts}
        return self._object(raw)  # A scalar still must fit an 8 MiB document.

    def _decode(self,node,depth=0,budget=None):
        if budget is None:budget=[STATE_BYTES]
        if depth>64 or not isinstance(node,dict):raise StoreError('STORE_CORRUPT')
        if set(node)=={'ref'}:
            key=node['ref']
            if not isinstance(key,str) or not re.fullmatch('[a-f0-9]{64}',key):raise StoreError('STORE_CORRUPT')
            path=self.objects/(key+'.json')
            if path.is_symlink():raise StoreError('STORE_CORRUPT')
            with open(path,'rb') as stream:raw=stream.read(MAX_JSON_BYTES+1)
            if len(raw)>MAX_JSON_BYTES or hashlib.sha256(raw).hexdigest()!=key:raise StoreError('STORE_CORRUPT')
            budget[0]-=len(raw)
            if budget[0]<0:raise StoreError('STORE_CORRUPT')
            value=json.loads(raw)
            if canonical(value)!=raw:raise StoreError('STORE_CORRUPT')
            return value
        if set(node)=={'dict','children'}:
            result={}
            for chunk in node['dict']:
                value=self._decode(chunk,depth+1,budget)
                if not isinstance(value,dict) or result.keys()&value.keys():raise StoreError('STORE_CORRUPT')
                result.update(value)
            for key,child in node['children'].items():
                if key in result:raise StoreError('STORE_CORRUPT')
                result[key]=self._decode(child,depth+1,budget)
            return result
        if set(node)=={'list'}:
            result=[]
            for part in node['list']:
                if set(part)=={'single'}:result.append(self._decode(part['single'],depth+1,budget))
                elif set(part)=={'chunk'}:
                    value=self._decode(part['chunk'],depth+1,budget)
                    if not isinstance(value,list):raise StoreError('STORE_CORRUPT')
                    result.extend(value)
                else:raise StoreError('STORE_CORRUPT')
            return result
        raise StoreError('STORE_CORRUPT')

    def snapshot(self):
        with self.mutex:
            if self.closed:raise StoreError('STORE_CLOSED')
            if self._decoded_generation!=self.generation:
                value=self.value
                if isinstance(value,dict) and 'aiStorageFormat' in value:
                    if set(value)!={'aiStorageFormat','state'} or type(value['aiStorageFormat']) is not int or value['aiStorageFormat']!=2:raise StoreError('STORE_CORRUPT_OR_UNSUPPORTED')
                    try:
                        value=self._decode(value['state']);state_bytes(value)
                    except StoreError:raise
                    except Exception as exc:raise StoreError('STORE_CORRUPT') from exc
                self._decoded=value;self._decoded_generation=self.generation
            return self.generation,copy.deepcopy(self._decoded)

    def commit(self,expected_generation,value):
        with self.mutex:
            if self.closed:raise StoreError('STORE_CLOSED')
            if expected_generation!=self.generation:raise StoreError('VERSION_CONFLICT')
            raw=state_bytes(value)
            payload=value if len(raw)<=CHUNK_BYTES else {'aiStorageFormat':2,'state':self._encode(value,raw)}
            canonical(payload)  # The atomic manifest itself is an ordinary bounded document.
            try:return super().commit(expected_generation,payload)
            finally:
                # after_publish may lose its reply: subsequent reads must reflect
                # the committed generation, never the old cached logical value.
                if self.generation==expected_generation+1:
                    self._decoded=copy.deepcopy(value);self._decoded_generation=self.generation
                else:self._decoded_generation=-1
