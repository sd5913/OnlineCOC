"""Bounded pack-declared references over already authorized entity query rows."""
import copy
import math
from .contracts import canonical,digest
from .data_edits import node
from .errors import AiError


def attach(pack,snapshot,value,*,administrator,kp_external):
    if not administrator or not kp_external:return value
    path=pack.contract['contextMapping'].get('gameTerms')
    if not path or not any(s['path']==path and s['visibility']=='kp' for s in pack.contract['sources']):return value
    terms=pack.json(path)
    if not isinstance(terms,dict):return value
    declarations=terms.get('runtimeReferences',[])
    if not isinstance(declarations,list) or len(declarations)>8:return value
    output=copy.deepcopy(value);facts=snapshot[0]['facts'];artifact=snapshot[2]
    for item in output.get('items',[]):
        entity=item.get('data',{})
        if item.get('ref',{}).get('kind')!='entity' or item.get('authority')!='host-state' or not isinstance(entity,dict) or not isinstance(entity.get('numbers'),dict):continue
        for declaration in declarations:
            try:
                if not isinstance(declaration['configurationIds'],list) or entity.get('configurationId') not in declaration['configurationIds']:continue
                slots=declaration['slots'];base=declaration['indexBase'];file=declaration['dataFile'];array_path=declaration['arrayPath']
                if type(base) is not int or base not in (0,1) or not isinstance(slots,list) or len(slots)>128:continue
                definitions=node(artifact['data'][file],array_path)
                if not isinstance(definitions,list):continue
                rows=[]
                for slot in slots:
                    index=entity['numbers'].get(slot['definitionField']);quantity=entity['numbers'].get(slot['quantityField'])
                    if type(slot['slot']) is not int or type(index) not in (int,float):continue
                    if type(index) is float and (not math.isfinite(index) or not index.is_integer()):continue
                    index=int(index)
                    if index<base or index-base>=len(definitions):continue
                    definition=definitions[index-base]
                    if not isinstance(definition,dict):continue
                    rows.append({'slot':slot['slot'],'definitionIndex':index,'definitionId':definition.get(declaration['idField']),
                        'label':definition.get(declaration['labelField']),'remainingQuantity':quantity,
                        'sourceFields':{'definition':slot['definitionField'],'quantity':slot['quantityField']}})
                projection={'entityId':entity['instanceId'],'source':{'file':file,'path':array_path,'revision':artifact['revision']},'slots':rows}
                if len(canonical(projection))>8192:continue
                item.setdefault('referenceProjections',[]).append(projection)
                facts.setdefault('runtimeReferenceProjections',{})[entity['instanceId']]=projection
                proof={'file':file,'path':array_path,'revision':artifact['revision'],'fileDigest':digest(artifact['data'][file]),'targetDigest':digest(definitions)}
                reads=facts.setdefault('configDataReads',[])
                if proof not in reads:reads.append(proof)
            except (AiError,KeyError,TypeError,IndexError,ValueError):continue
    return output
