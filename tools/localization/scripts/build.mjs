import {build as bundle} from 'esbuild';
import {build as vite} from 'vite';
import fs from 'node:fs/promises';
import path from 'node:path';
const root = path.resolve(import.meta.dirname, '..');
process.chdir(root);
const common = {bundle: true, sourcemap: true, logLevel: 'warning', target: 'es2022'};
await fs.mkdir('build', {recursive: true});
for (const [entry, outfile] of [['packages/cli/src/main.ts','build/cli/main.cjs'],['packages/desktop/src/main/index.ts','build/desktop/main.cjs'],['packages/desktop/src/preload/index.ts','build/desktop/preload.cjs'],['packages/core/src/index.ts','build/core/index.cjs']]) {
  const result = await bundle({...common, entryPoints: [entry], outfile, platform: 'node', format: 'cjs', external: ['electron'], metafile: true});
  await fs.writeFile(outfile + '.meta.json', JSON.stringify(result.metafile, null, 2));
}
for (const format of ['esm','iife']) {
  const result = await bundle({...common, entryPoints: ['packages/runtime/src/index.ts'], outfile: `build/runtime/localizer.${format === 'esm' ? 'mjs' : 'js'}`, platform: 'browser', format, globalName: 'Localizer', metafile: true});
  await fs.writeFile(`build/runtime/${format}.meta.json`, JSON.stringify(result.metafile, null, 2));
}
await vite({root: path.join(root,'packages/desktop/src/renderer'), base: './', configFile: false, logLevel: 'warn', build: {outDir: path.join(root,'build/desktop/renderer'), emptyOutDir: true}});
console.log('Built CLI, desktop, core and standalone runtime.');
