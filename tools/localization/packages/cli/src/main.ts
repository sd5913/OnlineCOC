import {VERSION} from '@localizer/contracts';
const args = process.argv.slice(2);
if (!args.length || args.includes('--help')) {
  console.log(JSON.stringify({name: 'Localizer', version: VERSION, stage: 'L10N-0', commands: ['--help', '--version'], note: '独立本地化工具；文件编辑命令尚未接入。'}));
} else if (args.includes('--version')) console.log(VERSION);
else { console.error(JSON.stringify({code: 'UNSUPPORTED_COMMAND', message: '该命令尚未实现'})); process.exitCode = 2; }
