"""ISSUE-017: readable history, explicit business identity and queue organization."""
import copy
import pytest
from onlinecoc_ai.contracts import digest
from onlinecoc_ai.errors import AiError
from test_entrypoints import application, command, committed
from test_coordinator import setup
from test_access_batches import batch
from test_known_answers import item


def test_ruling_keeps_authorized_old_body_after_success(application):
    app=application;b=batch(app)
    committed(command(app,'ai.ruling.decide',{'rulingId':'batch:'+b['batchId'],'digest':b['digest'],'decision':'approve'}))
    row=app.rulings.list('kp')['items'][0]
    assert row['status']=='completed' and row['summary']==b['summary']
    assert row['actions']==b['actions'] and row['receipts'][0]['receipt']['status']=='committed'
    assert row['historicalReadOnly'] and row['sourceState']=='stale' and not row['canDecide']


@pytest.mark.parametrize('change,readable',[('append',True),('value',True),('delete',False),('hidden',False)])
def test_config_history_reads_preserve_authorized_nodes(application,change,readable):
    from test_data_edits import install_game
    from onlinecoc_ai.sandbox import stage
    from onlinecoc_ai.history import assess
    app=application;install_game(app)
    context=app.proposals.snapshot('kp')[0];room=app.host.state()
    old=room['artifacts'][room['activeRuleset']];data=copy.deepcopy(old['data'])
    context['facts']['configDataReads']=[{'file':'game.json','path':['items'],'targetDigest':digest(data['game.json']['items'])}]
    if change=='append':data['game.json']['items'].append({'id':'new','name':'新物品'})
    if change=='value':data['game.json']['items'][0]['name']='改名'
    if change=='delete':data['game.json']['items'].pop(0)
    if change=='hidden':room['members']['kp']['authorizationEpoch']+=1
    artifact=stage(old['sources'],data);room['artifacts'][artifact['revision']]=artifact;room['activeRuleset']=artifact['revision'];app.host.commit(room)
    if readable:assert assess(app.host,app.repository,room,context) in ('SOURCE_STALE','BASELINE_STALE')
    else:
        with pytest.raises(Exception):assess(app.host,app.repository,room,context)


@pytest.mark.parametrize('legacy',[False,True])
def test_player_reference_does_not_dump_actions_into_chat(legacy):
    from onlinecoc_ai.known_answers import register,render,reference_token,format_data,format_legacy
    record=item();record['data']={'name':'奶酪机关','description':'已知的连接说明','actions':[{'label':'操作'+str(i),'choices':[{'process':'长执行流程'*50}]} for i in range(10)]}
    pool={};issued=register(pool,[record])
    text=(format_legacy('观察记录 · '+reference_token(record['ref'])+'\n\n'+format_data(record['data'])) if legacy else
        render({'evidence':[issued[0]['evidenceId']],'next':'none'},pool)['text'])
    assert '奶酪机关' in text and reference_token(record['ref']) in text
    assert '长执行流程' not in text and '行动选项' not in text and len(text)<700


def new_batch(app,sid,*,related=None,text='后续明确需求',name='后续名称',key=None):
    args={'sessionId':sid,'text':text,**({'replyToRequestId':related} if related else {}),**({'submissionKey':key} if key else {})}
    result=committed(command(app,'ai.session.submit',args));request=app.repository.state()['requests'][result['requestId']]
    snapshot,_=app.coordinator.context.capture('kp',request)
    actions=[{'target':'host','op':'entity.patch','args':{'id':'actor-one','name':name}}]
    bid=app.batches.create('kp',request,actions,text,snapshot[0])
    return app.repository.state()['settings']['batches'][bid]


def row(app,target):return next(i for i in app.rulings.list('kp')['items'] if i['rulingId']==target)


def archive(app,item,archived=True,who='kp'):
    return command(app,'ai.queue.archive',{'targetId':item['queueTargetId'],'digest':item['queueDigest'],'archived':archived,**({'reason':'已失效的旧申请'} if archived else {})},who)


def test_explicit_followup_replaces_pending_without_losing_original(application):
    app=application;first=batch(app);second=new_batch(app,first['sessionId'],related=first['requestId'])
    old=row(app,'batch:'+first['batchId']);new=row(app,'batch:'+second['batchId'])
    assert old['queueStatus']=='superseded' and not old['canDecide']
    assert old['summary']==first['summary'] and old['actions']==first['actions'] and old['status']=='pending'
    assert old['supersededBy']==new['rulingId'] and old['rulingId'] in new['supersedes']
    assert new['queueStatus']=='active' and new['canDecide']
    assert command(app,'ai.batch.approve',{'batchId':first['batchId'],'digest':first['digest']})['code']=='QUEUE_ITEM_INACTIVE'
    assert command(app,'ai.ruling.decide',{'rulingId':old['rulingId'],'digest':old['digest'],'decision':'approve'})['code']=='QUEUE_ITEM_INACTIVE'


