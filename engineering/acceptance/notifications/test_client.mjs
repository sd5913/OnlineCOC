import assert from 'node:assert/strict';
import test from 'node:test';
import {Client} from '../../client-sdk/client.js';

function clientWith(request) {
  const client = new Client({request});
  client.csrf = 'test-csrf'; client.connected = true;
  client.view = {roomId:'demo',runId:'run',authorityEpoch:'epoch',catalog:{revision:'catalog',rulesetRevision:'rules'},entities:{}};
  return client;
}

test('notification paging uses authenticated read transport', async () => {
  const calls=[];
  const client=clientWith(async (...args)=>{calls.push(args);return {items:[],nextAfter:17,hasMore:false};});
  assert.deepEqual(await client.notifications({after:17,limit:2}),{items:[],nextAfter:17,hasMore:false});
  assert.deepEqual(calls[0],['notifications?after=17&limit=2',undefined]);
  await client.notifications();
  assert.equal(calls[1][0],'notifications?after=0&limit=50');
});

test('acknowledgement is an idempotent CSRF protected host command', async () => {
  const calls=[];
  const client=clientWith(async (...args)=>{calls.push(args);return {status:'committed'};});
  await client.ackNotification('a'.repeat(64),'ack-1');
  await client.ackNotification('a'.repeat(64),'ack-1');
  assert.equal(calls[0][0],'commands');
  assert.equal(calls[0][1].csrf,'test-csrf');
  assert.equal(calls[0][1].body.payload.op,'notification.ack');
  assert.deepEqual(calls[0][1].body.payload.args,{notificationId:'a'.repeat(64)});
  assert.deepEqual(calls[0],calls[1]);
  await assert.rejects(client.ackNotification('b'.repeat(64),'ack-1'),/COMMAND_ID_CONFLICT/);
});

for (const operation of ['list','ack']) test(`late ${operation} response cannot cross account reset`, async () => {
  let resolve;
  const client=clientWith(()=>new Promise(r=>{resolve=r;}));
  const pending=operation==='list'?client.notifications():client.ackNotification('a'.repeat(64),'ack');
  const rejected=assert.rejects(pending,/SESSION_CHANGED/);
  client.resetSession();resolve({items:[{text:'private old recipient'}]});await rejected;
});
