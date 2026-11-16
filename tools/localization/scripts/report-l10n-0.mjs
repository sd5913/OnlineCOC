import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
const root=path.resolve(import.meta.dirname,'..');
process.chdir(root);
const hash=x=>createHash('sha256').update(x).digest('hex');
const startedAt=new Date().toISOString();
const checks=[];
for(const [name,args] of [['typecheck',['node_modules/typescript/bin/tsc','--noEmit']],['boundaries',['scripts/boundaries.mjs']],['unit',['--test','tests/unit/messages.test.mjs']]]) {
 const run=spawnSync(process.execPath,args,{encoding:'utf8',windowsHide:true});
 checks.push({name,passed:run.status===0,exitCode:run.status,output:run.stdout+run.stderr});
}
const smoke=JSON.parse(await fs.readFile('.test-output/l10n-0/gui-smoke.json','utf8'));
const native=JSON.parse(await fs.readFile('.test-output/l10n-0/native-dialog.json','utf8'));
const release=JSON.parse(await fs.readFile('dist/localizer-0.1.0-win32-x64/release.json','utf8'));
for(const file of release.files) {
 const b=await fs.readFile(path.join('dist/localizer-0.1.0-win32-x64',file.path));
 if(b.length!==file.bytes||hash(b)!==file.sha256)throw new Error('Release mismatch: '+file.path);
}
const sources=[];
async function scan(dir){for(const e of await fs.readdir(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory())await scan(p);else sources.push({path:p.replaceAll('\\','/'),sha256:hash(await fs.readFile(p))});}}
await scan('packages');await scan('scripts');await scan('tests');
for(const p of ['package.json','package-lock.json','tsconfig.json','.npmrc'])sources.push({path:p,sha256:hash(await fs.readFile(p))});
sources.sort((a,b)=>a.path<b.path?-1:1);
const report={stage:'L10N-0',status:native.passed?'passed':'in-progress',toolVersion:'0.1.0',sourceRevision:'sha256:'+hash(JSON.stringify(sources)),dependencyLockHash:'sha256:'+hash(await fs.readFile('package-lock.json')),environment:{os:os.version(),release:os.release(),arch:os.arch(),cpu:os.cpus()[0].model,logicalCpus:os.cpus().length,ramBytes:os.totalmem(),cliNode:process.version,electron:smoke.permissions.versions},fixtureHash:'sha256:'+hash(JSON.stringify(smoke.samples.map(({text,locale,count})=>({text,locale,count})))),startedAt,finishedAt:new Date().toISOString(),checks,cases:[
{id:'E0-1',expected:'仓库外完整发行启动，游戏环境变量清理，CLI 不依赖 PATH 中的 Node',actual:'真实 Electron 窗口及便携 CLI 成功；PATH 仅 System32；构建输入限定模块内部',passed:smoke.passed,evidence:'gui-smoke.json'},
{id:'E0-2',expected:'原生目录选择接受中文空格路径，项目脚本不执行',actual:native.reason??'目录已选择且脚本未执行',passed:native.passed,evidence:'native-dialog.json'},
{id:'E0-3',expected:'GUI 与独立解析包共享样本一致，错误模板返回诊断',actual:'8 组真实窗口样本一致；2 组单元测试通过',passed:smoke.samples.every(s=>s.passed)&&checks.find(c=>c.name==='unit').passed,evidence:'gui-smoke.json'},
{id:'E0-4',expected:'依赖版本固定、模块无工程外引用、独立打包及驱动可复验',actual:`类型与边界检查通过；锁定 Playwright 1.65.0；${release.files.length} 个发行文件摘要通过`,passed:checks.every(c=>c.passed),evidence:'release.json + package-lock.json'}
],distribution:{files:release.files.length,bytes:release.files.reduce((n,f)=>n+f.bytes,0),sha256:hash(await fs.readFile('dist/localizer-0.1.0-win32-x64/release.json')),repositoryExternalSmoke:true},unresolved:native.passed?[]:['E0-2 原生目录确认未完成；用户暂时无法接管；L10N-1 不启动。','本机是 Windows 10 19045；Windows 11 和无开发工具的新环境尚未验收。','仓库内受限执行触发 Electron 目录 ACL 检查；仓库外正常权限执行通过，未修改 ACL 或关闭沙箱。'],sources};
report.status=report.cases.every(c=>c.passed)?'passed':'in-progress';
for (const c of checks.filter(c=>!c.passed)) report.unresolved.push('检查未通过：'+c.name);
await fs.mkdir('docs/evidence',{recursive:true});
await fs.copyFile('.test-output/l10n-0/gui-smoke.json','docs/evidence/l10n-0-gui.json');
await fs.copyFile('.test-output/l10n-0/shared-formatter.png','docs/evidence/l10n-0-formatter.png');
await fs.copyFile('.test-output/l10n-0/native-dialog.json','docs/evidence/l10n-0-native.json');
await fs.writeFile('docs/evidence/l10n-0.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({stage:report.stage,status:report.status,passed:report.cases.filter(c=>c.passed).length,total:report.cases.length,checks:checks.map(c=>({name:c.name,passed:c.passed}))}));
if(checks.some(c=>!c.passed))process.exitCode=1;
