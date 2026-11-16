param([string]$Config = "$PSScriptRoot/local/client-config.json")
$ErrorActionPreference = 'Stop'
$env:PYTHONDONTWRITEBYTECODE = '1'
$python = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw '请先运行 setup.ps1 安装独立联网运行时。' }
if (-not (Test-Path -LiteralPath $Config)) { throw '缺少 local/client-config.json，请按 README 配置目录服务。' }
& $python -m onlinecoc_p2p client --config $Config
