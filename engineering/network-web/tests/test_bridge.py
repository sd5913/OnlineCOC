import copy
import pytest
from onlinecoc_p2p.common import Fault
from onlinecoc_web.bridge import validate_bridge, service_call, service_config


def contract():
    return {'version':1,'service':[{'path':'package/state','method':'GET','query':{'locale':['zh-CN','en']}}], 'storage':['sv.locale','sv.desktop.*']}


def test_bridge_declaration_and_explicit_identity():
    bridge=validate_bridge(contract())
    descriptor={'package':{'id':'p','version':'1'},'bridge':bridge}
    assert service_config({'packageService':{'version':1,'url':'http://127.0.0.1:1234','packageId':'p','packageVersion':'1'}},descriptor)=='http://127.0.0.1:1234'
    assert service_call(descriptor,{'path':'package/state','query':{'locale':'en'}})==('package/state','GET',{'locale':'en'},None)
    with pytest.raises(Fault):service_config({},descriptor)
    with pytest.raises(Fault):service_config({'packageService':{'version':1,'url':'https://example.com','packageId':'p','packageVersion':'1'}},descriptor)
    with pytest.raises(Fault):service_config({'packageService':{'version':1,'url':'http://127.0.0.1:1234','packageId':'another','packageVersion':'1'}},descriptor)


@pytest.mark.parametrize('params',[
    {'path':'package/state','query':{'preview':'kp'}}, {'path':'package/state','query':{'locale':['en']}},
    {'path':'package/state','url':'http://127.0.0.1:9999'}, {'path':'package/bundle'},
    {'path':'package/state/../../setup'}, {'path':'package/state','method':'POST','body':{}},
    {'path':'package/state','body':{'cookie':'fake'}},
])
def test_service_rejects_undeclared_routes_and_parameters(params):
    with pytest.raises(Fault):service_call({'bridge':contract()},params)


def test_descriptor_does_not_accept_wildcard_routes_or_storage_root():
    for mutate in (lambda d:d.update(version=99),lambda d:d.update(storage=['*']),lambda d:d['service'][0].update(path='*'),lambda d:d['service'].append(copy.deepcopy(d['service'][0]))):
        value=contract();mutate(value)
        with pytest.raises(Fault):validate_bridge(value)
