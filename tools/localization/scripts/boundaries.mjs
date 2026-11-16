import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const root = path.resolve(import.meta.dirname, '..');
for (const entry of ['cli/main.cjs','desktop/main.cjs','desktop/preload.cjs','core/index.cjs','runtime/esm','runtime/iife']) {
  const meta = JSON.parse(await fs.readFile(path.join(root, 'build', entry + '.meta.json'), 'utf8'));
  for (const input of Object.keys(meta.inputs)) {
    const full = path.resolve(root, input);
    assert(full.startsWith(root + path.sep), `Outside module: ${input}`);
    assert(!/(^|[\\/])(engineering|rulepacks)([\\/]|$)/.test(input), `Forbidden dependency: ${input}`);
    if (entry.startsWith('runtime')) assert(!/packages[\\/](core|desktop|cli)/.test(input), `Runtime boundary: ${input}`);
  }
  if (entry.startsWith('runtime')) for (const out of Object.values(meta.outputs)) assert(out.imports.length === 0, 'Browser runtime must be self-contained');
}
console.log('Dependency boundaries passed.');
