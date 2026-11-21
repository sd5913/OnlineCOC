"""Package ASGI error paths and real loopback refusal, without a formal room."""
import asyncio
import io
import json
import secrets
import socket
import sys
import urllib.error
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import httpx

PACK=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PACK/'tools'))
from client import Client,HostError,stateless_cookies
from launch import create_app


async def main():
    output=PACK/'tests/output'/('local-errors-'+secrets.token_hex(4));output.mkdir(parents=True)
    report={'checkedAt':datetime.now().astimezone().isoformat(),'checks':[],'externalModelCalls':0,'realSaveChanged':False,'evidenceDirectory':output.relative_to(PACK).as_posix()}
    try:
        failure=[None]
        def client(cookie):raise failure[0]
        runtime=SimpleNamespace(origin='http://testserver',backend='http://127.0.0.1:1',data=output,client=client,observe_request=lambda *a:None)
        app=create_app(runtime)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=runtime.origin) as browser:
            cases=[('timeout',TimeoutError('private detail'),503,'HOST_TIMEOUT'),('connect',ConnectionRefusedError('private detail'),503,'HOST_UNREACHABLE'),('file',FileNotFoundError('private secret path'),500,'LOCAL_IO_ERROR'),('protocol',httpx.RemoteProtocolError('private detail'),502,'HOST_PROTOCOL_ERROR'),('http',HostError({'code':'STORAGE_UNAVAILABLE','httpStatus':503}),503,'STORAGE_UNAVAILABLE')]
            for name,error,status,code in cases:
                failure[0]=error
                res=await browser.get('/package/state');value=res.json()
                assert res.status_code==status and value['code']==code,value
                assert value['operation']=='package/state' and len(value['traceId'])==32 and value['requestId'],value
                assert '恢复原行动' not in value['message'] and 'private' not in res.text,res.text
                report['checks'].append(name+'：保留类型、HTTP状态及查询定位，不误报恢复写行动')
            failure[0]=TimeoutError('never expose request body')
            res=await browser.post('/package/action',headers={'Origin':runtime.origin},json={'id':'action-018','operation':'location.reveal','args':{'password':'do-not-log'}});value=res.json()
            assert value['requestId']=='action-018' and value['operation']=='location.reveal' and '核对原行动回执' in value['message'],value
            assert 'do-not-log' not in (output/'request-errors.log').read_text(encoding='utf-8')
            assert value['traceId'] in (output/'request-errors.log').read_text(encoding='utf-8')
            report['checks'].append('写入超时显示原行动定位与核对回执要求，安全诊断落盘不含输入正文')
            failure[0]=HostError({'code':'NOT_VISIBLE','httpStatus':403})
            res=await browser.get('/package/state');assert res.status_code==403 and res.json()['code']=='NOT_VISIBLE',res.text
            report['checks'].append('明确HTTP权限拒绝保留403，不改判为网络未知')
        class Opener:
            def open(self,*args,**kwargs):raise urllib.error.HTTPError('http://local/api/v1/view',500,'error',{},io.BytesIO(b'private upstream text'))
        c=Client.__new__(Client);c.base='http://local';c.csrf=None;c.opener=Opener()
        try:c.request('/view');raise AssertionError('expected HTTP failure')
        except HostError as error:
            assert error.response['httpStatus']==500 and error.response['code']=='HOST_HTTP_ERROR',error.response
            assert 'private upstream text' not in str(error)
        report['checks'].append('Python包客户端保留非JSON HTTP500，不退化成400参数错误或丢状态')
        with socket.socket() as guard:guard.bind(('127.0.0.1',0));port=guard.getsockname()[1]
        try:Client('http://127.0.0.1:'+str(port),'fixture','fixture');raise AssertionError('expected connection refusal')
        except HostError as error:assert error.response['code']=='HOST_UNREACHABLE' and error.response['httpStatus']==503,error.response
        report['checks'].append('真实本机关闭端口连接拒绝稳定识别，无正式宿主参与')
        failures=[(httpx.ReadTimeout('private secret'),503,'HOST_TIMEOUT'),
                  (httpx.ConnectError('private secret'),503,'HOST_UNREACHABLE'),
                  (httpx.RemoteProtocolError('private secret'),502,'HOST_PROTOCOL_ERROR')]
        for injected,status,code in failures:
            def handler(request):raise injected
            with httpx.Client(transport=httpx.MockTransport(handler),cookies=stateless_cookies()) as transport:
                pooled=Client.__new__(Client);pooled.base='http://local';pooled.csrf='csrf';pooled.cookie='sid=player1';pooled.transport=transport
                try:pooled.request('/view');raise AssertionError('expected pooled failure')
                except HostError as error:
                    assert error.response['code']==code and error.response['httpStatus']==status,error.response
                    assert 'private secret' not in str(error)
        report['checks'].append('共享同步连接池的超时、拒连和协议错误保留安全分类')
        def handler(request):
            assert request.headers['cookie']=='sid=player1' and request.headers['x-csrf-token']=='csrf'
            return httpx.Response(500,text='private response',headers={'Set-Cookie':'sid=foreign; Path=/'})
        with httpx.Client(transport=httpx.MockTransport(handler),cookies=stateless_cookies()) as transport:
            pooled.transport=transport
            try:pooled.request('/view');raise AssertionError('expected pooled HTTP failure')
            except HostError as error:
                assert error.response['httpStatus']==500 and error.response['code']=='HOST_HTTP_ERROR'
                assert 'private response' not in str(error)
            assert not list(transport.cookies.jar)
        report['checks'].append('共享连接显式转发本请求Cookie和CSRF、拒绝储存响应Cookie、保留非JSON HTTP500')
        report['passed']=True
    except Exception as error:report.update(passed=False,error=repr(error))
    report['passedCount']=len(report['checks']);canonical=PACK/'tests/local-errors-results.json'
    if canonical.exists():
        old=json.loads(canonical.read_text(encoding='utf-8'));report['previousRuns']=[*old.get('previousRuns',[]),{k:old.get(k) for k in ('passed','error','checks','evidenceDirectory')}]
    for p in (canonical,output/'report.json'):p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('passed','passedCount','error','evidenceDirectory')},ensure_ascii=True));return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(asyncio.run(main()))
