"""Display-only response controls. A choice never carries an executable command."""
from jsonschema import Draft202012Validator
from .errors import require
from .references import TOKEN

def parse_answer(content):
    from .contracts import loads
    from .errors import AiError
    import re
    require(isinstance(content,str),'MODEL_JSON_INVALID',path='/')
    fenced=re.fullmatch(r'\s*```(?:json)?\s*\n([\s\S]*?)\n```\s*',content)
    try:output=loads(fenced[1] if fenced else content)
    except AiError:raise AiError('MODEL_JSON_INVALID',path='/') from None
    require(type(output) is dict,'MODEL_OBJECT_REQUIRED',path='/')
    require(output.get('kind') in ('plan','draft','clarification','batch'),'MODEL_KIND_INVALID',path='/kind')
    require(isinstance(output.get('text'),str) and 1<=len(output['text'])<=8000,'MODEL_TEXT_INVALID',path='/text')
    required={'kind','text'}|({'changeSet'} if output['kind']=='draft' else {'actions'} if output['kind']=='batch' else set())
    require(required<=set(output)<=required|{'choices'}|({'dataEdits'} if output['kind']=='draft' else set()),'MODEL_FIELDS_INVALID',path='/')
    return output

CHOICES = {'type':'object','additionalProperties':False,'required':['prompt','options'],'properties':{
    'prompt':{'type':'string','minLength':1,'maxLength':200},
    'options':{'type':'array','minItems':2,'maxItems':6,'items':{'type':'object','additionalProperties':False,
        'required':['id','label','text'],'properties':{
            'id':{'type':'string','pattern':'^[a-zA-Z0-9_-]{1,40}$'},
            'label':{'type':'string','minLength':1,'maxLength':60},
            'text':{'type':'string','minLength':1,'maxLength':800}}}}}}


def validate_choices(value):
    require(Draft202012Validator(CHOICES).is_valid(value),'MODEL_CHOICES_INVALID')
    options=value['options']
    require(value['prompt'].strip() and all(o['label'].strip() and o['text'].strip() for o in options)
        and len({o['id'] for o in options})==len(options),'MODEL_CHOICES_INVALID')


def validate_answer(output, issued):
    texts=[output['text']]
    if 'choices' in output:
        require(output['kind'] in ('plan','clarification'),'MODEL_CHOICES_INVALID')
        validate_choices(output['choices'])
        texts += [output['choices']['prompt']]+[v for o in output['choices']['options'] for v in (o['label'],o['text'])]
    import re
    for text in texts:
        found=list(TOKEN.finditer(text))
        require(len(re.findall(r'\[\[(?:config|entity|data|chat|event|ruling|knowledge):',text))==len(found),'REFERENCE_INVALID')
        require(all(m.group() in issued for m in found),'REFERENCE_UNVERIFIED')
