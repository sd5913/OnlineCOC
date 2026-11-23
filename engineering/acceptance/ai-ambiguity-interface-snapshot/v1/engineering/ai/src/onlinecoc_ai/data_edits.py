"""Explicit model-side data edits compiled to the existing complete ChangeSet."""
import copy
from jsonschema import Draft202012Validator
from .contracts import canonical,digest
from .errors import require

NAME='pack_read_config_data'
READ_SCHEMA={'type':'object','additionalProperties':False,'required':['file'],'properties':{
    'file':{'type':'string','minLength':1,'maxLength':200},
    'path':{'type':'array','maxItems':32,'items':{'oneOf':[{'type':'string','maxLength':200},{'type':'integer','minimum':0}]}},
    'offset':{'type':'integer','minimum':0},'limit':{'type':'integer','minimum':1,'maximum':20}}}
TOOL={'type':'function','function':{'name':NAME,
    'description':'Read a precise node of active artifact JSON data and obtain an editRef. Start with file and path (for example path:["items"]). Arrays paginate; large objects list child keys. Unread fields are preserved by explicit dataEdits; never reconstruct the whole file from fragments. This is read-only and grants no publication permission.',
    'parameters':READ_SCHEMA}}
EDITS_SCHEMA={'type':'array','minItems':1,'items':{'oneOf':[]}}
for op,extra,required in [('append',{'keyField':{'type':'string','minLength':1,'maxLength':200},'value':{'type':'object'}},['keyField','value']),
    ('append',{'value':{'type':'string','minLength':1}},['value']),
    ('append_value',{'value':{}},['value']),
    ('add',{'key':{'type':'string','minLength':1,'maxLength':200},'value':{}},['key','value']),
    ('replace',{'value':{}},['value']),('remove',{},[])]:
    EDITS_SCHEMA['items']['oneOf'].append({'type':'object','additionalProperties':False,'required':['op','ref']+required,
        'properties':{'op':{'const':op},'ref':{'type':'string','pattern':'^[a-f0-9]{64}$'},**extra}})


def node(document,path):
    value=document
    for part in path:
        require(type(value) is dict and type(part) is str and part in value or
            type(value) is list and type(part) is int and 0<=part<len(value),'INPUT_INVALID','Path must identify an existing node')
        value=value[part]
    return value


def kind(value):
    return 'object' if type(value) is dict else 'array' if type(value) is list else 'scalar'


def read(app,account,snapshot,args,pool):
    from .access import policy
    app.host.kp(account)
    require(snapshot[0]['facts'].get('sessionAccess',{}).get('level')=='administrator','TOOL_FORBIDDEN')
    require(policy(app.repository)['allowDataQueries'],'DATA_QUERIES_DISABLED')
    require(app.host.state()['aiControl']['settings']['externalSources']['kp'],'EXTERNAL_SCOPE_DISABLED')
    require(Draft202012Validator(READ_SCHEMA).is_valid(args),'INPUT_INVALID')
    artifact=snapshot[2];file=args['file'];path=args.get('path',[])
    require(file in artifact['data'],'NOT_VISIBLE')
    document=artifact['data'][file];value=node(document,path);offset=args.get('offset',0);limit=args.get('limit',12)
    bound={'revision':artifact['revision'],'file':file,'fileDigest':digest(document),'path':path,'targetDigest':digest(value)}
    ref=digest(bound)
    result={**bound,'editRef':ref,'type':kind(value),'notice':'Only this node was read. Omitted file fields remain intact when using explicit dataEdits. This is not an execution or approval receipt.'}
    if type(value) is list:
        require(offset<=len(value),'INPUT_INVALID')
        result.update(value=copy.deepcopy(value[offset:offset+limit]),total=len(value),offset=offset,
            nextOffset=offset+limit if offset+limit<len(value) else None,complete=offset==0 and len(value)<=limit)
        result['positions']=[{'zeroBasedIndex':i,'path':path+[i]} for i in range(offset,min(offset+limit,len(value)))]
        result['notice']+=' positions are JSON zero-based indexes, not runtime item numbers or instance IDs; use the author-declared mapping for command arguments.'
    elif len(canonical(value))<=20*1024:
        require(offset==0,'INPUT_INVALID');result.update(value=copy.deepcopy(value),complete=True)
    else:
        require(type(value) is dict,'QUERY_RESULT_LIMIT','Read a smaller node')
        keys=sorted(value);require(offset<=len(keys),'INPUT_INVALID')
        result.update(keys=[{'key':k,'type':kind(value[k]),**({'count':len(value[k])} if type(value[k]) in (list,dict) else {})} for k in keys[offset:offset+limit]],
            total=len(keys),offset=offset,nextOffset=offset+limit if offset+limit<len(keys) else None,complete=False)
    require(len(canonical(result))<=28*1024,'QUERY_RESULT_LIMIT','Use a smaller limit or more specific path')
    # An old page cannot upgrade replacement authority. Only a complete returned
    # value permits replace/remove; append/add remain guarded against the full base.
    pool[ref]={**bound,'complete':result['complete'] or pool.get(ref,{}).get('complete',False)}
    return result


