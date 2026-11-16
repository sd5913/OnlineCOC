import {_electron as electron} from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=path.resolve(import.meta.dirname,'../..');
const dir=path.resolve(process.argv[2] ?? path.join(root,'dist/localizer-0.1.0-win32-x64'));
const fixture=path.join(root,'.test-output/中文 空格 project');
await fs.mkdir(fixture,{recursive:true});
await fs.writeFile(path.join(fixture,'package.json'),JSON.stringify({scripts:{start:'node trap.js',postinstall:'node trap.js'}}));
await fs.writeFile(path.join(fixture,'trap.js'),"require('node:fs').writeFileSync('EXECUTED','bad');");
const output=path.join(root,'.test-output/l10n-0');
const env={...process.env};delete env.ELECTRON_RUN_AS_NODE;delete env.NODE_OPTIONS;
const app=await electron.launch({executablePath:path.join(dir,'gui/Localizer.exe'),args:['--settings-dir',path.join(output,'native-dialog-settings')],env,cwd:dir});
try {
const page=await app.firstWindow();
await page.getByRole('button',{name:'选择项目目录'}).waitFor();
await page.getByRole('button',{name:'选择项目目录'}).click();
console.log('在原生窗口选择目录后，脚本会核对结果：'+fixture);
await page.getByText('中文 空格 project',{exact:true}).waitFor({timeout:300000});
assert.equal(await fs.stat(path.join(root,'.test-output/中文 空格 project/EXECUTED')).catch(()=>false),false);
await page.screenshot({path:path.join(output,'native-directory.png'),fullPage:true});
await fs.writeFile(path.join(output,'native-dialog.json'),JSON.stringify({passed:true,selected:'中文 空格 project',scriptExecuted:false,nativeDialog:true}));
console.log('Native Unicode/space directory selected; project scripts were not executed.');
} catch (error) {
await fs.writeFile(path.join(output,'native-dialog.json'),JSON.stringify({passed:false,selected:null,nativeDialogOpened:true,reason:String(error),required:'原生目录确认尚未完成'},null,2));
throw error;
} finally {await app.close();}
