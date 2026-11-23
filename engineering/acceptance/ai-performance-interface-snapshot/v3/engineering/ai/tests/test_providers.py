import asyncio
import copy
import json
from pathlib import Path

import httpx
import pytest

from onlinecoc_ai.contracts import loads
from onlinecoc_ai.errors import AiError
from onlinecoc_ai.profiles import initialize, load_profiles, save_profile
from onlinecoc_ai.providers import create_provider
from onlinecoc_ai.providers.base import ProviderError
from onlinecoc_ai.providers.transport import VerifiedBackend


def profile():
    value=loads((Path(__file__).parents[1]/'examples/ai-providers.json').read_bytes())['profiles'][0]
    value['enabled']=True
    return value


def response(content='{"kind":"plan","text":"ok"}', **updates):
    value={'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':content}}],
           'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20}}
    value.update(updates)
    return value


def call(handler, value=None):
    async def run():
        provider=create_provider(value or profile(),transport=httpx.MockTransport(handler),credential_loader=lambda p:'test-only-key')
        try:return await provider.complete([{'role':'system','content':'Return json.'}])
        finally:await provider.close()
    return asyncio.run(run())


def test_deepseek_wire_format_and_secret_stays_in_header():
    seen=[]
    def handler(request):
        body=json.loads(request.content);seen.append(body)
        assert request.url.path=='/chat/completions'
        assert request.headers['authorization']=='Bearer test-only-key'
        assert 'test-only-key' not in request.content.decode()
        return httpx.Response(200,json=response())
    result=call(handler)
    assert seen[0]['thinking']=={'type':'disabled'} and seen[0]['stream'] is False
    assert result.usage['total_tokens']==20 and result.message['content']


def test_compatible_endpoint_omits_vendor_options():
    value=profile();value['adapter']='compatible-chat';value['baseUrl']='https://provider.example/v1'
    def handler(request):
        assert 'thinking' not in json.loads(request.content)
        assert request.url.path=='/v1/chat/completions'
        return httpx.Response(200,json=response())
    call(handler,value)


@pytest.mark.parametrize('status,code,retryable',[(401,'PROVIDER_AUTH_FAILED',False),(403,'PROVIDER_AUTH_FAILED',False),
    (429,'PROVIDER_RATE_LIMITED',True),(500,'PROVIDER_UNAVAILABLE',True),(503,'PROVIDER_UNAVAILABLE',True),
    (302,'PROVIDER_REDIRECT_REJECTED',False),(400,'PROVIDER_REQUEST_INVALID',False),(422,'PROVIDER_REQUEST_INVALID',False),
    (402,'PROVIDER_BALANCE_INSUFFICIENT',False),(404,'PROVIDER_NOT_FOUND',False),
    (408,'PROVIDER_TIMEOUT',True),(413,'PROVIDER_REQUEST_TOO_LARGE',False),(409,'PROVIDER_HTTP_ERROR',False),(204,'PROVIDER_HTTP_ERROR',False)])
def test_http_failures_are_bounded_and_redacted(status,code,retryable):
    with pytest.raises(ProviderError) as error:
        call(lambda request:httpx.Response(status,text='secret test-only-key private data',headers={'Location':'http://127.0.0.1/'}))
    assert error.value.code==code and error.value.retryable==retryable
    assert error.value.http_status==status
    assert 'secret' not in str(error.value) and 'key' not in str(error.value)


@pytest.mark.parametrize('content',['', '   '])
def test_empty_model_content_is_rejected(content):
    with pytest.raises(ProviderError):call(lambda request:httpx.Response(200,json=response(content)))

@pytest.mark.parametrize('content',['{','[]','{"x":1,"x":2}','{"n":NaN}'])
def test_bad_answer_json_keeps_usage_for_coordinator_repair(content):
    from onlinecoc_ai.answers import parse_answer
    reply=call(lambda request:httpx.Response(200,json=response(content)))
    assert reply.usage['total_tokens']==20
    with pytest.raises(AiError):parse_answer(reply.message['content'])


def test_truncation_usage_and_unknown_reasoning():
    for change in ['length','usage','reasoning']:
        value=response()
        if change=='length':value['choices'][0]['finish_reason']='length'
        elif change=='usage':value['usage']['total_tokens']=999
        else:value['choices'][0]['message']['reasoning_content']='private reasoning'
        with pytest.raises(ProviderError):call(lambda request:httpx.Response(200,json=value))