def test_same_session_and_same_text_without_relationship_remain_separate(application):
    app=application;first=batch(app);second=new_batch(app,first['sessionId'],text='修改名称')
    a=row(app,'batch:'+first['batchId']);b=row(app,'batch:'+second['batchId'])
    assert a['correlationId']!=b['correlationId'] and a['queueStatus']==b['queueStatus']=='active'


def test_pending_request_does_not_replace_candidate_before_checks(application):
    app=application;first=batch(app)
    committed(command(app,'ai.session.submit',{'sessionId':first['sessionId'],'text':'请修正','replyToRequestId':first['requestId']}))
    assert row(app,'batch:'+first['batchId'])['queueStatus']=='active'


def test_submission_key_replays_once_and_rejects_changed_payload(application):
    app=application;sid=committed(command(app,'ai.session.create',{'title':'幂等'}))['sessionId']
    args={'sessionId':sid,'text':'一项任务','submissionKey':'one-user-click'}
    a=committed(command(app,'ai.session.submit',args));b=committed(command(app,'ai.session.submit',args))
    assert a==b and len(app.sessions.get('kp',sid)['items'])==1
    assert command(app,'ai.session.submit',{**args,'text':'另一项任务'})['code']=='SUBMISSION_KEY_CONFLICT'


def test_cross_session_reply_is_rejected(application):
    app=application;first=batch(app);sid=committed(command(app,'ai.session.create',{'title':'另一会话'}))['sessionId']
    assert command(app,'ai.session.submit',{'sessionId':sid,'text':'不属于此会话','replyToRequestId':first['requestId']})['code']=='NOT_VISIBLE'


def test_same_request_cannot_create_two_batches(application):
    app=application;first=batch(app);request=app.repository.state()['requests'][first['requestId']]
    context=app.coordinator.context.capture('kp',request)[0][0]
    assert app.batches.create('kp',request,first['actions'],first['summary'],context)==first['batchId']
    with pytest.raises(AiError,match='REQUEST_CANDIDATE_CONFLICT'):
        app.batches.create('kp',request,first['actions'],'不同草稿',context)
    assert len(app.repository.state()['settings']['batches'])==1


def test_archive_restore_is_versioned_and_keeps_supersession(application):
    app=application;first=batch(app);second=new_batch(app,first['sessionId'],related=first['requestId']);target='batch:'+first['batchId']
    old=row(app,target);assert archive(app,old,who='player1')['code']=='PERMISSION_DENIED'
    assert committed(archive(app,old))['queueStatus']=='archived'
    assert archive(app,old)['code']=='QUEUE_VERSION_CONFLICT'
    current=row(app,target);assert current['canRestore'] and current['archiveReason']=='已失效的旧申请'
    assert committed(archive(app,current,False))['queueStatus']=='superseded'
    assert row(app,target)['supersededBy']=='batch:'+second['batchId']
    app.repository.verify(app.repository.state())


@pytest.mark.parametrize('status',['executing','unknown','partial','completed'])
def test_execution_records_cannot_be_archived_or_auto_replaced(application,status):
    app=application;first=batch(app)
    app.repository.update(lambda s:s['settings']['batches'][first['batchId']].update(status=status))
    new_batch(app,first['sessionId'],related=first['requestId'])
    old=row(app,'batch:'+first['batchId'])
    assert old['status']==status and not old['canArchive'] and 'supersededBy' not in old
    assert archive(app,old)['code']=='QUEUE_ITEM_PROTECTED'


def test_explicit_package_business_key_reuses_review_across_revision_and_category(application):
    from test_review_debug import source
    app=application;a=source(correlationKey='request:business-one')
    one=committed(command(app,'ai.review.create',{'source':a}))
    two=committed(command(app,'ai.review.create',{'source':{**a,'category':'event','id':'event-1','revision':'2','summary':'已更新的同项申请'}}))
    assert one['requestId']==two['requestId'] and one['sessionId']==two['sessionId']
    three=committed(command(app,'ai.review.create',{'source':{**a,'correlationKey':'request:other'}}))
    assert three['requestId']!=one['requestId']


def test_package_without_business_key_does_not_merge_changed_draft(application):
    from test_review_debug import source
    app=application;a=source();a['category']='draft'
    one=committed(command(app,'ai.review.create',{'source':a}));two=committed(command(app,'ai.review.create',{'source':{**a,'revision':'2'}}))
    assert one['requestId']!=two['requestId']


