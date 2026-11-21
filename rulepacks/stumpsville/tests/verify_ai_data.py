"""Real room and package evidence integration, isolated data and offline model."""
import json
import secrets
import time
from harness import PACK, running, provision
from verify_integrations import provider, ai, result


def main():
    output=PACK/'tests/output'/('ai-data-'+secrets.token_hex(4));output.mkdir(parents=True)
    checks=[]
    with provider(output) as (config,calls), running('ai-data',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
        kp,p1,p2=provision(runtime,password)
        result(ai(kp,'ai.access.update',{'revision':1,'allowPlayerChat':True,'autoApproveBatches':False}))
        result(ai(kp,'ai.settings.update',{'enabled':True,'profileId':'offline','externalSources':{'public':True,'private':True,'kp':False},'auto':{'enabled':False,'channelIds':[],'prefix':'!ai '}}))
        channel='sv-scene-'+str(p1.state()['character']['numbers']['location'])
        sent=p1.action('chat',{'operation':'chat.message.send','input':{'channelId':channel,'text':'我想观察门锁。'}})
        # Player conversation uses the package's authorized chat API. The AI
        # data-query API has a separate strict-player knowledge boundary.
        page=p1.request('/package/chat/history',{'channelId':channel,'limit':50})
        msg=next(x for x in page['items'] if x['text']=='我想观察门锁。')
        ref={k:msg[k] for k in ('channelId','messageId','revision','sequence')}
        pending=p1.action('request',{'kind':'free','text':'观察门锁','manual':True,'sourceMessages':[ref]})
        kp.action('resolve',{'requestId':pending['requestId'],'approve':True,'reason':'可以观察，无需检定'})
        events=kp.request('/api/v1/ai/data/search',{'types':['ruling']})['items']
        assert events,events
        bundles=kp.request('/api/v1/ai/data/case',{'refs':[e['ref'] for e in events]})['items']
        chosen=next(x for x in bundles if x['data']['messages'])
        assert chosen['data']['messages'][0]['text']=='我想观察门锁。'
        assert chosen['data']['rulings'][0]['outcome']=='allow'
        assert chosen['data']['executions'][0]['status']=='none'
        checks.append('真实消息→申请→KP叙事裁决；无执行不伪造成功')
        denied=p2.request('/api/v1/ai/data/case',{'refs':[chosen['ref']]},allow_error=True)
        assert denied.get('code')=='PERMISSION_DENIED',denied
        checks.append('其他玩家不可读取裁决资料')
        refs=kp.request('/api/v1/ai/references?kind=ruling&q=')['items']
        selection=next(x for x in refs if x['id']==chosen['ref']['id'])
        req=result(ai(kp,'ai.request.create',{'sourceKind':'manual','text':'解释这次裁决 '+selection['token']}))
        result(ai(kp,'ai.request.dispatch',req))
        for _ in range(100):
            tasks=kp.request('/api/v1/ai/tasks')['items']
            task=next(t for t in tasks if t['requestId']==req['requestId'])
            if task['status'] not in ('queued','generating','received'):break
            time.sleep(.05)
        assert task['status']=='review_ready',task
        assert calls and '我想观察门锁' in json.dumps(calls[-1],ensure_ascii=False)
        checks.append('公开CLI安装适配器、语义引用与离线模型咨询闭环')
        p1.action('chat',{'operation':'chat.message.edit','input':{'channelId':channel,'messageId':msg['messageId'],'revision':msg['revision'],'text':'更改后的描述'}})
        stale=kp.request('/api/v1/ai/data/case',{'refs':[chosen['ref']]},allow_error=True)
        assert stale.get('code')=='SOURCE_STALE',stale
        checks.append('消息修改使旧事件资料与模型来源失效')
    report={'passed':checks,'model':'isolated-offline','realSavesModified':False}
    (PACK/'tests/ai-data-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
