import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const read = name=>readFileSync(new URL(`../${name}`,import.meta.url),'utf8');

test('both real and demo pages load the dedicated gameplay visual layer',()=>{
  for(const name of ['live.html','index.html']){
    assert.match(read(name), /<link rel="stylesheet" href="experience\.css">/,name);
    assert.match(read(name), /class="hero-playbook"/,name);
    assert.match(read(name), /class="hero-eyebrow-pill"/,name);
  }
});

test('new visual layer is included in the static Sites build and API asset route',()=>{
  assert.match(read('scripts/build.mjs'),/['"]experience\.css['"]/);
  assert.match(read('backend/service.py'),/get\('\/experience\.css'\)/);
});

test('hero leads with a playable challenge, and voting instructions remain accurate',()=>{
  for(const name of ['live.html','index.html']){
    const html=read(name);
    assert.match(html,/AIの弱点を、/);
    assert.match(html,/攻略しよう。/);
    assert.match(html,/締切後にまとめて学習/);
    assert.match(html,/href="#explore"/);
  }
});

test('visual layer provides visible keyboard focus and reduced-motion support',()=>{
  const css=read('experience.css');
  assert.match(css,/:focus-visible/);
  assert.match(css,/prefers-reduced-motion/);
  assert.match(css,/\.sample-card/);
  assert.match(css,/\.explorer/);
});