def test_invalid_new_generation_retains_real_failure_without_inventing_body(application):
    from test_history_continuity import history_case
    app=application;sid,task=history_case(app)
    app.repository.update(lambda s:s['tasks'][task['taskId']].update(status='failed',text=None,error='MODEL_JSON_INVALID'))
    app.repository.update(lambda s:s['requests'][task['requestId']].update(status='failed'))
    item=app.sessions.get('kp',sid)['items'][0]
    assert item['status']=='failed' and item['error']=='MODEL_JSON_INVALID' and not item.get('response')


def test_changed_source_after_failure_creates_one_successor_and_retry_reuses_it(application):
    from test_review_debug import source
    app=application;a=source(correlationKey='one-business')
    first=committed(command(app,'ai.review.create',{'source':a}))
    state=app.repository.state();tid=state['settings'].get('dispatch',{}).get(first['requestId'])
    def fail(s):
        s['requests'][first['requestId']]['status']='failed'
        if tid:s['requests'][tid]['status']='failed';s['tasks'][tid].update(status='failed',error='MODEL_JSON_INVALID',lease=None)
    app.repository.update(fail)
    assert committed(command(app,'ai.review.create',{'source':a}))['requestId']==first['requestId']
    changed={**a,'revision':'2','summary':'来源已补充目标'}
    second=committed(command(app,'ai.review.create',{'source':changed}))
    assert second['requestId']!=first['requestId']
    assert committed(command(app,'ai.review.create',{'source':changed}))['requestId']==second['requestId']
    assert app.queue.fields('request:'+first['requestId'])['correlationId']==app.queue.fields('request:'+second['requestId'])['correlationId']


def test_archived_stale_reply_keeps_its_authorized_body(application):
    from test_history_continuity import history_case
    app=application;sid,task=history_case(app)
    item=app.sessions.get('kp',sid)['items'][0]
    committed(archive(app,item))
    after=app.sessions.get('kp',sid)['items'][0]
    assert after['response']==task['text'] and after['historicalReadOnly'] and after['queueStatus']=='archived'
    assert command(app,'ai.request.dispatch',{'requestId':after['requestId']})['code']=='QUEUE_ITEM_INACTIVE'


def test_single_same_request_configuration_candidate_and_inactive_host_approval(application):
    from test_entrypoints import delta
    from test_access_batches import session,submit
    app=application;s=session(app);r=submit(app,s,'修订配置');request=app.repository.state()['requests'][r['requestId']]
    p=app.proposals.create('kp','修订配置',delta(),request=request)
    assert app.proposals.create('kp','修订配置',delta(),request=request)['proposalId']==p['proposalId']
    app.proposals.validate('kp',p['proposalId'],1)
    old=row(app,'proposal:'+p['proposalId']);committed(archive(app,old))
    with pytest.raises(AiError,match='QUEUE_ITEM_INACTIVE'):app.proposals.prepared('kp',p['proposalId'],1)


def test_outstanding_approval_is_protected_from_archive_and_supersession(application):
    from test_entrypoints import delta
    from test_access_batches import session,submit
    app=application;s=session(app);r=submit(app,s,'配置方案');request=app.repository.state()['requests'][r['requestId']]
    p=app.proposals.create('kp','配置方案',delta(),request=request);app.proposals.validate('kp',p['proposalId'],1)
    old=row(app,'proposal:'+p['proposalId'])
    receipt=app.rulings.host_command('kp','durable-approval','ai.proposal.approve',{'proposalId':p['proposalId'],'proposalRevision':1,'explicitHighRiskDigest':old['digest'],'riskDecisions':{risk['id']:'已核对' for risk in old['risks']}})
    assert receipt['status']=='committed',receipt
    new_batch(app,s['sessionId'],related=r['requestId'])
    after=row(app,old['rulingId']);assert not after['canArchive'] and 'supersededBy' not in after


def test_player_text_submission_key_deduplicates_business_request(application):
    from test_access_batches import access,session
    app=application;access(app);s=session(app,'player1')
    args={'sessionId':s['sessionId'],'text':'创作一件装备','submissionKey':'one-click'}
    a=committed(command(app,'ai.player.request',args,'player1'));b=committed(command(app,'ai.player.request',args,'player1'))
    assert a['rulingId']==b['rulingId'] and a['requestId']==b['requestId']
    assert command(app,'ai.player.request',{**args,'text':'另一件装备'},'player1')['code']=='SUBMISSION_KEY_CONFLICT'
