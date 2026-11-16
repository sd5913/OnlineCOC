import test from 'node:test';
import assert from 'node:assert/strict';
import {formatMessage} from '../../build/runtime/localizer.mjs';
export const samples = [
  ['Confirm','en',{}, {}, 'Confirm'],
  ['确认','zh-CN',{}, {}, '确认'],
  ["This ''quote'' and '{brace}'",'en',{}, {}, "This 'quote' and {brace}"],
  ['{count, plural, one {# slot} other {# slots}}','en',{count:{type:'number'}},{count:2},'2 slots'],
  ['剩余 {count} 个槽位','zh-CN',{count:{type:'number'}},{count:3},'剩余 3 个槽位']
];
test('shared ICU formatting corpus', () => {for (const [text,locale,params,values,expected] of samples) assert.deepEqual(formatMessage(text,locale,params,values),{ok:true,text:expected});});
test('malformed messages and invalid arguments become diagnostics', () => {
  for (const text of ['{count, plural, one {one}}','{broken','{x, date}']) assert.equal(formatMessage(text,'en',{count:{type:'number'}},{count:2}).ok,false);
  assert.equal(formatMessage('{count}','en',{count:{type:'number'}},{count:'2'}).ok,false);
});
