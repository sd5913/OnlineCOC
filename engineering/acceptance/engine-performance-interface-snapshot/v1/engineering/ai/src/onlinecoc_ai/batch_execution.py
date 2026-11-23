"""Host atomic receipts, AI-only transactions, and explicit cross-store limits."""
import copy
from .errors import AiError,require
from .generation import ReadRepository,clone

LOCAL=frozenset(('ai.session.create','ai.session.update','ai.session.delete','ai.memory.create'))
MEMORY=frozenset(('ai.memory.confirm','ai.memory.revoke'))


def item(action,index,status,**extra):
    return {'index':index,'target':action['target'],'op':action['op'],'status':status,**extra}


def diagnostic(exc):
    from .diagnostics import error_code
    code=error_code(exc)
    return {'code':code,'reason':'操作未满足当前权限、引用或版本条件。','path':getattr(exc,'path','')[:300]}


def execution(status,items,scope):
    return {'status':status,'scope':scope,'items':items,
        'committedCount':sum(x['status']=='committed' for x in items),
        'failedCount':sum(x['status']=='failed' for x in items),
        'notExecutedCount':sum(x['status']=='not_executed' for x in items),
        'rolledBackCount':sum(x['status']=='rolled_back' for x in items)}


class AtomicExecution:
    def __init__(self,batches):
        self.batches=batches;self.app=batches.app;self.host=batches.host;self.repository=batches.repository

    def scope(self,actions):
        if all(a['target']=='host' for a in actions):return 'host.room.atomic.v1'
        if all(a['target']=='ai' and a['op'] in LOCAL for a in actions):return 'ai.store.atomic.v1'
        if len(actions)==1 and actions[0]['target']=='ai' and actions[0]['op'] in MEMORY:return 'host.memory.single.v1'
        return 'unsupported'

    def local_preview(self,account,actions):
        room=self.host.state();repo=ReadRepository(self.repository.state());host=copy.copy(self.host)
        host.state=lambda:copy.deepcopy(room)
        def deny(*_,**__):raise AiError('BATCH_UNSUPPORTED','Preview cannot write the host')
        host.commit=host.command=host.commit_memory_fact=deny
        app=clone(self.app,host,repo)
        for name in ('sessions','memory'):setattr(app,name,clone(getattr(self.app,name),host,repo,app))
        items=[];blocked=False
        for index,action in enumerate(actions):
            if blocked:
                items.append(item(action,index,'blocked',code='BATCH_DEPENDENCY_FAILED',reason='前项检查失败，未检查本项。'));continue
            try:
                result=app._execute(account,'preview:'+str(index),action['op'],action['args'])
                items.append(item(action,index,'passed',preview=True,result=result))
            except Exception as exc:
                blocked=True;items.append(item(action,index,'blocked',**diagnostic(exc)))
        return {'status':'blocked' if blocked else 'passed','scope':'ai.store.atomic.v1','checkedAt':self.host.clock(),'items':items}

    def preflight(self,account,actions):
        with self.host.lock,self.repository.lock:
            self.host.kp(account);self.batches.validate_actions(account,actions)
            scope=self.scope(actions)
            if scope=='host.room.atomic.v1':return self.host.preflight_batch(account,actions)
            if scope=='ai.store.atomic.v1':return self.local_preview(account,actions)
            if scope=='host.memory.single.v1':
                action=actions[0];args=action['args']
                try:
                    self.app.memory.transition_fact(account,args['memoryId'],args['revision'],'confirmed' if action['op'].endswith('.confirm') else 'revoked')
                    row=item(action,0,'passed');status='passed'
                except Exception as exc:row=item(action,0,'blocked',**diagnostic(exc));status='blocked'
                return {'status':status,'scope':scope,'checkedAt':self.host.clock(),'items':[row]}
            return {'status':'unsupported','scope':scope,'checkedAt':self.host.clock(),'items':[
                item(a,i,'unsupported',code='BATCH_UNSUPPORTED',reason='此组合跨越宿主与 AI 存储，不能作为一笔原子批次执行。',path=f'/actions/{i}') for i,a in enumerate(actions)]}

    def finish_host(self,account,record,receipt):
        record['batchReceipt']=copy.deepcopy(receipt)
        detail=receipt.get('result')
        if receipt['status'] in ('unknown','pending'):
            record['status']='unknown';record['execution']=execution('unknown',[
                item(a,i,'unknown',commandId=record['executionCommandId']) for i,a in enumerate(record['actions'])],self.scope(record['actions']))
        elif receipt['status']=='rejected' and not isinstance(detail,dict):
            record.update(status='failed',receipts=[],execution=execution('failed',[
                item(a,i,'not_executed',code=receipt.get('code','BATCH_REJECTED'),reason='宿主拒绝该批次，业务指令未提交。')
                for i,a in enumerate(record['actions'])],self.scope(record['actions'])))
        elif self.scope(record['actions'])=='host.memory.single.v1' and receipt['status']=='committed':
            fact=detail.get('memory');action=record['actions'][0]
            require(fact and fact['memoryId']==action['args']['memoryId'],'MEMORY_RESULT_UNKNOWN')
            with self.repository.transaction():
                self.app.memory.mirror_fact(fact)
                record['status']='completed';record['execution']=execution('committed',[item(action,0,'committed',commandId=record['executionCommandId'],result={'memory':fact})],'host.memory.single.v1')
                record['receipts']=[{'id':record['executionCommandId'],'account':account,'target':'host','receipt':copy.deepcopy(receipt)}]
                self.batches._save(record)
            return record
        else:
            require(detail.get('status') in ('committed','failed','rolled_back'),'BATCH_RESULT_INVALID')
            record['execution']=copy.deepcopy(detail)
            record['status']='completed' if detail['status']=='committed' else detail['status']
            record['receipts']=[]
            if record['status']=='completed':
                for row in detail['items']:
                    actual=self.host.receipt(account,row['commandId'])
                    require(actual['status']=='committed','BATCH_RESULT_INVALID')
                    record['receipts'].append({'id':row['commandId'],'account':account,'target':'host','receipt':actual})
        self.batches._save(record);return record

    def run_local(self,account,record):
        actions=record['actions'];rows=[];receipts=[];failed=None
        try:
            with self.repository.transaction():
                for index,action in enumerate(actions):
                    cid='ai-batch:'+record['batchId']+':'+str(index)
                    receipt=self.app._command(account,{'requestId':cid,'authorityEpoch':self.host.epoch,'op':action['op'],'args':action['args']})
                    if receipt['status']!='committed':
                        failed=item(action,index,'failed',commandId=cid,code=receipt.get('code','BATCH_INTERNAL_ERROR'),reason='AI 操作失败，当前事务尚未提交。')
                        raise AiError('LOCAL_BATCH_ABORT')
                    rows.append(item(action,index,'committed',commandId=cid,result=receipt.get('result')))
                    receipts.append({'id':cid,'account':account,'target':'ai','receipt':receipt})
                record.update(status='completed',receipts=receipts,execution=execution('committed',rows,'ai.store.atomic.v1'))
                self.batches._save(record)
            if self.app.coordinator.active:
                task=self.repository.state()['tasks'].get(self.app.coordinator.active_id,{})
                if task.get('status')=='cancelled':self.app.coordinator.loop.call_soon_threadsafe(self.app.coordinator.active.cancel)
            return record
        except Exception:
            if failed is None:
                durable=self.repository.state()['settings']['batches'].get(record['batchId'])
                if durable and durable['status']=='completed':return durable
                record.update(status='unknown',execution=execution('unknown',[item(a,i,'unknown') for i,a in enumerate(actions)],'ai.store.atomic.v1'))
            else:
                for row in rows:row['status']='rolled_back';row.pop('result',None)
                rows.append(failed);rows.extend(item(a,i,'not_executed') for i,a in enumerate(actions) if i>failed['index'])
                status='rolled_back' if failed['index'] else 'failed'
                record.update(status=status,receipts=[],execution=execution(status,rows,'ai.store.atomic.v1'))
            self.batches._save(record);return record

    def run(self,account,record):
        scope=self.scope(record['actions']);record['executionCommandId']='ai-atomic:'+record['batchId']
        record.update(status='executing',executionAccount=account);self.batches._save(record)
        if scope=='ai.store.atomic.v1':return self.run_local(account,record)
        try:
            if scope=='host.memory.single.v1':
                action=record['actions'][0];args=action['args']
                fact,expected=self.app.memory.transition_fact(account,args['memoryId'],args['revision'],'confirmed' if action['op'].endswith('.confirm') else 'revoked')
                receipt=self.host.commit_memory_fact(account,fact,command_id=record['executionCommandId'],expected_revision=expected)
            else:receipt=self.host.execute_batch(account,record['actions'],command_id=record['executionCommandId'])
        except Exception:
            receipt=self.host.receipt(account,record['executionCommandId'])
        return self.finish_host(account,record,receipt)

    def reconcile(self,account,record):
        if self.scope(record['actions'])=='ai.store.atomic.v1':
            # The local business changes and batch terminal state commit together.
            # An interrupted "executing" marker proves no local batch committed.
            record.update(status='failed',execution=execution('failed',[
                item(a,i,'not_executed',code='LOCAL_TRANSACTION_NOT_COMMITTED',reason='AI 单库事务未提交。') for i,a in enumerate(record['actions'])],'ai.store.atomic.v1'))
            self.batches._save(record);return record
        principal=record.get('executionAccount',account)
        return self.finish_host(principal,record,self.host.receipt(principal,record['executionCommandId']))
