import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
const root = path.resolve(import.meta.dirname, '..');
process.chdir(root);
const sha = data => createHash('sha256').update(data).digest('hex');
const version = JSON.parse(await fs.readFile('package.json')).version;
const out = path.join(root, 'dist', `localizer-${version}-win32-x64`);
await fs.mkdir(out, {recursive:true});
const lock = JSON.parse(await fs.readFile('package-lock.json'));
const dependencies = [];
const licenses = path.join(out, 'licenses');
await fs.mkdir(licenses,{recursive:true});
for (const [location, pkg] of Object.entries(lock.packages)) {
  if (!location.startsWith('node_modules/') || pkg.link) continue;
  const folder = path.join(root,location);
  let manifest;
  try { manifest = JSON.parse(await fs.readFile(path.join(folder,'package.json'))); } catch { continue; }
  const record = {name:manifest.name,version:manifest.version,license:manifest.license ?? 'SEE LICENSE',integrity:pkg.integrity,files:[]};
  for (const file of await fs.readdir(folder)) if (/^(licen[sc]e|copying|notice)(\.|$)/i.test(file)) {
    const dest = `${manifest.name.replaceAll('/','_').replaceAll('@','')}-${manifest.version}-${file}`;
    if ((await fs.stat(path.join(folder,file))).isFile()) {await fs.copyFile(path.join(folder,file),path.join(licenses,dest));record.files.push(dest);}
  }
  dependencies.push(record);
}
await fs.writeFile(path.join(out,'dependencies.json'),JSON.stringify(dependencies,null,2)+'\n');
const gui = path.join(out,'gui');
await fs.cp('node_modules/electron/dist',gui,{recursive:true});
if (await fs.stat(path.join(gui,'Localizer.exe')).catch(()=>false)) await fs.unlink(path.join(gui,'Localizer.exe'));
await fs.rename(path.join(gui,'electron.exe'),path.join(gui,'Localizer.exe'));
const app = path.join(gui,'resources','app');
await fs.mkdir(app,{recursive:true});
await fs.cp('build/desktop',app,{recursive:true,filter:p=>!p.endsWith('.map')&&!p.endsWith('.meta.json')});
await fs.writeFile(path.join(app,'package.json'),JSON.stringify({name:'independent-localizer',version,main:'main.cjs',private:true}));
const cli = path.join(out,'cli');
await fs.mkdir(path.join(cli,'runtime'),{recursive:true});
await fs.copyFile('.cache/node-v24.22.1-win-x64/node.exe',path.join(cli,'runtime','node.exe'));
await fs.copyFile('.cache/node-v24.22.1-win-x64/LICENSE',path.join(cli,'runtime','LICENSE'));
await fs.copyFile('build/cli/main.cjs',path.join(cli,'main.cjs'));
await fs.writeFile(path.join(cli,'l10n.cmd'),'@echo off\r\n"%~dp0runtime\\node.exe" "%~dp0main.cjs" %*\r\nexit /b %errorlevel%\r\n');
await fs.cp('build/runtime',path.join(out,'runtime'),{recursive:true,filter:p=>!p.endsWith('.map')&&!p.endsWith('.meta.json')});
await fs.writeFile(path.join(out,'README.txt'),'Localizer '+version+' / L10N-0 技术预览\r\nGUI：保留完整 gui 文件夹，运行 Localizer.exe。\r\nCLI：运行 cli\\l10n.cmd --help。无需系统 Node/npm/Python。\r\n当前只验证独立运行与共享格式化；尚未实现正式编辑。\r\n第三方许可位于 licenses、gui/LICENSE* 与 cli/runtime/LICENSE。\r\n');
const files=[];
async function walk(dir) {for (const e of await fs.readdir(dir,{withFileTypes:true})) {const p=path.join(dir,e.name);if(e.isDirectory())await walk(p);else if(p!==path.join(out,'release.json')) {const data=await fs.readFile(p);files.push({path:path.relative(out,p).replaceAll('\\','/'),bytes:data.length,sha256:sha(data)});}}}
await walk(out);
await fs.writeFile(path.join(out,'release.json'),JSON.stringify({version,stage:'L10N-0',platform:'win32-x64',node:'24.22.1',electron:'45.3.1',dependencyLockHash:sha(await fs.readFile('package-lock.json')),files:files.sort((a,b)=>a.path<b.path?-1:1)},null,2)+'\n');
console.log(JSON.stringify({directory:out,files:files.length,bytes:files.reduce((n,f)=>n+f.bytes,0)}));