def test_connection_failure_and_total_timeout():
    def disconnect(request):raise httpx.ReadError('secret error text')
    with pytest.raises(ProviderError,match='PROVIDER_UNAVAILABLE'):call(disconnect)
    async def delayed(request):
        await asyncio.sleep(.2)
        return httpx.Response(200,json=response())
    value=profile();value['request'].update(connectTimeoutMs=100,totalTimeoutMs=100)
    with pytest.raises(ProviderError,match='PROVIDER_TIMEOUT'):call(delayed,value)


@pytest.mark.parametrize('url',['file:///x','https://key:password@example.com','https://example.com?key=secret','http://127.0.0.1','https://example.com:99999','https://example.com/\r\nx'])
def test_unsafe_url_is_rejected(url):
    value=profile();value['baseUrl']=url
    with pytest.raises((AiError,ValueError)):create_provider(value)


def test_dns_pinning_blocks_rebinding_and_preserves_original_host():
    async def run():
        calls=[]
        class Backend:
            async def connect_tcp(self,host,*args):calls.append(host);return 'socket'
        async def public(*args):return ['8.8.8.8']
        backend=VerifiedBackend(backend=Backend(),resolver=public)
        assert await backend.connect_tcp('provider.example',443)=='socket'
        assert calls==['8.8.8.8']
        async def private(*args):return ['127.0.0.1']
        backend.resolver=private
        with pytest.raises(ProviderError,match='ENDPOINT_FORBIDDEN'):await backend.connect_tcp('provider.example',443)
        assert calls==['8.8.8.8']
    asyncio.run(run())


def test_local_profile_management_never_stores_key(tmp_path):
    path=tmp_path/'providers.json';initialize(path)
    assert load_profiles(path)['deepseek-main']['enabled'] is False
    value=profile();saved=save_profile(value,path)
    assert saved['revision']==2 and load_profiles(path)['deepseek-main']['revision']==2
    value['apiKey']='do-not-store'
    with pytest.raises(AiError):save_profile(value,path)
    assert 'do-not-store' not in path.read_text(encoding='utf-8')


def test_probe_requires_json_and_a_real_tool_call():
    async def run():
        seen=[]
        def handler(request):
            body=json.loads(request.content);seen.append(body)
            if 'tools' not in body:return httpx.Response(200,json=response('{"ok":true}'))
            value=response(None);value['choices'][0].update(finish_reason='tool_calls',message={'role':'assistant','content':None,
                'tool_calls':[{'id':'probe','type':'function','function':{'name':'connection_probe','arguments':'{}'}}]})
            return httpx.Response(200,json=value)
        provider=create_provider(profile(),transport=httpx.MockTransport(handler),credential_loader=lambda p:'fake-key')
        try:
            result=await provider.probe()
            assert result['jsonProbe']==result['toolProbe']=='passed' and result['usage']['total_tokens']==40
            assert len(seen)==2
        finally:await provider.close()
    asyncio.run(run())


@pytest.mark.parametrize('adapter',['deepseek-chat','compatible-chat'])
@pytest.mark.parametrize('content',['Return only {"ok":true}.','Return JSON only.'])
def test_json_mode_guard_preserves_caller_history_and_tool_envelope(adapter,content):
    value=profile();value['adapter']=adapter
    messages=[{'role':'system','content':content},{'role':'user','content':'Hello'}]
    before=copy.deepcopy(messages);seen=[]
    def handler(request):
        body=json.loads(request.content);seen.append(body)
        # Reproduce the provider's HTTP validation before producing any model text.
        if not any(m['role'] in ('system','user') and 'json' in m['content'].lower() for m in body['messages']):
            return httpx.Response(400,json={'error':{'message':'Prompt must contain json'}})
        assert body['response_format']=={'type':'json_object'}
        return httpx.Response(200,json=response())
    async def run():
        provider=create_provider(value,transport=httpx.MockTransport(handler),credential_loader=lambda _:'test-key')
        try:
            await provider.complete(messages);await provider.complete(messages)
        finally:await provider.close()
    asyncio.run(run())
    assert messages==before and seen[0]==seen[1]
    assert len(seen[0]['messages'])==len(messages)+(0 if 'json' in content.lower() else 1)
