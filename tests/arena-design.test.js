import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../',import.meta.url));
const file=path=>readFileSync(new URL(`../${path}`,import.meta.url),'utf8');
test('live and demo share the same accessible decision flow',()=>{
  const live=file('live.html'),demo=file('index.html');
  for(const html of [live,demo]){
    for(const id of ['query','label-filter','wrong-only-live','sample-grid','my-picks','my-count','pick-meter-fill','reason-live','save-reason','results','mode-badge','app-alert-text']) {
      assert.match(html,new RegExp(`id="${id}"`),id);
    }
    assert.match(html,/href="#explore"/);
    assert.match(html,/href="#vote-panel"/);
    assert.match(html,/aria-live="polite"/);
    assert.match(html,/TRAINING DATA MARKET/);
  }
  assert.match(demo,/DEMO · 模擬データ/);
  assert.match(live,/接続確認中/);
  assert.doesNotMatch(live,/id="metric-loss">0\./);
});
test('responsive design provides focus and reduced motion handling',()=>{
  const css=file('styles.css');
  assert.match(css,/@media\(max-width:620px\)/);
  assert.match(css,/@media\(prefers-reduced-motion:reduce\)/);
  assert.match(css,/:focus-visible/);
  assert.match(css,/\.mobile-vote-link\.is-visible/);
});
test('frontend shared card logic never uses innerHTML for untrusted dataset strings',()=>{
  const js=file('src/arena-view.js');
  assert.doesNotMatch(js,/\.innerHTML\s*=/);
  assert.match(js,/createSampleCard/);
  assert.match(js,/aria-pressed/);
  assert.match(js,/同一|代替表示|模擬表示|画像非公開/);
});
