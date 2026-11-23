import copy
import hashlib
import threading
from collections import OrderedDict
from onlinecoc_data import canonical
from .lua_runtime import execute
from .errors import require
from .contracts import input_schema, _json_tree
from .worker_process import POLICY_VERSION

_STAGED=OrderedDict()
_STAGED_LOCK=threading.Lock()
_STAGED_BYTES=0
STATIC_VALIDATION_VERSION='stage-1:'+POLICY_VERSION

def stage_delta(base,changes):
    """Reconstruct a detached complete artifact; never validate a fragment alone.

    The caller checks the active revision and holds the room lock through commit.
    Explicit deletions keep JSON null available as an ordinary data value.
    """
    sources=changes.get('sources',{});data=changes.get('data',{})
    remove_sources=changes.get('removeSources',[]);remove_data=changes.get('removeData',[])
    require(bool(sources or data or remove_sources or remove_data),'INPUT_INVALID')
    require(not set(sources).intersection(remove_sources) and not set(data).intersection(remove_data),'INPUT_INVALID')
    require(all(key in base['sources'] for key in remove_sources) and all(key in base['data'] for key in remove_data),'RULE_FILE_NOT_FOUND')
    merged_sources=copy.deepcopy(base['sources']);merged_data=copy.deepcopy(base['data'])
    for key in remove_sources:del merged_sources[key]
    for key in remove_data:del merged_data[key]
    merged_sources.update(copy.deepcopy(sources));merged_data.update(copy.deepcopy(data))
    return stage(merged_sources,merged_data)

def stage(sources,data=None):
    global _STAGED_BYTES
    require(isinstance(sources,dict) and 0<len(sources)<=64)
    require(len(canonical(sources))<=1024*1024,"LIMIT_EXCEEDED")
    require(all(isinstance(k,str) and k.endswith('.lua') and '/' not in k and '\\' not in k and isinstance(v,str) for k,v in sources.items()))
    require(data is None or isinstance(data,dict));require(len(canonical(data or {}))<=1024*1024,"LIMIT_EXCEEDED")
    cache_key=hashlib.sha256(canonical([STATIC_VALIDATION_VERSION,sources,data or {}])).digest() if _json_tree([sources,data],65536) else None
    if cache_key is not None:
        with _STAGED_LOCK:
            if cache_key in _STAGED:
                _STAGED.move_to_end(cache_key)
                return copy.deepcopy(_STAGED[cache_key][0])
    metadata=execute(sources,{"kind":"inspect"})["metadata"]
    for key,m in metadata.items():
        require(m["mode"] in ("action","calculation","flow"),"RULE_INVALID")
        require(isinstance(m["inputs"],dict) and len(m["inputs"])<=16,"RULE_INVALID")
        require(all(v in ("actor","skill","item","bag","amount","quantity","text","choice") for v in m["inputs"].values()),"RULE_INVALID")
        m["schema"]=input_schema(m["inputs"])
        if m["mode"]=="flow":
            nodes=m["nodes"];ids=[n["id"] for n in nodes]
            require(0<len(ids)<=32 and len(ids)==len(set(ids)),"FLOW_INVALID")
            graph={}
            for i,n in enumerate(nodes):
                opts=n["options"];require(isinstance(opts,dict),"FLOW_INVALID");targets=[opts[x] for x in ("yes","no","timeout") if x in opts]
                if not targets:targets=[ids[i+1] if i+1<len(ids) else "end"]
                require(all(x in ids or x=="end" for x in targets),"FLOW_INVALID")
                if n["kind"]=="wait":require(all(k in opts for k in ("yes","no","timeout")) and opts.get("role") in ("kp","initiator") and 1<=opts.get("seconds",0)<=86400,"FLOW_INVALID")
                require(n["kind"] in ("step","wait"),"FLOW_INVALID")
                require(not ("yes" in opts or "no" in opts) or ("yes" in opts and "no" in opts),"FLOW_INVALID")
                graph[n["id"]]=[x for x in targets if x!="end"]
            check_graph(graph)
    check_graph({k:list(m["dependencies"]) for k,m in metadata.items()})
    artifact={"sources":sources,"data":data or {},"metadata":metadata,"apiVersion":1}
    artifact["revision"]=hashlib.sha256(canonical(artifact)).hexdigest()
    if cache_key is not None:
        size=len(canonical(artifact))
        with _STAGED_LOCK:
            if cache_key not in _STAGED:
                _STAGED[cache_key]=(copy.deepcopy(artifact),size);_STAGED_BYTES+=size
            while len(_STAGED)>16 or _STAGED_BYTES>8*1024*1024:
                _,(_,old_size)=_STAGED.popitem(last=False);_STAGED_BYTES-=old_size
    return artifact

def check_graph(graph):
    def visit(key,path):
        require(key in graph and key not in path and len(path)<32,"RULE_CYCLE_OR_MISSING")
        for child in graph[key]:visit(child,path|{key})
    for key in graph:visit(key,set())