def compile_edits(change_set,edits,artifact,pool):
    require(Draft202012Validator(EDITS_SCHEMA).is_valid(edits),'DATA_EDITS_INVALID','Use the explicit dataEdits operation schema',path='/dataEdits')
    require(len(canonical(edits))<=64*1024,'DATA_EDITS_LIMIT',path='/dataEdits')
    output=copy.deepcopy(change_set);documents={};targets=[];proofs=[];appends={};array_keys={}
    for index,edit in enumerate(edits):
        error_path='/dataEdits/'+str(index)
        bound=pool.get(edit['ref']);require(bound,'DATA_EDIT_REFERENCE_UNVERIFIED','Read the target with pack_read_config_data in this generation first',path=error_path+'/ref')
        file=bound['file'];path=bound['path'];op=edit['op']
        require(artifact['revision']==bound['revision'] and file in artifact['data'] and digest(artifact['data'][file])==bound['fileDigest'] and digest(node(artifact['data'][file],path))==bound['targetDigest'],
            'DATA_EDIT_BASELINE_STALE','Read the current baseline again',path=error_path)
        require(file not in change_set['data'],'DATA_EDIT_MIXED_REPLACEMENT','Omit this file from changeSet.data when using dataEdits',path=error_path)
        target=path+[edit['key']] if op=='add' else path
        original=node(artifact['data'][file],path);array_append=op in ('append','append_value') and type(original) is list
        append_key=(file,tuple(path))
        write_target=path+[len(original)+appends.get(append_key,0)] if array_append else target
        for previous_file,previous_path,previous_op in targets:
            if previous_file==file and (write_target[:len(previous_path)]==previous_path or previous_path[:len(write_target)]==write_target):
                require(not array_append and op==previous_op=='append' and write_target==previous_path,'DATA_EDIT_OVERLAP','Overlapping mutations must be separated or reduced to one explicit edit',path=error_path)
        targets.append((file,write_target,op))
        if file not in documents:documents[file]=copy.deepcopy(artifact['data'][file])
        document=documents[file];value=node(document,path)
        if op=='append_value':
            require(type(value) is list,'DATA_EDIT_TARGET_INVALID','append_value requires an array node',path=error_path)
            value.append(copy.deepcopy(edit['value']));appends[append_key]=appends.get(append_key,0)+1
        elif op=='append':
            new=edit['value']
            if type(value) is str:
                require(path and bound['complete'] and type(new) is str and 'keyField' not in edit,'DATA_EDIT_TARGET_INVALID','String append needs a complete non-root string read and a string value',path=error_path)
                node(document,path[:-1])[path[-1]]=value+new
            else:
                key=edit.get('keyField')
                require(type(value) is list and type(new) is dict and key in new and type(new[key]) in (str,int) and type(new[key]) is not bool and
                    all(type(item) is dict and key in item and type(item[key])==type(new[key]) for item in value),'DATA_EDIT_TARGET_INVALID','Array append needs objects with a consistent unique keyField; use string append only on a string node',path=error_path)
                keys=[digest(item[key]) for item in value]
                require(len(set(keys))==len(keys) and digest(new[key]) not in keys,'DATA_EDIT_KEY_CONFLICT','The complete array already contains this key or has ambiguous keys',path=error_path)
                value.append(copy.deepcopy(new));appends[append_key]=appends.get(append_key,0)+1
                array_keys[(*append_key,key)]=type(new[key])
        elif op=='add':
            require(type(value) is dict and edit['key'] not in value,'DATA_EDIT_TARGET_INVALID','add requires a missing object key',path=error_path)
            value[edit['key']]=copy.deepcopy(edit['value'])
        else:
            require(path and bound['complete'],'DATA_EDIT_INCOMPLETE_READ','Read the complete non-root node before replace/remove; append does not need full-array pagination',path=error_path)
            parent=node(document,path[:-1]);key=path[-1]
            if op=='remove':
                require(type(parent) is dict,'DATA_EDIT_TARGET_INVALID','Array element removal is unsupported; no index shifting is implicit',path=error_path)
                del parent[key]
            else:parent[key]=copy.deepcopy(edit['value'])
        proofs.append({'file':file,'path':target,'op':op,'baseRevision':bound['revision'],'fileDigest':bound['fileDigest'],'targetDigest':bound['targetDigest']})
    # A later sibling edit must not introduce a duplicate ID into an array that
    # was already appended. Validate the combined candidate, in either order.
    for (file,path,key),key_type in array_keys.items():
        values=node(documents[file],path)
        require(all(type(v) is dict and key in v and type(v[key]) is key_type for v in values),'DATA_EDIT_KEY_CONFLICT')
        keys=[digest(v[key]) for v in values]
        require(len(keys)==len(set(keys)),'DATA_EDIT_KEY_CONFLICT','The combined edits introduce duplicate array keys',path='/dataEdits')
    output['data'].update(documents)
    return output,proofs
