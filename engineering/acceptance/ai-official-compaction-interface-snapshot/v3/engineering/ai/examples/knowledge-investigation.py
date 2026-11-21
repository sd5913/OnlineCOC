"""Second, non-location fixture package: individually disclosed witness statements.

Use with tests/fixtures/pack. The AI is optional; KP binds the descriptor and
observes identity on a selected fixture entity. It never auto-imports metadata.
"""
import copy
from onlinecoc.knowledge import HostStateProvider


class WitnessProvider(HostStateProvider):
    def __init__(self):super().__init__({'identity':{'name':'name'}})
    def pin(self,resource,facets,context):
        result=super().pin(resource,facets,context)
        # Only a deliberately authored testimony field; unrelated secrets,
        # solutions and statistics are outside this disclosure facet.
        result['facets']['identity']['testimony']=copy.deepcopy(self._entity(resource,context)['metadata'].get('testimony',''))
        return result


def install(host,path=None):
    descriptor={'policyId':'personal-test','namespace':'witness','providerId':'witness-statements-v1','contractVersion':1,
        'mode':'required-personal','selectors':[{'kind':'entity','configurationPrefix':'fixture.'}],
        'facetSchemas':{'identity':{'schema':{'type':'object','properties':{'name':{'type':'string'},'testimony':{'type':'string'}},
            'required':['name','testimony'],'additionalProperties':False},'modes':['observed_snapshot'],'labelField':'name'}},
        'egress':{key:'filtered' for key in ('view','query','rules','receipts','assets','export','ai')}}
    return host.register_knowledge_provider(descriptor,WitnessProvider())
