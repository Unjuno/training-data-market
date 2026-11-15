import {cp,mkdir,rm} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=fileURLToPath(new URL('../',import.meta.url));
const out=path.join(root,'dist');
// Explicit allowlist: never copy the full repository into the public site.
const files=['index.html','live.html','live.js','live.css','game.css','styles.css','app.js','src/arena-view.js','src/game-view.js','src/deadline.js','src/demo-data.js','src/selection.js','src/draft.js','docs/spec-v0.4.md','docs/sites-handoff.md','LICENSE'];
await rm(out,{recursive:true,force:true});
for(const file of files){
  await mkdir(path.dirname(path.join(out,file)),{recursive:true});
  await cp(path.join(root,file),path.join(out,file),{dereference:false});
}
await cp(path.join(root,'index.html'),path.join(out,'demo.html'));
// Sites/static hosts must enter the real API UI, never the simulated mock page.
await cp(path.join(root,'live.html'),path.join(out,'index.html'));
console.log(`Built ${files.length+1} static files in dist/`);
