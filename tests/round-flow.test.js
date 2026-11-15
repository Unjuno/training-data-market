import test from 'node:test';
import assert from 'node:assert/strict';
import { batchPhase } from '../src/round-flow.js';

test('time gated stages announce the real server-backed state',()=>{
  assert.equal(batchPhase({status:'OPEN',closes_at:200}, 100000).id,'voting');
  assert.equal(batchPhase({status:'OPEN',closes_at:200}, 200000).id,'awaiting-lock');
  assert.equal(batchPhase({status:'LOCKED',closes_at:200}, 201000).id,'locked');
  assert.equal(batchPhase({status:'TRAINING',closes_at:200}, 201000).id,'training');
  assert.equal(batchPhase({status:'PUBLISHED',closes_at:200}, 201000).id,'published');
  assert.equal(batchPhase(null,201000).id,'uninitialized');
});

test('batch phase does not invent training progress',()=>{
  const value=batchPhase({status:'TRAINING',closes_at:100}, 130000);
  assert.match(value.description,/学習/);
  assert.equal(value.percentage,undefined);
  assert.equal(value.canVote,false);
  assert.equal(batchPhase({status:'OPEN',closes_at:100}, 90000).canVote,true);
});
