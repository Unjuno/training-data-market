import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {nextAction, participationMessage, isCurrentRoundRevealed,promotionMessage} from '../src/game-view.js';

test('nextAction points to a directly actionable section in each stage',()=>{
  assert.deepEqual(nextAction({count:0,hasForecast:false,canVote:true,hasResults:false}),
    {href:'#explore',label:'画像を選ぶ',description:'気になる画像をまず1枚推薦してください。'});
  assert.equal(nextAction({count:2,hasForecast:false,canVote:true,hasResults:false}).href,'#prediction-section');
  assert.equal(nextAction({count:2,hasForecast:true,canVote:true,hasResults:true}).href,'#results-section');
  assert.equal(nextAction({count:2,hasForecast:true,canVote:false,hasResults:false}).href,'#batch-rail');
  assert.equal(nextAction({count:2,hasForecast:true,canVote:false,hasResults:true}).href,'#results-section');
});

test('participationMessage is careful about adoption vs individual learning effect',()=>{
  const r=participationMessage({recommended_count:3,adopted_count:1,adopted_ids:[3]});
  assert.match(r,/3枚中1枚/);
  assert.match(r,/学習バッチ/);
  assert.doesNotMatch(r,/あなたのおかげで|精度を上げた/);
  assert.match(participationMessage({recommended_count:0,adopted_count:0}),/推薦していません/);
  assert.match(participationMessage({recommended_count:1,adopted_count:null}),/記録がありません/);
  assert.equal(participationMessage(null),null);
});

test('live UX exposes a direct next action and previous-round personal recap',()=>{
  const html=readFileSync(new URL('../live.html',import.meta.url),'utf8');
  for(const id of ['next-step-action','next-step-description','result-context','personal-participation','personal-adoption','personal-adoption-detail']){
    assert.match(html,new RegExp(`id="${id}"`),id);
  }
});

test('a published previous round never completes current-round progress',()=>{
  assert.equal(isCurrentRoundRevealed({id:'round-0002',status:'OPEN'},'round-0001'),false);
  assert.equal(isCurrentRoundRevealed({id:'round-0001',status:'PUBLISHED'},'round-0001'),true);
  assert.equal(isCurrentRoundRevealed({id:'round-0001',status:'TRAINING'},'round-0001'),false);
  assert.equal(isCurrentRoundRevealed(null,'round-0001'),false);
});

test('the recap distinguishes training the Community arm from promoting it',()=>{
  assert.match(promotionMessage('community'),/共有AIに採用/);
  assert.match(promotionMessage('random'),/Randomモデル/);
  assert.match(promotionMessage('rollback'),/更新は見送られ/);
});
