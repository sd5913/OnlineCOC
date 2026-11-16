import {_electron as electron} from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {formatMessage} from '../../build/runtime/localizer.mjs';
const root=path.resolve(import.meta.dirname,'../..');
const dir=path.resolve(process.argv[2]??path.join(root,'dist/localizer-0.1.0-win32-x64'));
const output=path.join(root,'.test-output/l10n-0');
await fs.mkdir(output,{recursive:true});
const env=Object.fromEntries(Object.entries(process.env).filter(([k])=>!/^(ONLINECOC|COC_|LUA_|PYTHON|ELECTRON_RUN_AS_NODE|NODE_OPTIONS)/i.test(k)));
env.PATH=path.join(process.env.SystemRoot,'System32');
const cli=spawnSync(path.join(dir,'cli/runtime/node.exe'),[path.join(dir,'cli/main.cjs'),'--help'],{env,encoding:'utf8',cwd:dir,windowsHide:true});
assert.equal(cli.status,0,cli.stderr);
assert.equal(JSON.parse(cli.stdout).name,'Localizer');
const app=await electron.launch({executablePath:path.join(dir,'gui/Localizer.exe'),args:['--settings-dir',path.join(output,'独立设置 settings')],env,cwd:dir,timeout:45000});
try {
  const page=await app.firstWindow();
  await page.getByRole('heading',{name:'共享文本解析试验'}).waitFor();
  const permissions=await app.evaluate(({BrowserWindow,app})=>{const w=BrowserWindow.getAllWindows()[0];return {web:w.webContents.getLastWebPreferences(),versions:process.versions,appPath:app.getAppPath()};});
  assert.equal(permissions.web.nodeIntegration,false);
  assert.equal(permissions.web.contextIsolation,true);
  assert.equal(permissions.web.sandbox,true);
  assert.equal(await page.evaluate(()=>typeof window.require),'undefined');
  assert.deepEqual(await page.evaluate(()=>Object.keys(window.localizer)),['chooseProject']);
  const samples=[['Confirm {count}','en',3],['确认 {count}','zh-CN',3],["This ''quote'' and '{brace}' {count}",'en',2],['{count, plural, one {# slot} other {# slots}}','en',1],['{count, plural, one {# slot} other {# slots}}','en',2],['剩余 {count} 个槽位','zh-CN',3],['{count, plural, one {one}}','en',2],['{broken','en',2]];
  const checks=[];
  for (const [text,locale,count] of samples) {
    await page.getByLabel('ICU 模板').fill(text);
    await page.getByLabel('预览语言').selectOption(locale);
    await page.getByLabel('count',{exact:true}).fill(String(count));
    const expected=formatMessage(text,locale,{count:{type:'number'}},{count});
    const actual=await page.getByLabel('解析结果').textContent();
    assert.equal(actual,expected.ok?expected.text:`${expected.code}：${expected.message}`);
    checks.push({text,locale,count,expected,actual,passed:true});
  }
  await page.screenshot({path:path.join(output,'shared-formatter.png'),fullPage:true});
  await fs.writeFile(path.join(output,'gui-smoke.json'),JSON.stringify({passed:true,cli:JSON.parse(cli.stdout),permissions,samples:checks},null,2));
  console.log('Real Electron window, isolated bridge, CLI and 8 shared ICU samples passed.');
} finally {await app.close();}
