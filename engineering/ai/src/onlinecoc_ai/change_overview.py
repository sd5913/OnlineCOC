"""Bounded display paths computed from the actual complete candidate."""


def pointer(parts):
    return '/'+ '/'.join(str(p).replace('~','~0').replace('/','~1') for p in parts)


def overview(state,baseline,changes,limit=40):
    items=[];total=0;missing=object()
    def add(path,op,value):
        nonlocal total
        total+=1
        if len(items)>=limit:return
        label=next((value[k] for k in ('name','label','title') if isinstance(value,dict) and isinstance(value.get(k),str)),str(path[-1]))
        items.append({'path':pointer(path),'operation':op,'summary':{'add':'新增','replace':'修改','remove':'删除'}[op]+' '+label[:100]})
    def walk(old,new,path):
        if old==new:return
        if old is missing:add(path,'add',new)
        elif new is missing:add(path,'remove',old)
        elif isinstance(old,dict) and isinstance(new,dict):
            for key in sorted(old.keys()|new.keys()):walk(old.get(key,missing),new.get(key,missing),path+[key])
        elif isinstance(old,list) and isinstance(new,list):
            for index in range(max(len(old),len(new))):walk(old[index] if index<len(old) else missing,new[index] if index<len(new) else missing,path+[index])
        else:add(path,'replace',new)
    for change in changes['configurations']:
        old=state['configurations'].get(change['id'],missing)
        new=missing if change['kind']=='remove' else change['value']
        walk(old,new,['configurations',change['id']])
    for field in ('sources','data'):
        for name in sorted(baseline[field].keys()|changes[field].keys()):
            walk(baseline[field].get(name,missing),changes[field].get(name,missing),[field,name])
    return {'total':total,'items':items,'truncated':total>len(items)}
