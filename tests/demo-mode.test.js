import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

test('live mode differentiates measured procedural demo from real CIFAR-10',()=>{
  const source=fs.readFileSync('live.js','utf8');
  assert.match(source,/mode===['"]DEMO['"]/);
  assert.match(source,/dataset\.image_kind|data\.image_kind/);
  assert.match(source,/合成/);
});

test('card labels synthetic images without misrepresenting them as CIFAR',()=>{
  const source=fs.readFileSync('src/arena-view.js','utf8');
  assert.match(source,/image_kind/);
  assert.match(source,/合成/);
});
