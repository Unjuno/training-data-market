import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync, readFileSync, readdirSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../',import.meta.url));
test('static build includes complete demo and excludes private/server files',()=>{
  assert.ok(existsSync(new URL('../scripts/build.mjs',import.meta.url)),'build script exists');
  execFileSync(process.execPath,['scripts/build.mjs'],{cwd:root});
  for(const path of ['index.html','demo.html','live.html','live.js','live.css','styles.css','app.js','src/arena-view.js','src/selection.js','src/draft.js','src/demo-data.js','docs/spec-v0.4.md']) {
    assert.ok(existsSync(new URL('../dist/'+path,import.meta.url)),path);
  }
  const all=readdirSync(new URL('../dist/',import.meta.url),{recursive:true});
  assert.equal(all.some(path=>/(^|\/)(\.env|\.git|node_modules|data|checkpoints|tests)(\/|\.|$)/.test(path)),false);
  assert.match(readFileSync(new URL('../dist/index.html',import.meta.url),'utf8'),/DEMO/);
});
