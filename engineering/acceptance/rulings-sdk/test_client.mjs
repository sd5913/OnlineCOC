import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

const sdk = await readFile(new URL('../../client-sdk/client.js', import.meta.url), 'utf8');
const {Client} = await import('data:text/javascript;base64,' + Buffer.from(sdk).toString('base64'));

test('legacy review and ruling components have all client methods they call', async () => {
  const client = new Client({});
  for (const name of ['room-panel.js', 'rulings.js', 'debug.js']) {
    const source = await readFile(new URL('../../ai/web/components/' + name, import.meta.url), 'utf8');
    for (const [, method] of source.matchAll(/\bclient\.([A-Za-z_]\w*)\s*\(/g)) {
      assert.equal(typeof client[method], 'function', `${name} requires Client.${method}`);
    }
  }
});

test('ruling reads preserve high-risk digest and do not submit a decision', async () => {
  const calls = [];
  const ruling = {rulingId:'proposal:one', highRisk:true, digest:'a'.repeat(64), status:'pending'};
  const client = new Client({request:async (...args) => {calls.push(args); return {items:[ruling]};}});
  assert.deepEqual(await client.aiRulings(), {items:[ruling]});
  assert.deepEqual(calls, [['ai/rulings', undefined]]);
  assert.equal(client.pending.size, 0);
  assert.equal(client.aiPending, undefined);
});

test('reference resolution uses authenticated POST and preserves reference tokens', async () => {
  const tokens = ['@entity:one', '@knowledge:exact-version'];
  const calls = [];
  const response = {items:[{label:'authorized detail'}]};
  const client = new Client({request:async (...args) => {calls.push(args); return response;}});
  client.csrf = 'test-csrf';
  assert.equal(await client.aiResolve(tokens), response);
  assert.deepEqual(calls, [['ai/references/resolve', {method:'POST', csrf:'test-csrf', body:{tokens}}]]);
  assert.equal(client.pending.size, 0);
});

for (const method of ['aiRulings', 'aiResolve']) {
  test(`${method} discards a late private response after identity reset`, async () => {
    let finish;
    const client = new Client({request:() => new Promise(resolve => {finish = resolve;})});
    const pending = client[method]([]);
    client.resetSession();
    finish({items:[{private:'previous account'}]});
    await assert.rejects(pending, /SESSION_CHANGED/);
    assert.equal(client.view, null);
    assert.equal(client.pending.size, 0);
  });
}

test('ruling errors remain errors, never an empty approved queue', async () => {
  const error = Object.assign(new Error('PERMISSION_DENIED'), {code:'PERMISSION_DENIED'});
  const client = new Client({request:async () => {throw error;}});
  await assert.rejects(client.aiRulings(), thrown => thrown === error);
});

test('subscription and legacy onChange both see atomic snapshots, resets and disconnects', () => {
  let receive, disconnect;
  const client = new Client({open:(message, close) => {
    receive = message; disconnect = close; return {close(){}};
  }});
  let legacy = 0;
  const snapshots = [];
  client.onChange = () => {legacy++;};
  const unsubscribe = client.subscribe(value => snapshots.push([value.connected, value.view?.accountId]));
  client.connect();
  const snapshot = id => {
    receive({type:'snapshot.begin', id, parts:1});
    receive({type:'snapshot.part', id, index:0, data:JSON.stringify({accountId:'kp'})});
  };
  snapshot('one');
  assert.equal(snapshots.length, 0);
  receive({type:'snapshot.end', id:'one'});
  receive({type:'reset'});
  snapshot('two');
  receive({type:'snapshot.end', id:'two'});
  client.stopped = true;
  disconnect();
  assert.deepEqual(snapshots, [[true,'kp'], [false,undefined], [true,'kp'], [false,undefined]]);
  assert.equal(legacy, 4);
  unsubscribe();
  client.resetSession();
  assert.equal(snapshots.length, 4);
  assert.equal(legacy, 5);
});

test('identity reset notifies subscribers and old socket cannot restore private data', () => {
  let receive;
  const client = new Client({open:message => {receive = message; return {close(){}};}});
  const states = [];
  client.subscribe(value => states.push(value.view));
  client.connect();
  client.view = {accountId:'kp'};
  client.connected = true;
  client.resetSession();
  receive({type:'snapshot.begin', id:'old', parts:1});
  receive({type:'snapshot.part', id:'old', index:0, data:'{"accountId":"kp","secret":"old"}'});
  receive({type:'snapshot.end', id:'old'});
  assert.deepEqual(states, [null]);
  assert.equal(client.view, null);
  assert.equal(client.connected, false);
});
