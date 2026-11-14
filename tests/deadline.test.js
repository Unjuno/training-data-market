import test from 'node:test';
import assert from 'node:assert/strict';
import { deadlineState } from '../src/deadline.js';

test('server-corrected deadline is open strictly before closing',()=>{
  let state=deadlineState({status:'OPEN',closes_at:100},99000);
  assert.equal(state.isOpen,true);
  assert.equal(state.remainingSeconds,1);
  assert.match(state.label,/締切まで/);
  state=deadlineState({status:'OPEN',closes_at:100},100000);
  assert.equal(state.isOpen,false);
  assert.equal(state.remainingSeconds,0);
  assert.match(state.label,/締切.*終了/);
});

test('locked, uninitialized and malformed clocks always fail closed',()=>{
  assert.equal(deadlineState({status:'LOCKED',closes_at:100},90000).isOpen,false);
  assert.equal(deadlineState(null,90000).isOpen,false);
  assert.equal(deadlineState({status:'OPEN'},90000).isOpen,false);
});

test('countdown is formatted for long and short voting windows',()=>{
  assert.match(deadlineState({status:'OPEN',closes_at:7201},0).label,/2時間/);
  assert.match(deadlineState({status:'OPEN',closes_at:30},0).label,/30秒/);
});
