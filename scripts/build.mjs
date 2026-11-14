import {cp,mkdir,rm} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=fileURLToPath(new URL('../',import.meta.url));
const out=path.join(root,'dist');
// Explicit allowlist: never copy the full repository into the public site.
const files=['index.html','live.html','live.js','live.css','styles.css','app.js','src/demo-data.js','src/selection.js','src/draft.js','docs/spec-v0.4.md','docs/sites-handoff.md','LICENSE'];
await rm(out,{recursive:true,force:true});
for(const file of files){
  await mkdir(path.dirname(path.join(out,file)),{recursive:true});
  await cp(path.join(root,file),path.join(out,file),{dereference:false});
}
console.log(`Built ${files.length} static files in dist/`);
