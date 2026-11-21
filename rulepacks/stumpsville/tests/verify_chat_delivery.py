"""Four-page real local chat latency and concurrent ruling, using frozen engine."""
import argparse,json,secrets,time,statistics,threading
from pathlib import Path
from datetime import datetime
import harness
import launch
from harness import PACK,Account,provision,running
from verify_integrations import provider
from playwright.sync_api import sync_playwright,expect

def dist(values):
    values=sorted(values)
    return {'samples':len(values),'p50Ms':round(statistics.median(values),2),'p95Ms':round(values[min(len(values)-1,int(len(values)*.95))],2),'maxMs':round(max(values),2)}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',default='optimized');parser.add_argument('--source',type=Path,required=True);args=parser.parse_args()
    output=PACK/'tests/output'/('chat-delivery-'+args.label+'-'+secrets.token_hex(4));output.mkdir(parents=True)
    report={'at':datetime.now().astimezone().isoformat(),'label':args.label,'source':str(args.source),'output':str(output),'externalApiCalls':0,'checks':[],'measurements':{}};errors=[]
    original=harness.Runtime;original_root=launch.ROOT;launch.ROOT=args.source.resolve()
    def frozen(options):
        options.host_control_dir=output/'host-control';r=original(options);r.command[2]=str(args.source.resolve()/'engineering/backend/scripts/run.py');return r
    harness.Runtime=frozen
    try:
      with provider(output) as (config,calls),running(data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
        kp,p1,p2=provision(runtime,password)
        for i in range(16):kp.action('chat',{'operation':'chat.message.send','input':{'channelId':'general','text':'聊天历史 '+str(i)}})
        with sync_playwright() as pw:
          browser=pw.chromium.launch(channel='msedge',headless=True);pages=[];expect.set_options(timeout=20000)
          for i,(name,where) in enumerate([('kp','gm/rulings'),('player1','play/scene'),('player2','play/scene'),('kp','gm/room')]):
            page=browser.new_page(viewport={'width':1440,'height':960});page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(runtime.origin+'/sessions/delivery-'+str(i)+'/');page.locator('[name=loginName]').fill(name);page.locator('[name=password]').fill(password);page.get_by_role('button',name='进入冒险',exact=True).click();page.locator('.identity').first.wait_for()
            page.goto(runtime.origin+'/sessions/delivery-'+str(i)+'/#/'+where);pages.append(page)
          sender,receiver=pages[1:3]
          report['fixture']={'chatHistory':16,'pages':4,'visibility':[p.evaluate('document.visibilityState') for p in pages]}
          send_times=[];delivery_times=[];failures=[]
          for i in range(6):
            marker='CHAT-BENCH-'+args.label+'-'+str(i);field=sender.locator('[data-chat-form=general] textarea');field.fill(marker);start=time.perf_counter()
            field.locator('..').locator('[type=submit]').click()
            try:
              expect(field).to_have_value('');send_times.append((time.perf_counter()-start)*1000)
              expect(receiver.locator('.chat-history').first).to_contain_text(marker);delivery_times.append((time.perf_counter()-start)*1000)
            except Exception as e:failures.append({'sample':i,'error':str(e)[:600]})
          report['measurements']={'sendComposerReady':dist(send_times) if send_times else {},'receiverVisible':dist(delivery_times) if delivery_times else {},'failures':failures}
          assert not failures,failures
          report['checks'].append('four real pages deliver six distinct chat messages without transport failure')
          request=p1.action('request',{'kind':'free','manual':True,'text':'CHAT-CONCURRENCY-RULING'})['requestId'];page=pages[0]
          card=page.locator('[data-request-id="'+request+'"]');expect(card).to_be_visible();held=[];chat_requests=[]
          def gate(route):
            body=route.request.post_data_json
            if body and body.get('operation')=='resolve' and not held:held.append(route)
            else:route.continue_()
          page.route('**/package/action*',gate)
          page.on('request',lambda r:chat_requests.append(r.post_data_json) if '/package/action' in r.url and r.method=='POST' and r.post_data_json.get('operation')=='chat' else None)
          card.get_by_role('button',name='拒绝',exact=True).click();page.get_by_role('button',name='拒绝并回复',exact=True).click();expect(page.locator('#toast')).not_to_be_empty()
          assert held,'ruling was not intercepted'
          field=page.locator('[data-chat-form=general] textarea');field.fill('CHAT-WHILE-RULING');field.locator('..').locator('[type=submit]').click();page.wait_for_timeout(350)
          report['chatWhileRulingPending']=bool(chat_requests);report['concurrentToast']=page.locator('#toast').text_content()
          held[0].continue_();page.unroute('**/package/action*',gate)
          if args.label!='baseline':
            assert report['chatWhileRulingPending'],report['concurrentToast'];expect(field).to_have_value('');report['checks'].append('chat submits while an unrelated ruling response is held, with no shared busy rejection')
            # Preserve a newly typed draft while the previous message is in flight.
            draft_hold=[]
            def hold_message(route):
              if route.request.post_data_json.get('operation')=='chat':draft_hold.append(route)
              else:route.continue_()
            sender.route('**/package/action*',hold_message);field=sender.locator('[data-chat-form=general] textarea')
            field.fill('CHAT-DRAFT-FIRST');field.locator('..').locator('[type=submit]').click();expect(sender.locator('[data-chat=recover]').first).to_be_visible()
            field.fill('CHAT-DRAFT-NEXT');assert draft_hold;draft_hold[0].continue_();sender.unroute('**/package/action*',hold_message)
            expect(field.locator('..').locator('[type=submit]')).to_be_enabled();expect(field).to_have_value('CHAT-DRAFT-NEXT')
            report['checks'].append('newly typed draft survives completion of an earlier message')
            # Commit the request, drop only its response, and recover the same ID.
            sent=[]
            def lose_reply(route):
              body=route.request.post_data_json
              if body.get('operation')=='chat':
                sent.append(body);route.fetch();route.abort('failed')
              else:route.continue_()
            sender.route('**/package/action*',lose_reply);field.fill('CHAT-RECEIPT-RECOVERY');field.locator('..').locator('[type=submit]').click()
            expect(field.locator('..').locator('[type=submit]')).to_be_enabled();sender.unroute('**/package/action*',lose_reply)
            expect(sender.locator('[data-chat=recover]').first).to_be_visible();field.fill('CHAT-NEW-UNSENT');field.locator('..').locator('[type=submit]').click()
            expect(sender.locator('#toast')).to_contain_text('请先核对原消息');assert len(sent)==1
            recovery_ids=[]
            sender.on('request',lambda r:recovery_ids.append(r.post_data_json['id']) if '/package/action' in r.url and r.method=='POST' and r.post_data_json.get('operation')=='chat' else None)
            sender.locator('[data-chat=recover]').first.click();expect(sender.locator('[data-chat=recover]').first).to_be_hidden();expect(field).to_have_value('CHAT-NEW-UNSENT')
            assert recovery_ids==[sent[0]['id']],recovery_ids
            found=p1.request('/package/chat/history',{'channelId':'general','limit':100})['items'];assert len([m for m in found if m.get('text')=='CHAT-RECEIPT-RECOVERY'])==1
            report['checks'].append('lost success response blocks new sends and recovers original ID exactly once, preserving the new draft')
            # Host chat history must remain readable while a package write holds its lock.
            done=threading.Event();received=[]
            def read_unlocked():
              try:received.append(p1.request('/package/chat/history',{'channelId':'general','limit':1}))
              finally:done.set()
            with runtime.package.lock:
              worker=threading.Thread(target=read_unlocked);worker.start();unblocked=done.wait(5)
            worker.join(10);assert unblocked and received,'host chat history waited for unrelated package write lock'
            # Lightweight metadata and history retain the host's audience boundary.
            dm=p1.action('chat',{'operation':'chat.direct.open','input':{'accountId':'player2'}})['channelId']
            message=p1.action('chat',{'operation':'chat.message.send','input':{'channelId':dm,'text':'PRIVATE-ORIGINAL'}})
            assert dm not in kp.request('/package/chat/state')['channels']
            assert kp.request('/package/chat/history',{'channelId':dm,'limit':10},True).get('code')
            p1.action('chat',{'operation':'chat.message.edit','input':{'channelId':dm,'messageId':message['messageId'],'revision':1,'text':'PRIVATE-EDITED'}})
            assert p2.request('/package/chat/history',{'channelId':dm,'limit':10})['items'][-1]['text']=='PRIVATE-EDITED'
            p1.action('chat',{'operation':'chat.message.retract','input':{'channelId':dm,'messageId':message['messageId'],'revision':2}})
            assert p2.request('/package/chat/history',{'channelId':dm,'limit':10})['items'][-1]['deleted']
            assert p1.request('/package/chat/history',{'channelId':'sv-scene-999','limit':10},True).get('code')
            p1.action('chat',{'operation':'chat.message.send','input':{'channelId':'sv-party','text':'PARTY-SYNC'}})
            assert any(m.get('text')=='PARTY-SYNC' for m in p2.request('/package/chat/history',{'channelId':'sv-party','limit':10})['items'])
            report['checks'].append('host history bypasses package write lock; metadata/history isolate private and inaccessible scene channels; edit/retract and party delivery work')
          page.screenshot(path=str(output/'ruling-chat.png'),full_page=True)
          browser.close();assert not errors,errors
        assert not calls,'benchmark must not call a model'
      report['passed']=True
    except Exception as e:report.update(passed=False,error=repr(e));raise
    finally:
      harness.Runtime=original;launch.ROOT=original_root;report['pageErrors']=errors
      path=PACK/'tests'/('chat-delivery-'+args.label+'-results.json')
      if path.exists():
        old=json.loads(path.read_text(encoding='utf-8'));report['previousRuns']=old.get('previousRuns',[])+[{k:v for k,v in old.items() if k!='previousRuns'}]
      path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
      print(json.dumps({k:report.get(k) for k in ['passed','error','measurements','chatWhileRulingPending','output']},ensure_ascii=False))
if __name__=='__main__':main()
