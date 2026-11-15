import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const html=readFileSync(new URL('../live.html',import.meta.url),'utf8');
const script=readFileSync(new URL('../live.js',import.meta.url),'utf8');

test('timed batch status is visibly different from player progress',()=>{
  for(const id of ['batch-stage','batch-description','batch-voter-count','batch-pick-count','batch-forecast-count','batch-fixed-deadline']){
    assert.match(html,new RegExp(`id="${id}"`));
  }
  assert.match(script,/batchPhase\(/);
  assert.match(html,/id="hero-primary-action"/);
  assert.match(script,/hero-primary-action/);
});
