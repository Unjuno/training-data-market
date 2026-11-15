import test from 'node:test';
import assert from 'node:assert/strict';
import {questIntel, progressState, scoreSummary, forecastHint} from '../src/game-view.js';

test('questIntel shows observable recall, never invents targets or accuracy',()=>{
  const item=questIntel({recall:[0.1,0.4,0.7,0.2,0.5,0.6,0.8,0.9,0.8,0.7]},[3,5]);
  assert.deepEqual(item,[{label:'猫',recall:'20.0%'},{label:'犬',recall:'60.0%'}]);
  assert.deepEqual(questIntel(null,[3,5]),[{label:'猫',recall:'—'},{label:'犬',recall:'—'}]);
  assert.deepEqual(questIntel({recall:[0.1]},[3,5]),[{label:'猫',recall:'—'},{label:'犬',recall:'—'}]);
});

test('progressState reflects measured local actions and distinguishes pending results',()=>{
  assert.deepEqual(progressState(0,false,true),{next:'画像を1枚選ぶ',selected:false,forecasted:false});
  assert.deepEqual(progressState(2,false,true),{next:'次は結果を予測する',selected:true,forecasted:false});
  assert.deepEqual(progressState(2,true,true),{next:'締切後の学習結果を待つ',selected:true,forecasted:true});
  assert.equal(progressState(2,true,false).next,'投票受付終了・実験結果を確認');
});

test('scoreSummary differentiates participation from actual resolved points',()=>{
  assert.equal(scoreSummary({total_points:0,scored_rounds:0}), 'まだ採点された予測はありません');
  assert.equal(scoreSummary({total_points:179,scored_rounds:2}), '累計 179 pt / 2 ラウンド採点');
  assert.equal(forecastHint(50), '50%：五分五分の予測（基準点は75 pt）');
  assert.match(forecastHint(75), /75%/);
});
