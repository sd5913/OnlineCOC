$ErrorActionPreference = 'Stop'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PIP_CACHE_DIR = Join-Path $PSScriptRoot 'local/pip-cache'
py -3.14 -m venv (Join-Path $PSScriptRoot '.venv')
if ($LASTEXITCODE -ne 0) { throw '需要安装 Python 3.14 x64；创建联网运行时失败。' }
$python=Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
& $python -m pip install -r (Join-Path $PSScriptRoot 'requirements.lock')
if ($LASTEXITCODE -ne 0) { throw '安装联网依赖失败。' }
& $python -m pip install --no-deps -e $PSScriptRoot
if ($LASTEXITCODE -ne 0) { throw '安装联网模块失败。' }
